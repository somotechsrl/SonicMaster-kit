import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))
import midimix
from osc import encode, decode


class BankTests(unittest.TestCase):
    def test_bank_presses_releases_clamps_and_fader_identity(self):
        bank = midimix.Bank()
        self.assertTrue(bank.consume(bytes((0x90,26,127))))
        self.assertEqual(bank.command, bytes((0x9F,1,127)))
        for raw in ((0x90,26,0),(0x80,26,64),(0x91,26,127)):
            bank.consume(bytes(raw))
        self.assertEqual(bank.index, 1)
        for _ in range(200):bank.consume(bytes((0x90,25,127)))
        self.assertEqual(bank.index, 0)
        for _ in range(200):bank.consume(bytes((0x90,26,127)))
        self.assertEqual(bank.index, 127)
        self.assertFalse(bank.consume(bytes((0xB0,49,90))))
        self.assertEqual(bank.last_fader, 4)
        self.assertFalse(bank.consume(bytes((0xB0,62,90))))

    def test_map_preserves_original_bindings_and_adds_absolute_bank_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)
            midimix.install_map(config)
            tree = midimix.ET.parse(config/'midi_maps/TSMA_MIDIMix_Live.map')
            self.assertEqual(tree.getroot().get('name'), midimix.MAP_NAME)
            self.assertEqual(len(tree.findall(".//Binding[@channel='16']")),128)
            self.assertEqual(tree.find(".//Binding[@ctl='19']").get('uri'),'/route/gain B1')
            self.assertEqual(tree.find(".//Binding[@channel='16'][@note='7']").get('arg'),'7')


class UnityDetentTests(unittest.TestCase):
    def test_native_curve_silence_top_and_configurable_maximum(self):
        detent=midimix.UnityDetent()
        self.assertEqual(detent.db_for_cc(0),-float('inf'))
        self.assertAlmostEqual(detent.db_for_cc(127),6.020599913,places=6)
        self.assertAlmostEqual(detent.db_for_cc(127,1),0,places=6)
        self.assertLess(abs(detent.db_for_cc(99)),.45)

    def test_snap_release_hysteresis_and_bank_relative_target(self):
        detent=midimix.UnityDetent()
        message=lambda value:bytes((0xB0,19,value))
        self.assertIsNone(detent.target(message(103),0))
        self.assertEqual(detent.target(message(99),0),1)
        self.assertEqual(detent.target(message(103),0),1)
        self.assertIsNone(detent.target(message(104),0))
        self.assertIsNone(detent.target(message(103),0))
        self.assertEqual(detent.target(bytes((0xB0,49,100)),1),13)

    def test_other_controls_channels_and_master_are_not_snapped(self):
        detent=midimix.UnityDetent()
        for raw in ((0xB0,62,99),(0xB1,19,99),(0x90,19,99),(0xB0,16,99)):
            self.assertIsNone(detent.target(bytes(raw),0))


