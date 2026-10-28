"""Experimental observation-only resource allocation above the campaign planner."""
import math
from .navigation import travel_hours

STYLES = {'w1': 'W1 保底集中', 'w2': 'W2 风险抽调',
          'w3': 'W3 轮换出征', 'w4': 'W4 战区预备'}
PROFILES = {
    'w1': dict(attack_fraction=.65, attack_ratio=2.5, abort_ratio=2., tour_hours=0, chain=False),
    'w2': dict(attack_fraction=.85, attack_ratio=2., abort_ratio=1.5, tour_hours=0, chain=True),
    'w3': dict(attack_fraction=.75, attack_ratio=2.2, abort_ratio=1.7, tour_hours=336, chain=True),
    'w4': dict(attack_fraction=.9, attack_ratio=1.9, abort_ratio=1.5, tour_hours=504, chain=True),
}


def distance(a, b):
    return math.hypot(a['x']-b['x'], a['y']-b['y'])


def food_days(u, obs):
    return u['food']/max(1,(u['healthy']+u['wounded'])*obs['limits']['field_ration'])


def city_risks(obs):
    """Two-week trip cohorts, population trend, visible threats and real ready strength."""
    cities = [c for c in obs['cities'] if c['nation']==obs['nation'] and 'recruits' in c]
    parties = [u for u in obs['units'] if u['nation']==obs['nation'] and u['kind']=='party']
    risks = {}
    for c in cities:
        row = obs.get('economy',{}).get(c['id'],{})
        events = row.get('events',[])
        def rate(start,end):
            cohort=[e for e in events if start <= e['trip_start'] < end]
            departed=sum(e['kind']=='depart' for e in cohort)
            intercepted=sum(e['kind']=='intercept' for e in cohort)
            return min(1,intercepted/departed) if departed else 0, departed
        recent,count = rate(obs['hour']-336,obs['hour']+1)
        older,old_count = rate(obs['hour']-672,obs['hour']-336)
        samples=row.get('samples',[])
        previous=next((s for s in samples if s['hour']>=obs['hour']-168),None)
        population=sum(v['population'] for v in obs['villages'] if v['nation']==obs['nation'] and v['city']==c['id'])
        population+=sum(u['healthy']+u['wounded'] for u in obs['units'] if u['nation']==obs['nation'] and u['kind']=='village_cart' and any(v['id']==u['home'] and v['city']==c['id'] for v in obs['villages']))
        decline=bool(previous and obs['hour']-previous['hour']>=144 and population<previous['population']*.85)
        threats=[u for u in obs['units'] if u['nation']==-1 and distance(u,c)<=18000]
        needed=max(40,math.ceil(sum(u['healthy'] for u in threats)*.65)) if threats else 0
        ready=[u for u in parties if not u['battle'] and not u['army'] and u['healthy']>=20 and food_days(u,obs)>=5 and distance(u,c)<=8000]
        available=sum(u['healthy'] for u in ready)
        stalled=sum(obs['hour']-t['start']>168 and not t['delivered'] for t in row.get('trips',{}).values())
        crisis=(count>=6 and recent>=.5) or (decline and bool(threats)) or (stalled>=2 and bool(threats)) or (population<180 and bool(threats))
        warning=(count>=6 and recent>=.25) or decline or stalled>0 or needed>available
        recovery=old_count>=6 and older>=.5 and not crisis
        state='critical' if crisis else 'recovering' if recovery else 'warning' if warning else 'normal'
        risks[c['id']]=dict(state=state,intercept_rate=recent,departures=count,population=population,
                            declining=decline,stalled=stalled,required=needed,ready_strength=available,
                            needs_help=crisis and needed>available,threats=[u['id'] for u in threats])
    return risks


