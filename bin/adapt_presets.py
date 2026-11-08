"""Adapt exported ToneLib summaries to Pocket Master models and SonicMaster JSON.

Mappings are approximations; source settings and per-preset omissions accompany
all generated files. This command writes files only, never MIDI.
"""
import json
from pathlib import Path
import re
from pocket_bank import EFFECTS, MODULES, ROOT

AMP={'Ms JTM45':306,'Jc Clean':305,'Vx Ac30':304,'Fd Deluxe':301,'Vx Ac30Tb':310,'Ms Plexi':307,'Ms JCM800':308,'Dmb Drive':317,'Bass SVT':321,'Tube Warmth':321}
MOD={'Mt-Chorus':106,'Bi-Chorus':107,'Flanger':108,'Vibe':110,'Tremolo':112,'Phaser':109}
NAMES=['EqChoRvb','CrunchBlue','JazzClean','ArchVox30','ArchFDR','ArchJTM45','SantClean','SantCrunch','SantDrive','OmegaBass','FXBass','NewstedCLN','SlapBass','Microfone','JacoBird','JacoChick','BrandXApr']


def number(values,key,default=50):
    try:return float(values.get(key,default))
    except (ValueError,TypeError):return default


def parse(text):
    pattern=r'Effect: "([^"\n]+)"[^\n]*active - "(yes|no)"[^\n]*\n\s*\{([^{}]*)\}'
    return [(m[1],m[2]=='yes',{k:v.strip() for k,v in re.findall(r'"([^"\n]+)" = ([^\n]+)',m[3])}) for m in re.finditer(pattern,text)]


def module(effect,enabled=False,params=None):
    definition=EFFECTS[str(effect)]
    values={alg['name']:alg['defaultValue'] for alg in definition.get('alg',[])}
    for key,value in (params or {}).items():
        alg=next((p for p in definition.get('alg',[]) if p['name']==key),None)
        if alg is None:continue
        lo,hi=alg.get('min',0),alg.get('max',len(alg.get('options',[]))-1 if alg.get('options') else 100)
        step=alg.get('step',1)
        values[key]=round(max(lo,min(hi,round(value/step)*step)),3)
    return {'enabled':bool(enabled),'effect':definition['name'],'effectId':effect,'parameters':values}


def empty(name='Empty'):
    ids=[1,101,201,305,408,501,106,701,802]
    return {'version':'1.0','presetName':name,'deviceName':name,'ampMode':'Normal','presetVolume':50,'presetBpm':120,'signalChain':list(MODULES),'modules':{k:module(e) for k,e in zip(MODULES,ids)},'adaptationNotes':[]}


