import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from effect_bank import EffectBankMonitor
from pedals import save_profile,DEFAULT


class BankMonitor(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.path=Path(self.folder.name)/'pedals.conf';self.now=0
  self.device={'name':'TSMEGA','client':48,'port':0};self.devices=[self.device]
  self.events=[];self.transports=[]
  def transport(name):
   owner=self
   class Transport:
    closed=False
    def connect(self,source):self.source=source
    def pending(self):events,owner.events=owner.events,[];return events
    def close(self):self.closed=True
   seq=Transport();self.transports.append(seq);return seq
  self.monitor=EffectBankMonitor(self.path,lambda:self.devices,transport,lambda:self.now)
  self.addCleanup(self.monitor.close)
 def event(self,*raw,source=(48,0)):
  self.events.append((source,bytes(raw)));return self.monitor.poll()
 def test_unknown_until_a_valid_effect_press_on_any_channel(self):
  self.assertIsNone(self.monitor.poll());self.assertTrue(self.monitor.connected)
  self.assertIsNone(self.event(0xB1,22,64))
  self.assertEqual(self.event(0xC1,0),0)
  self.assertEqual(self.event(0xCF,4),1)
  self.assertEqual(self.event(0xC0,3),0)
 def test_all_banks_and_absolute_effects_never_wrap_at_eight(self):
  self.monitor.poll()
  for pc in range(128):
   self.assertEqual(self.event(0xC1,pc),pc//4)
   self.assertEqual(self.monitor.effect,pc)
 def test_effect_repress_and_preset_navigation_invalidate_names(self):
  self.monitor.poll();self.event(0xC1,0)
  generation=self.monitor.generation
  self.event(0xC1,0);self.assertGreater(self.monitor.generation,generation)
  for cc in (22,25):
   generation=self.monitor.generation
   self.event(0xB1,cc,127)
   self.assertGreater(self.monitor.generation,generation)
   self.assertEqual(self.monitor.effect,0)
 def test_other_pedals_and_configuration_fragments_do_not_change_bank(self):
  self.monitor.poll();self.assertEqual(self.event(0xC1,7),1)
  for message in ((0xC1,0),(0xF0,0x7E,0xF7),(0x14,0x01),(0xC1,255)):
   self.event(*message,source=(44,0))
  self.assertEqual(self.monitor.bank,1)
  self.event(0xF0,0xC1,0);self.assertEqual(self.monitor.bank,1)
 def test_disconnect_and_reconnect_clear_previous_bank(self):
  self.monitor.poll();self.event(0xC0,4)
  self.devices=[];self.now=3;self.assertIsNone(self.monitor.poll())
  self.assertFalse(self.monitor.connected);self.assertTrue(self.transports[0].closed)
  self.devices=[dict(self.device,client=52)];self.now=6
  self.assertIsNone(self.monitor.poll());self.assertTrue(self.monitor.connected)
  self.assertEqual(self.event(0xC2,0,source=(52,0)),0)
 def test_profile_offset_reload_clears_stale_bank(self):
  self.monitor.poll();self.event(0xC1,4)
  save_profile(self.path,dict(DEFAULT,effect_offset=4));self.now=3
  self.assertIsNone(self.monitor.poll());self.assertEqual(self.event(0xC1,4),0)
 def test_transport_error_can_recover(self):
  self.monitor.poll()
  def fail():raise OSError('Disconnected')
  self.transports[0].pending=fail
  self.assertIsNone(self.monitor.poll());self.assertFalse(self.monitor.connected)
  self.assertIsNone(self.monitor.poll());self.assertTrue(self.monitor.connected)


if __name__=='__main__':unittest.main()
