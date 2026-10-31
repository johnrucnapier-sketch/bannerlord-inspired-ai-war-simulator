"""Fetch selected archives, verify pieces, reassemble and verify; never execute agents."""
import argparse,hashlib,json,shutil,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--opponent',required=True,choices=['v20','v21','v22','v23','v24','calibration']);p.add_argument('--round',type=int,choices=[1,2]);p.add_argument('--output',required=True);a=p.parse_args()
assets=json.loads((Path(__file__).parent/'assets.json').read_text());out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
def valid(path,x):
 if not path.exists():return False
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return path.stat().st_size==x['bytes'] and h.hexdigest()==x['sha256']
def fetch(x):
 target=out/x['name']
 if target.exists():
  if valid(target,x):return target
  raise SystemExit('Existing file mismatch; refusing overwrite: '+str(target))
 partial=target.with_suffix(target.suffix+'.partial')
 print('Downloading',x['name'],x['bytes'],'bytes',flush=True)
 with urllib.request.urlopen(x['url'],timeout=120) as src,partial.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
 if not valid(partial,x):raise SystemExit('Verification failed; partial retained: '+str(partial))
 partial.rename(target);return target
for x in assets:
 if a.opponent=='calibration':
  if x['formal']:continue
 elif x.get('opponent')!=a.opponent:continue
 if a.round and x.get('round')!=a.round:continue
 target=out/x['name']
 if target.exists():
  if valid(target,x):print('Already verified',target);continue
  raise SystemExit('Existing archive mismatch: '+str(target))
 if 'parts' in x:
  files=[fetch(piece) for piece in x['parts']];tmp=target.with_suffix(target.suffix+'.partial')
  with tmp.open('wb') as dst:
   for file in files:
    with file.open('rb') as src:shutil.copyfileobj(src,dst,1024*1024)
  if not valid(tmp,x):raise SystemExit('Assembled archive mismatch: '+str(tmp))
  tmp.rename(target)
 else:fetch(x)
 print('Verified complete archive',target,flush=True)