def adapt(item,index):
    doc=empty(NAMES[index]);doc['presetName']=item['name'];notes=doc['adaptationNotes'];mods=doc['modules']
    effects=parse(item['summary']);active=[x for x in effects if x[1]]
    bass=any(n in ('Bass SVT','BassEQ','Tube Warmth') for n,_,_ in effects) or 'Bass' in item['name']
    for name,on,p in effects:
        if name=='Noise Reducer':mods['NR']=module(1,on,{'THRE':number(p,'Sens',30)})
    compressors=[x for x in active if x[0] in ('Compressor','Rack Comp')]
    if compressors:
        name,_,p=compressors[0]
        sustain=number(p,'Sense',max(10,min(60,-number(p,'Threshold (dB)',-20)*1.3)))
        mods['FX1']=module(102 if name=='Rack Comp' else 101,True,{'Sustain':sustain,'Vol':50,'Attack':60,'Clip':10})
    drives=[x for x in active if x[0] in ('T-Scream','B-Scream','Cent OD','Bass Drive','Booster')]
    if drives:
        name,_,p=drives[0];fx=208 if name=='Bass Drive' else 201 if name in ('T-Scream','B-Scream','Cent OD') else 202
        mods['DRV']=module(fx,True,{'Gain':number(p,'Drive',number(p,'Gain',20)),'Tone':number(p,'Tone',50),'Vol':number(p,'Level',50),'Blend':number(p,'Blend',50),'Bass':number(p,'Bass',50),'Treble':number(p,'Treble',50)})
        if name not in ('T-Scream','Bass Drive'):notes.append(name+' approssimato con '+mods['DRV']['effect'])
        if len(drives)>1:notes.append('Stadi drive multipli ridotti a un solo blocco DRV')
    amps=[x for x in active if x[0] in AMP]
    if amps:
        name,_,p=amps[0];fx=AMP[name]
        if fx==321:
            freq=p.get('Midrange','800 Hz');mid={'200 Hz':0,'800 Hz':2,'3 kHz':4}.get(freq,2)
            values={'Gain':min(40,20+number(p,'Volume',35)*.2),'Bass':50+4*number(p,'Bass',0),'Middle':50+4*number(p,'Middle',0),'Treble':50+4*number(p,'Treble',0),'MidFreq':mid,'Vol':50}
            if name=='Tube Warmth':values.update(Gain=30,Bass=55,Middle=45,Treble=60)
        else:
            values={'Gain':number(p,'Gain',30),'Gain 1':number(p,'Gain',30),'Gain 2':20,'Bass':number(p,'Bass',50),'Middle':number(p,'Middle',50),'Treble':number(p,'Treble',50),'Tone':number(p,'Treble',50),'Pres':number(p,'Presence',50),'Tone Cut':100-number(p,'Treble',50),'Vol':50}
        mods['AMP']=module(fx,True,values)
        if len(amps)>1:notes.append('Amplificatori paralleli ridotti al modello principale: '+name)
    cabinets=[x for x in active if x[0] in ('Guitar IRs Cab','Bass IRs Cab')]
    if cabinets and not bass:
        p=cabinets[0][2];name=p.get('Model','');fx=410 if 'Marshall' in name else 404 if 'Vox' in name else 406 if 'Twin' in name else 415 if 'Mesa' in name else 403
        mods['IR']=module(fx,True)
        notes.append('Microfono, distanza e filtri IR originali approssimati dalla cassa interna')
    elif bass:
        notes.append('IR per basso originali non disponibili nei modelli Pocket Master: IR bypassato per conservare la gamma bassa')
    eqs=[x for x in active if x[0] in ('Studio EQ','BassEQ')]
    if eqs:
        name,_,p=eqs[0];fx=503 if bass else 501
        source={'50Hz':'50 Hz','120Hz':'120 Hz','125Hz':'125 Hz','400Hz':'400 Hz','800Hz':'800 Hz','1.6kHz':'2 kHz','4kHz':'4 kHz','4.5kHz':'4.5 kHz'}
        values={key:number(p,source.get(key,key),0) for key in source}
        mods['EQ']=module(fx,True,values)
        notes.append('Curve EQ ridotte alle cinque bande disponibili; scale e bande non identiche')
    modulation=[x for x in active if x[0] in MOD]
    for name,_,p in modulation:
        slot='FX2' if not mods['FX2']['enabled'] else 'FX1' if not mods['FX1']['enabled'] else None
        if slot is None:notes.append(name+' omesso: entrambi i blocchi FX occupati');continue
        fx=MOD[name];mods[slot]=module(fx,True,{'Depth':number(p,'Depth',50),'Rate':number(p,'Speed',number(p,'Speed A',.5)),'F.Back':number(p,'Reso',30),'Vol':50})
        notes.append(name+' adattato: mix e ritardi interni non equivalenti')
    delays=[x for x in active if 'Dly' in x[0]]
    if delays:
        name,_,p=delays[0];fx=707 if name=='AnalogDly' else 709 if name=='TwoTapDly' else 702
        mods['DLY']=module(fx,True,{'Time':number(p,'Time',400),'F.Back':number(p,'Feedback',25),'Mix':number(p,'Mix',20)})
    reverbs=[x for x in active if 'Rvb' in x[0]]
    if reverbs:
        name,_,p=reverbs[-1];fx=807 if name in ('Spring Rvb','Bounce Rvb') else 802 if name=='Room Rvb' else 803 if name=='Hall Rvb' else 805
        mods['RVB']=module(fx,True,{'Mix':number(p,'Mix',20),'Decay':number(p,'Time',2.5)*10,'Damp':number(p,'HiDamp',30)})
        notes.append('Tempo riverbero in secondi approssimato con Decay percentuale')
    for name,_,p in active:
        if name in ('Pickup Mod','IR Processor','Splitter'):notes.append(name+' senza equivalente diretto; non trasferito')
    notes.append('Livelli ricentrati a 50 e volume preset 50; rifinitura all’ascolto necessaria')
    doc['sourcePreset']=item['source'];return doc


def main():
    source=ROOT/'presets/source/tonelib-summaries.json';items=json.loads(source.read_text())
    target=ROOT/'presets/pocket-master';target.mkdir(parents=True,exist_ok=True)
    for old in target.glob('P*.json'):old.unlink()
    manifest=[];occupied=set()
    short=['EqChoRv','Blues','Jazz','VoxAC30','FDeluxe','JTM45','SantCln','SantCrn','SantDrv','OmegaBs','FXBass','Newsted','SlapBas','Mic','JacoBrd','JacoChk','BXApril']
    for i,item in enumerate(items):
        doc=adapt(item,i);source_index=int(item['source'][6:9]);bank=i//4+1;letter=i%4
        slot=i+1;assert 1<=slot<=50 and slot not in occupied;occupied.add(slot)
        label=f'{bank}{chr(65+letter)}';doc['deviceName']=(label+':'+short[i])[:10];doc['presetName']=label+':'+item['name'].replace(' ','');doc['sourceLabel']=label
        name=f'P{slot:02}-{label}-{short[i]}.json';(target/name).write_text(json.dumps(doc,indent=2,ensure_ascii=False)+'\n');manifest.append({'slot':slot,'name':doc['deviceName'],'source':item['name'],'sourceLabel':label,'file':name,'notes':doc['adaptationNotes']})
    for i in range(1,51):
        if i in occupied:continue
        doc=empty(f'Empty P{i:02}');name=f'P{i:02}-Empty.json';(target/name).write_text(json.dumps(doc,indent=2)+'\n');manifest.append({'slot':i,'name':doc['deviceName'],'source':None,'file':name,'notes':['Slot inizializzato con tutti gli effetti bypassati']})
    manifest.sort(key=lambda x:x['slot'])
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    import csv
    with (target/'corrispondenza.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator="\n");writer.writerow(['Pocket','Sigla','Nome dispositivo','Originale ToneLib'])
        writer.writerows((f"P{e['slot']:02}",e['sourceLabel'],e['name'],e['source']) for e in manifest if e['source'])
    print('17 adattamenti + 33 slot bypass generati; nessun MIDI inviato.')


if __name__=='__main__':main()
