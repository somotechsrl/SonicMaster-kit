"""Small OSC codec: the OSC string/int/float types used by SooperLooper."""
import struct

def string(s):
 b=s.encode()+b'\0';return b+b'\0'*((-len(b))%4)
def encode(path,*args):
 types='';body=b''
 for a in args:
  if isinstance(a,str):types+='s';body+=string(a)
  elif isinstance(a,int):types+='i';body+=struct.pack('>i',a)
  else:types+='f';body+=struct.pack('>f',a)
 return string(path)+string(','+types)+body

def decode(data):
 def read_string(pos):
  end=data.index(0,pos);return data[pos:end].decode(),(end+4)&~3
 path,pos=read_string(0);types,pos=read_string(pos);args=[]
 for t in types[1:]:
  if t=='s':v,pos=read_string(pos)
  elif t in ('i','f'):v=struct.unpack_from('>'+t,data,pos)[0];pos+=4
  else:raise ValueError('Unsupported OSC type '+t)
  args.append(v)
 return path,args
