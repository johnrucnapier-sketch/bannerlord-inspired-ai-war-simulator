"""巴丹尼亚外交+战略原则（GrokBot小水）。军事层沿用 dev20_diplomacy_v080_rebuilt 的 Dev20 军事基线，
只替换外交决策。无状态：每次只看本国私有观察。参数 P 与唯一特殊战略指导 DIRECTIVE 由版本文件给出。"""
import importlib.util, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
_spec=importlib.util.spec_from_file_location('_dev20dip',ROOT/'strategies'/'submissions'/'dev20_diplomacy_v080_rebuilt'/'agent.py')
dev20=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(dev20)
from aiwar import diplomacy_policy as dp
rel=dp.relation

def info(obs):
    n=obs['nation']; a=dp.assessment(obs); cities=obs.get('cities',[])
    byid={c['id']:c for c in cities}
    own=[c for c in cities if c['nation']==n]
    adj={}
    for c in own:
        for i in c.get('neighbors',[]):
            k=byid.get(i,{}).get('nation',-1)
            if k>=0 and k!=n: adj[k]=adj.get(k,0)+1
    a['adj']=adj; a['own_cities']=len(own)
    return a

def pick_target(obs,a,P):
    """唯一主攻对象。指导优先，其次相邻国中 '城数小/接壤多' 的软目标。"""
    n=obs['nation']; alive=[k for k in a['nations'] if k!=n]
    pref=P.get('directive_target')
    if pref is not None and pref in alive and a['adj'].get(pref):
        return pref
    cands=[k for k in alive if a['adj'].get(k)]
    if not cands: return None
    def score(k):
        others_at_war=sum(1 for j in alive if j!=k and rel(obs,k,j)=='war')
        return (a['land'].get(k,99) - P['adj_weight']*a['adj'][k] - P['third_war_weight']*others_at_war, k)
    return min(cands,key=score)

def bloc(obs,k):
    return next((set(g) for g in obs['diplomacy'].get('alliance_components',[]) if k in g),{k})

def diplomacy_decide(obs,P):
    d=obs.get('diplomacy',{})
    if not d.get('enabled'): return []
    n=obs['nation']; a=info(obs); target=pick_target(obs,a,P); cmds=[]
    tb=bloc(obs,target) if target is not None else set()
    hour=obs['hour']
    incoming=[p for p in d.get('incoming',[]) if p.get('expires_hour',hour+1)>hour]
    outgoing=[p for p in d.get('outgoing',[]) if p.get('expires_hour',hour+1)>hour]
    losing=a['own_cities']<P['panic_cities']
    for p in sorted(incoming,key=lambda p:(p['created_hour'],p['id'])):
        k=p['from_nation']; kind=p['kind']
        if kind in ('peace','nap'):
            ok = (k not in tb) or losing
        else:  # alliance：只接受与我共同打主攻目标、且不额外带来新战争的盟约
            promised=set(p.get('promised_blocs',{}).get(str(k),[])) if isinstance(p.get('promised_blocs'),dict) else bloc(obs,k)
            their_wars={j for j in a['nations'] if j not in (n,k) and rel(obs,k,j)=='war'}
            imported=their_wars-set(a['wars'])
            ok = P['allow_alliance'] and target in their_wars and not imported and dp.alliance_feasible(obs,k)
        cmds.append(dict(type='diplomacy',action='accept' if ok else 'reject',proposal_id=p['id'],reason=dict(v=P['name'],target=target)))
    if not d.get('decision_due'): return cmds
    busy={p['to_nation'] for p in outgoing}|{p['from_nation'] for p in incoming}
    wars=[k for k in a['wars'] if k not in tb]
    choice=None
    # 原则1：除主攻目标外，对所有交战国求和；先求和于接壤多/城多的威胁
    peace_c=[k for k in wars if k not in busy]
    if peace_c:
        k=max(peace_c,key=lambda k:(a['adj'].get(k,0),a['land'].get(k,0),-k))
        choice=('propose_peace',k)
    # 原则2：主攻目标不在战争状态时，条件成熟就宣战（不对已有NAP宣战）
    elif target is not None and rel(obs,n,target)=='peace' and target not in busy \
            and a['readiness']>=P['declare_ready'] and a['food_days']>=P['declare_food']:
        choice=('declare_war',target)
    # 原则3：后方接壤国签互不侵犯，锁住背后（不对下一个目标签）
    else:
        rear=[k for k in a['nations'] if k!=n and k not in tb and k not in busy and a['adj'].get(k)
              and rel(obs,n,k)=='peace' and P['rear_nap']]
        if rear:
            choice=('propose_nap',max(rear,key=lambda k:(a['adj'][k],-k)))
    if choice:
        cmds.append(dict(type='diplomacy',action=choice[0],target=choice[1],reason=dict(v=P['name'],target=target)))
    else:
        cmds.append(dict(type='diplomacy',action='hold',reason=dict(v=P['name'],target=target)))
    return cmds

def make(P):
    def decide(observation,previous_outcomes=None):
        if observation.get('mode')!='realmap' or not observation.get('diplomacy',{}).get('enabled'):
            return dev20.decide(observation,previous_outcomes)
        dip=diplomacy_decide(observation,P)[:100]
        mil=dev20.WesternPlanner(observation).run()
        return dip+dev20.bounded_military(mil,100-len(dip))
    return decide
