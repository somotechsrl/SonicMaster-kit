import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from window_layout import minimum_size,sizes


class Layout(unittest.TestCase):
 def test_bundled_wxgtk_minimum_is_not_clipped(self):
  hints='WM_NORMAL_HINTS(WM_SIZE_HINTS):\n\t\tprogram specified minimum size: 848 by 187'
  width,height=minimum_size(hints)
  looper,tone=sizes(1506,920,height)
  self.assertGreaterEqual(looper[3],height)
  self.assertEqual(looper[1]+looper[3],920)
  self.assertEqual(tone[1]+tone[3],looper[1])
  self.assertEqual(width,848)

 def test_other_theme_minimum_still_fits(self):
  for screen in (600,768,920):
   for requested in (160,187,224):
    looper,tone=sizes(1000,screen,requested)
    self.assertGreaterEqual(looper[3],requested)
    self.assertEqual(looper[1]+looper[3],screen)
    self.assertEqual(tone[3],looper[1])

 def test_missing_hints_have_a_safe_default(self):
  self.assertEqual(minimum_size('WM_NORMAL_HINTS: not found.'),(848,187))
