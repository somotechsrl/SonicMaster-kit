#!/usr/bin/env python3
"""Convert a local drum-video collection into concise, organized local backing tracks."""
import argparse,concurrent.futures,json,re,subprocess
from pathlib import Path

TYPES={
 'Bossa Nova Brushes':('Bossa Nova','Brushes'),
 'Bossa Nova III':('Bossa Nova','III'),
 'Funk Basic':('Funk','Basic'),
 'Funk Swing':('Funk','Swing'),
 'Jazz 5⧸4':('Jazz','5-4'),
 'Jazz Swing 3⧸4 Backbeat 2':('Jazz','Swing 3-4 Backbeat 2'),
 'Jazz Swing Backbeat 2':('Jazz','Swing Backbeat 2'),
 'Jazz Swing Brushes Swirls in 2':('Jazz','Brushes Swirls in 2'),
 'Jazz Swing':('Jazz','Swing'),
 'Soul Blues':('Soul','Blues'),
 'Soul ⧸ R&B':('Soul','R&B'),
}
EXTENSIONS={'.mkv','.webm','.mp4','.mov','.mp3','.ogg','.flac','.wav'}

def target_name(source,base,format="flac"):
 style=source.parent.name.split(' • ')[0]
 folders=TYPES.get(style,(re.sub(r'[^\w &-]+','-',style).strip(),))
 match=re.search(r'(\d+)\s*BPM',source.stem,re.I)
 if not match:raise ValueError('Missing BPM: '+source.name)
 return Path(base).joinpath(*folders,f'{int(match[1]):03d} BPM.{format}')

def convert(source,target):
 target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists() and target.stat().st_mtime>=source.stat().st_mtime:return 'existing'
 partial=target.with_suffix('.partial'+target.suffix)
 try:
  subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(source),'-map','0:a:0','-vn','-ar','48000','-ac','2',*(['-c:a','libmp3lame','-q:a','2'] if target.suffix=='.mp3' else ['-c:a','flac','-sample_fmt','s16','-compression_level','5'] if target.suffix=='.flac' else ['-c:a','pcm_s16le']),'-map_metadata','-1','-metadata','title='+target.stem,'-threads','1',str(partial)],check=True)
  if target.suffix=='.wav':
   import wave
   with wave.open(str(partial)) as w:
    if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(48000,2,2) or not w.getnframes():raise ValueError('Invalid output: '+str(target))
  else:
   info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=codec_name,sample_rate,channels','-of','json',str(partial)]))['streams'][0]
   if (info['codec_name'],int(info['sample_rate']),info['channels'])!=(target.suffix[1:],48000,2):raise ValueError('Invalid compressed audio: '+str(target))
  partial.replace(target);return 'converted'
 finally:partial.unlink(missing_ok=True)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
 parser.add_argument('--format',choices=('flac','mp3','wav'),default='flac')
 parser.add_argument('--jobs',type=int,default=3)
 args=parser.parse_args();files=sorted(p for p in args.source.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS and not p.is_relative_to(args.destination))
 tasks=[(p,target_name(p,args.destination,args.format)) for p in files]
 if len({p for _,p in tasks})!=len(tasks):raise SystemExit('Duplicate style/BPM destinations; no files converted.')
 args.destination.mkdir(parents=True,exist_ok=True);entries=[];errors=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
  pending={pool.submit(convert,source,target):(source,target) for source,target in tasks}
  for future in concurrent.futures.as_completed(pending):
   source,target=pending[future]
   try:
    state=future.result();entries.append({'file':str(target.relative_to(args.destination)),'source':str(source),'result':state});print(f'{len(entries)}/{len(tasks)} {target.relative_to(args.destination)}',flush=True)
   except Exception as exc:errors.append({'source':str(source),'error':str(exc)})
 (args.destination/'index.json').write_text(json.dumps({'format':{'flac':'FLAC 16-bit stereo 48000 Hz','mp3':'MP3 VBR quality 2 stereo 48000 Hz','wav':'WAV PCM16 stereo 48000 Hz'}[args.format],'tracks':sorted(entries,key=lambda x:x['file']),'errors':errors},indent=2,ensure_ascii=False))
 (args.destination/'Drums.m3u8').write_text('#EXTM3U\n'+'\n'.join(x['file'] for x in sorted(entries,key=lambda x:x['file']))+'\n')
 print(f'Imported {len(entries)} tracks; {len(errors)} errors.',flush=True)
 if errors:raise SystemExit(1)

if __name__=='__main__':main()
