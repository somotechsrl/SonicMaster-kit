"""Export the musical profile for this public source tree, without personal data."""
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

def export_profile(source,target):
 source=Path(source);target=Path(target)
 presets=source/'Shared/presets_4.0'
 if presets.exists():
  for file in presets.glob('*.tlgfx'):
   dest=target/'Shared/presets_4.0'/file.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dest)
 for name in ('_app.cfg','looper.cfg','rhythm.cfg'):
  src=source/'ToneLib GFX'/name
  if not src.exists():continue
  tree=ET.parse(src);root=tree.getroot()
  for node in list(root):
   key=node.get('name','')
   if key.startswith(('recent_','forum.','gfx.presets..online.')) or key in ('unreg.warn','wnd.bk'):root.remove(node)
   elif key=='wnd.pos':node.set('val','100 100 1200 800 frame 37 0 0 0')
   elif key=='gfx.impulses.dir':node.set('val','')
  setup=root.find("VALUE[@name='audio.device.state']/DEVICESETUP")
  if setup is not None:
   for midi in list(setup):setup.remove(midi)
  for node in tree.iter():
   for key,value in list(node.attrib.items()):
    if any(part in value for part in ('/home/','/zpool/','file://')):node.set(key,'')
  dest=target/'ToneLib GFX'/name;dest.parent.mkdir(parents=True,exist_ok=True)
  tree.write(dest,encoding='utf-8',xml_declaration=True)
