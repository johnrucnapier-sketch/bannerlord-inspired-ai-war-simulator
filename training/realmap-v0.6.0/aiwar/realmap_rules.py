"""v0.6.0 opt-in logistics, local patrols and spoils. Saved configurations own opt-in."""
import math
from . import military


def enabled(w):
    return w.cfg.get('mode') == 'realmap' and w.cfg.get('realmap_rules_v6', False)


def can_supply(w, target):
    for member in w.members(target):
        b = w.battles.get(member['battle'])
        if b and (not b['city'] or member['nation'] == b['defender'] or
                  b.get('relief_battle') or b.get('assault_started') or
                  w.hour-b['start']-b.get('paused_hours', 0) >= b['prepare_hours']):
            return False
    return True


def resolve_target(w, key):
    ids = w.armies.get(key, [key])
    return next((w.units[i] for i in ids if i in w.units and w.units[i]['kind']=='party'), None)


def give_food(w, recipients, amount, source):
    left = amount
    for u in sorted(recipients, key=lambda p:p['id']):
        n = min(left, max(0, w.food_cap(u)-u['food']))
        u['food'] += n
        left -= n
    got = amount-left
    if source == 'loot':
        w.stats['food_looted'] = w.stats.get('food_looted', 0)+got
        w.stats['food_lost'] += left
    return got


def spoils(w, battle, winner):
    if winner is None:return
    recipients = [w.units[i] for i in battle['sides'].get(str(winner), [])
                  if i in w.units and w.units[i]['kind']=='party' and w.units[i]['healthy']>0]
    if not recipients:return
    amount = 0
    for n, ids in battle['sides'].items():
        if int(n)==winner:continue
        for uid in ids:
            u = w.units.get(uid)
            if u and u['kind'] in ('party','village_cart','city_cart','patrol'):
                amount += u['food']+u['cargo_food']
                u['food']=u['cargo_food']=0
    got = give_food(w, recipients, amount, 'loot')
    if amount:w.emit('food_looted', f'战后缴获粮食 {got/1000:.1f}，超额丢弃 {(amount-got)/1000:.1f}', nation=winner, battle=battle['id'], important=True)


def dispatch(w, nation, c, cmd):
    mission=cmd.get('mission','deliver')
    if mission not in ('deliver','fetch','supply'):raise ValueError('运输任务须为deliver/fetch/supply')
    target=resolve_target(w,cmd.get('destination')) if mission=='supply' else w.cities.get(cmd.get('destination'))
    if not target or target['nation']!=nation:raise ValueError('运输目标须为存活友方单位或据点')
    if mission!='supply' and (target['id'] not in c['supply_neighbors'] or w.besieged(target['id'])):raise ValueError('仅可运输到邻近未被围的友方据点')
    if c['convoy'] or any(u.get('militia_convoy') and u['home']==c['id'] and u['nation']==nation for u in w.units.values()):raise ValueError('本据点已有运输队')
    count=cmd.get('troops',0)
    if type(count) is not int or not 0<=count<=w.cfg['transport_troops']:raise ValueError(f"运兵人数须在0至{w.cfg['transport_troops']}以内")
    if mission!='deliver' and count:raise ValueError('运兵须以友方据点为目的地')
    g=w.units[c['garrison']];m=w.units[c['militia']];crew=w.cfg['city_crew']
    if g['battle'] or count>g['healthy'] or m['battle'] or m['healthy']<crew:raise ValueError('健康驻军或民兵不足')
    troop_type=cmd.get('troop_type')
    if troop_type not in (None,'infantry','cavalry'):raise ValueError('兵种无效')
    if troop_type=='cavalry' and count>g['cavalry']:raise ValueError('骑兵不足')
    if troop_type=='infantry' and count>g['healthy']-g['cavalry']:raise ValueError('步兵不足')
    reserve=(crew+count)*w.cfg['field_ration']*w.cfg['carry_days']
    if c['food']<reserve:raise ValueError('运输队出发口粮不足')
    amount=cmd.get('food',w.cfg['city_cargo'])
    if type(amount) is not int or amount<0:raise ValueError('粮食数量无效')
    path=w.route(m,target['x'],target['y'])
    if path is None:raise ValueError('目的地不可达')
    cargo=min(amount,w.cfg['city_cargo'],c['food']-reserve) if mission!='fetch' else 0
    u=w.new_unit('city_cart',nation,c['clan'],crew,c['x'],c['y'],home=c['id'],food=reserve)
    military.transfer(g,u,count,troop_type=troop_type)
    u.update(regular_healthy=count,regular_wounded=0,militia_convoy=True,
             mission=mission,requested_food=amount,cargo_food=cargo,phase='outbound',
             destination=target['id'],path=path,order={'type':'move','x':target['x'],'y':target['y']})
    if mission=='supply':
        u.update(supply_target=target['id'],supply_army=target['army'],supply_members=[m['id'] for m in w.members(target)])
    m['healthy']-=crew;c['food']-=reserve+cargo;c['convoy']=u['id']
    w.stats['supply_dispatches']+=1
    w.emit('supply_departed',f"{c['name']}派出{crew}民兵、{count}驻军，货粮{cargo/1000:.1f}，口粮另计",nation=nation,unit=u['id'],city=c['id'],important=True)
    resume(w,u)
    return {'ok':True,'unit':u['id']}


