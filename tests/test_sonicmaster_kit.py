"""Offline regressions for Pocket routing, pedal semantics and bank safety."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bin'))
from chocolate import action
from routing import plan
from pocket_bank import Pocket,P,code_for,MODULES,EFFECTS
from adapt_presets import module


class Routing(unittest.TestCase):
    def graph(self,*names):return {n:{'output':not ('common_in_' in n or 'playback_' in n or 'audio_in ' in n or 'PipeWire:capture' in n),'connections':[]} for n in names}
    def base(self):
        return self.graph(*[f'{client}:{port}_{i}' for i in (1,2) for client,port in [('PocketMaster_in','capture'),('PocketMaster_out','playback'),('SonicMaster_Looper','common_in'),('SonicMaster_Looper','common_out')]])
    def test_pocket_stereo_goes_directly_to_looper(self):
        add,remove=plan(self.base())
        self.assertIn(('PocketMaster_in:capture_1','SonicMaster_Looper:common_in_1'),add)
        self.assertIn(('PocketMaster_in:capture_2','SonicMaster_Looper:common_in_2'),add)
        self.assertEqual(len(add),4);self.assertFalse(remove)
        self.assertFalse(any('JUCE' in s or 'ToneLib' in s for edge in add for s in edge))
    def test_ardour_track_name_is_preserved(self):
        g=self.base();g.update(self.graph('ardour:TSMA-Kit/audio_in 1','ardour:TSMA-Kit/audio_in 2'))
        add,_=plan(g)
        self.assertIn(('SonicMaster_Looper:common_out_1','ardour:TSMA-Kit/audio_in 1'),add)
        self.assertFalse(any(d.startswith('PocketMaster_out:') for _,d in add))
    def test_obs_only_without_any_ardour(self):
        g=self.base();g.update(self.graph('PipeWire:capture_FL','PipeWire:capture_FR'))
        self.assertIn(('SonicMaster_Looper:common_out_1','PipeWire:capture_FL'),plan(g)[0])
        g.update(self.graph('ardour:Other/audio_in 1'))
        self.assertFalse(any(d.startswith('PipeWire:') for _,d in plan(g)[0]))
    def test_unrelated_routes_are_preserved(self):
        g=self.base();g.update(self.graph('PocketMaster_in:capture_1','ardour:Other/audio_in 1'))
        g['PocketMaster_in:capture_1']['connections']=['ardour:Other/audio_in 1']
        self.assertFalse(plan(g)[1])
    def test_backing_is_not_recorded_into_loop(self):
        g=self.base();g.update(self.graph('SonicMaster_Backing:out_1','SonicMaster_Backing:out_2'))
        add,_=plan(g)
        self.assertIn(('SonicMaster_Backing:out_2','PocketMaster_out:playback_2'),add)
        self.assertFalse(any(s.startswith('SonicMaster_Backing:') and 'common_in' in d for s,d in add))


class Chocolate(unittest.TestCase):
    def test_presses_releases_and_non_cc(self):
        for channel in range(16):
            for cc,expected in zip(range(80,84),('record_play','overdub','pause','clear')):
                self.assertEqual(action(bytes([0xb0|channel,cc,127])),expected)
                self.assertIsNone(action(bytes([0xb0|channel,cc,0])))
        for raw in (b'',b'\xf0\x50\x7f',b'\x90\x50\x7f',b'\xb0\x4f\x7f'):self.assertIsNone(action(raw))


class Bank(unittest.TestCase):
    def test_manifest_and_all_fifty_user_slots(self):
        manifest=json.loads((ROOT/'presets/pocket-master/manifest.json').read_text())
        self.assertEqual([e['slot'] for e in manifest],list(range(1,51)))
        adapted=[e for e in manifest if e.get('source')]
        self.assertEqual(len(adapted),17)
        self.assertEqual(next(e['slot'] for e in adapted if e['sourceLabel']=='5A'),17)
        for e in manifest:
            d=json.loads((ROOT/'presets/pocket-master'/e['file']).read_text())
            self.assertLessEqual(len(d['deviceName']),10)
            if e.get('source'):
                bank=int(e['sourceLabel'][:-1]);letter=ord(e['sourceLabel'][-1])-65
                self.assertEqual(e['slot'],(bank-1)*4+letter+1);self.assertNotIn(' ',d['deviceName'])
            else:self.assertFalse(any(m['enabled'] for m in d['modules'].values()))
    def test_models_are_supported_by_pocket_master(self):
        caps=json.loads((ROOT/'config/pocket/device_capabilities.json').read_text())['models']['pocketMaster']['effects']
        for f in (ROOT/'presets/pocket-master').glob('P*.json'):
            d=json.loads(f.read_text())
            for i,key in enumerate(MODULES):
                e=d['modules'][key]['effectId']
                if str(i) in caps:self.assertIn(e,caps[str(i)])
                if i:code_for(i,e)
    def test_firmware_parameter_resolution_is_respected(self):
        self.assertEqual(module(101,True,{'Sustain':31.2})['parameters']['Sustain'],31)
        self.assertEqual(module(106,True,{'Rate':1.26})['parameters']['Rate'],1.3)
    def test_factory_writes_are_rejected(self):
        with self.assertRaises(ValueError):P.save_preset(50,'Forbidden')
    def test_generated_wire_matches_captured_amp_code(self):
        self.assertEqual(code_for(3,321),0x07000073)
        self.assertEqual(P.parse_frame(P.query(P.Q_CURRENT_INDEX)).payload,b'\x12\x43')


if __name__=='__main__':unittest.main()
