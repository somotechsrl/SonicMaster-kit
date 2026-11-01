"""The public exporter must never copy personal registration/audio files."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from export_profile import export_profile

class ExportProfile(unittest.TestCase):
 def test_exports_parameters_without_personal_paths_or_registration(self):
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'source';target=Path(folder)/'target'
   (source/'ToneLib GFX').mkdir(parents=True);(source/'Shared/presets_4.0').mkdir(parents=True)
   config=source/'ToneLib GFX/_app.cfg'
   config.write_text('<PROPERTIES><VALUE name="recent_audio" val="/home/example/record.wav"/><VALUE name="gfx.impulses.dir" val="/home/example/IR"/><VALUE name="audio.device.state"><DEVICESETUP><MIDIINPUT name="old" identifier="48-0"/></DEVICESETUP></VALUE><VALUE name="musical-setting" val="1"/></PROPERTIES>')
   (source/'Shared/presets_4.0/patch_000.tlgfx').write_bytes(b'parameter-slot')
   (source/'Shared/com.tonelib.gfx4.reginfo').write_text('registration')
   (source/'ToneLib GFX/private-recording.wav').write_bytes(b'audio')
   export_profile(source,target)
   result=(target/'ToneLib GFX/_app.cfg').read_text()
   self.assertNotIn('/home/',result);self.assertNotIn('MIDIINPUT',result)
   self.assertNotIn('recent_audio',result);self.assertIn('musical-setting',result)
   self.assertEqual((target/'Shared/presets_4.0/patch_000.tlgfx').read_bytes(),b'parameter-slot')
   self.assertFalse(list(target.rglob('*.reginfo')));self.assertFalse(list(target.rglob('*.wav')))
   self.assertIn('/home/example',config.read_text())

if __name__=='__main__':unittest.main()
