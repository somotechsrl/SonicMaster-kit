"""Load a backing track and press ToneLib's enabled Play button after analysis."""
import ctypes as C,json,re,subprocess,time
from pathlib import Path
from xdnd import send_file

TEMPLATE=Path(__file__).resolve().parents[1]/'config/tonelib-play-icon.json'


def find_play(pixels,width,height,stride,channels,template):
    """Recognize the enabled triangle in the player's left control strip."""
    positive=[(x,y) for y,row in enumerate(template) for x,v in enumerate(row) if v=='1']
    negative=[(x,y) for y,row in enumerate(template) for x,v in enumerate(row) if v=='0' and (x+y)%3==0]
    def bright(x,y):
        offset=y*stride+x*channels;r,g,b=pixels[offset:offset+3]
        return min(r,g,b)>110 and max(r,g,b)-min(r,g,b)<30
    matches=[]
    for y in range(max(0,height-360),max(0,height-90-len(template))):
        for x in range(32,min(80,width-len(template[0]))):
            if not all(bright(x+px,y+py) for px,py in positive[::40]):continue
            errors=sum(not bright(x+px,y+py) for px,py in positive)+sum(bright(x+px,y+py) for px,py in negative)
            if errors<=4:matches.append((errors,x,y))
    if not matches:return None
    _,x,y=min(matches)
    if any(abs(mx-x)>4 or abs(my-y)>4 for _,mx,my in matches):return None
    return x+len(template[0])//2,y+len(template)//2


def click_at(target,x,y):
    from xdnd import X
    xtest=C.CDLL('libXtst.so.6')
    xtest.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
    xtest.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    X.XRaiseWindow.argtypes=[C.c_void_p,C.c_ulong]
    X.XQueryPointer.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_uint)]
    display=X.XOpenDisplay(None)
    if not display:raise RuntimeError('Display ToneLib non disponibile.')
    root=C.c_ulong();child=C.c_ulong();old_x=C.c_int();old_y=C.c_int();local_x=C.c_int();local_y=C.c_int();mask=C.c_uint()
    restore=X.XQueryPointer(display,X.XDefaultRootWindow(display),C.byref(root),C.byref(child),C.byref(old_x),C.byref(old_y),C.byref(local_x),C.byref(local_y),C.byref(mask))
    try:
        X.XRaiseWindow(display,target)
        xtest.XTestFakeMotionEvent(display,-1,x,y,0);X.XFlush(display);time.sleep(.05)
        xtest.XTestFakeButtonEvent(display,1,1,0);xtest.XTestFakeButtonEvent(display,1,0,0);X.XFlush(display)
        time.sleep(.05)
        if restore:xtest.XTestFakeMotionEvent(display,-1,old_x.value,old_y.value,0);X.XFlush(display)
    finally:X.XCloseDisplay(display)


def window_geometry(target):
    text=subprocess.check_output(['xwininfo','-id',hex(target)],text=True,timeout=3)
    return tuple(int(re.search(pattern,text)[1]) for pattern in
                 (r'Absolute upper-left X:\s*(-?\d+)',r'Absolute upper-left Y:\s*(-?\d+)',r'Width:\s*(\d+)',r'Height:\s*(\d+)'))


def load_and_play(target,file,timeout=180):
    import gi
    gi.require_version('Gdk','3.0')
    from gi.repository import Gdk
    pid_info=subprocess.check_output(['xprop','-id',hex(target),'_NET_WM_PID'],text=True,timeout=3)
    pid=re.search(r'=\s*(\d+)',pid_info)[1]
    x,y,width,height=window_geometry(target)
    if not send_file(target,file,x+width//2,y+height-80):
        raise RuntimeError('ToneLib non ha accettato la traccia audio.')
    # Let ToneLib replace the previous player controls with its analysis dialog.
    time.sleep(1)
    template=json.loads(TEMPLATE.read_text());root=Gdk.get_default_root_window()
    until=time.monotonic()+timeout;ready_since=None
    while time.monotonic()<until:
        rows=subprocess.check_output(['wmctrl','-lpG'],text=True,timeout=3).splitlines()
        # JUCE's analysis window is a separate top-level window with the same
        # PID and often an empty title. Never click through a loading dialog.
        busy=any(len(fields)>=3 and fields[2]==pid and int(fields[0],16)!=target
                 for fields in (row.split(None,8) for row in rows))
        if busy:ready_since=None;time.sleep(.2);continue
        x,y,width,height=window_geometry(target)
        pix=Gdk.pixbuf_get_from_window(root,x,y,width,height)
        if pix is not None:
            point=find_play(pix.get_pixels(),width,height,pix.get_rowstride(),pix.get_n_channels(),template)
            if point:
                if ready_since is None:ready_since=time.monotonic()
                if time.monotonic()-ready_since>=.5:
                    click_at(target,x+point[0],y+point[1]);return
            else:ready_since=None
        time.sleep(.2)
    raise RuntimeError('Traccia inviata a ToneLib, ma Play non è diventato disponibile. Avvia la riproduzione dal player.')


if __name__=='__main__':
    import sys
    try:load_and_play(int(sys.argv[1],0),sys.argv[2])
    except Exception as exc:print(str(exc),file=sys.stderr);raise SystemExit(1)
