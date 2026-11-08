#!/usr/bin/python3
"""Install launchers for the separate SonicMaster/Pocket Master kit."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from dependencies import sonicmaster_executable

ROOT=Path(__file__).resolve().parents[1]


def desktop_entry(root):
    def quote(value):return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('$','\\$').replace('`','\\`').replace('%','%%')+'"'
    return f'''[Desktop Entry]
Type=Application
Name=SonicMaster-kit
Comment=Pocket Master USB · SonicMaster · SooperLooper · Chocolate
Exec={quote(root/'start-sonicmaster')}
Icon={root/'icona.svg'}
Terminal=false
Categories=AudioVideo;Audio;
StartupWMClass=SonicMaster-kit
Actions=SaveLoop;

[Desktop Action SaveLoop]
Name=Salva il loop
Exec={quote(root/'save-loop')}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-deps',action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if args.dry_run:
        print('SonicMaster-kit: dipendenze, libreria SooperLooper, launcher Desktop e menu.');return
    if sonicmaster_executable(ROOT) is None:
        raise RuntimeError('Installa SonicMaster da https://github.com/Skyggedans/SonicMaster/releases oppure imposta SONICMASTER_EXECUTABLE.')
    if not args.no_deps:
        packages=['python3','python3-gi','python3-dbus','gir1.2-gtk-3.0','gir1.2-gstreamer-1.0','gir1.2-gst-plugins-base-1.0','gstreamer1.0-plugins-base','gstreamer1.0-plugins-good','gstreamer1.0-libav','gstreamer1.0-tools','jackd2','jack-tools','sooperlooper','zita-ajbridge','alsa-utils','xserver-xephyr','openbox','xauth','x11-utils','x11-xserver-utils','wmctrl','gcc','libnotify-bin','xdg-user-dirs']
        missing=[p for p in packages if subprocess.run(['dpkg-query','-W','-f=${Status}',p],capture_output=True,text=True).stdout!='install ok installed']
        if missing:
            subprocess.run(['sudo','apt-get','update'],check=True);subprocess.run(['sudo','apt-get','install','-y',*missing],check=True)
    (ROOT/'vendor').mkdir(exist_ok=True)
    subprocess.run(['cc','-O2','-shared','-fPIC',str(ROOT/'src/slgui-lock.c'),'-Wl,-l:libgtk-3.so.0','-Wl,-l:libgobject-2.0.so.0','-Wl,-l:libglib-2.0.so.0','-o',str(ROOT/'vendor/slgui-lock.so')],check=True)
    for folder in ['state','log']:(ROOT/folder).mkdir(exist_ok=True)
    desktop=Path(subprocess.check_output(['xdg-user-dir','DESKTOP'],text=True).strip())
    applications=Path.home()/'.local/share/applications';applications.mkdir(parents=True,exist_ok=True)
    text=desktop_entry(ROOT)
    for folder in [desktop,applications]:
        target=folder/'sonicmaster-kit.desktop';target.write_text(text);target.chmod(0o755)
        subprocess.run(['gio','set',str(target),'metadata::trusted','true'],capture_output=True)
    print('SonicMaster-kit installato. Avvio: ./start-sonicmaster oppure icona sul Desktop.')


if __name__=='__main__':main()
