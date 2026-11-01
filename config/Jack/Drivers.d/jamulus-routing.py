#!/usr/bin/python3
"""Route Jamulus, JackTrip and Carla JACK ports using the shared graph monitor."""
import argparse
import importlib.machinery
import importlib.util
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader('jack_bridge_monitor', str(ROOT / 'Monitor'))
spec = importlib.util.spec_from_loader(loader.name, loader)
monitor = importlib.util.module_from_spec(spec)
loader.exec_module(monitor)


def channel_ports(client, engine='jamulus'):
    if engine == 'carla':
        return ([f'{client}:audio-out{i}' for i in (1, 2)],
                [f'{client}:audio-in{i}' for i in (1, 2)])
    if engine == 'jacktrip':
        return ([f'{client}:receive_{i}' for i in (1, 2)],
                [f'{client}:send_{i}' for i in (1, 2)])
    return ([f'{client}:output {side}' for side in ('left', 'right')],
            [f'{client}:input {side}' for side in ('left', 'right')])


def route_pairs(client, daw, track, bus, engine='jamulus'):
    outputs, inputs = channel_ports(client, engine)
    return [(outputs[i], f'{daw}:{track}/audio_in {i+1}') for i in range(2)] + [
        (f'{daw}:{bus}/audio_out {i+1}', inputs[i]) for i in range(2)]


def default_connections(ports, client, engine='jamulus'):
    """Replace only this client's direct hardware routes."""
    result = []
    outputs, inputs = channel_ports(client, engine)
    for input_port, output_port in zip(inputs, outputs):
        for peer in ports.get(input_port, {}).get('connections', []):
            if peer.startswith('system:capture_'):
                result.append((peer, input_port))
        for peer in ports.get(output_port, {}).get('connections', []):
            if peer.startswith('system:playback_'):
                result.append((output_port, peer))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--engine', choices=('jamulus', 'jacktrip', 'carla'), default='jamulus')
    args = parser.parse_args()
    prefix = args.engine.upper()
    label = {'jamulus': 'Jamulus', 'jacktrip': 'JackTrip', 'carla': 'Carla'}[args.engine]
    client = os.environ.get(prefix + '_CLIENT', f'{label}')
    daw = os.environ.get(prefix + '_DAW_CLIENT', 'ardour')
    track = os.environ.get(prefix + '_INPUT_TRACK', f'FR {label}')
    bus = os.environ.get(prefix + '_OUTPUT_BUS', f'TO {label}')
    remove_system = os.environ.get(prefix + '_REMOVE_SYSTEM', '1')
    if not all((client, daw, track, bus)) or remove_system not in ('0', '1'):
        parser.error(f'Nomi delle porte o {prefix}_REMOVE_SYSTEM non validi')
    pairs = route_pairs(client, daw, track, bus, args.engine)
    if args.check:
        print('Routing ' + label + ' valido: ' + track + ' / ' + bus)
        return
    monitor.STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    logger = logging.getLogger(args.engine + '-routing')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(monitor.STATE / (args.engine + '-routing.log'), maxBytes=1024*1024, backupCount=2)
    os.chmod(monitor.STATE / (args.engine + '-routing.log'), 0o600)
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(handler)
    owner = int(os.environ.get('JACK_DRIVERS_OWNER_PID', '0'))
    owner_id = monitor.identity(owner) if owner else None
    alive = [True]
    signal.signal(signal.SIGINT, lambda *_: alive.__setitem__(0, False))
    signal.signal(signal.SIGTERM, lambda *_: alive.__setitem__(0, False))
    ready_since = None
    complete = False
    last_error = None
    logger.info('In attesa di %s, traccia %s, bus %s', client, track, bus)
    while alive[0] and (not owner or monitor.identity(owner) == owner_id):
        try:
            ports = monitor.graph()
            present = all(src in ports and dst in ports and ports[src]['output'] and not ports[dst]['output'] for src, dst in pairs)
            if not present:
                complete = False
                ready_since = None
            elif not complete:
                if monitor.restore(pairs, stop=lambda: not alive[0], timeout=2):
                    ready_since = None
                else:
                    if remove_system == '1':
                        for src, dst in default_connections(monitor.graph(), client, args.engine):
                            result = subprocess.run(['jack_disconnect', src, dst], capture_output=True, timeout=3)
                            if result.returncode:
                                logger.warning('Disconnessione non riuscita: %s → %s', src, dst)
                    # Allow native automatic connections to settle before
                    # finishing; user changes afterwards are left untouched.
                    ready_since = ready_since or time.monotonic()
                    if time.monotonic() - ready_since >= 2:
                        complete = True
                        logger.info('Collegato: %s → %s; %s → %s', client, track, bus, client)
            last_error = None
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            complete = False
            ready_since = None
            if str(exc) != last_error:
                logger.warning('Routing in attesa: %s', exc)
                last_error = str(exc)
        time.sleep(.5)
    logger.info('Routing %s terminato', label)


if __name__ == '__main__':
    main()
