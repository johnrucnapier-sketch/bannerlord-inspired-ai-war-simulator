"""Opt-in castle cavalry and militia logistics. Legacy worlds never enter these rules."""
import math

def enabled(w):return bool(w.cfg.get('castle_logistics'))
def distance(a,b):return math.isqrt((a['x']-b['x'])**2+(a['y']-b['y'])**2)
def portion(count,total,cavalry):
    if not total:return 0
    return min(cavalry,max(0,count-(total-cavalry),(2*count*cavalry+total)//(2*total)))
def take_cavalry(u,count,field='healthy',troop_type=None):
    key='cavalry_wounded' if field=='wounded' else 'cavalry'
    cav=u.get(key,0);total=u[field]
    if troop_type not in (None,'infantry','cavalry'):raise ValueError('兵种须为infantry或cavalry')
    if troop_type=='cavalry':
        if count>cav:raise ValueError('骑兵不足')
        take=count
    elif troop_type=='infantry':
        if count>total-cav:raise ValueError('步兵不足')
        take=0
    else:take=portion(count,total,cav)
    u[key]=cav-take
    return take

def transfer(src,dst,count,field='healthy',troop_type=None):
    n=take_cavalry(src,count,field,troop_type)
    src[field]-=count;dst[field]+=count
    key='cavalry_wounded' if field=='wounded' else 'cavalry'
    dst[key]=dst.get(key,0)+n

def casualties(u,loss,dead):
    hit=take_cavalry(u,loss)
    killed=portion(dead,loss,hit)
    u['cavalry_wounded']+=hit-killed

def heal(u,count):u['cavalry']+=take_cavalry(u,count,'wounded')

def speed(u,speeds,members=None):
    base=speeds.get('army' if u.get('army') else u['kind'],0)
    if 'cavalry' not in u or u['kind']!='party':return base
    group=members or [u]
    total=sum(p['healthy']+p['wounded'] for p in group)
    cavalry=sum(p.get('cavalry',0)+p.get('cavalry_wounded',0) for p in group)
    return base*(5*total+cavalry)//(5*total) if total else base

def exchange(u,g):
    if 'cavalry_target' not in u:return
    target=min(u['healthy'],u['cavalry_target'])
    if target>u['cavalry']:
        n=min(target-u['cavalry'],u['healthy']-u['cavalry'],g['cavalry'])
        u['cavalry']+=n;g['cavalry']-=n
    else:
        n=min(u['cavalry']-target,g['healthy']-g['cavalry'])
        u['cavalry']-=n;g['cavalry']+=n

def service(w,u,c):
    if not w.cfg.get('auto_city_service') or u['kind']!='party' or u['battle'] or c['nation']!=u['nation'] or w.besieged(c['id']):return
    g=w.units[c['garrison']]
    if g['battle'] or g['army'] or distance(g,c)>500:return
    moved=min(u['wounded'],max(0,w.cfg['garrison_cap']-w.size(g)))
    transfer(u,g,moved,'wounded')
    if moved:g['last_battle']=max(g['last_battle'],u['last_battle'])
    reserve=w.cfg.get('expansion_reserve',0) if sum(p['kind']=='party' and p['clan']==c['clan'] for p in w.units.values())<w.cfg['clan_party_cap'] else 0
    target=min(w.cfg['party_cap'],max(u.get('refill_target',w.cfg['party_cap']),u.get('reserve_refill_target',0)))
    taken=min(max(0,g['healthy']-reserve),max(0,target-w.size(u)))
    transfer(g,u,taken)
    extra=min(max(0,g['healthy']-w.cfg.get('garrison_expansion_threshold',400)),max(0,w.cfg['party_cap']-w.size(u)))
    if extra:
        transfer(g,u,extra)
        u['reserve_refill_target']=max(u.get('reserve_refill_target',0),u['healthy'])
        u['refill_target']=max(u.get('refill_target',150),u['reserve_refill_target'])
    exchange(u,g);w.trim_food(u);w.refill(u,c)

def train(w):
    for c in w.cities.values():
        if c.get('settlement_type')!='castle':continue
        g=w.units[c['garrison']]
        if w.besieged(c['id']) or g['battle'] or g['healthy']<=g['cavalry']:continue
        c['training_hours']+=1
        if c['training_hours']>=72:
            c['training_hours']-=72;g['cavalry']+=1;w.stats['cavalry_trained']+=1
            w.emit('cavalry_trained',f"{c['name']}将1名驻军步兵训练为骑兵",city=c['id'],nation=c['nation'])

def away_militia(w,c):
    return sum(w.size(u) for u in w.units.values() if u.get('militia_convoy') and u['home']==c['id'] and u['nation']==c['nation'])

def dispatch(w,nation,c,cmd):
    dst=w.cities.get(cmd.get('destination'));mission=cmd.get('mission','deliver')
    if mission not in ('deliver','fetch'):raise ValueError('运输任务须为deliver或fetch')
    if not dst or dst['nation']!=nation or dst['id'] not in c['supply_neighbors'] or w.besieged(dst['id']):raise ValueError('仅可运输到邻近、未被围城的友方据点')
    if c['convoy'] or any(u.get('militia_convoy') and u['home']==c['id'] and u['nation']==nation for u in w.units.values()):raise ValueError('本据点已有运粮队')
    m=w.units[c['militia']];crew=w.cfg['city_crew'];reserve=w.cfg['city_reserve']
    if m['battle'] or m['healthy']<crew or c['food']<reserve:raise ValueError('需50名健康民兵及150粮口粮')
    amount=cmd.get('food',w.cfg['city_cargo']-reserve)
    if type(amount) is not int or amount<0:raise ValueError('粮食数量无效')
    path=w.route(m,dst['x'],dst['y'])
    if path is None:raise ValueError('目的地不可达')
    cargo=min(amount,w.cfg['city_cargo']-reserve,max(0,c['food']-reserve)) if mission=='deliver' else 0
    u=w.new_unit('city_cart',nation,c['clan'],crew,c['x'],c['y'],home=c['id'],food=reserve)
    m['healthy']-=crew;c['food']-=reserve+cargo
    u.update(militia_convoy=True,mission=mission,requested_food=amount,cargo_food=cargo,phase='outbound',destination=dst['id'],path=path,order={'type':'move','x':dst['x'],'y':dst['y']})
    c['convoy']=u['id'];w.stats['supply_dispatches']+=1
    w.emit('supply_departed',f"{c['name']}派出50民兵前往{dst['name']}"+('取粮' if mission=='fetch' else '送粮'),nation=nation,unit=u['id'],city=c['id'],important=True)
    return {'ok':True,'unit':u['id']}

def resume(w,u):
    home=w.cities.get(u['home']);dst=w.cities.get(u.get('destination'))
    if not home or home['nation']!=u['nation'] or home['convoy'] not in (None,u['id']):
        if home and home.get('convoy')==u['id']:home['convoy']=None
        choices=sorted((c for c in w.cities.values() if c['nation']==u['nation'] and c['convoy'] in (None,u['id']) and w.size(w.units[c['militia']])+w.size(u)<=w.cfg['militia_cap'] and not w.besieged(c['id'])),key=lambda c:(distance(u,c),c['id']))
        for c in choices:
            if w.route(u,c['x'],c['y']) is not None:
                home=c;u['home']=c['id'];c['convoy']=u['id'];u['phase']='orphan_return';break
        else:u.update(phase='orphan_return',path=[],order=None);return
    home['convoy']=u['id']
    if u['phase']=='outbound' and (not dst or dst['nation']!=u['nation'] or w.besieged(dst['id'])):u['phase']='return'
    target=dst if u['phase']=='outbound' else home
    path=w.route(u,target['x'],target['y'])
    u.update(path=path or [],order={'type':'move','x':target['x'],'y':target['y']})

def arrival(w,u):
    home=w.cities.get(u['home'])
    if not home or home['nation']!=u['nation'] or home['convoy']!=u['id']:
        resume(w,u)
        home=w.cities.get(u['home'])
        if not home or home['nation']!=u['nation'] or home['convoy']!=u['id']:return
    if u['phase']=='outbound':
        c=w.cities.get(u.get('destination'));home=w.cities.get(u['home'])
        if not home or home['nation']!=u['nation'] or not c or c['nation']!=u['nation'] or w.besieged(c['id']):resume(w,u);return
        if distance(u,c)>500:return
        if u['mission']=='fetch':
            # Do not drain the source's final 150 food. Waiting/consumption cannot manufacture cargo.
            n=min(u['requested_food'],w.cfg['city_cargo']-u['food']-u['cargo_food'],max(0,c['food']-w.cfg['city_reserve']))
            c['food']-=n;u['cargo_food']+=n;w.stats['supply_fetched_food']+=n
        else:
            n=min(u['cargo_food'],max(0,w.cfg['warehouse']-c['food']))
            c['food']+=n;u['cargo_food']-=n;w.stats['supply_delivered_food']+=n
        w.emit('supply_exchange',f"{w.unit_name(u)}在{c['name']}"+('取粮' if u['mission']=='fetch' else '交粮')+f" {n/1000:.1f}",nation=u['nation'],unit=u['id'],city=c['id'],important=True)
        u['phase']='return';resume(w,u);return
    c=w.cities.get(u['home'])
    if not c or c['nation']!=u['nation']:resume(w,u);return
    if distance(u,c)>500 or w.besieged(c['id']):return
    m=w.units[c['militia']]
    if m['battle']:return
    capacity=max(0,w.cfg['warehouse']-c['food'])
    for field in ('cargo_food','food'):
        n=min(u[field],capacity);u[field]-=n;c['food']+=n;capacity-=n
    # A full warehouse does not delete cargo or duplicate men: wait with the actual load.
    if u['food']+u['cargo_food']:return
    room=max(0,w.cfg['militia_cap']-w.size(m))
    for field in ('healthy','wounded'):
        n=min(u[field],room);u[field]-=n;m[field]+=n;room-=n
    if not w.size(u):w.remove(u['id'])


def check(w):
    for u in w.units.values():
        assert 0<=u['cavalry']<=u['healthy'],u
        assert 0<=u['cavalry_wounded']<=u['wounded'],u
        if u['kind'] not in ('party','garrison'):assert u['cavalry']==u['cavalry_wounded']==0
        if u.get('militia_convoy'):
            assert u['food']+u['cargo_food']<=w.cfg['city_cargo']
            assert w.size(u)<=50
    for c in w.cities.values():
        own=[u for u in w.units.values() if u.get('militia_convoy') and u['home']==c['id'] and u['nation']==c['nation']]
        assert len(own)<=1
        assert not own or c['convoy']==own[0]['id']


def policy_commands(obs):
    """Small observation-only baseline adapter, not an optimized logistics policy."""
    cities=[c for c in obs['cities'] if c['nation']==obs['nation'] and 'food' in c]
    units={u['id']:u for u in obs['units']};byid={c['id']:c for c in cities};cmd=[]
    planned={c['id']:c['food'] for c in cities}
    for c in sorted(cities,key=lambda c:c['id']):
        if c.get('convoy') or c.get('militia') not in units or units[c['militia']]['healthy']<50:continue
        peers=[byid[i] for i in c.get('supply_neighbors',[]) if i in byid]
        needy=[d for d in peers if planned[d['id']]<200000]
        if planned[c['id']]>450000 and needy:
            d=min(needy,key=lambda d:(planned[d['id']],d['id']))
            amount=min(planned[c['id']]-300000,500000-planned[d['id']])
            cmd.append(dict(type='dispatch',city=c['id'],destination=d['id'],food=amount))
            planned[c['id']]-=amount+150000;planned[d['id']]+=amount
        elif planned[c['id']]>=150000 and planned[c['id']]<200000:
            donors=[d for d in peers if planned[d['id']]>500000]
            if donors:
                d=max(donors,key=lambda d:(planned[d['id']],d['id']));amount=min(500000-planned[c['id']],planned[d['id']]-300000)
                cmd.append(dict(type='dispatch',city=c['id'],destination=d['id'],mission='fetch',food=amount))
                planned[d['id']]-=amount;planned[c['id']]+=amount-150000
    for u in units.values():
        if u['nation']!=obs['nation'] or u['kind']!='party' or u['battle'] or u.get('cavalry_target')==obs['limits']['party_cap']:continue
        if any(distance(u,c)<=500 and units.get(c['garrison'],{}).get('cavalry',0)>0 for c in cities):
            cmd.append(dict(type='set_composition',unit=u['id'],cavalry_target=obs['limits']['party_cap']))
    return cmd
