#!/usr/bin/python3
"""Launch SonicMaster and the dedicated Pocket Master/Chocolate looper kit."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'config/kit.json').read_text())
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp'))/'sonicmaster-kit'
PYTHON = '/usr/bin/python3'
UNITS = ('editor', 'looper-gui', 'midi', 'routing', 'engine', 'gui')


def clean_environment():
    for key in list(os.environ):
        if key.startswith(('GTK_', 'GIO_', 'GDK_PIXBUF_', 'LD_', 'SNAP', 'PYTHONHOME', 'PYTHONPATH', 'GI_TYPELIB_', 'GSETTINGS_SCHEMA_DIR')):
            os.environ.pop(key, None)
    os.environ.update(GDK_BACKEND='x11', XDG_DATA_DIRS='/usr/local/share:/usr/share', SMASTER_PYTHON=PYTHON)


def run(*args, check=True, timeout=10):
    return subprocess.run(args, check=check, capture_output=True, text=True, timeout=timeout)


def unit(name, args, extra=None):
    name = 'sonicmaster-'+name
    if run('systemctl', '--user', 'is-active', '--quiet', name+'.service', check=False).returncode == 0:
        return
    keys = ('DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','GDK_BACKEND','XDG_DATA_DIRS','SMASTER_PYTHON')
    env = {key:os.environ[key] for key in keys if key in os.environ}
    env.update(extra or {})
    run('systemd-run','--user','--collect','--unit='+name,'--working-directory='+str(ROOT),*[f'--setenv={k}={v}' for k,v in env.items()],*args)


def wait_for(predicate, seconds, message):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.2)
    raise RuntimeError(message)


def main():
    clean_environment()
    needed = ('jack_control','jack_lsp','jack_samplerate','systemd-run','sooperlooper','slgui','Xephyr','openbox','xauth','xprop','xwininfo','xrandr','wmctrl','zita-a2j','zita-j2a')
    missing = [name for name in needed if not shutil.which(name)]
    if missing: raise RuntimeError('Dipendenze mancanti: '+', '.join(missing)+'. Esegui ./install-sonicmaster.')
    from dependencies import sonicmaster_executable, configure_pocket_autoconnect
    editor = sonicmaster_executable(ROOT)
    if editor is None: raise RuntimeError('SonicMaster non trovato. Installa l’editor o imposta SONICMASTER_EXECUTABLE.')
    ports = run('jack_lsp',check=False).stdout.splitlines()
    if any(port.startswith('TSMA_Looper:') for port in ports):
        raise RuntimeError('Chiudi TSMega-kit prima di avviare SonicMaster-kit: condividono Chocolate e la traccia TSMA-Kit.')
    existing = RUNTIME/'sonicmaster-gui.json'
    try:
        status = json.loads(existing.read_text())
        if status.get('ready') and Path(f'/proc/{status["pid"]}').exists():
            run('wmctrl','-xa','SonicMaster-kit',check=False)
    except (OSError,ValueError,KeyError): pass
    if run('jack_control','status',check=False).returncode:
        run('jack_control','ds','dummy','dps','rate',str(CONFIG['sample_rate']),'dps','period',str(CONFIG['buffer_size']),'dps','wait',str(round(1e6*CONFIG['buffer_size']/CONFIG['sample_rate'])),'start',timeout=20)
    rate = int(run('jack_samplerate').stdout.strip().splitlines()[-1])
    if rate != CONFIG['sample_rate']: raise RuntimeError(f'JACK è a {rate} Hz; il kit richiede {CONFIG["sample_rate"]} Hz. Regola QjackCtl.')
    ports = run('jack_lsp').stdout.splitlines()
    if not all(name in ports for name in ('PocketMaster_in:capture_1','PocketMaster_out:playback_1')):
        unit('pocket-bridge',[str(ROOT/'config/Jack/Drivers.d/PocketMaster')],{'JACK_DRIVERS_CONFIG':str(ROOT/'config/portable-drivers.conf')})
        wait_for(lambda:all(p in run('jack_lsp').stdout for p in ('PocketMaster_in:capture_1','PocketMaster_out:playback_1')),12,'Pocket Master USB non disponibile: verifica il collegamento.')
    from midimix_setup import prepare
    prepare(Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'ardour8')
    unit('engine',[PYTHON,str(ROOT/'bin/service.py')])
    def ready():
        try:return json.loads((RUNTIME/'kit.status.json').read_text()).get('ready',False)
        except (OSError,ValueError):return False
    wait_for(ready,15,'SooperLooper non pronto: consulta log/engine.log.')
    unit('routing',['--property=Restart=always','--property=RestartSec=1',PYTHON,str(ROOT/'bin/routing.py')])
    unit('midi',[PYTHON,str(ROOT/'bin/chocolate.py')])
    unit('gui',[PYTHON,str(ROOT/'bin/gui.py')])
    gui = {}
    def gui_ready():
        try:
            gui.update(json.loads((RUNTIME/'sonicmaster-gui.json').read_text()))
            return gui.get('ready') and Path(f'/proc/{gui["pid"]}').exists()
        except (OSError,ValueError,KeyError):return False
    wait_for(gui_ready,15,'Finestra del kit non pronta: consulta log/gui.log.')
    display = {'DISPLAY':gui['display'],'XAUTHORITY':gui['xauthority'],'GDK_BACKEND':'x11'}
    editor_running=False
    for pid in run('pgrep','-x','sonicmaster',check=False).stdout.split():
        try: own_display=('DISPLAY='+gui['display']).encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        except OSError:continue
        if not own_display:raise RuntimeError('SonicMaster è già aperto separatamente. Chiudilo per incorporarlo nel kit.')
        editor_running=True
    if not editor_running:
        configure_pocket_autoconnect()
        unit('editor',[str(editor)],display)
    unit('looper-gui',['slgui','-N','-n','-H','127.0.0.1','-P',str(CONFIG['osc_port']),'-X','0:0'],dict(display,GTK_MODULES=str(ROOT/'vendor/slgui-lock.so')))
    print('SonicMaster-kit pronto: Pocket Master → SooperLooper → TSMA-Kit; Chocolate CC80–83.',flush=True)


if __name__ == '__main__':
    RUNTIME.mkdir(parents=True,exist_ok=True,mode=0o700);(ROOT/'log').mkdir(exist_ok=True);(ROOT/'state').mkdir(exist_ok=True)
    with (RUNTIME/'launch.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(0)
        try:main()
        except Exception as exc:
            print(str(exc),file=sys.stderr,flush=True)
            subprocess.run(['notify-send','-u','critical','SonicMaster-kit',str(exc)],capture_output=True)
            raise SystemExit(1)
