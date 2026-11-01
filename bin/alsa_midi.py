"""Small ALSA sequencer transport using the runtime's existing libasound.

Subscribers can monitor a hardware port without taking it away from the kit.
No raw-MIDI device is opened, and no global subscriptions are removed.
"""
import ctypes as C
import errno
import re
from pathlib import Path


def devices(text=None):
    text = Path('/proc/asound/seq/clients').read_text() if text is None else text
    result = []
    client = name = None
    for line in text.splitlines():
        match = re.match(r'Client\s+(\d+)\s+:\s+"([^"]+)" \[Kernel', line)
        if line.startswith('Client'):
            client, name = (int(match[1]), match[2]) if match else (None, None)
        port = re.match(r'\s+Port\s+(\d+)\s+:\s+"([^"]+)" \(([^)]+)\)', line)
        if client is not None and name in ('TSMEGA', 'SINCO') and port and 'R' in port[3] and 'e' in port[3]:
            result.append({'client': client, 'port': int(port[1]), 'name': name, 'port_name': port[2]})
    return result


class Sequencer:
    def __init__(self, name='TSMA Pedal Check'):
        self.lib = lib = C.CDLL('libasound.so.2')
        self.handle = C.c_void_p()
        self.decoder = C.c_void_p(); self.encoder = C.c_void_p()
        self.subscribed = set()
        self.outputs = set()
        self.closed = False
        signatures = {
            'snd_seq_open': ([C.POINTER(C.c_void_p), C.c_char_p, C.c_int, C.c_int], C.c_int),
            'snd_seq_close': ([C.c_void_p], C.c_int),
            'snd_seq_set_client_name': ([C.c_void_p, C.c_char_p], C.c_int),
            'snd_seq_client_id': ([C.c_void_p], C.c_int),
            'snd_seq_create_simple_port': ([C.c_void_p, C.c_char_p, C.c_uint, C.c_uint], C.c_int),
            'snd_seq_connect_from': ([C.c_void_p, C.c_int, C.c_int, C.c_int], C.c_int),
            'snd_seq_connect_to': ([C.c_void_p, C.c_int, C.c_int, C.c_int], C.c_int),
            'snd_seq_event_input': ([C.c_void_p, C.POINTER(C.c_void_p)], C.c_int),
            'snd_seq_event_output_direct': ([C.c_void_p, C.c_void_p], C.c_int),
            'snd_midi_event_new': ([C.c_size_t, C.POINTER(C.c_void_p)], C.c_int),
            'snd_midi_event_free': ([C.c_void_p], None),
            'snd_midi_event_no_status': ([C.c_void_p, C.c_int], None),
            'snd_midi_event_reset_encode': ([C.c_void_p], None),
            'snd_midi_event_decode': ([C.c_void_p, C.c_void_p, C.c_long, C.c_void_p], C.c_long),
            'snd_midi_event_encode': ([C.c_void_p, C.c_void_p, C.c_long, C.c_void_p], C.c_long),
            'snd_strerror': ([C.c_int], C.c_char_p),
        }
        for key, (args, result) in signatures.items():
            fn = getattr(lib, key); fn.argtypes = args; fn.restype = result
        try:
            self.check(lib.snd_seq_open(C.byref(self.handle), b'default', 3, 1))
            self.check(lib.snd_seq_set_client_name(self.handle, name.encode()))
            self.client = self.check(lib.snd_seq_client_id(self.handle))
            self.port = self.check(lib.snd_seq_create_simple_port(self.handle, b'Pedal diagnostics', 1 | 2 | 32 | 64, 1 << 20))
            self.check(lib.snd_midi_event_new(65536, C.byref(self.decoder)))
            self.check(lib.snd_midi_event_new(65536, C.byref(self.encoder)))
            lib.snd_midi_event_no_status(self.decoder, 1)
        except Exception:
            self.close(); raise

    def check(self, result):
        if result < 0: raise OSError(-result, self.lib.snd_strerror(result).decode())
        return result

    def connect(self, source):
        pair = source['client'], source['port']
        rc = self.lib.snd_seq_connect_from(self.handle, self.port, *pair)
        if rc not in (0, -errno.EBUSY): self.check(rc)
        self.subscribed.add(pair)

    def pending(self):
        result = []
        for _ in range(256):
            event = C.c_void_p()
            rc = self.lib.snd_seq_event_input(self.handle, C.byref(event))
            if rc in (-errno.EAGAIN, -errno.EINTR): break
            self.check(rc)
            header = C.string_at(event, 16)
            raw = C.create_string_buffer(65536)
            length = self.lib.snd_midi_event_decode(self.decoder, raw, len(raw), event)
            if length > 0: result.append(((header[12], header[13]), raw.raw[:length]))
        return result

    def send(self, target, data):
        if not data or data[0] != 0xF0 or data[-1] != 0xF7: raise ValueError('Only complete configuration SysEx is accepted.')
        pair = target['client'], target['port']
        if pair not in self.outputs:
            # A subscription activates the kernel's USB-MIDI output stream.
            self.check(self.lib.snd_seq_connect_to(self.handle, self.port, *pair))
            self.outputs.add(pair)
        raw = C.create_string_buffer(bytes(data))
        event = C.create_string_buffer(64)
        self.lib.snd_midi_event_reset_encode(self.encoder)
        count = self.lib.snd_midi_event_encode(self.encoder, raw, len(data), event)
        self.check(count)
        if count != len(data): raise ValueError('Incomplete MIDI configuration event.')
        event[3] = bytes([253])  # direct queue
        event[12] = bytes([self.client]); event[13] = bytes([self.port])
        event[14] = bytes([target['client']]); event[15] = bytes([target['port']])
        self.check(self.lib.snd_seq_event_output_direct(self.handle, event))

    def close(self):
        if self.closed: return
        self.closed = True
        for codec in (self.decoder, self.encoder):
            if codec: self.lib.snd_midi_event_free(codec)
        if self.handle: self.lib.snd_seq_close(self.handle)

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
