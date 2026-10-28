"""Frozen-manifest curriculum runner: training / validation / untouched holdout."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from aiwar.engine import World
from aiwar.policies import decide
from aiwar.patrols import decide as patrol
from aiwar.warfare import city_risks


def write(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)


def run(args):
    job,out=args;path=Path(out)/job['id'];path.mkdir(exist_ok=False)
    start=time.perf_counter();w=World(job['seed'],{'clan_party_cap':job['cap'],'mode':job.get('mode','duel')})
    errors=[Counter(),Counter()];risk_hours=Counter();rescue_decisions=0;timeline=[]
    try:
        while not w.result:
            observations=[w.observe(n) for n in (0,1)]
            for n in (0,1):
                if n==1 and w.cfg.get('mode')=='rural':continue
                style=job['styles'][n]
                cmds=patrol(observations[n],style) if style=='p5_eta' else decide(observations[n],style)
                rescue_decisions+=sum(c.get('campaign_phase')=='economy_relief' for c in cmds)
                for c in cmds:
                    answer=w.command(n,c)
                    if not answer['ok']:errors[n][answer['error']]+=1
            w.step(6)
            if w.hour%24==0:w.check()
            if w.hour%168==0:
                for n in (0,1):
                    if n==1 and w.cfg.get('mode')=='rural':continue
                    for r in city_risks(w.observe(n)).values():risk_hours[str(n)+':'+r['state']]+=168
            if w.hour%2016==0:
                timeline.append(dict(hour=w.hour,totals=w.observer_totals()))
                write(path/'progress.json',dict(id=job['id'],hour=w.hour,status='running'))
        w.check()
        result=dict(job=job,status='complete',seconds=time.perf_counter()-start,result=w.result,
                    totals=w.observer_totals(),physics_digest=w.physics_digest(),command_errors=[dict(e) for e in errors],
                    sampled_city_risk_hours=dict(risk_hours),rescue_commands=rescue_decisions,timeline=timeline)
        write(path/'result.json',result);write(path/'progress.json',dict(id=job['id'],hour=w.hour,status='complete'))
        return result
    except Exception:
        import traceback
        write(path/'error.json',dict(job=job,hour=w.hour,traceback=traceback.format_exc()))
        w.save(path/'failed.save.json');raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--host',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    m=json.loads(Path(a.manifest).read_text(encoding='utf-8'))
    hashes={str(f.relative_to(ROOT).as_posix()):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((ROOT/'aiwar').glob('*.py'))}
    hashes['aiwar/config.json']=hashlib.sha256((ROOT/'aiwar/config.json').read_bytes()).hexdigest()
    assert hashes==m['source_sha256']
    jobs=[j for j in m['jobs'] if j['host']==a.host];assert jobs
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
    report=dict(host=a.host,python=sys.version,platform=platform.platform(),status='running',source_sha256=hashes,results=[],failures=[],workers=m['workers'][a.host])
    write(out/'summary.json',report)
    with ProcessPoolExecutor(max_workers=m['workers'][a.host]) as pool:
        futures={pool.submit(run,(j,str(out))):j for j in jobs}
        for f in as_completed(futures):
            try:report['results'].append(f.result())
            except Exception as e:report['failures'].append(dict(job=futures[f],error=repr(e)))
            report['seconds']=time.perf_counter()-start;write(out/'summary.json',report)
            print(json.dumps(dict(host=a.host,done=len(report['results']),failed=len(report['failures']),total=len(jobs))),flush=True)
    report['status']='complete' if len(report['results'])==len(jobs) and not report['failures'] else 'failed'
    report['seconds']=time.perf_counter()-start;write(out/'summary.json',report)
    if report['status']!='complete':raise SystemExit(1)


if __name__=='__main__':main()
