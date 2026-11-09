"""分阶段战略（v3 起）：原则 + 唯一特殊指导（先灭瓦兰迪亚，仅在它另有战事时进攻，否则防守）。
无状态：阶段由当前私有观察推出。姿态通过过滤军事层命令实现，不改引擎。"""
from bat_core import dev20, dp, rel, info, distracted

VL, WEST, NORTH, STURGIA = 5, 0, 1, 6

def phase(obs,a,P):
    n=obs['nation']; alive=set(a['nations'])
    if VL in alive: return 1
    second=max([a['land'].get(k,0) for k in alive if k!=n] or [0])
    if STURGIA in alive and a['adj'].get(STURGIA) and a['own_cities']<P['p3_cities'] and not (a['own_cities']>=P['p3_lead']*second):
        return 2
    return 3

def plan(obs,P):
    """返回 (phase, target, offensive, wanted_war)"""
    n=obs['nation']; a=info(obs); ph=phase(obs,a,P); alive=[k for k in a['nations'] if k!=n]
    wars=[k for k in a['wars']]
    target=None; offensive=False
    if ph==1:
        target=VL
        others_busy=[j for j in distracted(obs,a,VL)]
        offensive = bool(others_busy) and set(wars)<= {VL}
    elif ph==2:
        target=STURGIA
        ok = bool(distracted(obs,a,STURGIA)) or a['land'].get(STURGIA,0)<=a['own_cities']*P['p2_ratio']
        offensive = set(wars)<= {STURGIA} and (ok or rel(obs,n,STURGIA)=='war')
    else:
        # 均势期：只对"正与别国交战、且明显比我小"的接壤国做有限的趁火打劫；不打最大的国家，不吃掉只剩很少城的国家（保持四强格局）
        biggest=max(alive,key=lambda k:(a['land'].get(k,0),-k)) if alive else None
        cur=[k for k in wars if a['adj'].get(k)]
        if len(cur)==1: target=cur[0]
        else:
            c=[k for k in alive if a['adj'].get(k) and k!=biggest and distracted(obs,a,k)
               and a['land'].get(k,0)<=a['own_cities']*P['p3_ratio'] and a['land'].get(k,0)>=P['p3_min_victim']]
            target=min(c,key=lambda k:(a['land'].get(k,0),k)) if c else None
        offensive = target is not None and set(wars)<={target}
    return ph,a,target,offensive

def diplomacy(obs,P,ph,a,target,offensive):
    d=obs.get('diplomacy',{}); n=obs['nation']; hour=obs['hour']; cmds=[]
    incoming=[p for p in d.get('incoming',[]) if p.get('expires_hour',hour+1)>hour]
    outgoing=[p for p in d.get('outgoing',[]) if p.get('expires_hour',hour+1)>hour]
    wars=a['wars']
    for p in sorted(incoming,key=lambda p:(p['created_hour'],p['id'])):
        k=p['from_nation']; kind=p['kind']
        if kind in ('peace','nap'):
            if k!=target: ok=True
            elif ph==1: ok = not offensive and kind=='peace'    # 不能对瓦兰迪亚签互不侵犯（否则无法再宣战）
            elif ph==2: ok = not offensive and kind=='peace'
            else: ok = kind=='peace'                            # 均势期：有限战争，对方求和就收手
            if a['own_cities']<P['panic_cities']: ok=True
        else:
            ok=False  # 同盟会同步战争，一律不入
        cmds.append(dict(type='diplomacy',action='accept' if ok else 'reject',proposal_id=p['id'],reason=dict(v=P['name'],ph=ph,t=target)))
    if not d.get('decision_due'): return cmds
    busy={p['to_nation'] for p in outgoing}|{p['from_nation'] for p in incoming}
    choice=None
    # 1 除目标外的战争：先对接壤国直接提互不侵犯（战争中对方压力大，最容易接受，还能挡宣战），否则求和
    extra=[k for k in wars if k!=target and k not in busy]
    if extra:
        k=max(extra,key=lambda k:(a['adj'].get(k,0),a['land'].get(k,0),-k))
        choice=('propose_nap' if a['adj'].get(k) and P['nap_first'] else 'propose_peace',k)
    # 2 与目标交战但不该进攻（另有敌人/目标不分心）：求和
    elif target is not None and target in wars and not offensive and target not in busy and (ph>1 or P['p1_seek_peace']):
        choice=('propose_peace',target)
    # 3 目标在和平状态且时机成熟：宣战
    elif target is not None and rel(obs,n,target)=='peace' and offensive and target not in busy \
            and a['readiness']>=P['declare_ready'] and a['food_days']>=P['declare_food']:
        choice=('declare_war',target)
    else:
        # 4 续签/新签互不侵犯：所有非目标国，接壤国优先，快到期的优先
        tr=d.get('treaties',{})
        def expiry(k):
            t=tr.get(':'.join(map(str,sorted((n,k)))))
            return t['expires_hour'] if t and t.get('kind')=='nap' else -1
        c=[k for k in a['nations'] if k not in (n,target) and k not in busy and rel(obs,n,k) in ('peace','nap')
           and (rel(obs,n,k)=='peace' or expiry(k)-hour<P['renew_hours'])]
        if c:
            k=max(c,key=lambda k:(bool(a['adj'].get(k)),-expiry(k) if expiry(k)>=0 else 10**9,-k))
            choice=('propose_nap',k)
    cmds.append(dict(type='diplomacy',action=choice[0] if choice else 'hold',**({'target':choice[1]} if choice else {}),
                     reason=dict(v=P['name'],ph=ph,t=target,off=offensive)))
    return cmds

OFF_TASKS=('clan_campaign','rally','approach','scout','conquer','new_army','intercept','harass','raid_supply')
def posture(obs,commands,allowed_nations):
    owners={x['id']:x['nation'] for key in ('cities','villages') for x in obs.get(key,[])}
    def ok(t): return t not in owners or owners[t] in allowed_nations
    out=[]
    for g in dev20.military_groups(commands):
        if g[0]['type'] in ('assemble','disband') and any(not ok(c.get(k)) for c in g for k in ('west_target','vanilla_target','campaign_target') if k in c):
            continue
        for c in g:
            c=dict(c)
            if c['type'] in ('siege','raid') and not ok(c.get('target')): continue
            if any(k in c and not ok(c[k]) for k in ('west_target','vanilla_target','campaign_target')):
                if c['type']=='assemble': continue
                if c.get('west_task') in OFF_TASKS or c.get('vanilla_task') in OFF_TASKS:
                    c=dict(type='stop',unit=c['unit'])
                else:
                    for k in ('west_target','vanilla_target','campaign_target'): c.pop(k,None)
            out.append(c)
    return out

def make(P):
    def decide(observation,previous_outcomes=None):
        if observation.get('mode')!='realmap' or not observation.get('diplomacy',{}).get('enabled'):
            return dev20.decide(observation,previous_outcomes)
        ph,a,target,offensive=plan(observation,P)
        dip=diplomacy(observation,P,ph,a,target,offensive)[:100]
        mil=dev20.WesternPlanner(observation).run()
        allowed={target} if (offensive and target is not None) else set()
        if ph==3 and not offensive: allowed=set()
        mil=posture(observation,mil,allowed)
        return dip+dev20.bounded_military(mil,100-len(dip))
    return decide
