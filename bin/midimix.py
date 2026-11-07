"""MIDImix bank proxy and live Ardour names. No audio or gain is generated here.

A private map adds absolute bank selection on MIDI channel 16. All hardware
messages except Bank Left/Right pass unchanged to Generic MIDI. The worker's
stdin is a lifetime lease: even a crashed GUI restores the physical connection.
"""
import ctypes as C
import json
import math
import os
from pathlib import Path
import selectors
import signal
import socket
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from alsa_midi import Sequencer, devices
from osc import encode, decode
from midimix_setup import prepare, ardour_running

ROOT = Path(__file__).resolve().parents[1]
MAP_NAME = 'Akai MidiMix TSMA Live'
CLIENT = 'TSMA MIDImix bridge'


def install_map(config):
    target = config / 'midi_maps/TSMA_MIDIMix_Live.map'
    root = ET.Element('ArdourMIDIBindings', version='1.1.0', name=MAP_NAME)
    ET.SubElement(root, 'DeviceInfo', **{'bank-size': '8'})
    for number, cc in enumerate((19,23,27,31,49,53,57,61), 1):
        for offset, control in enumerate(('mute', 'solo', 'recenable')):
            ET.SubElement(root, 'Binding', channel='1', note=str((number-1)*3+offset+1),
                          uri=f'/route/{control} B{number}')
        ET.SubElement(root, 'Binding', channel='1', ctl=str(cc), uri=f'/route/gain B{number}')
    ET.SubElement(root, 'Binding', channel='1', note='25', function='prev-bank')
    ET.SubElement(root, 'Binding', channel='1', note='26', function='next-bank')
    ET.SubElement(root, 'Binding', channel='1', ctl='62', uri='/bus/gain master')
    tree = ET.ElementTree(root)
    for bank in range(128):
        ET.SubElement(tree.getroot(), 'Binding', channel='16', note=str(bank),
                      function='set-bank', arg=str(bank))
    target.parent.mkdir(parents=True, exist_ok=True)
    data = ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True)
    if not target.exists() or target.read_bytes() != data:
        target.write_bytes(data)


class Bank:
    def __init__(self):
        self.index = 0
        self.last_fader = None
        self.touched = 0

    def consume(self, raw):
        if len(raw) == 3 and raw[0] in (0x80, 0x90) and raw[1] in (25, 26):
            if raw[0] == 0x90 and raw[2]:
                self.index = min(127, max(0, self.index + (1 if raw[1] == 26 else -1)))
            return True
        if len(raw) == 3 and raw[0] == 0xB0 and raw[1] in (19,23,27,31,49,53,57,61):
            self.last_fader = (19,23,27,31,49,53,57,61).index(raw[1])
            self.touched = time.monotonic()
        return False

    @property
    def command(self):
        return bytes((0x9F, self.index, 127))


class Midi(Sequencer):
    def emit(self, data):
        """Send to this client's subscribers (a2j), never to the hardware."""
        raw = C.create_string_buffer(bytes(data))
        event = C.create_string_buffer(64)
        self.lib.snd_midi_event_reset_encode(self.encoder)
        count = self.lib.snd_midi_event_encode(self.encoder, raw, len(data), event)
        self.check(count)
        if count != len(data):
            raise ValueError('Incomplete MIDI event')
        event[3] = bytes([253])
        event[12] = bytes([self.client])
        event[13] = bytes([self.port])
        event[14] = bytes([254]); event[15] = bytes([0])
        self.check(self.lib.snd_seq_event_output_direct(self.handle, event))


def command(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=2)


def connections():
    graph = {}
    port = None
    result = command('jack_lsp', '-c')
    if result.returncode:
        raise OSError('JACK non disponibile')
    for line in result.stdout.splitlines():
        if line.startswith('   ') and port:
            graph[port].add(line.strip())
        else:
            port = line; graph[port] = set()
    return graph


class Patch:
    def __init__(self):
        self.original = None
        self.proxy = None

    def restore(self):
        if self.original:
            command('jack_connect', *self.original)
        if self.proxy:
            command('jack_disconnect', *self.proxy)
        self.original = self.proxy = None

    def activate(self, auto_connect=False):
        graph = connections()
        source = next((p for p in graph if p.startswith('a2j:MIDI Mix ') and '(capture)' in p), None)
        proxy = next((p for p in graph if p.startswith('a2j:'+CLIENT+' ') and '(capture)' in p), None)
        target = next((p for p in graph if p.endswith(':MIDI Control In')), None)
        if not all((source, proxy, target)):
            return False
        had_original = target in graph[source]
        if not had_original and not auto_connect:
            return False
        self.original = (source, target)
        self.proxy = (proxy, target)
        try:
            if command('jack_connect', *self.proxy).returncode:
                raise OSError('Collegamento MIDImix non riuscito')
            if had_original and command('jack_disconnect', *self.original).returncode:
                raise OSError('Passaggio MIDImix non riuscito')
        except Exception:
            self.restore(); raise
        return True


def active_map(config):
    try:
        root = ET.parse(config/'config').getroot()
        return any(p.get('binding') == MAP_NAME and p.get('active') == '1'
                   for p in root.findall('.//Protocol'))
    except (OSError, ET.ParseError):
        return False


