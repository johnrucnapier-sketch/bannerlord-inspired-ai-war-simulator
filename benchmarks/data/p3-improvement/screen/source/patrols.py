"""Four observation-only rural patrols. No hidden state, randomness or world access."""
import math

PATROLS = {'p1': 'P1 驻点守护', 'p2': 'P2 随车护送',
           'p3': 'P3 环线巡防', 'p4': 'P4 就近救援'}


def distance(a, b):
    return math.hypot(a['x']-b['x'], a['y']-b['y'])


def decide(obs, style):
    variant=style if style in ('p3_resume','p3_outer','p3_strong') else None
    if variant:style='p3'
    strength=60 if variant=='p3_strong' else 40
    nation = obs['nation']
    cities = sorted((c for c in obs['cities'] if c['nation']==nation and 'recruits' in c), key=lambda c:c['id'])
    if not cities:return []
    own = {u['id']:u for u in obs['units'] if u['nation']==nation}
    parties = sorted((u for u in own.values() if u['kind']=='party'), key=lambda u:u['id'])
    villages = sorted((v for v in obs['villages'] if v['nation']==nation), key=lambda v:v['id'])
    bandits = [u for u in obs['units'] if u['nation']==-1]
    carts = [u for u in own.values() if u['kind']=='village_cart' and (u['phase']!='idle' or u['battle'])]
    commands = []
    cap = obs['limits']['clan_party_cap']
    ration = obs['limits']['field_ration']
    # Shared force budget: three modest 40-person parties per clan, no free resources.
    for clan in sorted({c['clan'] for c in cities}):
        if sum(u['clan']==clan for u in parties)>=cap:continue
        for c in (c for c in cities if c['clan']==clan):
            if any(b.get('city')==c['id'] for b in obs['battles']):continue
            g=own[c['garrison']]
            source='recruits' if c['recruits']>=30 else 'garrison' if g['healthy']>=50 and not g['battle'] and not g['army'] and distance(g,c)<=500 else None
            if source:
                commands.append(dict(type='create',city=c['id'],count=30,source=source));break

    def move(u, point, **meta):
        order=u.get('order') or {}
        if order.get('type')=='move' and order.get('x')==point['x'] and order.get('y')==point['y'] and all(order.get(k)==v for k,v in meta.items()):return
        commands.append(dict(type='move',unit=u['id'],x=int(point['x']),y=int(point['y']),**meta))

    def attack(u, target):
        if (u.get('order') or {}).get('target')!=target['id']:
            commands.append(dict(type='attack',unit=u['id'],target=target['id']))

    ready=[]
    for u in parties:
        if u['battle']:continue
        if u['army']:
            # One disband command per army, then assign individuals next decision.
            if u['id']==min(p['id'] for p in parties if p['army']==u['army']):
                commands.append(dict(type='disband',unit=u['id']))
            continue
        if u.get('refill_target',150)!=strength:
            commands.append(dict(type='set_strength',unit=u['id'],target=strength))
        home=min(cities,key=lambda c:(distance(u,c),c['id']))
        days=u['food']/max(1,(u['healthy']+u['wounded'])*ration)
        # Conservative travel reserve; no abandoning the return halfway for a fresh target.
        return_days=math.ceil(distance(u,home)/250/24)+3
        returning=(u.get('order') or {}).get('patrol_return',False)
        if days<return_days or u['healthy']<20 or u['wounded']>=10 or (returning and distance(u,home)>500):
            move(u,home,patrol_return=True)
            continue
        ready.append(u)

    # Fixed responsibilities: pair each clan's six villages into three nearby sectors.
    assigned={}
    for clan in sorted({u['clan'] for u in parties}):
        peers=[u for u in parties if u['clan']==clan]
        city_ids={c['id'] for c in cities if c['clan']==clan}
        remaining=[v for v in villages if v['city'] in city_ids]
        for i,u in enumerate(peers):
            quota=math.ceil(len(remaining)/(len(peers)-i))
            # Geography-only anchor is stable even as parties move and fight.
            anchor=next(c for c in cities if c['id'] in city_ids)
            first=min(remaining,key=lambda v:(v['x'],v['y'],v['id'])) if remaining else anchor
            sector=sorted(remaining,key=lambda v:(distance(first,v),v['id']))[:quota]
            assigned[u['id']]=sector
            remaining=[v for v in remaining if v not in sector]

    claimed=set()
    for u in ready:
        sector=assigned.get(u['id'],[])
        if not sector:continue
        center=dict(x=sum(v['x'] for v in sector)//len(sector),y=sum(v['y'] for v in sector)//len(sector))
        local_carts=[c for c in carts if c['home'] in {v['id'] for v in sector}]
        # Finish a local pursuit instead of cancelling it each six-hour decision.
        current=next((b for b in bandits if b['id']==(u.get('order') or {}).get('target')),None)
        if current and distance(u,current)<10000 and distance(current,center)<18000:
            continue
        nearby=[b for b in bandits if distance(u,b)<8000]
        if style in ('p1','p3') and nearby:
            attack(u,min(nearby,key=lambda b:(distance(u,b),b['id'])))
            continue
        if style=='p4':
            # Global matching uses only friendly carts and currently visible threats.
            available=[c for c in carts if c['id'] not in claimed and distance(u,c)<10000]
            def priority(c):
                danger=min((distance(c,b) for b in bandits),default=99999)
                return (0 if c['battle'] else 1 if danger<8000 else 2, distance(u,c),c['id'])
            previous=next((c for c in available if c['id']==(u.get('order') or {}).get('patrol_cart')),None)
            urgent=[c for c in available if c['battle']]
            target=min(urgent,key=priority) if urgent else previous or (min(available,key=priority) if available else None)
            if target:
                claimed.add(target['id'])
                threats=[b for b in bandits if distance(b,target)<6000 and distance(u,b)<8000]
                if threats:attack(u,min(threats,key=lambda b:(distance(u,b),b['id'])))
                else:move(u,target,patrol_cart=target['id'])
            elif nearby:attack(u,min(nearby,key=lambda b:(distance(u,b),b['id'])))
            else:move(u,sector[(obs['hour']//168)%len(sector)])
        elif style=='p2':
            target=min(local_carts,key=lambda c:(not bool(c['battle']),distance(u,c),c['id'])) if local_carts else None
            if target:
                threats=[b for b in bandits if distance(b,target)<5000 and distance(u,b)<6000]
                if threats:attack(u,min(threats,key=lambda b:(distance(u,b),b['id'])))
                else:move(u,target,patrol_cart=target['id'])
            elif nearby:attack(u,min(nearby,key=lambda b:(distance(u,b),b['id'])))
            else:move(u,sector[(obs['hour']//168)%len(sector)])
        elif style=='p1':
            # Presence discourages spawning/approach; do not chase fleeing bandits away.
            threats=[b for b in bandits if distance(b,center)<5000 and distance(u,b)<4000]
            if threats:attack(u,min(threats,key=lambda b:(distance(u,b),b['id'])))
            else:move(u,sector[(obs['hour']//168)%len(sector)])
        else:  # p3: sweep each sector's city-village routes continuously.
            threats=[b for b in bandits if distance(u,b)<6000 and distance(b,center)<9000]
            if threats:
                attack(u,min(threats,key=lambda b:(distance(u,b),b['id'])))
                continue
            order=u.get('order') or {}
            if u.get('path') and order.get('patrol_style')=='p3':continue
            points=[]
            for v in sector:
                c=next(c for c in cities if c['id']==v['city'])
                if variant=='p3_outer':
                    points.append(v)  # City trips are handled separately by actual resupply needs.
                else:
                    points.extend([v,dict(x=(v['x']+c['x'])//2,y=(v['y']+c['y'])//2),c])
            if variant and 'patrol_index' not in order:
                # Battle clears orders: resume after the nearest point, rather than village zero.
                idx=(min(range(len(points)),key=lambda i:distance(u,points[i]))+1)%len(points)
            else:idx=(order.get('patrol_index',-1)+1)%len(points)
            move(u,points[idx],patrol_style='p3',patrol_index=idx)
    return commands[:100]
