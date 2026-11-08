"""Offline regressions for pedal semantics, OSC messages and partial routing."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
from controls import transition
from osc import encode,decode

class Pedals(unittest.TestCase):
 def test_record_play_and_separate_overdub(self):
  self.assertEqual(transition('record_play',0,0),(['record'],2,False))
  self.assertEqual(transition('record_play',2,1),(['record'],4,True))
  self.assertEqual(transition('overdub',4,1),(['pause_off','mute_off','overdub'],5,False))
  self.assertEqual(transition('overdub',5,1),(['overdub'],4,True))
  self.assertNotIn('overdub',transition('record_play',4,1)[0])
 def test_pause_preserves_loop_and_resumes(self):
  self.assertEqual(transition('pause',4,1),(['pause_on'],14,True))
  self.assertEqual(transition('pause',14,1),(['pause_off'],4,False))
  self.assertEqual(transition('pause',5,1),(['overdub','pause_on'],14,True))
 def test_clear_finishes_active_operation(self):
  self.assertEqual(transition('clear',5,1),(['overdub','pause_off','undo_all'],0,True))
  self.assertEqual(transition('clear',2,1),(['record','pause_off','undo_all'],0,True))
 def test_empty_overdub_and_pause_do_nothing(self):
  for action in ('overdub','pause'):
   self.assertEqual(transition(action,0,0),([],0,False))
 def test_osc_roundtrip_and_alignment(self):
  for args in [('/ping','osc.udp://127.0.0.1:11111/','/pong'),('/update',0,'state',14.),('/save_session','a b.slsess','url','/error',1)]:
   data=encode(*args);self.assertEqual(len(data)%4,0);self.assertEqual(decode(data),(args[0],list(args[1:])))

if __name__=='__main__':unittest.main()