def allocate(obs, style):
    cities=sorted([c for c in obs['cities'] if c['nation']==obs['nation'] and 'recruits' in c],key=lambda c:c['id'])
    units=sorted([u for u in obs['units'] if u['nation']==obs['nation'] and u['kind']=='party'],key=lambda u:u['id'])
    risks=city_risks(obs)
    free=[u for u in units if not u['army'] and not u['battle'] and (u.get('order') or {}).get('campaign_phase') not in ('rally','return','relief','economy_relief')]
    assigned={};protected=set()
    # One real party per city, then risk-sensitive extra coverage; no fractional units.
    priority=sorted(cities,key=lambda c:({'critical':0,'recovering':1,'warning':2,'normal':3}[risks[c['id']]['state']],c['id']))
    for c in priority:
        options=[u for u in free if u['id'] not in protected]
        if not options:break
        u=min(options,key=lambda u:(u['clan']!=c['clan'],distance(u,c),u['id']))
        protected.add(u['id']);assigned[u['id']]=c['id']
    if style!='w1':
        elevated=[c for c in priority if risks[c['id']]['state']!='normal']
        for i,c in enumerate(elevated):
            if risks[c['id']]['state']!='critical' and i%2:continue
            options=[u for u in free if u['id'] not in protected]
            if not options:break
            u=min(options,key=lambda u:(distance(u,c),u['id']))
            protected.add(u['id']);assigned[u['id']]=c['id']
    commands=[];handled=set();by_id={u['id']:u for u in units}
    def move(u,c,**meta):
        cmd=dict(type='move',unit=u['id'],x=c['x'],y=c['y'],**meta)
        if any((u.get('order') or {}).get(k)!=v for k,v in cmd.items()):commands.append(cmd)
    # Group rescue missions by city so individually arriving parties can assemble.
    missions={}
    for u in units:
        order=u.get('order') or {}
        if order.get('campaign_phase')=='economy_relief':
            missions.setdefault(order.get('economy_city'),[]).append(u)
    for cid,members in missions.items():
        handled.update(p['id'] for p in members)
        c=next((c for c in cities if c['id']==cid),None)
        risk=risks.get(cid,{})
        until=min((p.get('order') or {}).get('economy_until',0) for p in members)
        active=c and risk.get('state') in ('critical','recovering') and obs['hour']<until and min(food_days(p,obs) for p in members)>=5
        groups={}
        for p in members:groups.setdefault(p['army'] or p['id'],[]).append(p)
        if any(p['battle'] for p in members):continue
        if not active:
            for group in groups.values():
                if group[0]['army']:commands.append(dict(type='disband',unit=group[0]['id']))
            for p in members:
                if cities:move(p,min(cities,key=lambda c:distance(p,c)),campaign_phase='return')
            continue
        threats=[b for b in obs['units'] if b['id'] in risk['threats']]
        assembled=len(groups)==1
        together=all(distance(p,c)<=500 for p in members)
        sufficient=sum(p['healthy'] for p in members)>=risk['required']
        leader=min(members,key=lambda p:p['id'])
        if sufficient and (assembled or together) and threats:
            if not assembled:
                for group in groups.values():
                    if group[0]['army']:commands.append(dict(type='disband',unit=group[0]['id']))
                commands.append(dict(type='assemble',unit=leader['id'],units=[p['id'] for p in members if p!=leader]))
            target=min(threats,key=lambda b:(distance(leader,b),b['id']))
            order=leader.get('order') or {}
            if not assembled or order.get('type')!='attack' or order.get('target')!=target['id']:
                commands.append(dict(type='attack',unit=leader['id'],target=target['id'],campaign_phase='economy_relief',economy_city=cid,economy_until=until))
        else:
            for group in groups.values():move(group[0],c,campaign_phase='economy_relief',economy_city=cid,economy_until=until)
    # Allocate an affordable joint team; stage first and attack only with enough strength.
    for c in priority:
        risk=risks[c['id']]
        if not risk['needs_help']:continue
        if any((u.get('order') or {}).get('economy_city')==c['id'] and u['id'] in handled for u in units):continue
        choices=[]
        for u in free:
            if u['id'] in handled:continue
            home=assigned.get(u['id'])
            if home and home!=c['id']:continue  # Never empty another city's minimum cover.
            if u['healthy']<20 or u['wounded']>=u['healthy']:continue
            eta=travel_hours(obs['terrain'],u,c,obs['speeds'],max_hours=96)
            if eta is not None and food_days(u,obs)>=eta/24+5:choices.append((eta,u['id'],u))
        team=[];total=0
        for _,_,u in sorted(choices):
            team.append(u);total+=u['healthy']
            if total>=risk['required']:break
        if total<risk['required']:continue
        arrived=all(distance(u,c)<=500 for u in team)
        for u in team:
            handled.add(u['id']);protected.add(u['id'])
            if u.get('refill_target',150)!=60:commands.append(dict(type='set_strength',unit=u['id'],target=60))
        if arrived and len(team)>1:
            commands.append(dict(type='assemble',unit=team[0]['id'],units=[u['id'] for u in team[1:]]))
            move(team[0],c,campaign_phase='economy_relief',economy_city=c['id'],economy_until=obs['hour']+336)
        else:
            for u in team:move(u,c,campaign_phase='economy_relief',economy_city=c['id'],economy_until=obs['hour']+336)
    # W4 holds a regional spare only while the region is at risk.
    if style=='w4' and any(r['state']!='normal' for r in risks.values()):
        spare=next((u for u in free if u['id'] not in protected|handled),None)
        if spare and cities:
            protected.add(spare['id']);assigned[spare['id']]=priority[0]['id']
    # Every remaining rear party gets a concrete city, including landless clans.
    for u in units:
        if u['id'] not in assigned and cities:
            assigned[u['id']]=min(cities,key=lambda c:(c['clan']!=u['clan'],distance(u,c),c['id']))['id']
    plan=dict(PROFILES[style],protected=protected,handled=handled,commands=commands,sectors=assigned,risks=risks)
    return plan


def decide(obs,style):
    from .policies import _base_decide
    return _base_decide(obs,'march_p5',allocate(obs,style))
