"""Run under Xvfb: verify the GTK test/learn flow with an isolated MIDI source."""
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
import pedal_check as ui
from gi.repository import GLib,Gtk


class Midi:
 events=[]
 def connect(self,*_):pass
 def pending(self):
  events,self.events=self.events,[]
  return events
 def close(self):pass


def main():
 with tempfile.TemporaryDirectory() as folder:
  root=Path(folder)
  ui.ROOT=root;ui.RUNTIME=root/'runtime';ui.STORE=root/'state/pedals'
  ui.devices=lambda:[{'client':203,'port':0,'name':'SINCO','port_name':'SINCO MIDI 1'}]
  ui.Sequencer=Midi;ui.guard_available=lambda:True
  window=ui.PedalCheck();errors=[]
  def exercise():
   try:
    window.start_test('SINCO')
    assert window.lease.is_file()
    window.seq.events=[((203,0),bytes([176,cc,127])) for cc in range(80,84)]
    window.tick()
    assert len(window.passed)==4 and not window.steps
    window.spins['previous_cc'].set_value(10);window.save_tone()
    assert window.profile['previous_cc']==10
    window.test_mode.set_active(False)
    assert not window.lease.exists()
    window.save_report()
    assert list(ui.STORE.glob('report-*.json'))
   except BaseException as exc:errors.append(exc)
   finally:window.destroy();Gtk.main_quit()
   return False
  GLib.timeout_add(300,exercise);Gtk.main()
  if errors:raise errors[0]
 print('Pedal Check GTK guided test, mapping save, report and lease cleanup passed.')


if __name__=='__main__':main()
