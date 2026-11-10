"""v6：v5 + 精确探针 + 说服层。无状态，只用本国观察。
说服层依据默认外交策略（aiwar/diplomacy_policy.py）的接受公式预测对方反应：
- 互不侵犯：对方 pressure≥0.7（≈有 ≥2 条接壤战线）或不接壤才接受 → 只在对方吃紧时提/续签，吃紧时提前续签。
- 停战：对方 pressure+0.6·min(2,我/它)+0.8(不接壤)−1.2(它只剩≤1场仗且整备好) ≥1.5 → 预测会过才提；
  对只和我们打的强邻提了也白提，改为防守等待它出现第二条战线。
- 宣战选"拖得住"的目标：目标 k 正和接壤的 j 打仗，且 j 只有这一场仗（按公式 j 会拒绝 k 的停战，k 的第二战线不会马上消失）。
  v5 教训：我们一宣战瓦兰迪亚，它压力骤增，0.1 天内就和西帝国停战，回头单挑我们。
- 被宣战风险：闲着（零战争）的接壤国若城数×100 ≥ 我方代理×1.1 就可能对我们宣战 → 优先在它有战事时锁互不侵犯。"""
import bat_core
from bat_core import dev20, dp, rel
import probe as pb

def info(obs):
    a=dp.assessment(obs); pr=pb.probe(obs); n=obs['nation']
    a['adj']=dict(pr['border'].get(n,{})); a['own_cities']=pr['land'].get(n,0); a['land']=pr['land']; a['probe']=pr
    return a

def sticky_front(pr,k,me):
    """k 的其他接壤战线中，'对方只和 k 打'（会拒绝 k 的停战）的国家"""
    return [j for j in pr['wars'][k] if j!=me and pr['border'][k].get(j) and set(pr['wars'][j])<= {k,me}]

def pick_target(obs,a,P):
    n=obs['nation']; pr=a['probe']; alive=[k for k in pr['live'] if k!=n]
    pref=P.get('directive_target')
    if pref in alive and a['adj'].get(pref): return pref
    gate=P.get('join_gate')   # (目标, 伙伴)：只在伙伴正与目标交战、且伙伴只有这一场仗（会拒绝目标求和）时加入
    if gate and gate[0] in alive:
        k,j=gate
        partner_locked = j in pr['live'] and rel(obs,j,k)=='war' and set(pr['wars'][j])<={k,n}
        if rel(obs,n,k)=='war' and partner_locked and a['adj'].get(k): return k
        if partner_locked and a['adj'].get(k) and pr['land'].get(k,0)<=a['own_cities']*P['gate_ratio']: return k
        if P.get('gate_exclusive'): return None
    cur=[k for k in alive if a['adj'].get(k) and rel(obs,n,k)=='war']
    if len(cur)==1: return cur[0]
    mine=a['own_cities']; cands=[]
    pu=P.get('protect_until',{}); protected=set(pu.get('nations',[])) if (pu and (pu.get('while_alive') is None or pu.get('while_alive') in alive)) else set()
    for k in alive:
        if not a['adj'].get(k) or (k in protected and pr['land'].get(k,0)>mine*P['weak_ratio']): continue
        lk=pr['land'].get(k,0); sf=sticky_front(pr,k,n); busy=[j for j in pr['wars'][k] if j!=n and pr['border'][k].get(j)]
        if (sf and lk<=mine*P['max_target_ratio']) or (busy and lk<=mine*P['busy_ratio']) or lk<=mine*P['weak_ratio']:
            cands.append((lk-a['adj'][k]-2*len(sf)-len(busy),k))
    return min(cands)[1] if cands else None

def our_proxy(a): return max(a['own_healthy'],a['own_cities']*100)

def decide_diplomacy(obs,P):
    d=obs.get('diplomacy',{})
    if not d.get('enabled'): return []
    n=obs['nation']; a=info(obs); pr=a['probe']; target=pick_target(obs,a,P); hour=obs['hour']; cmds=[]
    tb=bat_core.bloc(obs,target) if target is not None else set()
    incoming=[p for p in d.get('incoming',[]) if p.get('expires_hour',hour+1)>hour]
    outgoing=[p for p in d.get('outgoing',[]) if p.get('expires_hour',hour+1)>hour]
    losing=a['own_cities']<P['panic_cities'] or (target is not None and rel(obs,n,target)=='war' and pr['land'].get(target,0)>a['own_cities']*P['exit_ratio'])
    for p in sorted(incoming,key=lambda p:(p['created_hour'],p['id'])):
        k=p['from_nation']; kind=p['kind']
        if kind in ('peace','nap'): ok=(k not in tb) or losing
        else:
            their={j for j in pr['live'] if j not in (n,k) and rel(obs,k,j)=='war'}
            ok=target in their and not (their-set(a['wars'])) and dp.alliance_feasible(obs,k)
        cmds.append(dict(type='diplomacy',action='accept' if ok else 'reject',proposal_id=p['id'],reason=dict(v=P['name'],t=target)))
    if not d.get('decision_due'): return cmds
    busy={p['to_nation'] for p in outgoing}|{p['from_nation'] for p in incoming}
    opts=[]   # (优先级, 动作, 对象, 预测通过)
    me_proxy=our_proxy(a)
    for k in pr['live']:
        if k==n or k in busy: continue
        r=rel(obs,n,k); border=a['adj'].get(k,0); nap_ok=pb.est_nap_accept(pr,k,n)
        peace_s=pb.est_peace_score(pr,k,n,strength_other=me_proxy)
        if r=='war' and k not in tb:
            if border and nap_ok: opts.append((100+border+P.get('nap_bonus',{}).get(k,0),'propose_nap',k))
            elif peace_s>=1.5: opts.append((90+border,'propose_peace',k))
            else: opts.append((10+border,'propose_peace',k))      # 预测不过，只在无事可做时试
        elif r=='war' and k in tb and losing:
            opts.append((80 if peace_s>=1.5 else 5,'propose_peace',k))
        elif r in ('peace','nap') and k not in tb:
            t=pr['treaties'].get(tuple(sorted((n,k))))
            left=(t['expires_hour']-hour) if (t and t.get('kind')=='nap') else 0
            idle_threat=border and not pr['wars'][k] and pr['land'].get(k,0)*100>=me_proxy*1.1
            no_renew = P.get('join_gate') and k==P['join_gate'][0]   # 不续签将来要打的目标，否则宣不了战
            if nap_ok and left<P['renew_hours'] and not no_renew:
                opts.append(((70 if border else 30)+(15 if idle_threat else 0)+pr['land'].get(k,0)/10,'propose_nap',k))
    if target is not None and rel(obs,n,target)=='peace' and target not in busy and not a['wars'] \
            and a['readiness']>=P['declare_ready'] and a['food_days']>=P['declare_food']:
        opts.append((60,'declare_war',target))
    if opts:
        _,action,k=max(opts,key=lambda o:(o[0],-o[2]))
        cmds.append(dict(type='diplomacy',action=action,target=k,reason=dict(v=P['name'],t=target)))
    else:
        cmds.append(dict(type='diplomacy',action='hold',reason=dict(v=P['name'],t=target)))
    return cmds

def make(P):
    def decide(observation,previous_outcomes=None):
        if observation.get('mode')!='realmap' or not observation.get('diplomacy',{}).get('enabled'):
            return dev20.decide(observation,previous_outcomes)
        dip=decide_diplomacy(observation,P)[:100]
        mil=dev20.WesternPlanner(observation).run()
        return dip+dev20.bounded_military(mil,100-len(dip))
    return decide
