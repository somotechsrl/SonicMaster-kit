"""Locate the installed SonicMaster editor without a personal path in Git."""
import os
from pathlib import Path
import shutil


def sonicmaster_executable(root, home=None):
    home = Path.home() if home is None else Path(home)
    candidates = [os.environ.get('SONICMASTER_EXECUTABLE'),str(Path(root)/'vendor/sonicmaster/sonicmaster'),shutil.which('sonicmaster'),str(home/'.local/opt/sonicmaster/current/sonicmaster')]
    return next((Path(path) for path in candidates if path and Path(path).is_file() and os.access(path, os.X_OK)), None)


def configure_pocket_autoconnect(home=None):
    import json, shutil, time
    home = Path.home() if home is None else Path(home)
    prefs = home/'.local/share/dev.skyggedans.sonicmaster/shared_preferences.json'
    try: data = json.loads(prefs.read_text())
    except FileNotFoundError: data = {}
    changed = data.get('flutter.auto_connect') is not True or data.get('flutter.transport') != 'usb'
    if not changed:return
    if prefs.exists():
        backup = home/'.local/share/sonicmaster-kit/backups'
        backup.mkdir(parents=True,exist_ok=True)
        shutil.copy2(prefs,backup/f'editor-prefs-{time.time_ns()}.json')
    data.update({'flutter.auto_connect':True,'flutter.transport':'usb'})
    prefs.parent.mkdir(parents=True,exist_ok=True)
    temp = prefs.with_suffix('.tmp');temp.write_text(json.dumps(data));temp.replace(prefs)
