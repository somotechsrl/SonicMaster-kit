#!/usr/bin/env python3
"""Build the pinned SonicMaster editor with the kit's Pocket-only patch."""
import argparse,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMMIT='931a68f4ee06263e1eb622ee0fccf9f84d2b9751'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--flutter',required=True,type=Path);args=p.parse_args()
    cache=Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')/'sonicmaster-kit-editor-build'
    source=cache/'source';cache.mkdir(parents=True,exist_ok=True)
    if not source.exists():subprocess.run(['git','clone','--branch','v1.0.10','--depth','1','https://github.com/Skyggedans/SonicMaster.git',str(source)],check=True)
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    if actual!=COMMIT:raise RuntimeError('Unexpected upstream commit')
    patch=ROOT/'editor/sonicmaster-pocket-only.patch'
    if subprocess.run(['git','apply','--reverse','--check',str(patch)],cwd=source,capture_output=True).returncode:
        subprocess.run(['git','apply',str(patch)],cwd=source,check=True)
    env={k:v for k,v in os.environ.items() if not k.startswith(('GTK_','GIO_','GDK_PIXBUF_','LD_','SNAP','PYTHONHOME','PYTHONPATH'))}
    env.update(PATH=str(args.flutter.resolve().parent)+':'+str(Path.home()/'.cargo/bin')+':/usr/bin:/bin',CI='true',XDG_DATA_DIRS='/usr/local/share:/usr/share')
    dsp=Path.home()/'.local/opt/sonicmaster/current/lib/libclo_generator.so'
    if dsp.is_file():env['SONICMASTER_CLO_LIBRARY']=str(dsp)
    subprocess.run([str(args.flutter.resolve()),'build','linux','--release'],cwd=source/'app',env=env,check=True)
    target=ROOT/'vendor/sonicmaster';target.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source/'app/build/linux/x64/release/bundle',target,dirs_exist_ok=True)
    for name in ['LICENSE','THIRD_PARTY_NOTICES.md']:shutil.copy2(source/name,target/name)
    print('Built editor:',target/'sonicmaster')

if __name__=='__main__':main()