class Names:
    def __init__(self, port=3819):
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
        self.udp.bind(('127.0.0.1', 0)); self.udp.setblocking(False)
        self.target = ('127.0.0.1', port)
        self.rows = {}; self.pending = None
        self.gains = {}; self.meters = {}
        self.last_reply = 0; self.next_query = 0; self.configured = False

    def send(self, path, *args):
        self.udp.sendto(encode(path, *args), self.target)

    def poll(self, now):
        if now >= self.next_query:
            if not self.configured or now - self.last_reply > 3:
                # All visible routes, excluding master/monitor/VCA, in the same
                # presentation order as Generic MIDI's /route/... Bn bindings.
                self.send('/set_surface', 0, 15, 16514, 0, 0, 0, self.udp.getsockname()[1])
                self.configured = True
            self.pending = {}
            self.send('/strip/list')
            self.next_query = now + 1
        for _ in range(4096):
            try:
                packet, peer = self.udp.recvfrom(65535)
            except BlockingIOError:
                break
            if peer != self.target:
                continue
            try:
                path, args = decode(packet)
            except (ValueError, IndexError, UnicodeError, TypeError, struct.error):
                continue
            if path == '/reply' and args and args[0] == 'end_route_list':
                if self.pending is not None:
                    self.rows = self.pending; self.pending = None
                    self.last_reply = now
            elif path == '/reply' and len(args) >= 7 and self.pending is not None:
                self.pending[int(args[6])] = str(args[1])
            elif path == '/strip/name' and len(args) == 2:
                index, name = int(args[0]), str(args[1])
                if self.pending is None:
                    self.rows[index] = name
            elif path in ('/strip/gain', '/strip/meter') and len(args) == 2:
                index, value = int(args[0]), float(args[1])
                if math.isfinite(value):
                    (self.gains if path == '/strip/gain' else self.meters)[index] = value
            elif path == '/strip/list':
                self.next_query = 0
        return bool(self.last_reply and now - self.last_reply < 3)

    def close(self):
        # Drop observers belonging only to this UDP client.
        self.send('/set_surface/feedback', 0)
        self.udp.close()


def worker():
    config = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'ardour8'
    install_map(config)
    names = Names(int(os.environ.get('TSMA_ARDOUR_OSC_PORT', '3819')))
    lease = selectors.DefaultSelector(); lease.register(sys.stdin, selectors.EVENT_READ)
    patch = Patch(); midi = None; source = None; bank = Bank()
    next_scan = 0; last_state = None; next_bank = 0
    status = 'Ardour Midimix · configurazione automatica in corso…'
    try:
        while True:
            if lease.select(.02):
                data = os.read(sys.stdin.fileno(), 4096)
                if not data:
                    break
                for line in data.splitlines():
                    try:
                        delta = json.loads(line).get('bank_delta')
                        if delta in (-1, 1):
                            bank.index = min(127, max(0, bank.index + delta)); next_bank = 0
                    except (ValueError, AttributeError):
                        pass
            now = time.monotonic()
            live = names.poll(now)
            try:
                if now >= next_scan:
                    next_scan = now + 1
                    prepare(config)
                    status = 'Ardour Midimix · in attesa di Ardour'
                    hardware = next((d for d in devices(names=('MIDI Mix',)) if d['name'] == 'MIDI Mix'), None)
                    current = (hardware['client'], hardware['port']) if hardware else None
                    ready = live and active_map(config)
                    if current != source or not ready:
                        patch.restore()
                        if midi: midi.close()
                        midi = None; source = None; bank = Bank()
                    if current and ready and midi is None:
                        midi = Midi(CLIENT); midi.connect(hardware); source = current
                    if midi and not patch.original:
                        if patch.activate(auto_connect=True):
                            midi.emit(bank.command); next_bank = now + .5
                    if live and not active_map(config):
                        status = 'Ardour Midimix · configurazione automatica al prossimo avvio di Ardour'
                    elif not live and ardour_running():
                        status = 'Ardour Midimix · configurazione automatica al prossimo avvio di Ardour'
                    elif not current:
                        status = 'MIDImix non collegato'
                    elif live:
                        status = 'MIDImix: collegamento in corso…'
                if midi:
                    for sender, raw in midi.pending():
                        if sender != source:
                            continue
                        consumed = bank.consume(raw)
                        if patch.original:
                            midi.emit(bank.command if consumed else raw)
                    if patch.original and now >= next_bank:
                        midi.emit(bank.command); next_bank = now + .5
                active = bool(live and patch.original)
                if active:
                    status = f'Ardour Midimix · Banco {bank.index+1} · Tracce {bank.index*8+1}–{bank.index*8+8}'
                state = {'active': active, 'status': status,
                         'names': [names.rows.get(bank.index*8+i+1, '—') if active else '—' for i in range(8)],
                         'gains': [names.gains.get(bank.index*8+i+1) if active and bank.index*8+i+1 in names.rows else None for i in range(8)],
                         'meters': [names.meters.get(bank.index*8+i+1) if active and bank.index*8+i+1 in names.rows else None for i in range(8)],
                         'fader': bank.last_fader if active and now-bank.touched < 1 else None}
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                patch.restore()
                if midi: midi.close()
                midi = None; source = None
                state = {'active': False, 'status': 'MIDImix: '+str(exc), 'names': ['—']*8, 'fader': None}
            if state != last_state:
                print(json.dumps(state), flush=True); last_state = state
    finally:
        patch.restore()
        if midi: midi.close()
        names.close(); lease.close()


if __name__ == '__main__':
    def stop(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    worker()
