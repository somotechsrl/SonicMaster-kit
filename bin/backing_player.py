"""Independent JACK backing-track player; never records the base into loops."""
import json
import math
import os
from pathlib import Path
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst


class BackingPlayer:
    def __init__(self):
        Gst.init(None)
        self.settings = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'sonicmaster-kit/backing.json'
        try: saved = json.loads(self.settings.read_text())
        except (OSError, ValueError): saved = {}
        self.db = max(-40, min(0, float(saved.get('db', -18))))
        self.folder = saved.get('folder', '')
        self.player = Gst.ElementFactory.make('playbin', 'backing')
        sink = Gst.ElementFactory.make('jackaudiosink', 'jack')
        if self.player is None or sink is None:
            raise RuntimeError('Installa GStreamer e il plugin JACK.')
        sink.set_property('client-name', 'SonicMaster_Backing')
        sink.set_property('connect', 0)
        self.player.set_property('audio-sink', sink)
        self.player.set_property('flags', 2)  # audio only
        self.player.set_property('volume', math.pow(10, self.db/20))
        bus = self.player.get_bus(); bus.add_signal_watch(); bus.connect('message', self.message)

    def message(self, bus, message):
        if message.type in (Gst.MessageType.ERROR, Gst.MessageType.EOS):
            if message.type == Gst.MessageType.ERROR:
                error, _ = message.parse_error(); print('Base:', error, flush=True)
            self.stop()

    def save(self):
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps({'db':self.db, 'folder':self.folder})+'\n')

    def set_db(self, db):
        self.db = max(-40, min(0, db)); self.player.set_property('volume', math.pow(10, self.db/20)); self.save()

    def play(self, file):
        self.stop(); file = Path(file).resolve()
        if not file.is_file(): raise ValueError('File audio non disponibile')
        self.folder = str(file.parent); self.save()
        self.player.set_property('uri', file.as_uri())
        if self.player.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('Impossibile riprodurre la base audio')

    def stop(self):
        self.player.set_state(Gst.State.NULL)
