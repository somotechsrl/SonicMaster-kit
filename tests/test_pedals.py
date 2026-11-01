"""Protocol safety and kit behavior, with no hardware settings or personal dump."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from alsa_midi import devices
from pedals import (Chocolate, DEFAULT, describe, kit_values, load_profile,
                    is_channel_message, restore_values, save_profile, summary, unpack_reply, write_message)


def frame_for(blob):
    # The device's stream has a final partial byte, not an extra zero group.
    packed = bytearray(); acc = bits = 0
    for value in blob:
        acc |= value << bits; bits += 8
        while bits >= 7:
            packed.append(acc & 127); acc >>= 7; bits -= 7
    if bits and acc: packed.append(acc)
    header = bytes.fromhex('F0 00 32 0D 49 3F 00 00 02 00 00 00 00 10 7E 00 00')
    assert len(packed) == 1153
    return header + packed + bytes([0, 0, 247])


class FakeChocolate(Chocolate):
    def __init__(self, mismatch=False):
        self.blob = bytearray(1009); self.writes = []; self.mismatch = mismatch
        self.blob[200] = 87  # an unrelated setting that must survive
    def read(self): return bytes(self.blob), frame_for(self.blob)
    def exchange(self, message, prefix, timeout=3):
        address, value = message[9], message[17]
        self.writes.append((address, value)); self.blob[address] = value
        if self.mismatch: self.blob[200] ^= 1
        return bytes.fromhex('F0 00 32 01 08 00 00 00 00 7F 01 F7')


class PedalProtocol(unittest.TestCase):
    def test_known_mode_checksum_and_invalid_write_addresses(self):
        self.assertEqual(write_message(0, 7).hex(' '), 'f0 00 32 09 49 00 00 00 02 00 00 00 00 10 00 00 00 07 66 03 f7')
        for address, value in ((10, 0), (-1, 0), (1, 16), (3, 2), (2, 128)):
            with self.assertRaises(ValueError): write_message(address, value)

    def test_program_backups_readback_and_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            device = FakeChocolate()
            result, before = device.program(folder)
            self.assertEqual(result['mode'], 7); self.assertEqual(result['channel'], 1)
            self.assertEqual([s['cc'] for s in result['switches'].values()], [80, 81, 82, 83])
            self.assertEqual(device.blob[200], 87)
            self.assertEqual(device.writes[-1], (0, 7))
            self.assertEqual(restore_values(before), {i: 0 for i in range(10)})
            device.writes.clear(); device.program(folder)
            self.assertEqual(device.writes, [])  # idempotent programming

    def test_unexpected_readback_stops_before_further_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            device = FakeChocolate(mismatch=True)
            with self.assertRaisesRegex(RuntimeError, 'Readback mismatch'): device.program(folder)
            self.assertEqual(len(device.writes), 1)
            self.assertEqual(len(list(Path(folder).glob('*.json'))), 1)

    def test_readback_rejects_wrong_model_or_region(self):
        frame = frame_for(bytearray(1009)); self.assertEqual(len(unpack_reply(frame)), 1009)
        for bad in (frame[:-1], bytes([0]) + frame[1:], frame[:9] + b'\x01' + frame[10:]):
            with self.assertRaises(ValueError): unpack_reply(bad)

    def test_custom_software_profile_and_alternating_press_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pedals.conf'
            save_profile(path, {'previous_cc': 10, 'next_cc': 11, 'effect_offset': 4})
            profile = load_profile(path)
            for value in (0, 64, 127):
                self.assertEqual(describe('TSMEGA', bytes([176, 10, value]), profile)[1], ('tsmega', 'previous'))
            self.assertEqual(describe('TSMEGA', bytes([192, 4]), profile)[1], ('tsmega', 0))
            with self.assertRaises(ValueError): save_profile(path, {'previous_cc': 1, 'next_cc': 1, 'effect_offset': 0})
            self.assertEqual(load_profile(path), profile)

    def test_release_events_and_unrelated_sources_are_not_test_steps(self):
        self.assertIsNone(describe('SINCO', bytes([176, 83, 0]))[1])
        self.assertIsNone(describe('other', bytes([176, 83, 127]))[1])
        self.assertEqual(describe('SINCO', bytes([176, 83, 127]))[1], ('chocolate', 3))

    def test_detection_uses_names_not_fixed_client_numbers(self):
        text = 'Client 203 : "SINCO" [Kernel Legacy]\n  Port 2 : "SINCO MIDI 1" (RWeX) [In/Out]\nClient 204 : "TSMEGA ToneLib" [User Legacy]\n  Port 0 : "Controller input" (RWe-) [In/Out]\n'
        self.assertEqual(devices(text), [{'client': 203, 'port': 2, 'name': 'SINCO', 'port_name': 'SINCO MIDI 1'}])

    def test_fragmented_sysex_is_not_pedal_traffic(self):
        frame=frame_for(bytearray(1009))
        for fragment in (frame[:90],frame[90:900],frame[900:],b'\xf7',b''):
            self.assertFalse(is_channel_message(fragment))
        self.assertTrue(is_channel_message(b'\xb0\x50\x7f'))
        class Transport:
            events=[]
            def connect(self,*_):pass
            def send(self,*_):
                self.events=[((203,0),raw) for raw in (frame[:90],b'\xb0\x50\x7f',frame[90:900],frame[900:])]
            def pending(self):
                result,self.events=self.events,[]
                return result
        device=Chocolate(Transport(),{'name':'SINCO','client':203,'port':0})
        self.assertEqual(device.exchange(b'\xf0\xf7',frame[:5]),frame)


if __name__ == '__main__': unittest.main()
