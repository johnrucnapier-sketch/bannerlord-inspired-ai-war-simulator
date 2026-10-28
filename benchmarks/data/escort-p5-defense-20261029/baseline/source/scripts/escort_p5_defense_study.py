"""Paired D1 versus unchanged march; common current engine, 20-year limit."""
import argparse,json,hashlib,sys,time,platform
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from aiwar.engine import World
from aiwar.policies import decide
from scripts.escort_p5_defense_policy import Controller

def write(path,value):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(path)
def hashes():
 files=list((ROOT/'aiwar').glob('*.py'))+[ROOT/'aiwar/config.json']+[ROOT/'scripts'/f for f in ('transport_growth_policy.py','transport_triple_policy.py','escort_p5_defense_policy.py','escort_p5_defense_study.py')]
 return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
def run(args):
 job,out=args;path=Path(out)/job['id'];path.mkdir();start=time.perf_counter()
 w=World(job['seed']);c=Controller();errors=[Counter(),Counter()];examples=[];timeline=[]
 try:
  while not w.result:
   obs=[w.observe(n) for n in (0,1)]
   cmds=[c.decide(obs[0]) if job['style']=='d1' else decide(obs[0],'march'),decide(obs[1],'march')]
   for n in (0,1):
    for cmd in cmds[n]:
     r=w.command(n,cmd)
     if not r['ok']:
      errors[n][r['error']]+=1
      if len(examples)<20:examples.append(dict(hour=w.hour,nation=n,command=cmd,error=r['error']))
      if n==0 and job['style']=='d1':raise RuntimeError((w.hour,cmd,r))
   w.step(6)
   if w.hour%24==0:w.check()
   if w.hour%2016==0:
    timeline.append(dict(hour=w.hour,totals=w.observer_totals(),bandits=sum(u['kind']=='bandit' for u in w.units.values()),switched=len(c.switched),missions=len(c.missions)))
    write(path/'progress.json',dict(hour=w.hour))
  row=dict(job=job,status='complete',result=w.result,totals=w.observer_totals(),seconds=time.perf_counter()-start,command_errors=[dict(x) for x in errors],error_examples=examples,timeline=timeline,phase_events=c.phase_events,war_events=c.war_events,upgrades=c.upgrade_events,physics_digest=w.physics_digest(),config=w.cfg)
  write(path/'result.json',row);return row
 except Exception:
  import traceback
  write(path/'error.json',dict(hour=w.hour,traceback=traceback.format_exc()));w.save(path/'failed.save.json');raise

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
