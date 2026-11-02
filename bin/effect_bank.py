"""Observe the last Tone Shifter effect bank without sending MIDI to the pedal."""
import time
from alsa_midi import Sequencer,devices
from pedals import load_profile


class EffectBankMonitor:
    def __init__(self, profile, scan=devices, transport=Sequencer, clock=time.monotonic):
        self.path=profile;self.scan=scan;self.transport=transport;self.clock=clock
        self.seq=None;self.source=None;self.effect=None;self.next_scan=0;self.generation=0
        self.profile=load_profile(profile)

    @property
    def connected(self):return self.source is not None

    @property
    def bank(self):return None if self.effect is None else self.effect//4

    def close(self):
        if self.seq is not None:self.seq.close()
        self.seq=None;self.source=None;self.effect=None;self.generation+=1

    def poll(self):
        try:
            if self.clock()>=self.next_scan:
                self.next_scan=self.clock()+2
                profile=load_profile(self.path)
                if profile['effect_offset']!=self.profile['effect_offset']:self.effect=None;self.generation+=1
                self.profile=profile
                device=next((d for d in self.scan() if d['name']=='TSMEGA'),None)
                source=(device['client'],device['port']) if device else None
                if source!=self.source:
                    self.close()
                    if device:
                        self.seq=self.transport('TSMA effect bank monitor')
                        self.seq.connect(device);self.source=source
            if self.seq is not None:
                for source,raw in self.seq.pending():
                    if source==self.source and len(raw)==2 and raw[0]&0xF0==0xC0 and raw[1]<128:
                        self.effect=(raw[1]-self.profile['effect_offset'])%128
                        self.generation+=1
                    elif source==self.source and len(raw)==3 and raw[0]&0xF0==0xB0 and raw[1] in (self.profile['previous_cc'],self.profile['next_cc']):
                        self.generation+=1
        except OSError:
            self.close();self.next_scan=0
        return self.bank
