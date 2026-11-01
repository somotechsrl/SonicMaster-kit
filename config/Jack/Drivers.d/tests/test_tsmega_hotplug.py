"""USB reconnect regressions without opening audio or MIDI devices."""
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

module = runpy.run_path(str(Path(__file__).parents[1] / 'Monitor'))
Supervisor = module['Supervisor']

class ToneShifterHotplugTests(unittest.TestCase):
    def supervisor(self):
        s = Supervisor.__new__(Supervisor)
        s.usb_path = Mock()
        s.usb_missing = False
        s.usb_recovering = False
        s.usb_retry_at = 0
        s.usb_attempts = 0
        s.usb_ready_since = None
        s.proc = Mock()
        s.proc.poll.return_value = None
        s.pending = set()
        s.stop_bridge = Mock()
        s.restart = Mock(return_value=True)
        s.log = Mock()
        s.policy = SimpleNamespace(auto=True)
        return s

    def test_absence_stops_once_and_return_retries_even_with_old_pending_routes(self):
        s = self.supervisor()
        s.pending = {('TSMEGA_in:capture_1', 'JUCEJack:in_1')}
        s.usb_path.exists.return_value = False
        self.assertTrue(s.handle_usb())
        self.assertTrue(s.handle_usb())
        s.stop_bridge.assert_called_once()
        s.restart.assert_not_called()
        s.usb_path.exists.return_value = True
        self.assertTrue(s.handle_usb())
        s.restart.assert_called_once_with('Tone Shifter USB ricollegato', manual=True)
        self.assertFalse(s.usb_missing)
        self.assertFalse(s.handle_usb())

    def test_recovery_lock_contention_keeps_return_pending(self):
        s = self.supervisor()
        s.usb_missing = True
        s.usb_path.exists.return_value = True
        s.restart.return_value = False
        self.assertTrue(s.handle_usb())
        self.assertTrue(s.usb_missing)
        s.restart.return_value = True
        self.assertTrue(s.handle_usb())
        self.assertFalse(s.usb_missing)

    def test_pcm_not_ready_retries_with_pending_connections_after_return(self):
        s = self.supervisor()
        s.usb_missing = True
        s.usb_path.exists.return_value = True
        s.pending = {('TSMEGA_in:capture_1', 'JUCEJack:in_1')}
        clock = Mock(return_value=100)
        with patch.dict(Supervisor.handle_usb.__globals__, time=SimpleNamespace(monotonic=clock)):
            self.assertTrue(s.handle_usb())
            self.assertTrue(s.usb_recovering)
            s.proc.poll.return_value = 1  # ALSA open failed after enumeration.
            clock.return_value = 101
            self.assertTrue(s.handle_usb())
            self.assertEqual(s.restart.call_count, 1)
            clock.return_value = 103
            self.assertTrue(s.handle_usb())
            self.assertEqual(s.restart.call_count, 2)
            s.proc.poll.return_value = None
            s.pending.clear()
            clock.return_value = 104
            self.assertFalse(s.handle_usb())
            clock.return_value = 110
            self.assertFalse(s.handle_usb())
            self.assertFalse(s.usb_recovering)

    def test_other_devices_and_disabled_automatic_recovery_are_untouched(self):
        s = self.supervisor()
        s.usb_path = None
        self.assertFalse(s.handle_usb())
        s.stop_bridge.assert_not_called()
        s.usb_path = Mock()
        s.usb_path.exists.return_value = True
        s.usb_missing = True
        s.policy.auto = False
        self.assertTrue(s.handle_usb())
        s.restart.assert_not_called()

    def test_return_recovers_dead_bridge_with_saved_connections(self):
        s = self.supervisor()
        s.usb_missing = False
        s.usb_recovering = True
        s.proc = Mock()
        s.proc.poll.return_value = 1
        s.policy = SimpleNamespace(window=600, auto=True, cooldown=60, limit=3)
        from collections import deque
        s.restarts = deque()
        s.last_restart = 0
        s.saved = [('TSMEGA_in:capture_1', 'JUCEJack:in_1')]
        s.pending = set(s.saved)
        s.have_snapshot = True
        s.stopping = False
        s.connection_path = Path('/unused')
        s.client = 'TSMEGA_in'
        s.start = Mock()
        glob = Supervisor._restart.__globals__
        with patch.dict(glob, graph=Mock(return_value={}), atomic=Mock(), restore=Mock(return_value=set())):
            self.assertTrue(s._restart('USB return', manual=True))
        s.start.assert_called_once()
        self.assertFalse(s.pending)

if __name__ == '__main__':
    unittest.main()
