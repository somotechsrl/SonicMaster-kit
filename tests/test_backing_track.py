import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from backing_track import find_play
ROOT=Path(__file__).resolve().parents[1]


class PlayerRecognition(unittest.TestCase):
 def setUp(self):
  self.template=json.loads((ROOT/'config/tonelib-play-icon.json').read_text())
  self.width=848;self.height=600;self.stride=self.width*3
  self.pixels=bytearray(self.stride*self.height)
 def draw(self,x,y,color=(160,160,160)):
  for py,row in enumerate(self.template):
   for px,v in enumerate(row):
    if v=='1':
     offset=(y+py)*self.stride+(x+px)*3
     self.pixels[offset:offset+3]=bytes(color)
 def locate(self):return find_play(self.pixels,self.width,self.height,self.stride,3,self.template)
 def test_ready_play_is_recognized_but_disabled_play_is_not(self):
  self.assertIsNone(self.locate())
  self.draw(48,420,(70,70,70));self.assertIsNone(self.locate())
  self.draw(48,420);self.assertEqual(self.locate(),(59,431))
 def test_colored_waveform_and_ambiguous_controls_are_rejected(self):
  self.draw(48,420,(10,180,170));self.assertIsNone(self.locate())
  self.draw(48,420);self.draw(48,330);self.assertIsNone(self.locate())


if __name__=='__main__':unittest.main()
