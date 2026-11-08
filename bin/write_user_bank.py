#!/usr/bin/python3
"""Write an explicitly requested bank after a complete local backup.

Requires --apply; never runs from the normal kit launcher.
"""
import argparse,json
from pathlib import Path
from pocket_bank import Pocket,ROOT,MODULES,code_for


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    metadata=json.loads((args.backup/'manifest.json').read_text())
    if len(metadata.get('slots',{}))!=50 or any(not (args.backup/f'P{i:02}.bin').is_file() for i in range(1,51)):
        raise RuntimeError('Prima serve un backup completo dei 50 slot User')
    manifest=json.loads((ROOT/'presets/pocket-master/manifest.json').read_text())
    if not args.apply:
        print('17 adattamenti consecutivi 1A–5A, in gruppi di quattro; altri 33 slot bypass. Factory invariati.');return
    pocket=Pocket();journal=args.backup/'write-results.json';results=[]
    previous=json.loads(journal.read_text()) if journal.exists() else []
    completed={e['slot']:e for e in previous}
    try:
        for entry in manifest:
            doc=json.loads((ROOT/'presets/pocket-master'/entry['file']).read_text())
            already=completed.get(entry['slot'],{}).get('name')==doc['deviceName']
            if already:
                pocket.select(entry['slot']-1)
                from pocket_bank import P
                expected={i:(0x1b if i==0 else code_for(i,doc['modules'][k]['effectId'])) for i,k in enumerate(MODULES)}
                try:pocket.verify(doc,P.dump_fields(pocket.dump()),expected)
                except RuntimeError:already=False
            if not already:pocket.apply(doc,entry['slot']-1)
            results.append({'slot':entry['slot'],'name':doc['deviceName'],'flash_readback':'verified'})
            journal.write_text(json.dumps(results,indent=2))
            print(f"P{entry['slot']:02} {doc['deviceName']}: salvato e verificato dalla memoria",flush=True)
        names=pocket.names()
        for entry in manifest:
            if names.get(entry['slot']-1)!=entry['name']:raise RuntimeError('Nome slot diverso dopo salvataggio')
        old_factory={int(k):v for k,v in metadata['names'].items() if int(k)>=50}
        if {k:v for k,v in names.items() if k>=50}!=old_factory:raise RuntimeError('Elenco Factory diverso dal backup')
        pocket.select(next(e['slot']-1 for e in manifest if e.get('source') == 'Jaco Birdland'))
        print('50 User verificati. Nomi Factory invariati. Banco raggruppato per quattro; attivo Jaco Birdland.',flush=True)
    finally:pocket.close()


if __name__=='__main__':main()