class LiveNamesTests(unittest.TestCase):
    def test_complete_snapshot_rename_reorder_removal_timeout_reconnect(self):
        server = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        server.bind(('127.0.0.1',0)); self.addCleanup(server.close)
        names = midimix.Names(server.getsockname()[1]); self.addCleanup(names.close)
        target = names.udp.getsockname()
        now = time.monotonic()
        self.assertFalse(names.poll(now))
        names.poll(now+.21)
        def route(number,name):server.sendto(encode('/reply','AT',name,2,2,0,0,number,0),target)
        def end():server.sendto(encode('/reply','end_route_list',48000,2000,0),target)
        route(1,'Chitarra');route(2,'Voce')
        names.poll(now+.25);self.assertEqual(names.rows,{})
        end();self.assertTrue(names.poll(now+.3));self.assertEqual(names.rows,{1:'Chitarra',2:'Voce'})
        self.assertFalse(names.mutes[1])
        server.sendto(encode('/strip/mute',1,1.0),target)
        server.sendto(encode('/strip/gain',1,-3.5),target)
        server.sendto(encode('/strip/meter',1,-12.0),target)
        server.sendto(encode('/strip/meter',2,float('nan')),target)
        server.sendto(encode('/strip/name',1,'Guitar'),target)
        names.poll(now+.4);self.assertEqual(names.rows[1],'Guitar')
        self.assertEqual(names.gains[1],-3.5);self.assertEqual(names.meters[1],-12.0)
        self.assertTrue(names.mutes[1])
        self.assertNotIn(2,names.meters)
        names.poll(now+1.3);route(1,'Voce');end();names.poll(now+1.4)
        self.assertEqual(names.rows,{1:'Voce'})
        self.assertFalse(names.poll(now+5))
        names.poll(now+5.21)
        route(1,'Nuova sessione');end();self.assertTrue(names.poll(now+5.3))
        self.assertEqual(names.rows,{1:'Nuova sessione'})

    def test_startup_burst_is_drained_before_list_without_restarting_observers(self):
        server=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        server.bind(('127.0.0.1',0));server.settimeout(.05);self.addCleanup(server.close)
        names=midimix.Names(server.getsockname()[1]);self.addCleanup(names.close)
        now=time.monotonic();names.poll(now)
        data,_=server.recvfrom(65535);self.assertEqual(decode(data)[0],'/set_surface')
        with self.assertRaises(socket.timeout):server.recvfrom(65535)
        names.poll(now+.21)
        data,_=server.recvfrom(65535);self.assertEqual(decode(data)[0],'/strip/list')
        names.poll(now+1.22)
        data,_=server.recvfrom(65535);self.assertEqual(decode(data)[0],'/strip/list')

    def test_int64_ardour_end_message(self):
        packet=encode('/reply','end_route_list')
        from osc import string
        packet=string('/reply')+string(',shh')+string('end_route_list')+struct.pack('>qq',48000,99999999999)
        self.assertEqual(decode(packet),('/reply',['end_route_list',48000,99999999999]))


class RoutingTests(unittest.TestCase):
    def test_handoff_and_restore_preserve_unrelated_connections(self):
        graph={'a2j:MIDI Mix (capture): MIDI Mix MIDI 1':{'ardour:MIDI Control In','other:in'},
               'a2j:'+midimix.CLIENT+' (capture): Pedal diagnostics':set(),
               'ardour:MIDI Control In':set()}
        calls=[]
        def command(*args):
            calls.append(args)
            return type('Result',(),{'returncode':0})()
        with patch.object(midimix,'connections',return_value=graph),patch.object(midimix,'command',side_effect=command):
            routing=midimix.Patch();self.assertTrue(routing.activate());routing.restore()
        self.assertEqual([x[0] for x in calls],['jack_connect','jack_disconnect','jack_connect','jack_disconnect'])
        self.assertFalse(any('other:in' in call for call in calls))

    def test_unconnected_device_is_not_taken_over(self):
        graph={'a2j:MIDI Mix (capture): MIDI Mix MIDI 1':set(),
               'a2j:'+midimix.CLIENT+' (capture): Pedal diagnostics':set(),
               'ardour:MIDI Control In':set()}
        with patch.object(midimix,'connections',return_value=graph),patch.object(midimix,'command') as command:
            self.assertFalse(midimix.Patch().activate());command.assert_not_called()



class AutomaticSetupTests(unittest.TestCase):
    def test_closed_ardour_is_configured_once_preserving_preferences(self):
        import midimix_setup
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)
            original=b'<Ardour><Other keep="yes"/><ControlProtocols><Protocol name="Generic MIDI" binding="old" active="1"><Controls/></Protocol></ControlProtocols></Ardour>'
            (config/'config').write_bytes(original)
            with patch.object(midimix_setup,'ardour_running',return_value=False):
                self.assertTrue(midimix_setup.prepare(config))
                saved=(config/'config').read_bytes()
                self.assertTrue(midimix_setup.prepare(config))
                self.assertEqual((config/'config').read_bytes(),saved)
            root=midimix.ET.fromstring(saved)
            self.assertEqual(root.find('Other').get('keep'),'yes')
            self.assertIsNotNone(root.find('.//Controls'))
            self.assertEqual((config/'config.before-tsma-midimix').read_bytes(),original)
            self.assertTrue(midimix.active_map(config))
            self.assertEqual(root.find(".//Protocol[@name='Open Sound Control (OSC)']").get('active'),'1')

    def test_running_ardour_preferences_are_never_overwritten(self):
        import midimix_setup
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder);(config/'config').write_text('<Ardour/>')
            with patch.object(midimix_setup,'ardour_running',return_value=True):
                self.assertFalse(midimix_setup.prepare(config))
            self.assertEqual((config/'config').read_text(),'<Ardour/>')

if __name__=='__main__':unittest.main()
