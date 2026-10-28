import argparse
import json
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from .engine import World
from .policies import decision_cycle
from .agents import PolicyPool
from .metrics import peak_memory_mib


def run_one(args):
    seed,days,styles,verify,isolated,*modes=args
    mode=modes[0] if modes else 'duel'
    w=World(seed,{'days':days,'mode':mode})
    start=time.perf_counter()
    cpu_start=time.process_time()
    pool=PolicyPool(styles=styles) if isolated else None
    while not w.result:
        if w.hour%w.cfg['decision_hours']==0:
            pool.cycle(w) if pool else decision_cycle(w,styles)
        w.step()
        if verify and w.hour%24==0:
            w.check()
    if pool: pool.close()
    elapsed=time.perf_counter()-start
    return {'seed':seed,'result':w.result,'seconds':round(elapsed,4),
            'process_cpu_seconds':round(time.process_time()-cpu_start,4),'peak_memory_mib':peak_memory_mib(),
            'hours_per_second':round(w.hour/elapsed,1),'digest':w.digest(),'physics_digest':w.physics_digest(),
            'stats':w.stats,'captures':len(w.history),'units':len(w.units)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['duel','rural'],default='duel')
    p.add_argument('--days',type=int,default=1680)
    p.add_argument('--seed',type=int,default=1)
    p.add_argument('--games',type=int,default=1)
    p.add_argument('--workers',type=int,default=1)
    p.add_argument('--styles',nargs=2,default=['march','march'],choices=['march','guard','manual','p1','p2','p3','p4','p5','march_p5','w1','w2','w3','w4'])
    p.add_argument('--check',action='store_true')
    p.add_argument('--isolated',action='store_true',help='Run policy controllers in separate processes')
    p.add_argument('--output',default='artifacts/benchmark.json')
    a=p.parse_args()
    jobs=[(a.seed+i,a.days,a.styles,a.check,a.isolated,a.mode) for i in range(a.games)]
    start=time.perf_counter()
    if a.workers==1:
        results=[run_one(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=a.workers) as pool:
            results=list(pool.map(run_one,jobs))
    report={'wall_seconds':round(time.perf_counter()-start,3),'workers':a.workers,'games':results}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