def assign_supply(w,u,target):
    if u['kind']!='city_cart' or not u.get('militia_convoy') or not target or target['nation']!=u['nation']:raise ValueError('补给目标无效')
    if u.get('regular_healthy',0)+u.get('regular_wounded',0):raise ValueError('请先完成驻军运输')
    if w.route(u,target['x'],target['y']) is None:raise ValueError('目的地不可达')
    u.update(mission='supply',supply_target=target['id'],supply_army=target['army'],supply_members=[m['id'] for m in w.members(target)],destination=target['id'],phase='outbound')
    resume(w,u)
    arrival(w,u)
    return {'ok':True}


def supply_target(w,u):
    target=w.units.get(u.get('supply_target'))
    aid=u.get('supply_army')
    if aid in w.armies:
        target=next((w.units[i] for i in w.armies[aid] if i in w.units),None)
    elif not target:
        target=next((w.units[i] for i in u.get('supply_members',[]) if i in w.units),None)
    if target:
        u['supply_target']=target['id']
        if target['army']:
            u['supply_army']=target['army']
            u['supply_members']=[m['id'] for m in w.members(target)]
    return target


def regular_size(u):return u.get('regular_healthy',0)+u.get('regular_wounded',0)

def militia_size(w,u):return w.size(u)-regular_size(u)


def move_regular(u,g,count,field):
    key='regular_'+field
    cavkey='cavalry_wounded' if field=='wounded' else 'cavalry'
    cav=military.portion(count,u[key],u[cavkey])
    u[key]-=count;u[field]-=count;u[cavkey]-=cav
    g[field]+=count;g[cavkey]+=cav
    if count:g['last_battle']=max(g['last_battle'],u['last_battle'])


def resume(w,u):
    home=w.cities.get(u['home'])
    if not home or home['nation']!=u['nation'] or home['convoy'] not in (None,u['id']):
        if home and home.get('convoy')==u['id']:home['convoy']=None
        choices=sorted((c for c in w.cities.values() if c['nation']==u['nation'] and c['convoy'] in (None,u['id']) and not w.besieged(c['id']) and w.size(w.units[c['militia']])+militia_size(w,u)<=w.cfg['militia_cap']),key=lambda c:(military.distance(u,c),c['id']))
        for c in choices:
            if w.route(u,c['x'],c['y']) is not None:
                home=c;u.update(home=c['id'],phase='orphan_return');c['convoy']=u['id'];break
        else:u.update(phase='orphan_return',path=[],order=None);return
    home['convoy']=u['id']
    target=supply_target(w,u) if u['mission']=='supply' else w.cities.get(u.get('destination'))
    if u['phase'] in ('outbound','waiting_supply'):
        if not target or target['nation']!=u['nation'] or (u['mission']!='supply' and w.besieged(target['id'])):u['phase']='return'
    outbound=u['phase'] in ('outbound','waiting_supply')
    target=target if outbound else home
    path=w.route(u,target['x'],target['y'])
    if path is None:u.update(path=[],order=None);return
    if outbound and u['mission']=='supply' and not can_supply(w,target):
        # Wait 1.5 map units before the target on the actual navigable route.
        points=[(u['x'],u['y'])]+path;remaining=1500
        while len(points)>1 and remaining>0:
            a,b=points[-2],points[-1];length=math.dist(a,b)
            if length<=remaining:remaining-=length;points.pop()
            else:
                ratio=(length-remaining)/length
                points[-1]=(round(a[0]+(b[0]-a[0])*ratio),round(a[1]+(b[1]-a[1])*ratio));remaining=0
        path=points[1:];u['phase']='waiting_supply'
    elif outbound:u['phase']='outbound'
    u.update(path=path,order={'type':'move','x':target['x'],'y':target['y']})


