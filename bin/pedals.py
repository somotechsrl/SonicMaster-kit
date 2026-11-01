"""Pedal profiles and verified Chocolate Custom CC transactions.

Protocol facts: https://github.com/cbix/mvave-chocolate-sysex
The first 1009-byte settings region is backed up; only offsets 0..9 are writable.
"""
import configparser
import json
import os
from pathlib import Path
import tempfile
import time

DEFAULT = {'previous_cc': 22, 'next_cc': 25, 'effect_offset': 0}
LOOP_ACTIONS = ('Record / Play', 'Overdub', 'Pause / Resume', 'Clear')
DISCOVERY = bytes.fromhex('F0 00 32 45 00 00 00 40 7F F7')
READ = bytes.fromhex('F0 00 32 0D 41 00 00 00 02 00 00 00 00 10 7E 00 00 07 00 F7')


def atomic_write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True); raise
    tmp.replace(path)


def load_profile(path):
    parser = configparser.ConfigParser()
    try:
        parser.read(path)
        values = {key: parser.getint('ToneShifter', key, fallback=value) for key, value in DEFAULT.items()}
        validate_profile(values)
        return values
    except (ValueError, configparser.Error): return dict(DEFAULT)


def validate_profile(values):
    for key in DEFAULT:
        if type(values[key]) is not int or not 0 <= values[key] <= (7 if key == 'effect_offset' else 127):
            raise ValueError('Invalid Tone Shifter mapping: ' + key)
    if values['previous_cc'] == values['next_cc']: raise ValueError('Previous and next must use different CC numbers.')


def save_profile(path, values):
    validate_profile(values)
    content = '[ToneShifter]\n' + ''.join(f'{key} = {values[key]}\n' for key in DEFAULT)
    atomic_write(path, content.encode())


def describe(name, raw, profile=None):
    if not raw: return '', None
    profile = profile or DEFAULT
    status = raw[0] & 0xF0
    channel = (raw[0] & 15) + 1
    if status == 0xB0 and len(raw) >= 3:
        cc, value = raw[1:3]
        text = f'Ch {channel} · CC {cc} · value {value}'
        if name == 'SINCO' and 80 <= cc <= 83:
            action = LOOP_ACTIONS[cc - 80]
            return text + ' · ' + action + (' (release)' if value == 0 else ''), ('chocolate', cc - 80) if value else None
        if name == 'TSMEGA':
            if cc == profile['previous_cc']: return text + ' · previous preset', ('tsmega', 'previous')
            if cc == profile['next_cc']: return text + ' · next preset', ('tsmega', 'next')
        return text + ' · unmapped', None
    if status == 0xC0 and len(raw) >= 2:
        pc = raw[1]
        if name == 'TSMEGA':
            effect = (pc - profile['effect_offset']) % 8
            return f'Ch {channel} · PC {pc} · page {effect // 4 + 1}, effect {effect + 1}', ('tsmega', effect)
        return f'Ch {channel} · PC {pc} · unmapped', None
    if raw[0] == 0xF0: return 'Configuration SysEx response', None
    return raw.hex(' ').upper(), None


def write_message(address, value):
    if type(address) is not int or type(value) is not int or not 0 <= address <= 9:
        raise ValueError('Only the documented Custom CC fields 0..9 can be written.')
    limit = 11 if address == 0 else 15 if address == 1 else 1 if address % 2 else 127
    if not 0 <= value <= limit: raise ValueError('Invalid Custom CC field value.')
    data = [0, 50, 9, 73, 0, 0, 0, 2, address, 0, 0, 0, 16, 0, 0, 0, value]
    checksum = (0x28A - sum(data) - address - value) & 0x3FFF
    return bytes([240, *data, checksum & 127, checksum >> 7, 247])


