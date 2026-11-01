#!/usr/bin/python3
"""Toggle ToneLib's tuner, targeting only its own X11 windows and toolbar icon."""
import ctypes as C,fcntl,json,os,re,subprocess,time
from pathlib import Path
import gi
gi.require_version('Gdk','3.0')
from gi.repository import Gdk
ROOT=Path(__file__).resolve().parent

def command(*args):
 return subprocess.check_output(args,text=True,env={**os.environ,'LC_ALL':'C'})

def owned(window,pids):
 pid=re.search(r'= (\d+)',command('xprop','-id',window,'_NET_WM_PID'))
 return pid is not None and int(pid[1]) in pids

def click_at(px,py,window):
 x=C.CDLL('libX11.so.6');t=C.CDLL('libXtst.so.6');x.XOpenDisplay.restype=C.c_void_p;display=x.XOpenDisplay(None)
 if not display:raise RuntimeError('X display unavailable')
 t.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
 t.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
 x.XRaiseWindow.argtypes=[C.c_void_p,C.c_ulong]
 x.XDefaultRootWindow.argtypes=[C.c_void_p];x.XDefaultRootWindow.restype=C.c_ulong
 x.XQueryPointer.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_uint)]
 x.XFlush.argtypes=[C.c_void_p];x.XCloseDisplay.argtypes=[C.c_void_p]
 root=C.c_ulong();child=C.c_ulong();old_x=C.c_int();old_y=C.c_int();local_x=C.c_int();local_y=C.c_int();mask=C.c_uint()
 have_pointer=x.XQueryPointer(display,x.XDefaultRootWindow(display),C.byref(root),C.byref(child),C.byref(old_x),C.byref(old_y),C.byref(local_x),C.byref(local_y),C.byref(mask))
 try:
  x.XRaiseWindow(display,int(window,16));x.XFlush(display);time.sleep(.06)
  t.XTestFakeMotionEvent(display,-1,px,py,0);x.XFlush(display);time.sleep(.06)
  t.XTestFakeButtonEvent(display,1,1,0);t.XTestFakeButtonEvent(display,1,0,0);x.XFlush(display);time.sleep(.08)
  if have_pointer:t.XTestFakeMotionEvent(display,-1,old_x.value,old_y.value,0);x.XFlush(display)
 finally:x.XCloseDisplay(display)

def toggle():
 pids={int(p) for p in command('pgrep','-x','ToneLib-GFX').split()}
 windows=command('xwininfo','-root','-tree').splitlines()
 matches=[]
 for line in windows:
  m=re.match(r'\s*(0x[0-9a-f]+) "(Tuner|ToneLib GFX)": \("ToneLib GFX" "ToneLib GFX"\)\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)',line)
  if m and owned(m[1],pids):matches.append(m)
 for m in matches:
  if m[2]=='Tuner':
   if (int(m[3]),int(m[4]))!=(471,317):raise RuntimeError('Unexpected tuner dialog layout')
   absolute=re.search(r'\s+([+-]\d+)([+-]\d+)\s*$',next(line for line in windows if line.lstrip().startswith(m[1]+' ')))
   click_at(int(absolute[1])+int(m[3])-37,int(absolute[2])+29,m[1]);return
 main=next((m for m in matches if m[2]=='ToneLib GFX'),None)
 if main is None:raise RuntimeError('ToneLib main window not found')
 window=main[1];width=int(main[3]);absolute=re.search(r'\s+([+-]\d+)([+-]\d+)\s*$',next(line for line in windows if line.lstrip().startswith(window+' ')))
 origin_x=int(absolute[1]);origin_y=int(absolute[2])
 subprocess.run(['wmctrl','-ia',window],check=True);time.sleep(.18)
 active=re.search(r'0x[0-9a-f]+',command('xprop','-root','_NET_ACTIVE_WINDOW'))
 if active is None or int(active[0],16)!=int(window,16):raise RuntimeError('ToneLib did not become active')
 pix=Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(),origin_x,origin_y+11,width,24)
 if pix is None:raise RuntimeError('ToneLib toolbar not visible')
 data=pix.get_pixels();stride=pix.get_rowstride();channels=pix.get_n_channels()
 template=json.loads((ROOT/'tonelib-tuner-icon.json').read_text())
 positive=[(x,y) for y,row in enumerate(template) for x,v in enumerate(row) if v]
 negative=[(x,y) for y,row in enumerate(template) for x,v in enumerate(row) if not v and (x+y)%3==0]
 def bright(x,y):
  offset=y*stride+x*channels
  return min(data[offset:offset+3])>120
 candidates=[]
 for start in range(width-23):
  # Cheap anchor before comparing the full icon; never click on a weak match.
  if not all(bright(start+x,y) for x,y in positive[::8]):continue
  error=sum(not bright(start+x,y) for x,y in positive)+sum(bright(start+x,y) for x,y in negative)
  if error<=3:candidates.append((error,start))
 if not candidates:raise RuntimeError('ToneLib tuner icon not recognized')
 best=min(candidates)
 if any(abs(start-best[1])>3 and err<=best[0]+2 for err,start in candidates):raise RuntimeError('Ambiguous tuner icon')
 click_at(origin_x+best[1]+12,origin_y+23,window)

if __name__=='__main__':
 runtime=Path(os.environ.get('XDG_RUNTIME_DIR','/tmp'))
 with open(runtime/f'tonelib-tuner-{os.getuid()}.lock','w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise SystemExit(0)
  toggle();time.sleep(.2)
