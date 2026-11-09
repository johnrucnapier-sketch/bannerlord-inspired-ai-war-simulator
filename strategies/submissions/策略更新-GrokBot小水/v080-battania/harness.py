"""单种子八国外交对局（v0.8.0-rebuilt）。巴丹尼亚(nation 4)用指定策略，其余7国用默认外交实验策略
dev20_diplomacy_v080_rebuilt。一次只跑一个模拟；8国策略在8个常驻进程里并行计算（多核加速单局）。
用法: python harness.py <battania_module|default> <seed> --days 1680 --out res/x"""
import argparse, json, multiprocessing as mp, sys, time, importlib.util, os
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]
ENG=ROOT/'training'/'realmap-v0.8.0-rebuilt'
sys.path.insert(0,str(ENG))
DEFAULT=ROOT/'strategies'/'submissions'/'dev20_diplomacy_v080_rebuilt'/'agent.py'
BATTANIA=4

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def speedup():
    # 纯函数记忆化，仅在策略进程内生效：路线结果完全相同，不改任何规则
    from aiwar import real_map
    orig_local=real_map.local_path; cache={}
    def local_path(poly,a,b):
        k=(id(poly),tuple(a),tuple(b)); r=cache.get(k)
        if r is None:
            if len(cache)>400000: cache.clear()
            r=orig_local(poly,a,b); cache[k]=r if r is not None else False
        return None if r is False else [list(x) for x in r]
    real_map.local_path=local_path

def worker(conn,path):
    sys.path.insert(0,str(ENG)); sys.path.insert(0,str(HERE))
    speedup()
    m=load(path,'pol_'+Path(path).stem)
    prev=None
    while True:
        obs=conn.recv()
        if obs is None: break
        try: cmds=m.decide(obs,prev)[:100]; err=None
        except Exception as e:
            import traceback; cmds=[]; err=traceback.format_exc()[-800:]
        conn.send((cmds,err))

def fast_step(env,actions):
    # 与 Environment.step 相同的命令/外交/推进顺序，只省掉回放用的 before 观察快照
    from aiwar.sdk import command_error
    from aiwar import diplomacy
    import json as _j
    actions=_j.loads(_j.dumps(actions,allow_nan=False))
    outcomes=[[] for _ in env.world.nation_ids()]
    for n in env.world.nation_ids():
        for cmd in actions[n]:
            e=command_error(cmd)
            outcomes[n].append({'ok':False,'error':e} if e else env.world.command(n,cmd))
    dr=diplomacy.resolve(env.world)
    env.world.step(env.world.cfg['decision_hours'])
    done=env.world.result is not None
    return dict(observations=env.observations() if not done else None,outcomes=outcomes,terminated=done,diplomatic_results=dr)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('policy'); ap.add_argument('seed',type=int)
    ap.add_argument('--days',type=int,default=1680); ap.add_argument('--out',required=True)
    a=ap.parse_args()
    from aiwar.sdk import Environment
    from aiwar import diplomacy
    cfg=dict(mode='realmap',diplomacy_enabled=True,days=a.days)
    env=Environment(a.seed,cfg); obs=env.reset(a.seed)
    names=[obs[0]['nations'][str(i)]['kingdom'] for i in range(8)]
    assert names[BATTANIA]=='battania',names
    bpath=DEFAULT if a.policy=='default' else HERE/(a.policy+'.py')
    paths=[str(bpath if n==BATTANIA else DEFAULT) for n in range(8)]
    ctx=mp.get_context('fork'); pipes=[]; procs=[]
    for p in paths:
        c1,c2=ctx.Pipe(); pr=ctx.Process(target=worker,args=(c2,p),daemon=True); pr.start(); pipes.append(c1); procs.append(pr)
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    yearly=[]; dlog=[]; errors=[0]*8; invalid=[0]*8; t0=time.time(); step=0
    def snap():
        w=env.world; tot=w.observer_totals()
        rel={f'{i}-{j}':w.relations[str(i)][str(j)] for i in range(8) for j in range(i+1,8) if i in diplomacy.live(w) and j in diplomacy.live(w)}
        return dict(day=w.hour//24,cities=[t['cities'] for t in tot],healthy=[t['healthy'] for t in tot],field=[t['field'] for t in tot],
                    armies=[t['armies'] for t in tot],extinct=list(w.extinct_nations),
                    blocs=[c for c in diplomacy.components(w) if len(c)>1],
                    wars_of_battania=[j for j in range(8) if j!=4 and str(j) in w.relations.get('4',{}) and w.relations['4'][str(j)]=='war' and j in diplomacy.live(w)],
                    rel=rel,elapsed=round(time.time()-t0,1))
    yearly.append(snap())
    while True:
        live=env.world.nation_ids()
        for n in live: pipes[n].send(obs[n])
        acts=[]
        for n in live:
            cmds,err=pipes[n].recv()
            if err:
                errors[n]+=1
                if errors[n]<=3: print('ERR',n,err,file=sys.stderr)
            acts.append(cmds)
        r=fast_step(env,acts); obs=r['observations']; step+=1
        for n,oc in enumerate(r['outcomes']):
            invalid[n]+=sum(1 for o in oc if not o.get('ok'))
        for d in r.get('diplomatic_results',[]):
            if d.get('status') in ('accepted','applied','executed','ok','success') or d.get('action') not in ('hold',):
                if d.get('action')!='hold': dlog.append({k:d.get(k) for k in ('hour','nation','action','status','target','proposal_id','kind','reason') if k!='reason' or isinstance(d.get(k),str)})
        h=env.world.hour
        if h%(84*24)==0 or r['terminated']:
            s=snap(); yearly.append(s)
            print(f"y{h/(84*24):.1f} t={s['elapsed']}s cities={s['cities']} blocs={s['blocs']} B-wars={s['wars_of_battania']} ext={s['extinct']}",flush=True)
        if r['terminated']: break
    for p in pipes: p.send(None)
    res=dict(policy=a.policy,seed=a.seed,days=a.days,result=env.world.result,yearly=yearly,errors=errors,invalid=invalid,
             wall_seconds=round(time.time()-t0,1),diplomacy_events=dlog,captures=env.world.history[-3000:] if isinstance(env.world.history,list) else None,
             names=names)
    out.with_suffix('.json').write_text(json.dumps(res,ensure_ascii=False))
    print('DONE',json.dumps(env.world.result,ensure_ascii=False),'wall',res['wall_seconds'])
if __name__=='__main__': main()