def arrival(w,u):
    if u['battle']:return
    home=w.cities.get(u['home'])
    if not home or home['nation']!=u['nation'] or home['convoy']!=u['id']:
        resume(w,u)
        home=w.cities.get(u['home'])
        if not home or home['nation']!=u['nation'] or home['convoy']!=u['id']:return
    if u['phase'] in ('outbound','waiting_supply') and u['mission']=='supply':
        target=supply_target(w,u)
        if not target or target['nation']!=u['nation']:u['phase']='return';resume(w,u);return
        if not can_supply(w,target) or military.distance(u,target)>1000:return
        n=give_food(w,w.members(target),u['cargo_food'],'supply');u['cargo_food']-=n
        w.stats['supply_delivered_food']+=n
        w.emit('supply_exchange',f'部队接收补给 {n/1000:.1f}',nation=u['nation'],unit=u['id'],target=target['id'])
        u['phase']='return';resume(w,u);return
    if u['phase']=='outbound':
        c=w.cities.get(u.get('destination'))
        if not c or c['nation']!=u['nation'] or w.besieged(c['id']):resume(w,u);return
        if military.distance(u,c)>500:return
        g=w.units[c['garrison']];room=max(0,w.cfg['garrison_cap']-w.size(g))
        for field in ('healthy','wounded'):
            n=min(u['regular_'+field],room);move_regular(u,g,n,field);room-=n
        if u['mission']=='fetch':
            n=min(u['requested_food'],w.cfg['city_cargo']-u['cargo_food'],max(0,c['food']-w.cfg['city_reserve']))
            c['food']-=n;u['cargo_food']+=n;w.stats['supply_fetched_food']+=n
        else:
            n=min(u['cargo_food'],max(0,w.cfg['warehouse']-c['food']))
            c['food']+=n;u['cargo_food']-=n;w.stats['supply_delivered_food']+=n
        u['phase']='return';resume(w,u);return
    c=w.cities.get(u['home'])
    if not c or c['nation']!=u['nation']:resume(w,u);return
    if military.distance(u,c)>500 or w.besieged(c['id']):return
    g=w.units[c['garrison']];m=w.units[c['militia']]
    if g['battle'] or m['battle']:return
    # Return personnel even if the warehouse is full; leave excess stores with the cart.
    room=max(0,w.cfg['garrison_cap']-w.size(g))
    for field in ('healthy','wounded'):
        n=min(u['regular_'+field],room);move_regular(u,g,n,field);room-=n
    room=max(0,w.cfg['militia_cap']-w.size(m))
    for field in ('healthy','wounded'):
        n=min(u[field]-u['regular_'+field],room);u[field]-=n;m[field]+=n;room-=n
    for field in ('cargo_food','food'):
        n=min(u[field],max(0,w.cfg['warehouse']-c['food']));u[field]-=n;c['food']+=n
    if not w.size(u) and not u['food']+u['cargo_food']:w.remove(u['id'])


