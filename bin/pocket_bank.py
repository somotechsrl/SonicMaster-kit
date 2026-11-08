"""Pocket Master bank backup/apply with CRC validation and readback.

Protocol codec: pocket-master-mcp (MIT); model tables: SonicMaster (MIT).
Only the exact kernel USB-MIDI client 'Pocket Master' is accepted.
"""
import json
import math
from pathlib import Path
import struct
import time
from alsa_midi import Sequencer, devices
import pocket_protocol as P

ROOT=Path(__file__).resolve().parents[1]
EFFECTS=json.loads((ROOT/'config/pocket/effect_library.json').read_text())
COMMANDS=json.loads((ROOT/'config/pocket/command_library.json').read_text())
MODULES=P.MODULES


def wire(frame):
    raw=bytes.fromhex(frame)
    return raw[2:] if raw.startswith(b'\x80\x80') else raw


def code_for(module, effect):
    frame=P.parse_frame(P.hex_to_sysex_data(COMMANDS['effectTypes'][str(module)][str(effect)]))
    return struct.unpack_from('<I',frame.payload,len(frame.payload)-4)[0]


class Pocket:
    def __init__(self):
        targets=devices(names=('Pocket Master',))
        if len(targets)!=1:raise RuntimeError('Serve un solo Pocket Master USB collegato.')
        self.target=targets[0];self.origin=(self.target['client'],self.target['port'])
        self.seq=Sequencer('SonicMaster bank manager');self.seq.connect(self.target)
        self.responses=[];self.parts={}

    def close(self):self.seq.close()

    def send(self, frame):
        self.seq.send(self.target,b"\xf0"+bytes(frame)+b"\xf7");time.sleep(.025)

    def receive(self):
        result=[]
        for source, raw in self.seq.pending():
            if source!=self.origin:continue
            try:frame=P.parse_frame(raw[1:-1])
            except ValueError:continue
            if not frame.crc_ok:continue
            if frame.total<=1:result.append(frame.payload);continue
            if frame.index==0:self.parts[frame.total]={}
            parts=self.parts.setdefault(frame.total,{})
            parts[frame.index]=frame.payload
            if len(parts)==frame.total:
                result.append(b''.join(parts[i] for i in range(frame.total)));del self.parts[frame.total]
        return result

    def request(self,kind,timeout=4):
        for attempt in range(3):
            self.receive();self.parts={};self.send(P.query(kind))
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                for payload in self.receive():
                    if payload[:2]==bytes([P.GET,kind]):return payload
                time.sleep(.005)
            time.sleep(.25)
        raise TimeoutError(f'Pocket Master non risponde alla lettura {kind:02x}')

    def current(self):
        data=self.request(P.Q_CURRENT_INDEX)
        return data[2]

    def dump(self):return self.request(P.Q_CURRENT_DUMP)

    def select(self,index):
        self.send(P.select_preset(index));time.sleep(.08)
        if self.current()!=index:raise RuntimeError('Slot attivo diverso da quello richiesto')

    def names(self):return P.preset_name_records(self.request(P.Q_PRESET_NAMES,8))

    def backup(self,folder):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
        original=self.current();initial=self.dump();names=self.names()
        metadata={'current':original,'names':names,'slots':{}}
        (folder/'active-edit-buffer.bin').write_bytes(initial)
        try:
            for i in range(50):
                self.select(i);payload=self.dump()
                fields=P.dump_fields(payload)
                if not all(k in fields for k in ('codes','params','mask','chain','volume')):raise RuntimeError(f'Backup incompleto P{i+1:02}')
                (folder/f'P{i+1:02}.bin').write_bytes(payload)
                metadata['slots'][str(i)]={'name':names.get(i,''),'bytes':len(payload)}
                (folder/'manifest.json').write_text(json.dumps(metadata,indent=2))
                if (i+1)%10==0:print('Backup',i+1,'/50 verificati',flush=True)
        finally:self.select(original)
        return metadata

    def apply(self,doc,slot):
        if not 0<=slot<50:raise ValueError('Sono scrivibili solo i 50 slot User')
        modules=doc['modules'];self.select(slot)
        # Disable first, select models, then apply every parameter; model changes
        # reset parameters on the pedal. No unspecified live settings carry over.
        for i in range(10):self.send(P.module_state(i,False))
        self.send(P.amp_mode(False));expected={}
        for i,key in enumerate(MODULES):
            mod=modules[key];effect=mod.get('effectId')
            if effect is not None:
                code=0x1b if i == 0 else code_for(i,effect)
                if i != 0:self.send(P.select_effect(i,code))
                expected[i]=code
                definition=EFFECTS[str(effect)]
                for alg in definition.get('alg',[]):
                    if alg['name'] in ('Sync','Trail'):continue
                    value=mod['parameters'].get(alg['name'],alg['defaultValue'])
                    self.send(P.set_param(i,alg['algId'],value))
            self.send(P.module_state(i,mod['enabled']))
        self.send(P.set_chain([MODULES.index(k) for k in doc['signalChain']]))
        self.send(P.preset_volume(doc['presetVolume']))
        # Model changes can reinitialize another block after queued writes.
        # Repair only mismatched scalar values in the live buffer, then verify
        # everything before committing any flash write.
        for attempt in range(3):
            live=P.dump_fields(self.dump());repairs=[];model_repairs=False
            for i,code in expected.items():
                if live['codes'][i]!=code and i!=0:
                    self.send(P.select_effect(i,code));time.sleep(.05)
                    self.send(P.module_state(i,modules[MODULES[i]]['enabled']))
                    model_repairs=True
            if model_repairs:
                time.sleep(.1);live=P.dump_fields(self.dump())
            for i,key in enumerate(MODULES):
                mod=modules[key];effect=mod.get('effectId')
                if effect is None:continue
                for alg in EFFECTS[str(effect)].get('alg',[]):
                    if alg['name'] in ('Sync','Trail'):continue
                    target=mod['parameters'].get(alg['name'],alg['defaultValue'])
                    actual=P.param_from_block(live['params'],i,alg['algId'])
                    if actual is None or not math.isclose(actual,float(target),abs_tol=.02):repairs.append((i,alg['algId'],target))
            if not repairs:break
            if attempt==2:break
            for i,alg,value in repairs:self.send(P.set_param(i,alg,value))
            time.sleep(.1)
        self.verify(doc,live,expected)
        self.receive();self.send(P.save_preset(slot,doc['deviceName']))
        deadline=time.monotonic()+3;acked=False
        while time.monotonic()<deadline:
            for payload in self.receive():
                if payload[:2]==bytes([P.ACK,P.CMD_ACK]):
                    if payload[2]!=0:raise RuntimeError('Il pedale ha rifiutato il salvataggio')
                    acked=True
            if acked:break
            time.sleep(.01)
        if not acked:raise TimeoutError('Conferma di salvataggio assente')
        time.sleep(.8)
        # Reload from flash; validation of the edit buffer alone is insufficient.
        self.select(50);self.select(slot)
        self.verify(doc,P.dump_fields(self.dump()),expected)

    @staticmethod
    def verify(doc,live,expected):
        mask=sum(1<<i for i,key in enumerate(MODULES) if doc['modules'][key]['enabled'])
        if live['mask']&0x3ff!=mask:raise RuntimeError('Readback: stato effetti diverso')
        if live['volume']!=doc['presetVolume']:raise RuntimeError('Readback: volume diverso')
        if live['chain']!=[MODULES.index(k) for k in doc['signalChain']]:raise RuntimeError('Readback: ordine effetti diverso')
        for i,code in expected.items():
            if live['codes'][i]!=code:raise RuntimeError(f'Readback: modello diverso nel modulo {i}')
            mod=doc['modules'][MODULES[i]]
            for alg in EFFECTS[str(mod['effectId'])].get('alg',[]):
                if alg['name'] in ('Sync','Trail'):continue
                target=mod['parameters'].get(alg['name'],alg['defaultValue'])
                actual=P.param_from_block(live['params'],i,alg['algId'])
                if actual is None or not math.isclose(actual,float(target),abs_tol=.02):
                    raise RuntimeError(f'Readback: parametro {MODULES[i]}/{alg["name"]}: {actual} != {target}')
