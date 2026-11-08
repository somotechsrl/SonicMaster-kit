"""Isolated native X11 regression: keyboard focus and pointer after resize.

Run with a working host DISPLAY/XAUTHORITY. Two disposable Xephyr servers keep
synthetic input away from the user's applications; no audio server is touched.
"""
import ctypes as C
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'bin'))
from keyboard_focus import EmbeddedFocus


def main():
    host_env = os.environ.copy()
    free = [n for n in range(91, 120) if not Path(f'/tmp/.X11-unix/X{n}').exists() and not Path(f'/tmp/.X{n}-lock').exists()][:2]
    assert len(free) == 2
    outer_env = dict(host_env, DISPLAY=f':{free[0]}')
    inner_env = dict(host_env, DISPLAY=f':{free[1]}')
    children = []
    connection = None

    def run(args, env=outer_env):
        return subprocess.run(args, env=env, capture_output=True, text=True, check=True, timeout=5).stdout

    def spawn(args, env, output=subprocess.DEVNULL):
        process = subprocess.Popen(args, env=env, stdout=output, stderr=subprocess.DEVNULL)
        children.append(process)
        return process

    def wait_for(condition):
        deadline = time.monotonic()+4
        while time.monotonic() < deadline:
            try:
                if condition():
                    return
            except (subprocess.SubprocessError, ValueError):
                pass
            time.sleep(.05)
        raise AssertionError('Native input condition timed out')

    def ready(env):
        return subprocess.run(['xprop', '-root'], env=env, capture_output=True).returncode == 0

    try:
        spawn(['Xephyr', outer_env['DISPLAY'], '-screen', '1000x800', '-no-host-grab', '-nolisten', 'tcp', '-ac', '-noreset'], host_env)
        wait_for(lambda: ready(outer_env))
        os.environ['DISPLAY'] = outer_env['DISPLAY']
        x = C.CDLL('libX11.so.6')
        x.XOpenDisplay.argtypes = [C.c_char_p]; x.XOpenDisplay.restype = C.c_void_p
        connection = x.XOpenDisplay(None)
        x.XDefaultRootWindow.argtypes = [C.c_void_p]; x.XDefaultRootWindow.restype = C.c_ulong
        x.XCreateSimpleWindow.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_uint, C.c_ulong, C.c_ulong]
        x.XCreateSimpleWindow.restype = C.c_ulong
        x.XMapWindow.argtypes = [C.c_void_p, C.c_ulong]
        x.XResizeWindow.argtypes = [C.c_void_p, C.c_ulong, C.c_uint, C.c_uint]
        x.XSync.argtypes = [C.c_void_p, C.c_int]
        x.XCloseDisplay.argtypes = [C.c_void_p]
        root = x.XDefaultRootWindow(connection)
        host = x.XCreateSimpleWindow(connection, root, 0, 0, 900, 740, 0, 0, 0)
        area = x.XCreateSimpleWindow(connection, host, 10, 60, 850, 650, 0, 0, 0)
        header = x.XCreateSimpleWindow(connection, host, 10, 10, 200, 40, 0, 0, 0)
        other = x.XCreateSimpleWindow(connection, root, 920, 0, 60, 100, 0, 0, 0)
        for window in (host, area, header, other):
            x.XMapWindow(connection, window)
        x.XSync(connection, False)
        spawn(['Xephyr', inner_env['DISPLAY'], '-parent', str(area), '-screen', '640x480', '-resizeable', '-no-host-grab', '-nolisten', 'tcp', '-ac', '-noreset'], outer_env)
        wait_for(lambda: ready(inner_env))
        tree = run(['xwininfo', '-id', str(area), '-children'])
        peer = int(re.search(r'(?m)^\s+(0x[0-9a-fA-F]+) "', tree)[1], 16)
        spawn([sys.executable, str(ROOT/'bin/keyboard_focus.py'), str(host), str(peer), str(os.getpid()), inner_env['DISPLAY'], inner_env.get('XAUTHORITY', '')], outer_env)
        focus = EmbeddedFocus(host, peer)
        def focused():
            value, revert = C.c_ulong(), C.c_int()
            focus.x.XGetInputFocus(focus.display, C.byref(value), C.byref(revert))
            return value.value
        run(['xdotool', 'windowfocus', str(host), 'mousemove', '100', '120'])
        wait_for(lambda: focused() == peer)
        run(['xdotool', 'mousemove', '50', '30', 'windowfocus', str(header)])
        time.sleep(.2)
        assert focused() == header, 'Header focus was stolen'
        run(['xdotool', 'mousemove', '100', '120'])
        wait_for(lambda: focused() == peer)
        run(['xdotool', 'mousemove', '950', '50', 'windowfocus', str(other), 'mousemove', '100', '120'])
        time.sleep(.2)
        assert focused() == other, 'Another application lost focus'
        run(['xdotool', 'windowfocus', str(host)])
        wait_for(lambda: focused() == peer)
        # Check both growth beyond the original pointer bounds and shrinkage.
        for width, height in ((800, 600), (500, 350), (820, 620)):
            x.XResizeWindow(connection, peer, width, height); x.XSync(connection, False)
            time.sleep(.4)
            px, py = width-20, height-20
            run(['xdotool', 'mousemove', str(px+10), str(py+60)])
            time.sleep(.1)
            location = run(['xdotool', 'getmouselocation', '--shell'], inner_env)
            actual = {key:int(value) for key,value in re.findall(r'^(X|Y)=(\d+)', location, re.M)}
            assert actual == {'X':px, 'Y':py}, (width, height, actual)
        with tempfile.TemporaryFile(mode='w+') as events:
            event_reader = spawn(['xev', '-name', 'TSMA input regression', '-geometry', '180x100+20+20'], inner_env, events)
            def test_window():
                found = run(['xdotool', 'search', '--name', '^TSMA input regression$'], inner_env).split()
                return found[0] if found else None
            wait_for(test_window)
            run(['xdotool', 'windowfocus', test_window()], inner_env)
            run(['xdotool', 'key', 'F8'])
            time.sleep(.2); event_reader.terminate(); event_reader.wait(timeout=3)
            events.seek(0)
            assert 'F8' in events.read(), 'Host keystroke did not reach nested application'
        focus.x.XCloseDisplay(focus.display)
        print('Native focus, header/other-app isolation, three resizes and keyboard delivery passed.')
    finally:
        if connection:
            x.XCloseDisplay(connection)
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
        os.environ.update(DISPLAY=host_env.get('DISPLAY', ''))


if __name__ == '__main__':
    main()
