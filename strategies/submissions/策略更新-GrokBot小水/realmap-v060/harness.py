"""North(1)=custom agent vs West(0)=builtin style. In-process, no engine changes."""
import sys,json,time,importlib,argparse
from pathlib import Path
RM=Path(__file__).resolve().parents[4]/'training/realmap-v0.6.0'
sys.path.insert(0,str(RM));sys.path.insert(0,str(Path(__file__).parent))
from aiwar.engine import World
from aiwar.policies import decide as builtin
def run(seed,agent,west='vanilla_v1',days=None,log_every=60):
    w=World(seed,{'mode':'realmap',**({'days':days} if days else {})})
    mod=importlib.import_module(agent) if agent not in('vanilla_v1','march') else None
    tl=[];errs=0;t=time.time()
    while not w.result:
        if w.hour%w.cfg['decision_hours']==0:
            o0=w.observe(0);o1=w.observe(1)
            c0=builtin(o0,west)
            try:c1=mod.decide(o1) if mod else builtin(o1,agent)
            except Exception as e:
                errs+=1;c1=[]
                if errs<3:import traceback;traceback.print_exc()
            for c in c0[:100]:w.command(0,c)
            for c in c1[:100]:w.command(1,c)
        w.step()
        if w.hour%(24*log_every)==0:
            cnt={0:0,1:0}
            for c in w.cities.values() if isinstance(w.cities,dict) else w.cities:cnt[c['nation']]=cnt.get(c['nation'],0)+1
            tl.append((w.hour//24,cnt[0],cnt[1]))
    return dict(seed=seed,agent=agent,west=west,result=w.result,timeline=tl,history=[(h['hour']//24,w.cities[h['city']]['name'],h['from'],h['to']) for h in w.history],army=sum(u['healthy'] for u in w.units.values() if u['nation']==1 and u['kind']=='party'),army0=sum(u['healthy'] for u in w.units.values() if u['nation']==0 and u['kind']=='party'),errors=errs,sec=round(time.time()-t),stats=w.stats)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('agent');p.add_argument('seed',type=int);p.add_argument('--west',default='vanilla_v1');p.add_argument('--days',type=int);p.add_argument('--out')
    a=p.parse_args();r=run(a.seed,a.agent,a.west,a.days)
    s=json.dumps(r,ensure_ascii=False)
    if a.out:Path(a.out).parent.mkdir(parents=True,exist_ok=True);Path(a.out).write_text(s)
    print(r['agent'],r['west'],r['seed'],r['result'],r['timeline'],r['errors'],r['sec'])
