"""Prepare Ardour preferences while it is closed, preserving user settings."""
import os
from pathlib import Path
import xml.etree.ElementTree as ET


def ardour_running():
    # This is also true during session loading, before JACK ports exist.
    for path in Path('/proc').glob('[0-9]*/comm'):
        try:
            if path.read_text().strip().lower().startswith(('ardour','ardourgui')):
                return True
        except OSError:
            pass
    return False


def prepare(config):
    from midimix import MAP_NAME, install_map
    install_map(config)
    if ardour_running():
        return False
    path = config/'config'
    try:
        original = path.read_bytes()
        tree = ET.fromstring(original)
    except (OSError, ET.ParseError):
        return False  # Let Ardour finish its first-run setup normally.
    protocols = tree.find('ControlProtocols')
    if protocols is None:
        protocols = ET.SubElement(tree,'ControlProtocols')
    changed = False
    for name, options in (
        ('Generic MIDI', {'active':'1','binding':MAP_NAME}),
        ('Open Sound Control (OSC)', {'active':'1','address-only':'0'}),
    ):
        node = next((p for p in protocols if p.get('name') == name), None)
        if node is None:
            node = ET.SubElement(protocols,'Protocol',name=name)
        for key, value in options.items():
            if node.get(key) != value:
                node.set(key,value); changed = True
    generic = next(p for p in protocols if p.get('name') == 'Generic MIDI')
    for parent_tag, direction, hardware in (
        ('Input', 'Input', 'a2j:MIDI Mix (capture): MIDI Mix MIDI 1'),
        ('Output', 'Output', 'a2j:MIDI Mix (playback): MIDI Mix MIDI 1'),
    ):
        parent = generic.find(parent_tag)
        if parent is None:
            parent = ET.SubElement(generic,parent_tag)
        port = parent.find('Port')
        if port is None:
            port = ET.SubElement(parent,'Port',name='MIDI Control '+('In' if direction == 'Input' else 'Out'),type='midi',direction=direction)
        for connection in list(port):
            if connection.get('other','').startswith('a2j:TSMA MIDImix bridge '):
                port.remove(connection); changed = True
        if not any(c.get('for') == 'JACK' and c.get('other') == hardware for c in port):
            ET.SubElement(port,'ExtConnection',{'for':'JACK','other':hardware}); changed = True
    if changed:
        backup = config/'config.before-tsma-midimix'
        if not backup.exists():
            backup.write_bytes(original); backup.chmod(0o600)
        temporary = config/'config.tsma-tmp'
        temporary.write_bytes(ET.tostring(tree,encoding='utf-8',xml_declaration=True))
        temporary.chmod(path.stat().st_mode & 0o777)
        # Avoid overwriting preferences saved concurrently during shutdown.
        if ardour_running() or path.read_bytes() != original:
            temporary.unlink(); return False
        temporary.replace(path)
    return True
