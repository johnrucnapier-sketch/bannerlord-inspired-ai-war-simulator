"""Observation-only coordination for external relief; no changes to city combat rules."""
import math
from .navigation import find_route,travel_hours,passable,relief_terrain


def distance(a,b):return math.hypot(a['x']-b['x'],a['y']-b['y'])

def staging_point(obs,alert,cities):
    anchors=[c for c in cities if c['id']!=alert['city']] or cities
    anchor=min(anchors,key=lambda c:(distance(c,alert),c['id']))
    offsets=((4000,0),(-4000,0),(0,4000),(0,-4000),(2800,2800),(2800,-2800),(-2800,2800),(-2800,-2800))
    candidates=[]
    for dx,dy in offsets:
        p={'x':alert['x']+dx,'y':alert['y']+dy}
        if passable(obs['terrain'],p['x']//2000,p['y']//2000) and (anchor['id']==alert['city'] or find_route(relief_terrain(obs['terrain'],alert,anchor),anchor,p['x'],p['y']) is not None):
            candidates.append(p)
    return min(candidates,key=lambda p:(distance(p,anchor),p['x'],p['y'])) if candidates else None


def coordinate_relief(obs,groups,cities,commands,handled,move,return_home,food_days):
    n=obs['nation'];hour=obs['hour'];alerts={a['city']:a for a in obs.get('relief_requests',[])}
    def send_home(group):
        if group[0]['army']:commands.append(dict(type='disband',unit=group[0]['id']))
        for u in group:return_home(u)
    for group in groups:
        if any(u['battle'] for u in group):continue
        order=group[0].get('order') or {}
        if order.get('campaign_phase')=='relief' and order.get('relief_city') not in alerts:send_home(group)
    for alert in sorted(alerts.values(),key=lambda a:(a['assault_at'],a['city'])):
        stage=staging_point(obs,alert,cities)
        if not stage:continue
        battle_ids={alert['battle'],alert.get('relief_battle')}
        enemies=[u for u in obs['units'] if u['nation']>=0 and u['nation']!=n and u.get('battle') in battle_ids and u.get('battle') is not None and u['healthy']>0]
        enemy_strength=sum(u['healthy'] for u in enemies)
        engaged=sum(u['healthy'] for u in obs['units'] if u['nation']==n and u['kind']=='party' and alert.get('relief_battle') and u['battle']==alert['relief_battle'])
        required=math.ceil(enemy_strength*1.1) if enemies else 0
        potential=engaged;chosen=[];options=[]
        window=max(0,alert['assault_at']-hour) if alert['phase']=='siege' else 24
        for group in groups:
            if any(u['id'] in handled or u['battle'] for u in group):continue
            leader=group[0];order=leader.get('order') or {}
            current=order.get('campaign_phase')=='relief' and order.get('relief_city')==alert['city']
            healthy=sum(u['healthy'] for u in group)
            if current and (min(food_days(u) for u in group)<5 or healthy<20):
                send_home(group);continue
            if healthy<20:continue
            if current:
                chosen.append(group);potential+=healthy
            else:
                eta=travel_hours(relief_terrain(obs['terrain'],alert,leader),leader,stage,obs['speeds'],window)
                if eta is not None and min(food_days(u) for u in group)>=max(5,eta/24+2):options.append((eta,leader['id'],group))
        # No city garrison or militia counts toward the field force.
        for _,_,group in sorted(options,key=lambda x:x[:2]):
            if potential>=required:break
            chosen.append(group);potential+=sum(u['healthy'] for u in group)
        ready=[]
        for group in chosen:
            handled.update(u['id'] for u in group)
            leader=group[0];order=leader.get('order') or {}
            at_stage=all(distance(u,stage)<=100 for u in group)
            advancing=order.get('relief_action')=='attack' and order.get('relief_city')==alert['city']
            if at_stage or advancing:ready.append(group)
            else:move(leader,stage,campaign_phase='relief',relief_city=alert['city'],relief_battle=alert['battle'],relief_action='wait')
        # Only troops physically together can pool their strength before launching.
        clusters=[]
        for group in ready:
            cluster=next((c for c in clusters if all(distance(u,v)<=500 for u in group for g in c for v in g)),None)
            if cluster is None:clusters.append([group])
            else:cluster.append(group)
        for cluster in clusters:
            members=[u for group in cluster for u in group]
            if not enemies or engaged+sum(u['healthy'] for u in members)<required:
                for group in cluster:move(group[0],stage,campaign_phase='relief',relief_city=alert['city'],relief_battle=alert['battle'],relief_action='wait')
                continue
            leader=min((u for u in members if u['healthy']>0),key=lambda u:u['id'])
            target=min(enemies,key=lambda u:(distance(u,leader),u['id']))
            # Use the existing army mechanism so different movement speeds cannot
            # turn the coordinated attack into serial suicidal single-party charges.
            already_together=len(cluster)==1 and (len(members)==1 or leader['army'] is not None)
            if not already_together:
                for group in cluster:
                    if group[0]['army']:commands.append(dict(type='disband',unit=group[0]['id']))
                commands.append(dict(type='assemble',unit=leader['id'],units=[u['id'] for u in members if u['id']!=leader['id']]))
            order=leader.get('order') or {}
            if not already_together or order.get('type')!='attack' or order.get('target')!=target['id']:
                commands.append(dict(type='attack',unit=leader['id'],target=target['id'],campaign_phase='relief',relief_city=alert['city'],relief_battle=alert['battle'],relief_action='attack'))
