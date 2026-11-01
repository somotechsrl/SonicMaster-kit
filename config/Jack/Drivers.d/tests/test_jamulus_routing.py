import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'jamulus-routing.py'
spec = importlib.util.spec_from_file_location('jamulus_routing', path)
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class JamulusRoutingTests(unittest.TestCase):
    def test_stereo_track_receives_and_bus_sends(self):
        self.assertEqual(routing.route_pairs('Jamulus', 'ardour', 'FR Jamulus', 'TO Jamulus'), [
            ('Jamulus:output left', 'ardour:FR Jamulus/audio_in 1'),
            ('Jamulus:output right', 'ardour:FR Jamulus/audio_in 2'),
            ('ardour:TO Jamulus/audio_out 1', 'Jamulus:input left'),
            ('ardour:TO Jamulus/audio_out 2', 'Jamulus:input right')])

    def test_only_native_hardware_defaults_are_removed(self):
        ports = {'Jamulus:input left': {'connections': ['system:capture_1', 'ardour:TO Jamulus/audio_out 1']},
                 'Jamulus:output left': {'connections': ['system:playback_1', 'ardour:FR Jamulus/audio_in 1', 'Other:input']},
                 'Other:output': {'connections': ['system:playback_2']}}
        self.assertEqual(routing.default_connections(ports, 'Jamulus'), [
            ('system:capture_1', 'Jamulus:input left'), ('Jamulus:output left', 'system:playback_1')])

    def test_absent_client_leaves_other_routes_untouched(self):
        self.assertEqual(routing.default_connections({'Other:output': {'connections': ['system:playback_1']}}, 'Jamulus'), [])


    def test_jacktrip_stereo_ports_keep_correct_direction(self):
        self.assertEqual(routing.route_pairs('JackTrip', 'ardour', 'FR JackTrip', 'TO JackTrip', 'jacktrip'), [
            ('JackTrip:receive_1', 'ardour:FR JackTrip/audio_in 1'),
            ('JackTrip:receive_2', 'ardour:FR JackTrip/audio_in 2'),
            ('ardour:TO JackTrip/audio_out 1', 'JackTrip:send_1'),
            ('ardour:TO JackTrip/audio_out 2', 'JackTrip:send_2')])

    def test_jacktrip_removes_only_its_hardware_defaults(self):
        ports = {'JackTrip:send_1': {'connections': ['system:capture_1', 'ardour:TO JackTrip/audio_out 1']},
                 'JackTrip:receive_2': {'connections': ['system:playback_2', 'Other:input']},
                 'Jamulus:input left': {'connections': ['system:capture_1']}}
        self.assertEqual(routing.default_connections(ports, 'JackTrip', 'jacktrip'), [
            ('system:capture_1', 'JackTrip:send_1'), ('JackTrip:receive_2', 'system:playback_2')])

    def test_carla_stereo_uses_native_audio_ports(self):
        self.assertEqual(routing.route_pairs('Carla', 'ardour', 'FR Carla', 'TO Carla', 'carla'), [
            ('Carla:audio-out1', 'ardour:FR Carla/audio_in 1'),
            ('Carla:audio-out2', 'ardour:FR Carla/audio_in 2'),
            ('ardour:TO Carla/audio_out 1', 'Carla:audio-in1'),
            ('ardour:TO Carla/audio_out 2', 'Carla:audio-in2')])

    def test_carla_removes_hardware_defaults_and_preserves_midi_and_other_routes(self):
        ports = {'Carla:audio-in1': {'connections': ['system:capture_1', 'ardour:TO Carla/audio_out 1']},
                 'Carla:audio-out2': {'connections': ['system:playback_2', 'Other:input']},
                 'Carla:events-in': {'connections': ['a2j:keyboard']},
                 'Jamulus:output left': {'connections': ['system:playback_1']}}
        self.assertEqual(routing.default_connections(ports, 'Carla', 'carla'), [
            ('system:capture_1', 'Carla:audio-in1'), ('Carla:audio-out2', 'system:playback_2')])
        self.assertEqual(routing.default_connections(ports, 'Absent', 'carla'), [])

    def test_carla_custom_names_preserve_channel_order(self):
        self.assertEqual(routing.route_pairs('Carla FX', 'daw', 'Return', 'Send', 'carla')[2:], [
            ('daw:Send/audio_out 1', 'Carla FX:audio-in1'),
            ('daw:Send/audio_out 2', 'Carla FX:audio-in2')])


if __name__ == '__main__':
    unittest.main()