def patrol_tick(w):
    for c in w.cities.values():
        if any(u['kind']=='patrol' and u['home']==c['id'] for u in w.units.values()):continue
        g=w.units[c['garrison']];count=w.cfg['patrol_size']
        villages=sorted(v['id'] for v in w.villages.values() if v['city']==c['id'])
        reserve=count*w.cfg['field_ration']*w.cfg['carry_days']
        if not villages or w.hour<c.get('patrol_due',0) or w.besieged(c['id']) or g['battle'] or g['healthy']-count<w.cfg['patrol_reserve'] or c['food']<reserve:continue
        p=w.new_unit('patrol',c['nation'],c['clan'],0,c['x'],c['y'],home=c['id'],food=reserve)
        military.transfer(g,p,count);c['food']-=reserve
        p.update(patrol_route=villages+[c['id']],patrol_index=0,patrol_phase='route')
        w.emit('patrol_departed',f"{c['name']}派出{count}人巡逻队",nation=c['nation'],unit=p['id'])
    for p in list(w.units.values()):
        if p['kind']!='patrol' or p['battle']:continue
        home=w.cities.get(p['home'])
        if not home or home['nation']!=p['nation']:
            choices=sorted((c for c in w.cities.values() if c['nation']==p['nation'] and not w.besieged(c['id'])),key=lambda c:(military.distance(p,c),c['id']))
            home=next((c for c in choices if w.route(p,c['x'],c['y']) is not None),None)
            if not home:p.update(order=None,path=[]);continue
            p.update(home=home['id'],patrol_phase='return')
        if p['healthy']<w.cfg['patrol_size'] or p['wounded'] or p['food']<w.size(p)*w.cfg['field_ration']*3:p['patrol_phase']='return'
        if p['patrol_phase']=='chase':
            target=w.units.get((p['order'] or {}).get('target'))
            anchor=p['chase_anchor']
            if target and target['healthy'] and w.hour-p['chase_start']<w.cfg['patrol_chase_hours'] and military.distance(target,anchor)<=w.cfg['patrol_chase_distance'] and military.distance(p,anchor)<=w.cfg['patrol_chase_distance']:continue
            p['patrol_phase']='route';p.update(order=None,path=[],patrol_scan_after=w.hour+w.cfg['patrol_chase_hours'])
        if p['patrol_phase']=='route':
            threats=sorted((u for u in w.units.values() if u['kind']=='bandit' and w.hour>=p.get('patrol_scan_after',0) and u['healthy'] and military.distance(p,u)<=w.cfg['patrol_chase_distance']),key=lambda u:(military.distance(p,u),u['id']))
            target=next((u for u in threats if w.route(p,u['x'],u['y']) is not None),None)
            if target:
                p.update(patrol_phase='chase',chase_start=w.hour,chase_anchor={'x':p['x'],'y':p['y']})
                w.go(p,target['x'],target['y'],{'type':'attack','target':target['id']});continue
            key=p['patrol_route'][p['patrol_index']]
            target=w.villages.get(key,w.cities.get(key))
            if not target or target['nation']!=p['nation']:p['patrol_phase']='return'
            elif military.distance(p,target)<=500:
                p['patrol_index']+=1
                if p['patrol_index']>=len(p['patrol_route']):p['patrol_phase']='return'
                else:target=w.villages.get(p['patrol_route'][p['patrol_index']],home)
        if p['patrol_phase']=='return':
            target=home
            if military.distance(p,home)<=500 and not w.besieged(home['id']):
                g=w.units[home['garrison']];room=max(0,w.cfg['garrison_cap']-w.size(g))
                for field in ('healthy','wounded'):
                    n=min(p[field],room);military.transfer(p,g,n,field);room-=n
                n=min(p['food'],max(0,w.cfg['warehouse']-home['food']));home['food']+=n;p['food']-=n
                if not w.size(p):
                    w.remove(p['id']);home['patrol_due']=w.hour+24
                continue
        path=w.route(p,target['x'],target['y'])
        p.update(path=path or [],order={'type':'move','x':target['x'],'y':target['y']})


def tick(w):
    patrol_tick(w)
    for u in list(w.units.values()):
        if u.get('militia_convoy') and not u['battle']:resume(w,u)
