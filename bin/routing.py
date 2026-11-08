"""Pocket Master USB directly into SooperLooper; optional TSMA-Kit/OBS outputs."""
import ctypes as C
import json
import os
from pathlib import Path
import re
import signal
import time

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'config/kit.json').read_text())


def plan(graph, track='TSMA-Kit', client='SonicMaster_Looper', ardour=False):
    wanted = []
    owned = []
    def edge(source, target):
        if source in graph and target in graph:
            wanted.append((source, target))
    for i in (1, 2):
        target = f'{client}:common_in_{i}'
        owned.append(target)
        edge(f'PocketMaster_in:capture_{i}', target)
    daw = all(f'ardour:{track}/audio_in {i}' in graph for i in (1, 2))
    daw_active = ardour or any(re.fullmatch(r'ardour(-?[0-9][a-zA-Z0-9.~+-]*)?', name.partition(':')[0], re.I) for name in graph)
    for i, channel in ((1, 'FL'), (2, 'FR')):
        source = f'{client}:common_out_{i}'
        edge(source, f'ardour:{track}/audio_in {i}' if daw else f'PocketMaster_out:playback_{i}')
        if not daw_active:
            edge(source, f'PipeWire:capture_{channel}')
    # Backing tracks join the monitored mix after the looper, so they are not
    # recorded into loops. Their output cannot feed the Pocket capture ports.
    for name, data in graph.items():
        if name.startswith('SonicMaster_Backing:') and data['output']:
            i = 2 if name.endswith(('_2', '_FR', 'out_2')) else 1
            edge(name, f'ardour:{track}/audio_in {i}' if daw else f'PocketMaster_out:playback_{i}')
            if not daw_active:
                edge(name, f'PipeWire:capture_{"FR" if i == 2 else "FL"}')
    disconnect = []
    for name, data in graph.items():
        if name in owned:
            disconnect.extend((source, name) for source in data['connections'] if (source, name) not in wanted)
        if name.startswith((client+':', 'SonicMaster_Backing:')) and data['output']:
            disconnect.extend((name, dest) for dest in data['connections'] if (name, dest) not in wanted)
    connect = [(source, dest) for source, dest in wanted if dest not in graph[source]['connections']]
    return connect, disconnect


class JackGraph:
    def __init__(self):
        self.lib = lib = C.CDLL('libjack.so.0')
        ptr, array = C.c_void_p, C.POINTER(C.c_char_p)
        signatures = {
            'jack_client_open': ([C.c_char_p, C.c_int, C.POINTER(C.c_int)], ptr),
            'jack_client_close': ([ptr], C.c_int),
            'jack_get_ports': ([ptr, C.c_char_p, C.c_char_p, C.c_ulong], array),
            'jack_port_by_name': ([ptr, C.c_char_p], ptr),
            'jack_port_flags': ([ptr], C.c_int),
            'jack_port_get_all_connections': ([ptr, ptr], array),
            'jack_connect': ([ptr, C.c_char_p, C.c_char_p], C.c_int),
            'jack_disconnect': ([ptr, C.c_char_p, C.c_char_p], C.c_int),
            'jack_free': ([ptr], None),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(lib, name); fn.argtypes = args; fn.restype = result
        status = C.c_int()
        self.client = lib.jack_client_open(b'SonicMaster_Routing', 1, C.byref(status))
        if not self.client:
            raise OSError('JACK non disponibile')
        self.alive = True
        callback_type = C.CFUNCTYPE(None, ptr)
        self.shutdown = callback_type(lambda _: setattr(self, 'alive', False))
        lib.jack_on_shutdown.argtypes = [ptr, callback_type, ptr]
        lib.jack_on_shutdown(self.client, self.shutdown, None)

    def strings(self, pointer):
        result = []
        if pointer:
            try:
                i = 0
                while pointer[i]:
                    result.append(pointer[i].decode()); i += 1
            finally:
                self.lib.jack_free(C.cast(pointer, C.c_void_p))
        return result

    def read(self):
        result = {}
        for name in self.strings(self.lib.jack_get_ports(self.client, None, None, 0)):
            port = self.lib.jack_port_by_name(self.client, name.encode())
            if port:
                result[name] = {'output':bool(self.lib.jack_port_flags(port)&2), 'connections':self.strings(self.lib.jack_port_get_all_connections(self.client, port))}
        return result

    def close(self):
        self.lib.jack_client_close(self.client)


def main():
    graph = JackGraph()
    signal.signal(signal.SIGTERM, lambda *_:setattr(graph, 'alive', False))
    signal.signal(signal.SIGINT, lambda *_:setattr(graph, 'alive', False))
    try:
        while graph.alive:
            connect, disconnect = plan(graph.read(), CONFIG['ardour_track'], CONFIG['jack_client'])
            for fn, edges in ((graph.lib.jack_disconnect, disconnect), (graph.lib.jack_connect, connect)):
                for source, target in edges:
                    fn(graph.client, source.encode(), target.encode())
            time.sleep(.3)
    finally:
        graph.close()


if __name__ == '__main__':
    main()
