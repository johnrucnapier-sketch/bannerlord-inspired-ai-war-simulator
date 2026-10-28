"""Manifest-driven multi-host paired strategy study."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import traceback
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from aiwar.engine import World
from aiwar.policies import decide
from aiwar.metrics import peak_memory_mib


def write_json(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)


def run(job):
    seed,out,styles=job
    path=Path(out)/str(seed);path.mkdir(exist_ok=False)
    started=time.perf_counter();cpu=time.process_time()
    w=World(seed)
    assert w.cfg['days']==1680 and w.cfg['clan_party_cap']==3 and w.cfg.get('mode','duel')=='duel'
    errors=[Counter(),Counter()];examples=[];timeline=[];peak=0;decisions=0
    try:
        write_json(path/'progress.json',dict(seed=seed,hour=0,status='running'))
        while not w.result:
            if w.hour%w.cfg['decision_hours']==0:
                # Exactly the existing default cycle: simultaneous observations, order 0 then 1.
                observations=[w.observe(n) for n in (0,1)]
                batches=[decide(observations[n],styles[n]) for n in (0,1)]
                for n in (0,1):
                    for command in batches[n]:
                        r=w.command(n,command);decisions+=1
                        if not r['ok']:
                            errors[n][r['error']]+=1
                            if len(examples)<20:examples.append(dict(hour=w.hour,nation=n,command=command,error=r['error']))
            w.step()
            if w.hour%24==0:
                w.check();peak=max(peak,len(w.units))
            if w.hour%2016==0:
                timeline.append(dict(hour=w.hour,totals=w.observer_totals(),stats=w.stats.copy()))
                write_json(path/'progress.json',dict(seed=seed,hour=w.hour,status='running',seconds=round(time.perf_counter()-started,2),cities={n:sum(c['nation']==n for c in w.cities.values()) for n in (0,1)}))
        w.check()
        result=dict(seed=seed,styles=styles,status='complete',result=w.result,config=w.cfg,
                    seconds=round(time.perf_counter()-started,3),cpu_seconds=round(time.process_time()-cpu,3),
                    peak_memory_mib=peak_memory_mib(),peak_units=peak,command_count=decisions,
                    command_errors=[dict(e) for e in errors],error_examples=examples,
                    totals=w.observer_totals(),stats=w.stats,captures=w.history,timeline=timeline,
                    physics_digest=w.physics_digest())
        write_json(path/'result.json',result)
        write_json(path/'progress.json',dict(seed=seed,hour=w.hour,status='complete',result=w.result))
        return result
    except Exception:
        report=dict(seed=seed,status='failed',hour=w.hour,traceback=traceback.format_exc())
        write_json(path/'error.json',report);write_json(path/'progress.json',report)
        w.save(path/'failed.save.json')
        raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--host',choices=['mac','pc','rig'],required=True);p.add_argument('--output',required=True);a=p.parse_args()
    manifest=json.loads(Path(a.manifest).read_text(encoding='utf-8'))
    sources={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((ROOT/'aiwar').glob('*.py'))}
    sources['aiwar/config.json']=hashlib.sha256((ROOT/'aiwar/config.json').read_bytes()).hexdigest()
    assert sources==manifest['source_sha256'],'Source/config mismatch against predeclared manifest'
    styles=manifest['styles'];assert styles==['march_p5','march']
    workers=manifest['workers_per_host'][a.host]
    seeds=manifest['host_seeds'][a.host];assert seeds and len(set(seeds))==len(seeds)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    report=dict(status='running',host=a.host,workers=workers,expected_seeds=seeds,styles=styles,platform=platform.platform(),python=sys.version,source_sha256=sources,results=[],failures=[])
    write_json(out/'summary.json',report)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(run,(seed,str(out),styles)):seed for seed in seeds}
        for future in as_completed(futures):
            try:
                row=future.result();report['results'].append(row)
                print(json.dumps(dict(host=a.host,seed=row['seed'],result=row['result'],seconds=row['seconds']),ensure_ascii=False),flush=True)
            except Exception as exc:
                report['failures'].append(dict(seed=futures[future],error=repr(exc)))
                print('FAILED',futures[future],repr(exc),flush=True)
            report['seconds']=round(time.perf_counter()-started,3)
            write_json(out/'summary.json',report)
    report['status']='complete' if len(report['results'])==len(seeds) and not report['failures'] else 'failed'
    report['seconds']=round(time.perf_counter()-started,3);write_json(out/'summary.json',report)
    if report['status']!='complete':raise SystemExit(1)

if __name__=='__main__':main()
