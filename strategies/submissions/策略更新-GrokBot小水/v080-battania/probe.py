"""外交探针：只用本国私有观察。
- 国与国关系：observation.diplomacy.public_relations 是全矩阵（公开），treaties 是全体条约及到期时间，alliance_components 是全体同盟。
- 国家接壤：用观察里所有已知据点的坐标 + 同一静态地图包的 aiwar.real_map.mesh().neighbors()（与引擎建图同一函数）算出精确的据点邻接，
  再按我方所知的据点归属聚合到国家层面（外国据点归属可能过期 stale）。
- 估算他国在默认外交策略里的打分：战线数精确可算；整备、粮食、可见兵力不可见，用保守假设。"""
from functools import lru_cache

_ADJ={}
def city_adjacency(obs):
    key=tuple(sorted(c['id'] for c in obs.get('cities',[])))
    if key in _ADJ: return _ADJ[key]
    from aiwar.real_map import mesh
    cities={c['id']:dict(id=c['id'],x=c['x'],y=c['y']) for c in obs.get('cities',[])}
    links=mesh().neighbors(cities)
    _ADJ[key]={k:set(v) for k,v in links.items()}
    return _ADJ[key]

def relation(obs,a,b):
    if a==b: return 'self'
    m=obs.get('diplomacy',{}).get('public_relations',{})
    return m.get(str(a),{}).get(str(b),'war')

def probe(obs):
    n=obs['nation']; d=obs.get('diplomacy',{}); cities=obs.get('cities',[])
    owner={c['id']:c['nation'] for c in cities}
    live=sorted({int(k) for k in d.get('public_relations',{})}-set(obs.get('extinct_nations',[])))
    adj=city_adjacency(obs)
    border={k:{} for k in live}            # border[k][j] = 接壤段数（k 的据点数，其邻居属于 j）
    for cid,links in adj.items():
        k=owner.get(cid)
        if k not in border: continue
        for j in {owner.get(x) for x in links}:
            if j is not None and j>=0 and j!=k and j in border:
                border[k][j]=border[k].get(j,0)+sum(1 for x in links if owner.get(x)==j)
    land={k:sum(1 for c in cities if c['nation']==k) for k in live}
    rel={(a,b):relation(obs,a,b) for a in live for b in live if a<b}
    wars={k:[j for j in live if j!=k and relation(obs,k,j)=='war'] for k in live}
    fronts={k:sum(1 for j in wars[k] if border[k].get(j)) for k in live}
    treaties={}
    for key,t in d.get('treaties',{}).items():
        a,b=map(int,key.split(':')); treaties[(a,b)]=t
    blocs=[set(g) for g in d.get('alliance_components',[])]
    return dict(live=live,owner=owner,border=border,land=land,rel=rel,wars=wars,fronts=fronts,treaties=treaties,blocs=blocs)

def est_pressure(pr,k,assume_ready=.8,assume_food=20):
    """默认策略 pressure 的估计：只有战线项可精确计算，其余按假设（整备 .8、粮 20 天 → 0）。"""
    return max(0,pr['fronts'][k]-1)*1.4

def est_peace_score(pr,k,other,own_strength_k=None,strength_other=None,ready_k=.8,food_k=20):
    """k 对 other 的停战打分（默认策略 scores().peace 的复刻），≥1.5 即接受/提出。实力代理用城数×100。"""
    p=est_pressure(pr,k)
    ratio=(strength_other if strength_other is not None else pr['land'].get(other,0)*100)/max(1,own_strength_k if own_strength_k is not None else pr['land'].get(k,0)*100)
    s=p+min(2.,ratio)*.6+(.8 if not pr['border'][k].get(other) else 0)
    if len(pr['wars'][k])<=1 and ready_k>=.7 and food_k>=14: s-=1.2
    return s

def est_nap_accept(pr,k,other):
    return est_pressure(pr,k)>=.7 or not pr['border'][k].get(other)
