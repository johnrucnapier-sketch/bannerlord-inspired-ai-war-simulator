"""Observation-only demonstration controllers, not built-in country rules."""
import math


def d(a,b):
    return math.hypot(a['x']-b['x'],a['y']-b['y'])


def decide(obs, style='march'):
    n=obs['nation']
    cities=[c for c in obs['cities'] if c['nation']==n and 'recruits' in c]
    enemy=[c for c in obs['cities'] if c['nation']!=n and ('frontier_targets' not in obs or c['id'] in obs['frontier_targets'])]
    units=[u for u in obs['units'] if u['nation']==n and u['kind']=='party']
    commands=[]
    for c in cities:
        if c['recruits']<=0:continue
        target_size=40 if style=='guard' else 150
        local=[u for u in units if not u['battle'] and d(u,c)<=500 and u['healthy']+u['wounded']<target_size]
        if local:
            u=sorted(local,key=lambda u:u['id'])[0]
            count=min(c['recruits'],target_size-u['healthy']-u['wounded'])
            commands.append(dict(type='recruit',city=c['id'],unit=u['id'],count=count))
        elif c['recruits']>=(30 if style=='guard' else 60) and sum(u['clan']==c['clan'] for u in units)<4:
            commands.append(dict(type='create',city=c['id'],count=min(target_size,c['recruits'])))
    for u in units:
        if u['battle'] or not cities:continue
        own=min(cities,key=lambda c:(d(u,c),c['id']))
        count=u['healthy']+u['wounded']
        order=u.get('order') or {}
        if u['food']<count*100*5 and d(u,own)>500:
            if order.get('type')!='move' or order.get('x')!=own['x'] or order.get('y')!=own['y']:
                commands.append(dict(type='move',unit=u['id'],x=own['x'],y=own['y']))
            continue
        # Nearby fighting transports are rescuable, but only actual arrival helps.
        bandits=[t for t in obs['units'] if t['nation']==-1 and d(u,t)<8000]
        if bandits and u['healthy']>=20:
            t=min(bandits,key=lambda t:(d(u,t),t['id']))
            if order.get('type')!='attack' or order.get('target')!=t['id']:
                commands.append(dict(type='attack',unit=u['id'],target=t['id']))
            continue
        if u.get('path') or order.get('type') in ('siege','raid','attack'):continue
        if style=='guard':
            # Distribute available parties across real village/road circuits.
            home=next((c for c in cities if c['clan']==u['clan']),own)
            villages=sorted([v for v in obs['villages'] if v['nation']==n and v.get('city')==home['id']],key=lambda v:v['id'])
            peers=sorted([p['id'] for p in units if p['clan']==u['clan']])
            idx=peers.index(u['id'])
            assigned=villages[idx::len(peers)] or villages[idx%max(1,len(villages)):idx%max(1,len(villages))+1]
            waypoints=[]
            for v in assigned:
                mid={'x':(home['x']+v['x'])//2,'y':(home['y']+v['y'])//2}
                waypoints.extend([home,mid,v,mid])
            if waypoints:
                waypoint=(order.get('patrol_index',-1)+1)%len(waypoints)
                t=waypoints[waypoint]
                commands.append(dict(type='move',unit=u['id'],x=t['x'],y=t['y'],patrol_index=waypoint))
        elif u['healthy']>=85 and enemy:
            t=min(enemy,key=lambda c:(d(u,c),c['id']))
            if not t.get('stale'):
                commands.append(dict(type='siege',unit=u['id'],target=t['id']))
            else:
                commands.append(dict(type='move',unit=u['id'],x=t['x'],y=t['y']))
        elif d(u,own)>500:
            commands.append(dict(type='move',unit=u['id'],x=own['x'],y=own['y']))
    return commands[:100]


def decision_cycle(world, styles=('march','march')):
    observations=[world.observe(n) for n in (0,1)]
    batches=[decide(observations[n],styles[n]) if styles[n]!='manual' else [] for n in (0,1)]
    return [world.command(n,cmd) for n in (0,1) for cmd in batches[n]]
