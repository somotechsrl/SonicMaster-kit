"""Run under Xvfb: verify bank labels and JUCE progress-window exclusion."""
from pathlib import Path
from types import SimpleNamespace
import sys,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
import gui


class Monitor:
 generation=0
 effect=None
 connected=True
 closed=False
 def __init__(self,*_):pass
 def poll(self):return None if self.effect is None else self.effect//4
 def close(self):self.closed=True


def main():
 assert isinstance(gui.Gdk.Display.get_default(),gui.GdkX11.X11Display)
 errors=[]
 with tempfile.TemporaryDirectory() as folder, patch.object(gui,'EffectBankMonitor',Monitor), patch.object(gui.Container,'start',lambda self:False), patch.object(gui,'monitor_area',lambda:(0,0,1600,1000)):
  gui.STATE=Path(folder)/'runtime.json';gui.WINDOW_SETTINGS=Path(folder)/'window.json'
  window=gui.Container()
  def exercise():
   try:
    assert window.bank_display.get_label()=='Banco: — · Effetto: —'
    heights={widget.get_allocated_height() for widget in (window.drums,window.bank_display)}
    assert len(heights)==1,heights
    for effect,text in ((0,'Banco: 1–4 · Effetto: 1 → 1'),(4,'Banco: 5–8 · Effetto: 1 → 5'),(7,'Banco: 5–8 · Effetto: 4 → 8'),(8,'Banco: 9–12 · Effetto: 1 → 9 · non assegnato'),(127,'Banco: 125–128 · Effetto: 4 → 128 · non assegnato'),(None,'Banco: — · Effetto: —')):
     window.bank_monitor.effect=effect;window.update_bank();assert window.bank_display.get_label()==text
    window.bank_monitor.connected=False;window.update_bank()
    assert 'non collegata' in window.bank_display.get_tooltip_text()
    window.bank_monitor.effect=4
    with patch.object(window.effect_names,'update',return_value='Spring Rvb'):
     window.update_bank()
    assert window.bank_display.get_label()=='Banco: 5–8 · Effetto: 1 → 5 · Spring Rvb'
    assert window.bank_display.get_allocated_height()==window.drums.get_allocated_height()
    with patch.object(gui,'call',return_value=SimpleNamespace(stdout='_NET_WM_WINDOW_TYPE(ATOM) = _KDE_NET_WM_WINDOW_TYPE_OVERRIDE')):
     assert not gui.normal_tonelib_window('0x123',{})
    with patch.object(gui,'call',return_value=SimpleNamespace(stdout='_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_NORMAL')):
     assert gui.normal_tonelib_window('0x123',{})
    window.close();assert window.bank_monitor.closed
   except BaseException as exc:errors.append(exc)
   finally:window.window.destroy()
   return False
  gui.GLib.timeout_add(300,exercise);gui.Gtk.main()
  if errors:raise errors[0]
 print('GTK effect-bank states, cleanup and progress-dialog exclusion passed.')


if __name__=='__main__':main()