def unpack_reply(frame):
    if len(frame) != 1173 or frame[:5] != bytes.fromhex('F0 00 32 0D 49') or frame[8:13] != bytes([2, 0, 0, 0, 0]) or frame[-1] != 247:
        raise ValueError('Unsupported Chocolate settings reply; no settings were written.')
    if any(v > 127 for v in frame[1:-1]): raise ValueError('Invalid 7-bit SysEx data.')
    output = bytearray(); acc = bits = 0
    for value in frame[17:-3]:
        acc |= value << bits; bits += 7
        while bits >= 8:
            output.append(acc & 255); acc >>= 8; bits -= 8
    if bits: output.append(acc & 255)
    if len(output) != 1009: raise ValueError('Unexpected Chocolate settings region length.')
    return bytes(output)


def summary(blob):
    return {'mode': blob[0], 'channel': blob[1] + 1,
            'switches': {letter: {'cc': blob[2 + i * 2], 'latch': blob[3 + i * 2]} for i, letter in enumerate('ABCD')}}


def kit_values():
    return {0: 7, 1: 0, **{2 + i * 2: 80 + i for i in range(4)}, **{3 + i * 2: 0 for i in range(4)}}


class Chocolate:
    def __init__(self, transport, target):
        if target['name'] != 'SINCO': raise ValueError('USB programming is limited to the standard SINCO Chocolate.')
        self.transport, self.target = transport, target
        self.transport.connect(target)

    def exchange(self, message, prefix, timeout=3):
        self.transport.pending()
        self.transport.send(self.target, message)
        deadline = time.monotonic() + timeout
        pending = bytearray()
        while time.monotonic() < deadline:
            for source, raw in self.transport.pending():
                if source != (self.target['client'], self.target['port']): continue
                if raw.startswith(b'\xf0'): pending.clear()
                pending.extend(raw)
                if pending.startswith(prefix) and pending.endswith(b'\xf7'): return bytes(pending)
                if len(pending) > 65536: pending.clear()
            time.sleep(.01)
        raise TimeoutError('Chocolate did not return the expected reply. Check its USB U mode and connection.')

    def read(self):
        self.exchange(DISCOVERY, bytes.fromhex('F0 00 32 45 58'))
        frame = self.exchange(READ, bytes.fromhex('F0 00 32 0D 49'))
        blob = unpack_reply(frame)
        return blob, frame

    def backup(self, folder, blob, frame):
        path = Path(folder) / (time.strftime('%Y%m%d-%H%M%S') + f'-{time.time_ns() % 1000000:06d}.json')
        atomic_write(path, (json.dumps({'format': 'tsma-chocolate-custom-v1', 'settings_region': blob.hex(),
                                       'frame': frame.hex(), 'decoded': summary(blob)}, indent=2) + '\n').encode())
        return path

    def program(self, folder, values=None, report=lambda message: None):
        values = kit_values() if values is None else values
        for address, value in values.items(): write_message(address, value)
        current, frame = self.read()
        backup = self.backup(folder, current, frame)
        report('Backup saved: ' + str(backup))
        # Apply mode last. Never send CC/PC notes to the kit during programming.
        for address in [i for i in sorted(values) if i != 0] + ([0] if 0 in values else []):
            value = values[address]
            if current[address] == value: continue
            try: self.exchange(write_message(address, value), bytes.fromhex('F0 00 32 01 08'))
            except TimeoutError: report('No ACK; checking actual readback before proceeding.')
            actual, frame = self.read()
            expected = bytearray(current); expected[address] = value
            if actual != expected:
                raise RuntimeError(f'Readback mismatch at field {address}. Programming stopped; backup: {backup}')
            current = actual
            report(f'Field {address} verified.')
        self.backup(folder, current, frame)
        return summary(current), backup


def restore_values(path):
    data = json.loads(Path(path).read_text())
    if data.get('format') != 'tsma-chocolate-custom-v1': raise ValueError('Not a TSMA Chocolate backup.')
    blob = unpack_reply(bytes.fromhex(data['frame']))
    if blob.hex() != data['settings_region']: raise ValueError('Backup frame and settings disagree.')
    values = {i: blob[i] for i in range(10)}
    for address, value in values.items(): write_message(address, value)
    return values
