"""Chocolate CC80..83 to the kit looper. No device configuration writes."""
import os
from pathlib import Path
import signal
import socket
import time
from alsa_midi import Sequencer, devices

RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp'))/'sonicmaster-kit'
LEASE = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp'))/f'jack-hooks-{os.getuid()}'/'tsma-pedal-check.lease'
ACTIONS = ('record_play', 'overdub', 'pause', 'clear')


def action(raw):
    if len(raw) == 3 and raw[0]&0xF0 == 0xB0 and 80 <= raw[1] <= 83 and raw[2] > 0:
        return ACTIONS[raw[1]-80]
    return None


def checking():
    try:
        expiry, pid = map(int, LEASE.read_text().split())
        return expiry >= time.time() and Path(f'/proc/{pid}').exists()
    except (OSError, ValueError):
        return False


def main():
    running = [True]
    signal.signal(signal.SIGTERM, lambda *_:running.__setitem__(0, False))
    signal.signal(signal.SIGINT, lambda *_:running.__setitem__(0, False))
    seq = None; source = None; scan = 0
    try:
        while running[0]:
            try:
                if time.monotonic() >= scan:
                    found = devices(names=('SINCO',))
                    target = found[0] if found else None
                    pair = (target['client'], target['port']) if target else None
                    if seq is None or pair != source:
                        if seq: seq.close()
                        seq = Sequencer('SonicMaster Chocolate'); source = pair
                        if target: seq.connect(target)
                    scan = time.monotonic()+1
                for origin, raw in seq.pending():
                    command = action(raw) if origin == source else None
                    if command and not checking():
                        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as output:
                            output.sendto(command.encode(), str(RUNTIME/'looper.sock'))
            except OSError:
                if seq: seq.close()
                seq = None; scan = time.monotonic()+1
            time.sleep(.01)
    finally:
        if seq: seq.close()


if __name__ == '__main__':
    main()
