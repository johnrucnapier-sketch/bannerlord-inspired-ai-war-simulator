"""Frozen-seed, observation-only patrol candidates with diagnostic traces."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from aiwar.engine import World
from scripts.patrol_candidates import decide as candidate_decide, distance
from aiwar.patrols import decide as production_decide

def decide(obs,style):
    return production_decide(obs,style) if style in ("p3","p5") else candidate_decide(obs,style)


def run(job):
    seed,style,out,trace=job
    w=World(seed,{'mode':'rural'})
    errors=Counter();losses=Counter();coverage=Counter();activities=Counter();route_starts=Counter()
    path=Path(out)/f'{style}-{seed}'
    path.mkdir()
    log=(path/'trace.jsonl').open('w') if trace else None
    last_event=0;peak=0;loss_dist=[];loss_chasing=0
    while not w.result:
        if w.hour%6==0:
            obs=w.observe(0)
            for cmd in decide(obs,style):
                r=w.command(0,cmd)
                if not r['ok']:errors[r['error']]+=1
                if cmd.get('patrol_style')=='p3':route_starts[str(cmd['patrol_index'])]+=1
            for u in w.units.values():
                if u['kind']=='party':
                    activities['battle' if u['battle'] else 'return' if (u.get('order') or {}).get('patrol_return') else (u.get('order') or {}).get('type','idle')]+=1
        before={u['id']:dict(u) for u in w.units.values() if u['kind']=='village_cart'}
        w.step()
        for event in w.events:
            if event['id']<=last_event:continue
            if log:log.write(json.dumps(event,ensure_ascii=False)+'\n')
            if event['kind']=='transport_lost' and event['unit'] in before:
                cart=before[event['unit']];losses[cart['home']]+=1
                parties=[u for u in w.units.values() if u['kind']=='party']
                near=min(parties,key=lambda u:distance(u,cart)) if parties else None
                if near:
                    loss_dist.append(distance(near,cart))
                    loss_chasing+=((near.get('order') or {}).get('type')=='attack')
                if log:log.write(json.dumps(dict(kind='loss_context',hour=w.hour,village=cart['home'],nearest_party=near,cart=cart),ensure_ascii=False)+'\n')
        last_event=w.event_seq
        if w.hour%24==0:
            w.check()
            ps=[u for u in w.units.values() if u['kind']=='party'];peak=max(peak,len(ps))
            for v in w.villages.values():
                if any(distance(v,u)<=8000 for u in ps):coverage[v['id']]+=1
            if log:log.write(json.dumps(dict(kind='daily_score',hour=w.hour,score=w.rural_score()),ensure_ascii=False)+'\n')
    if log:log.close()
    w.save(path/'final.save.json')
    result=dict(seed=seed,style=style,score=w.rural_score(),stats=w.stats,errors=dict(errors),peak_parties=peak,
                digest=w.physics_digest(),losses_by_village=dict(losses),covered_days=dict(coverage),
                activity_samples=dict(activities),route_starts=dict(route_starts),
                losses_nearest_chasing=loss_chasing,
                loss_nearest_mean=sum(loss_dist)/len(loss_dist) if loss_dist else 0)
    (path/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--styles',nargs='+',default=['p3','p3_resume','p3_outer','p3_strong'])
    p.add_argument('--seeds',nargs='+',type=int,default=[1]);p.add_argument('--output',required=True);p.add_argument('--trace',action='store_true');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    source=out/'source';source.mkdir()
    for file in (ROOT/'aiwar').glob('*.py'):(source/file.name).write_bytes(file.read_bytes())
    for file in (Path(__file__),ROOT/'scripts/patrol_candidates.py'):(source/file.name).write_bytes(file.read_bytes())
    results=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(run,(seed,style,str(out),a.trace)) for seed in a.seeds for style in a.styles]):
            r=future.result();results.append(r)
            print(json.dumps({k:r[k] for k in ('seed','style','score','errors','peak_parties')},ensure_ascii=False),flush=True)
            (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
