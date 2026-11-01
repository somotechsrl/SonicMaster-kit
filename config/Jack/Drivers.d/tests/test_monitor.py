"""Offline detector regressions; never connect to JACK or start audio."""
import json
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
import unittest

monitor = runpy.run_path(str(Path(__file__).parents[1] / 'Monitor'))
Detector = monitor['Detector']
telemetry = monitor['telemetry']


class MonitorTelemetryTests(unittest.TestCase):
    def detector(self):
        policy = SimpleNamespace(warmup=30, sustain=10, error_limit=64,
                                 ratio_span=1000, ratio_limit=10000)
        return Detector(policy, 0)

    def test_valid_and_malformed_telemetry(self):
        self.assertEqual(telemetry('  -0.203 1.000398 -12 '), (-.203, 1.000398))
        self.assertEqual(telemetry('1e-3 1. 0'), (.001, 1.))
        for text in ('Starting synchronisation', '... 1 0', '1 1', '1 1 nope'):
            self.assertIsNone(telemetry(text))

    def test_nonfinite_fault_is_sustained_and_json_safe(self):
        for value in ('nan', '-nan', 'NaN', 'inf', '-Inf', 'Infinity', '1e309'):
            with self.subTest(value=value):
                d = self.detector()
                self.assertIsNone(d.feed('0 1 0', 31))
                for tick in range(40, 50):
                    self.assertIsNone(d.feed('10 ' + value + ' 0', tick))
                self.assertIn('NaN/Inf', d.feed('10 ' + value + ' 0', 50))
                self.assertIsNone(d.last_ratio)
                json.dumps({'ratio':d.last_ratio}, allow_nan=False)

    def test_invalid_error_also_detected(self):
        d = self.detector()
        for tick in range(40, 51):
            reason = d.feed('-nan 1 0', tick)
        self.assertIn('NaN/Inf', reason)
        self.assertIsNone(d.last_error)

    def test_warmup_and_telemetry_gaps_do_not_trigger_recovery(self):
        d = self.detector()
        for tick in range(30):
            self.assertIsNone(d.feed('nan nan 0', tick))
        self.assertIsNone(d.feed('nan nan 0', 40))
        self.assertIsNone(d.feed('nan nan 0', 60))
        self.assertEqual(d.invalid_since, 60)

    def test_finite_recovery_clears_fault(self):
        d = self.detector()
        for tick in range(40, 46):
            self.assertIsNone(d.feed('0 nan 0', tick))
        self.assertIsNone(d.feed('0 1 0', 46))
        self.assertIsNone(d.invalid_since)
        self.assertIsNone(d.feed('0 nan 0', 50))
        self.assertEqual(d.invalid_since, 50)

    def test_status_reads_live_log_without_touching_a_worker(self):
        observed = monitor['observed_status']
        original = observed.__globals__['STATE']
        with tempfile.TemporaryDirectory() as folder:
            observed.__globals__['STATE'] = Path(folder)
            try:
                path = Path(folder)/'test.log'
                path.write_text('2026-10-11 10:00:00,000 0 1 0\n2026-10-11 10:00:01,000 -123 -nan -1\n')
                state = observed('test', {'ratio':1, 'error_samples':0})
                self.assertTrue(state['telemetry_invalid'])
                self.assertIsNone(state['ratio'])
                self.assertEqual(state['error_samples'], -123)
                json.dumps(state, allow_nan=False)
                path.write_text('2026-10-11 10:00:02,000 0 1 0\n')
                self.assertFalse(observed('test', {})['telemetry_invalid'])
                self.assertEqual(observed('missing', {'ratio':1}), {'ratio':1})
            finally:
                observed.__globals__['STATE'] = original


if __name__ == '__main__':
    unittest.main()
