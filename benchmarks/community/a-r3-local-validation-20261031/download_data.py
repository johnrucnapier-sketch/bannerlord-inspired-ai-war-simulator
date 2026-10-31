"""Download selected public data assets with SHA256 verification; never extract or execute."""
import argparse,hashlib,json,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--opponent',required=True,choices=['v20','v21','v22','v23','v24','calibration']);p.add_argument('--round',type=int,choices=[1,2]);p.add_argument('--output',required=True);a=p.parse_args()
assets=json.loads((Path(__file__).parent/'assets.json').read_text());out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
for x in assets:
 if a.opponent=='calibration':
  if x['formal']:continue
 elif x.get('opponent')!=a.opponent:continue
 if a.round and x.get('round')!=a.round:continue
 target=out/x['name']
 if target.exists():raise SystemExit('Refusing to overwrite '+str(target))
 partial=target.with_suffix(target.suffix+'.partial')
 if partial.exists():raise SystemExit('Incomplete previous download: '+str(partial))
 h=hashlib.sha256();size=0
 print('Downloading',x['name'],x['bytes'],'bytes',flush=True)
 with urllib.request.urlopen(x['url'],timeout=120) as src,partial.open('xb') as dst:
  while True:
   buf=src.read(1024*1024)
   if not buf:break
   dst.write(buf);h.update(buf);size+=len(buf)
 if size!=x['bytes'] or h.hexdigest()!=x['sha256']:raise SystemExit('Verification failed; partial retained: '+str(partial))
 partial.rename(target);print('Verified',target,flush=True)
