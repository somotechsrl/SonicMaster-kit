#!/usr/bin/env python3
"""Build the tested USB PCM capture library and bridges with baseline x86_64 flags."""
import hashlib,json,subprocess,tarfile,urllib.request
from pathlib import Path
ROOT=Path('/src');work=ROOT/'.cache-build/custom-dsp';work.mkdir(parents=True,exist_ok=True)
SOURCES=[('zita-alsa-pcmi','0.6.1','8a297ace3d7a474131ed3fa321069c131337785b56a237d6f168c85ee796d56c'),('zita-ajbridge','0.8.4','bc264e36ba4d715c34ec7dd6e317cd1ed4bb8a4656980d6b2200e2fa0105bb3c')]
records=[]
for name,version,digest in SOURCES:
 filename=f'{name}-{version}.tar.bz2';url='https://kokkinizita.linuxaudio.org/linuxaudio/downloads/'+filename;archive=work/filename
 if not archive.exists():urllib.request.urlretrieve(url,archive)
 if hashlib.sha256(archive.read_bytes()).hexdigest()!=digest:raise RuntimeError('Source checksum mismatch: '+filename)
 with tarfile.open(archive) as package:package.extractall(work,filter='data')
 folder=work/f'{name}-{version}'/'source';makefile=folder/'Makefile';makefile.write_text(makefile.read_text().replace('-march=native','-march=x86-64'))
 subprocess.run(['make','clean'],cwd=folder,check=True)
 subprocess.run(['make','PREFIX=/usr','LIBDIR=/usr/lib/x86_64-linux-gnu','CXXFLAGS=-O2 -Wall -fPIC -march=x86-64'],cwd=folder,check=True)
 subprocess.run(['make','install','PREFIX=/usr','LIBDIR=/usr/lib/x86_64-linux-gnu'],cwd=folder,check=True)
 records.append({'name':name,'version':version,'source':url,'sha256':digest,'cxxflags':'-O2 -Wall -fPIC -march=x86-64'})
(work/'custom-dsp-builds.json').write_text(json.dumps(records,indent=2)+'\n')
