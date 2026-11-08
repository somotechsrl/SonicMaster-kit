"""Keep keyboard focus and pointer bounds correct in embedded Xephyr.

Xephyr's -parent window is not an XEmbed plug. GTK otherwise keeps keyboard
focus on its own toplevel while mouse clicks reach the nested applications.
Watch crossing/focus/resize events; never grab or synthesize keyboard input.
"""
import ctypes as C
import os
import select
import subprocess
import sys
import time


class EmbeddedFocus:
    def __init__(self, host, peer, nested_env=None):
        self.host, self.peer = host, peer
        self.nested_env = nested_env
        self.x = x = C.CDLL('libX11.so.6')
        window = C.c_ulong
        x.XOpenDisplay.argtypes = [C.c_char_p]
        x.XOpenDisplay.restype = C.c_void_p
        x.XCloseDisplay.argtypes = [C.c_void_p]
        x.XConnectionNumber.argtypes = [C.c_void_p]
        x.XSelectInput.argtypes = [C.c_void_p, window, C.c_long]
        x.XPending.argtypes = [C.c_void_p]
        x.XNextEvent.argtypes = [C.c_void_p, C.c_void_p]
        x.XFlush.argtypes = [C.c_void_p]
        x.XGetInputFocus.argtypes = [C.c_void_p, C.POINTER(window), C.POINTER(C.c_int)]
        x.XSetInputFocus.argtypes = [C.c_void_p, window, C.c_int, window]
        x.XQueryTree.argtypes = [C.c_void_p, window, C.POINTER(window), C.POINTER(window), C.POINTER(C.POINTER(window)), C.POINTER(C.c_uint)]
        x.XFree.argtypes = [C.c_void_p]
        x.XQueryPointer.argtypes = [C.c_void_p, window, C.POINTER(window), C.POINTER(window), C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_uint)]
        self.display = x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('Host X display unavailable')
        # Crossing, focus and structure are nonexclusive selections. Do not select
        # ButtonPress or keyboard events owned by GTK and Xephyr.
        x.XSelectInput(self.display, host, (1 << 21) | (1 << 4))
        x.XSelectInput(self.display, peer, (1 << 21) | (1 << 4) | (1 << 17))
        x.XFlush(self.display)

    def descendant(self, child, parent):
        for _ in range(32):
            if child == parent:
                return True
            if child <= 1:
                return False
            root, above = C.c_ulong(), C.c_ulong()
            children, count = C.POINTER(C.c_ulong)(), C.c_uint()
            ok = self.x.XQueryTree(self.display, child, C.byref(root), C.byref(above), C.byref(children), C.byref(count))
            if children:
                self.x.XFree(children)
            if not ok or above.value == child:
                return False
            child = above.value
        return False

    def focus(self):
        current, revert = C.c_ulong(), C.c_int()
        self.x.XGetInputFocus(self.display, C.byref(current), C.byref(revert))
        if current.value == self.peer or not self.descendant(current.value, self.host):
            return False
        # Query the area containing Xephyr: a child result identifies the visible
        # embedded window, excluding the header, mixer controls and overlays.
        root, parent = C.c_ulong(), C.c_ulong()
        children, count = C.POINTER(C.c_ulong)(), C.c_uint()
        self.x.XQueryTree(self.display, self.peer, C.byref(root), C.byref(parent), C.byref(children), C.byref(count))
        if children:
            self.x.XFree(children)
        child = C.c_ulong()
        rx, ry, px, py = (C.c_int() for _ in range(4))
        mask = C.c_uint()
        same = self.x.XQueryPointer(self.display, parent.value, C.byref(root), C.byref(child), C.byref(rx), C.byref(ry), C.byref(px), C.byref(py), C.byref(mask))
        if not same or child.value != self.peer:
            return False
        self.x.XSetInputFocus(self.display, self.peer, 2, 0)
        self.x.XFlush(self.display)
        return True

    def run(self, owner):
        event = (C.c_long * 24)()
        refresh_at = time.monotonic() if self.nested_env else None
        self.focus()
        try:
            while True:
                try:
                    os.kill(owner, 0)
                except ProcessLookupError:
                    break
                while self.x.XPending(self.display):
                    self.x.XNextEvent(self.display, C.byref(event))
                    kind = C.cast(event, C.POINTER(C.c_int))[0]
                    if kind in (7, 9):
                        self.focus()
                    if kind == 22 and self.nested_env:
                        refresh_at = time.monotonic() + .1
                if refresh_at is not None and time.monotonic() >= refresh_at:
                    # Xephyr resizes its framebuffer but leaves the RandR CRTC
                    # at the previous size. A full query runs its GetInfo hook,
                    # updating the pointer limits too. --current skips that hook.
                    try:
                        subprocess.run(['xrandr', '--query'], env=self.nested_env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                    refresh_at = None
                timeout = .5 if refresh_at is None else max(0, min(.5, refresh_at-time.monotonic()))
                select.select([self.x.XConnectionNumber(self.display)], [], [], timeout)
        finally:
            self.x.XCloseDisplay(self.display)


if __name__ == '__main__':
    nested_env = None
    if len(sys.argv) == 6:
        nested_env = os.environ.copy()
        nested_env.update(DISPLAY=sys.argv[4], XAUTHORITY=sys.argv[5])
    EmbeddedFocus(int(sys.argv[1], 0), int(sys.argv[2], 0), nested_env).run(int(sys.argv[3]))
