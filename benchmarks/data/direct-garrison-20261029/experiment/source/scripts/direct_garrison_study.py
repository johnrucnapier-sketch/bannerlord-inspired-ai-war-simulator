"""D2 versus default under shared direct-to-garrison rules."""
import argparse,json,hashlib,sys,time,platform
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.escort_p5_defense_v2_study import run,write

def hashes():
 files=list((ROOT/'aiwar').glob('*.py'))+[ROOT/'aiwar/config.json']+[ROOT/'scripts'/f for f in ('transport_growth_policy.py','transport_triple_policy.py','escort_p5_defense_policy.py','escort_p5_defense_v2_policy.py','escort_p5_defense_v2_study.py','direct_garrison_study.py')]
 return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--host',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 m=json.loads(Path(a.manifest).read_text());assert hashes()==m['source_sha256'];out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
 jobs=[j for j in m['jobs'] if j['host']==a.host];start=time.perf_counter();report=dict(status='running',host=a.host,source_sha256=hashes(),python=sys.version,platform=platform.platform(),results=[],failures=[])
 write(out/'summary.json',report)
 with ProcessPoolExecutor(max_workers=m['workers'][a.host]) as pool:
  fs={pool.submit(run,(j,str(out))):j for j in jobs}
  for f in as_completed(fs):
   try:report['results'].append(f.result())
   except Exception as e:report['failures'].append(dict(job=fs[f],error=repr(e)))
   report['seconds']=time.perf_counter()-start;write(out/'summary.json',report);print(json.dumps(dict(done=len(report['results']),failed=len(report['failures']),total=len(jobs))),flush=True)
 report['status']='complete' if not report['failures'] else 'failed';write(out/'summary.json',report)
if __name__=='__main__':main()
