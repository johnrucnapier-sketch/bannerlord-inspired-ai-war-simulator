"""Observation-only sample controllers. Campaign intent travels in ordinary orders."""
import math
from .policies_legacy import decide as legacy_decide
from .policies_v014 import decide as previous_decide
from .policies_v015 import decide as prior_relief_decide
from .relief import coordinate_relief
from .patrols import PATROLS, decide as patrol_decide


def d(a,b):return math.hypot(a['x']-b['x'],a['y']-b['y'])
def size(u):return u['healthy']+u['wounded']

def default_styles(mode):
    return ('vanilla_v1','vanilla_v1') if mode=='realmap' else ('march','march')

def decide(obs,style=None):
    style=style or default_styles(obs.get('mode'))[0]
    if style=='vanilla_v1':
        from .vanilla_policy import decide as vanilla_decide
        return vanilla_decide(obs)
    commands=_decide_existing(obs,style)
    if obs.get('castle_logistics') and style!='manual':
        from .military import policy_commands
        return (policy_commands(obs)+commands)[:100]
    return commands

def _decide_existing(obs,style='march'):
    if style in ('w1','w2','w3','w4'):
        from .warfare import decide as war_decide
        return war_decide(obs,style)
    return _base_decide(obs,style)


def _base_decide(obs,style='march',doctrine=None):
    economic_p5 = style == 'march_p5'
    if economic_p5:style='march'
    if style in PATROLS:return patrol_decide(obs,style)
    if obs.get('rule_version')=='0.1.4':return previous_decide(obs,style)
    if obs.get('rule_version')=='0.1.5':return prior_relief_decide(obs,style)
    if obs.get('rule_version')!='0.1.6':return legacy_decide(obs,style)
    if style=='manual':return []
    n=obs['nation'];hour=obs['hour'];commands=list(doctrine['commands']) if doctrine else [];handled=set(doctrine['handled']) if doctrine else set()
    attack_ratio=doctrine['attack_ratio'] if doctrine else 2.5
    abort_ratio=doctrine['abort_ratio'] if doctrine else 2.
    cities=sorted([c for c in obs['cities'] if c['nation']==n and 'recruits' in c],key=lambda c:c['id'])
    if not cities:return []
    units=sorted([u for u in obs['units'] if u['nation']==n and u['kind']=='party'],key=lambda u:u['id'])
    by_id={u['id']:u for u in obs['units']}
    enemies={c['id']:c for c in obs['cities'] if c['nation']!=n and c['id'] in obs.get('frontier_targets',[])}
    cap=obs['limits']['clan_party_cap'];ration=obs['limits']['field_ration']
    def food_days(u):return u['food']/max(1,size(u)*ration)
    def home(u):
        own=[c for c in cities if c['clan']==u['clan']] or cities
        return min(own,key=lambda c:(d(u,c),c['id']))
    def strength(u,target):
        if obs.get('direct_garrison_delivery'):target=max(target,u.get('reserve_refill_target',0))
        if u.get('refill_target',150)!=target:commands.append(dict(type='set_strength',unit=u['id'],target=target))
    def move(u,c,**meta):
        order=u.get('order') or {}
        if order.get('type')=='move' and order.get('x')==c['x'] and order.get('y')==c['y'] and all(order.get(k)==v for k,v in meta.items()):return
        commands.append(dict(type='move',unit=u['id'],x=c['x'],y=c['y'],**meta))
    def return_home(u):
        handled.add(u['id']);strength(u,40)
        c=home(u)
        if d(u,c)>500:move(u,c,campaign_phase='return',return_city=c['id'])
        else:commands.append(dict(type='stop',unit=u['id']))

    # New formations have priority over filling one party to 150.
    # A sample policy keeps 20 healthy soldiers in the garrison; this isn't a rule.
    for clan in sorted({c['clan'] for c in cities}):
        if sum(u['clan']==clan for u in units)>=cap:continue
        local_cities=[c for c in cities if c['clan']==clan]
        for c in local_cities:
            if any(b.get('city')==c['id'] for b in obs['battles']):continue
            source=None
            if c['recruits']>=30:source='recruits'
            elif by_id[c['garrison']]['healthy']>=50 and not by_id[c['garrison']]['battle'] and ((not doctrine and not obs.get('direct_garrison_delivery')) or (not by_id[c['garrison']]['army'] and d(by_id[c['garrison']],c)<=500)):source='garrison'
            else:
                donor=next((u for u in units if u['clan']==clan and not u['battle'] and not u['army'] and d(u,c)<=500 and u['healthy']>=70 and (not doctrine or u['id'] not in handled)),None)
                if donor:source=donor['id']
            if source is not None:
                commands.append(dict(type='create',city=c['id'],count=30,source=source));break

    armies={}
    for u in units:
        if u['army']:armies.setdefault(u['army'],[]).append(u)
    groups=list(armies.values())+[[u] for u in units if not u['army']]
    coordinate_relief(obs,groups,cities,commands,handled,move,return_home,food_days)
    for members in armies.values():
        if any(u['id'] in handled for u in members):continue
        handled.update(u['id'] for u in members)
        if any(u['battle'] for u in members):continue
        leader=members[0];target=enemies.get(leader.get('army_target'))
        if doctrine and doctrine['chain']:
            target=enemies.get((leader.get('order') or {}).get('target')) or target
            if not target and enemies:target=min(enemies.values(),key=lambda c:(d(leader,c),c['id']))
        fought=any(u['last_battle']>=u.get('army_formed',hour) for u in members)
        abort=(fought and not (doctrine and doctrine['chain'])) or len(members)<2 or not target or min(food_days(u) for u in members)<5
        if doctrine and doctrine['tour_hours'] and hour-leader.get('army_formed',hour)>=doctrine['tour_hours']:abort=True
        if target and not target.get('stale') and sum(u['healthy'] for u in members)<abort_ratio*(target.get('healthy',0)+target.get('militia_healthy',0)/2):abort=True
        if style!='march':abort=True
        if abort:
            commands.append(dict(type='disband',unit=leader['id']))
            for u in members:return_home(u)
        elif not target.get('stale'):
            if (leader.get('order') or {}).get('type')!='siege' or leader['order'].get('target')!=target['id']:
                commands.append(dict(type='siege',unit=leader['id'],target=target['id']))
        else:move(leader,target,campaign_phase='approach')

    # Complete a return before allowing another expedition. Defeat/interception can
    # clear a movement order, so recent independent survivors also return to refit.
    for u in units:
        if u['id'] in handled or u['battle']:continue
        if (u.get('order') or {}).get('campaign_phase')=='return' or hour-u['last_battle']<24:
            return_home(u)

    rally=[u for u in units if u['id'] not in handled and (u.get('order') or {}).get('campaign_phase')=='rally']
    if rally:
        plan=rally[0]['order'];target=enemies.get(plan.get('campaign_target'))
        rally_city=next((c for c in cities if c['id']==plan.get('rally_city')),None)
        roster=[u for u in rally if u['order'].get('campaign_target')==plan.get('campaign_target')]
        handled.update(u['id'] for u in rally)
        arrived=[u for u in roster if not u['battle'] and rally_city and d(u,rally_city)<=500 and food_days(u)>=10]
        if doctrine and arrived:
            anchor=arrived[0]
            arrived=[u for u in arrived if d(u,anchor)<=500]
        required=max(100,math.ceil(attack_ratio*((target or {}).get('healthy',50)+(target or {}).get('militia_healthy',100)/2)))
        if style!='march' or not target or not rally_city or hour>plan['rally_deadline'] or armies:
            for u in rally:
                if not u['battle']:return_home(u)
        elif len(arrived)>=2 and sum(u['healthy'] for u in arrived)>=required:
            commands.append(dict(type='assemble',unit=arrived[0]['id'],units=[u['id'] for u in arrived[1:]],campaign_target=target['id']))
            for u in rally:
                if u not in arrived and not u['battle']:return_home(u)
        else:
            for u in roster:
                if not u['battle']:
                    strength(u,150)
                    move(u,rally_city,campaign_phase='rally',campaign_target=target['id'],rally_city=rally_city['id'],rally_deadline=plan['rally_deadline'])

    # One expedition per country for this initial controller; retain one patrol
    # party in every clan. No teleportation: all members walk to the rally city.
    if style=='march' and not armies and not rally and enemies:
        patrol={min((u for u in units if u['clan']==clan),key=lambda u:u['id'])['id'] for clan in {u['clan'] for u in units}}
        if doctrine:patrol=set(doctrine['protected'])
        ready=[u for u in units if u['id'] not in handled|patrol and not u['battle'] and not u['army'] and u['healthy']>=30 and food_days(u)>=15]
        if len(ready)>=2:
            if doctrine:ready=sorted(ready,key=lambda u:(-u['healthy'],u['id']))[:max(2,math.ceil(len(ready)*doctrine['attack_fraction']))]
            options=[]
            for t in enemies.values():
                bases=[c for c in cities if t['id'] in c['neighbors']]
                if bases:
                    base=min(bases,key=lambda c:(sum(d(u,c) for u in ready),c['id']))
                    options.append(((t.get('healthy',50)+t.get('militia_healthy',100)/2),sum(d(u,base) for u in ready),t['id'],base,t))
            if options:
                _,_,_,base,target=min(options,key=lambda x:x[:3])
                required=max(100,math.ceil(attack_ratio*(target.get('healthy',50)+target.get('militia_healthy',100)/2)));roster=[];total=0
                for u in sorted(ready,key=lambda u:(d(u,base),u['id']))[:12]:
                    roster.append(u);total+=u['healthy']
                    if len(roster)>=2 and total>=required:break
                # Strong targets can trigger real preparation at the rally city.
                # Actual assembly still requires the full healthy-strength threshold.
                if len(roster)>=2 and len(roster)*obs['limits']['party_cap']>=required:
                    for u in roster:
                        handled.add(u['id']);strength(u,150)
                        move(u,base,campaign_phase='rally',campaign_target=target['id'],rally_city=base['id'],rally_deadline=hour+240)

    # Preserve the complete campaign planner; only replace its unassigned patrol layer.
    if economic_p5:
        available={u['id'] for u in units if u['id'] not in handled and not u['battle']}
        patrol_style='p5_eta' if doctrine and len(available)/max(1,len(cities))>=1.75 else 'p5'
        commands.extend(patrol_decide(obs,patrol_style,available_ids=available,allow_create=False,sectors_by_unit=doctrine['sectors'] if doctrine else None))
        return commands[:100]

    # Unassigned forces protect home villages and real transport routes.
    for u in units:
        if u['id'] in handled or u['battle']:continue
        strength(u,40)
        own=home(u);order=u.get('order') or {}
        if food_days(u)<5 or u['healthy']<20:
            if d(u,own)>500:return_home(u)
            continue
        bandits=[t for t in obs['units'] if t['nation']==-1 and d(u,t)<8000]
        if bandits and u['healthy']>=20:
            t=min(bandits,key=lambda t:(d(u,t),t['id']))
            if order.get('type')!='attack' or order.get('target')!=t['id']:
                commands.append(dict(type='attack',unit=u['id'],target=t['id']))
            continue
        if u.get('path') or order.get('type')=='attack':continue
        villages=sorted([v for v in obs['villages'] if v['nation']==n and v.get('city')==own['id']],key=lambda v:v['id'])
        peers=[p['id'] for p in units if p['clan']==u['clan'] and p['id'] not in handled]
        idx=peers.index(u['id']);assigned=villages[idx::len(peers)] or villages[idx%max(1,len(villages)):idx%max(1,len(villages))+1]
        waypoints=[]
        for v in assigned:
            midpoint={'x':(own['x']+v['x'])//2,'y':(own['y']+v['y'])//2}
            if obs.get('castle_logistics'):
                from .navigation import find_route
                if find_route(obs['terrain'],own,midpoint['x'],midpoint['y']) is None:
                    waypoints.extend([own,v])
                    continue
            waypoints.extend([own,midpoint,v,midpoint])
        if waypoints:
            waypoint=(order.get('patrol_index',-1)+1)%len(waypoints)
            move(u,waypoints[waypoint],patrol_index=waypoint)
    return commands[:100]


def decision_cycle(world,styles=None):
    styles=styles or default_styles(world.cfg.get('mode'))
    observations=[world.observe(n) for n in (0,1)]
    batches=[decide(observations[n],styles[n]) if styles[n]!='manual' and (n==0 or world.cfg.get('mode')!='rural') else [] for n in (0,1)]
    return [world.command(n,cmd) for n in (0,1) for cmd in batches[n]]
