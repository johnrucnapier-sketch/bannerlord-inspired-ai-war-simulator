"""验证探针：默认策略八国跑 N 天，每 7 天对比巴丹尼亚观察推出的视图与引擎真值。"""
import sys,json,importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]; ENG=ROOT/'training'/'realmap-v0.8.0-rebuilt'
sys.path.insert(0,str(ENG)); sys.path.insert(0,str(HERE))
import harness; harness.speedup()
from aiwar.sdk import Environment
from aiwar import diplomacy, diplomacy_policy as dp
import probe, bat_core
spec=importlib.util.spec_from_file_location('d20',ROOT/'strategies/submissions/dev20_diplomacy_v080_rebuilt/agent.py'); d20=importlib.util.module_from_spec(spec); spec.loader.exec_module(d20)
seed=int(sys.argv[1]); days=int(sys.argv[2]); B=4
env=Environment(seed,dict(mode='realmap',diplomacy_enabled=True,days=1680)); obs=env.reset(seed); w=env.world
true_adj={cid:set(c['neighbors']) for cid,c in w.cities.items()}
rows=[]
step=0
while w.hour<days*24:
    if w.hour%(7*24)==0:
        o=obs[B]; pr=probe.probe(o)
        live=sorted(diplomacy.live(w))
        rel_ok=sum(pr['rel'][(a,b)]==w.relations[str(a)][str(b)] for a in live for b in live if a<b); rel_n=len(live)*(len(live)-1)//2
        st=diplomacy.state(w)['treaties']
        tr_ok=(set(st)=={f'{a}:{b}' for a,b in pr['treaties']}) and all(pr['treaties'][tuple(map(int,k.split(':')))]==v for k,v in st.items())
        al_ok=sorted(map(sorted,pr['blocs']))==sorted(map(sorted,diplomacy.components(w)))
        cadj=probe.city_adjacency(o); cadj_ok=sum(cadj[c]==true_adj[c] for c in true_adj)
        own_ok=sum(pr['owner'][cid]==c['nation'] for cid,c in w.cities.items())
        # 真实国家层接壤
        tb={k:set() for k in live}
        for cid,c in w.cities.items():
            for x in c['neighbors']:
                a,b=c['nation'],w.cities[x]['nation']
                if a!=b and a in tb and b in tb: tb[a].add(b)
        nb_ok=sum((bool(pr['border'][a].get(b)))==(b in tb[a]) for a in live for b in live if a!=b); nb_n=len(live)*(len(live)-1)
        # 旧方法 supply_neighbors+distracted 的国家邻接
        old_ok=0
        byid={c['id']:c for c in o['cities']}
        for a in live:
            kn=set()
            for c in o['cities']:
                if c['nation']==a:
                    for i in set(c.get('neighbors',[]))|set(c.get('supply_neighbors',[])): kn.add(byid.get(i,{}).get('nation',-1))
            for b in live:
                if b!=a: old_ok+=((b in kn)==(b in tb[a]))
        # 他国真实 pressure / 对巴丹尼亚停战打分（用它们自己的观察跑默认策略函数）
        perr=[];serr=[];agree=0;cnt=0
        for k in live:
            if k==B: continue
            ak=dp.assessment(obs[k]); true_p=ak['pressure']; perr.append(abs(probe.est_pressure(pr,k)-true_p))
            true_s=dp.scores(obs[k],ak,B)['peace']; est_s=probe.est_peace_score(pr,k,B)
            serr.append(abs(est_s-true_s)); agree+=((est_s>=1.5)==(true_s>=1.5)); cnt+=1
        rows.append(dict(day=w.hour//24,rel=f'{rel_ok}/{rel_n}',treaties_exact=tr_ok,alliances_exact=al_ok,city_adj=f'{cadj_ok}/120',
                         owner=f'{own_ok}/120',nation_border_new=f'{nb_ok}/{nb_n}',nation_border_old=f'{old_ok}/{nb_n}',
                         pressure_mae=round(sum(perr)/len(perr),2),peace_score_mae=round(sum(serr)/len(serr),2),peace_accept_agree=f'{agree}/{cnt}'))
        print(rows[-1],flush=True)
    acts=[d20.decide(obs[n],None) for n in w.nation_ids()]
    harness.fast_step(env,acts); obs=env.observations()
json.dump(rows,open(HERE/'res'/f'probe_validation_s{seed}.json','w'),ensure_ascii=False,indent=1)
