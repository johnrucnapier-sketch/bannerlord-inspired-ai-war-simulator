"""Download verified 16 MiB pieces, resume safely, never execute a strategy."""
import argparse,hashlib,json,shutil,urllib.request
from pathlib import Path

def valid(p,x):
 if not p.exists() or p.stat().st_size!=x['bytes']:return False
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()==x['sha256']

def main():
 p=argparse.ArgumentParser();p.add_argument('--package',required=True,choices=['gptdot-a-r3','grok-v25','grok-v23','march','development','three-losses','all']);p.add_argument('--output',required=True);a=p.parse_args()
 assets=json.loads((Path(__file__).parent/'assets.json').read_text());out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 for x in assets:
  if a.package!='all' and not x['name'].startswith('hengyue-v1-'+a.package+'-20261031'):continue
  target=out/x['name']
  if valid(target,x):print('Already verified',target);continue
  if target.exists():raise SystemExit('Archive hash mismatch; refusing overwrite: '+str(target))
  files=[]
  for part in x['parts']:
   final=out/part['name']
   if final.exists():
    if not valid(final,part):raise SystemExit('Part hash mismatch; refusing overwrite: '+str(final))
   else:
    partial=out/(part['name']+'.partial')
    print('Downloading',part['name'],flush=True)
    with urllib.request.urlopen(part['url'],timeout=120) as src,partial.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
    if not valid(partial,part):raise SystemExit('Downloaded part failed SHA256: '+str(partial))
    partial.rename(final)
   files.append(final)
  assembled=out/(x['name']+'.partial')
  with assembled.open('wb') as dst:
   for part in files:
    with part.open('rb') as src:shutil.copyfileobj(src,dst,1024*1024)
  if not valid(assembled,x):raise SystemExit('Assembled archive failed SHA256')
  assembled.rename(target);print('Verified',target,flush=True)
if __name__=='__main__':main()
