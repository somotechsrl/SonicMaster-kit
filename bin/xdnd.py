"""Deliver a local audio file to an X11 application's normal drag/drop handler."""
import ctypes as C,time
from pathlib import Path
X=C.CDLL('libX11.so.6')
class Data(C.Union):_fields_=[('l',C.c_long*5),('b',C.c_char*20)]
class Client(C.Structure):_fields_=[('type',C.c_int),('serial',C.c_ulong),('send',C.c_int),('display',C.c_void_p),('window',C.c_ulong),('message',C.c_ulong),('format',C.c_int),('data',Data)]
class Request(C.Structure):_fields_=[('type',C.c_int),('serial',C.c_ulong),('send',C.c_int),('display',C.c_void_p),('owner',C.c_ulong),('requestor',C.c_ulong),('selection',C.c_ulong),('target',C.c_ulong),('property',C.c_ulong),('time',C.c_ulong)]
class Selection(C.Structure):_fields_=[('type',C.c_int),('serial',C.c_ulong),('send',C.c_int),('display',C.c_void_p),('requestor',C.c_ulong),('selection',C.c_ulong),('target',C.c_ulong),('property',C.c_ulong),('time',C.c_ulong)]
class Event(C.Union):_fields_=[('client',Client),('request',Request),('selection',Selection),('pad',C.c_long*24)]
X.XOpenDisplay.argtypes=[C.c_char_p];X.XOpenDisplay.restype=C.c_void_p
X.XDefaultRootWindow.argtypes=[C.c_void_p];X.XDefaultRootWindow.restype=C.c_ulong
X.XCreateSimpleWindow.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_uint,C.c_ulong,C.c_ulong];X.XCreateSimpleWindow.restype=C.c_ulong
X.XInternAtom.argtypes=[C.c_void_p,C.c_char_p,C.c_int];X.XInternAtom.restype=C.c_ulong
X.XSetSelectionOwner.argtypes=[C.c_void_p,C.c_ulong,C.c_ulong,C.c_ulong]
X.XSendEvent.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_long,C.POINTER(Event)]
X.XChangeProperty.argtypes=[C.c_void_p,C.c_ulong,C.c_ulong,C.c_ulong,C.c_int,C.c_int,C.c_void_p,C.c_int]
X.XPending.argtypes=[C.c_void_p];X.XNextEvent.argtypes=[C.c_void_p,C.POINTER(Event)];X.XFlush.argtypes=[C.c_void_p]
X.XDestroyWindow.argtypes=[C.c_void_p,C.c_ulong];X.XCloseDisplay.argtypes=[C.c_void_p]
def send_file(target,file,x=400,y=400):
 display=X.XOpenDisplay(None)
 if not display:raise RuntimeError('Cannot connect to the application display.')
 source=X.XCreateSimpleWindow(display,X.XDefaultRootWindow(display),0,0,1,1,0,0,0)
 atom=lambda name:X.XInternAtom(display,name.encode(),0)
 uri=atom('text/uri-list');selection=atom('XdndSelection');copy=atom('XdndActionCopy')
 def message(name,*values):
  event=Event();event.client.type=33;event.client.send=1;event.client.display=display;event.client.window=target;event.client.message=atom(name);event.client.format=32
  for i,value in enumerate(values):event.client.data.l[i]=value
  X.XSendEvent(display,target,0,0,C.byref(event));X.XFlush(display)
 payload=(Path(file).resolve().as_uri()+'\r\n').encode()
 try:
  X.XSetSelectionOwner(display,selection,source,0)
  message('XdndEnter',source,3<<24,uri,0,0)
  message('XdndPosition',source,0,(x<<16)|y,0,copy)
  accepted=False;dropped=False;until=time.monotonic()+4
  while time.monotonic()<until:
   while X.XPending(display):
    event=Event();X.XNextEvent(display,C.byref(event))
    if event.client.type==33 and event.client.message==atom('XdndStatus'):
     accepted=bool(event.client.data.l[1]&1)
     if accepted and not dropped:message('XdndDrop',source,0,0,0,0);dropped=True
    elif event.request.type==30:
     request=event.request;prop=request.property or request.target
     X.XChangeProperty(display,request.requestor,prop,uri,8,0,payload,len(payload))
     reply=Event();reply.selection.type=31;reply.selection.send=1;reply.selection.display=display;reply.selection.requestor=request.requestor;reply.selection.selection=request.selection;reply.selection.target=request.target;reply.selection.property=prop;reply.selection.time=request.time
     X.XSendEvent(display,request.requestor,0,0,C.byref(reply));X.XFlush(display)
    elif event.client.type==33 and event.client.message==atom('XdndFinished'):return accepted
   time.sleep(.01)
  return accepted and dropped
 finally:X.XDestroyWindow(display,source);X.XCloseDisplay(display)
if __name__=='__main__':
 import sys
 if not send_file(int(sys.argv[1],0),sys.argv[2],int(sys.argv[3]),int(sys.argv[4])):raise SystemExit('The application did not accept the audio file.')
