"""Observation-only organization helpers shared by baseline and submitted policies.

These helpers plan physical commands, never create troops, infer unseen enemies,
or count promised militia. Support eligibility follows published observation
rules; the engine remains the authority for acceptance and courier lifecycle.
"""
import copy
import math
from .navigation import find_route


def near(a,b):return math.hypot(a['x']-b['x'],a['y']-b['y'])<=500

def combat_strength(members):
    return sum(u['healthy']*(.5 if u['kind']=='levy' else 1) for u in members)

def attached_members(obs,members):
    ids={u['id'] for u in members};armies={u.get('army') for u in members if u.get('army')}
    return list(members)+[u for u in obs['units'] if u['nation']==obs['nation'] and u['kind']=='levy' and u.get('army') in armies and u['id'] not in ids]


def _travel_days(obs, leader, city):
    path=find_route(obs['terrain'],leader,city['x'],city['y'])
    if path is None:return math.inf
    points=[(leader['x'],leader['y'])]+list(path)
    length=sum(math.dist(a,b) for a,b in zip(points,points[1:]))
    return length/max(1,leader.get('movement_speed',obs['speeds']['army']))/24


def _prepare_mobilization(obs, commands, records, existing, cities, courier_ready, overwhelmed):
    """Plan the missing physical castle visit, without overriding combat.

    These are baseline strategy choices, not extra engine mobilization rules:
    a threatened clan may visit a reachable own castle; after issuing, its army
    waits at the real family rally through the published collection deadline.
    Seven days is a policy wait budget, not an acknowledgement of remote levies.
    Late cohorts still travel normally and are never counted before arrival.
    """
    result=list(commands);hour=obs['hour'];byclan={r['clan']:r for r in records}
    besieged={b.get('city') for b in obs.get('battles',[]) if b.get('city')}
    for leader,aid,_ in existing:
        if leader.get('battle'):continue
        members=[u for u in obs['units'] if u.get('army')==aid and u['nation']==obs['nation']]
        if any(u.get('battle') for u in members):continue
        ids={u['id'] for u in members}
        # A fight/relief/raid selected by the main policy takes precedence.
        if any(c.get('unit') in ids and (c['type'] in ('attack','siege','raid','disband')
               or c.get('vanilla_task')=='relief') for c in result):continue
        old=leader.get('order') or {}
        if old.get('type') in ('attack','siege','raid'):continue
        if old.get('vanilla_task')=='relief' and not any(c.get('unit') in ids and c['type']=='move' for c in result):continue
        rec=byclan.get(leader['clan']);city=None;phase=None
        if rec and not rec.get('demobilize_requested'):
            deadline=rec.get('rally_until')
            if hour-rec['started']>=168 or (deadline is not None and hour>=deadline):continue
            city=cities.get(rec['rally']);phase='mobilization_rally'
        elif rec is None:
            threatened=any(c['clan']==leader['clan'] and c['id'] in besieged for c in cities.values())
            # Re-evaluate need from the current private view. Retaining an old
            # prepare order alone would pin a clan here after its threat ended,
            # although the issuance check below would then refuse to mobilize.
            if not (threatened or overwhelmed):continue
            options=[c for c in cities.values() if c['clan']==leader['clan']
                     and c.get('settlement_type')=='castle' and courier_ready(c)]
            options.sort(key=lambda c:(_travel_days(obs,leader,c),c['id']))
            city=next(iter(options),None);phase='mobilization_prepare'
        if not city or city['id'] in besieged:continue
        rate=max(1,sum(u['healthy']+u['wounded'] for u in members)*obs['limits']['field_ration'])
        days=sum(u.get('food',0) for u in members)/rate
        if days<2 and city.get('food',0)<rate*2:continue
        if not near(leader,city) and days<=_travel_days(obs,leader,city)+2:continue
        move=dict(type='move',unit=leader['id'],x=city['x'],y=city['y'],
                  vanilla_task=phase,vanilla_base=city['id'])
        # Preserve the campaign to resume after collection, rather than erasing
        # its target when the logistical detour temporarily owns movement.
        intended=next((c for c in reversed(result) if c.get('unit')==leader['id'] and c['type']=='move'),old)
        for key in ('west_target','vanilla_target','vanilla_started'):
            if key in intended:move[key]=intended[key]
        if 'west_target' in move:move['west_task']='clan_campaign'
        result=[c for c in result if not (c.get('unit') in ids and c['type'] in ('move','stop'))]
        if any(old.get(k)!=v for k,v in move.items()):result.append(move)
    return result


def can_support(obs,unit,leader):
    organization=obs.get('organization',{});rules=organization.get('support_rules')
    if not organization.get('ruler_support_exception') or not rules:return False
    n=obs['nation'];own=[u for u in obs['units'] if u['nation']==n and u['kind']=='party']
    registry=obs.get('nations',{}).get(str(n),{})
    hosts={organization.get('ruler_clan',registry.get('ruler_clan')),organization.get('marshal_clan')}-{None}
    if leader['clan'] not in hosts or unit['kind']!='party' or unit['nation']!=n or unit['clan']==leader['clan']:return False
    clan=unit['clan'];parties=[u for u in own if u['clan']==clan]
    if unit.get('army') or unit.get('battle') or any(u.get('army') for u in parties):return False
    candidates=[u for u in parties if not u.get('battle') and not u.get('army')]
    if not candidates or unit['id']!=max(candidates,key=lambda u:(u['healthy'],u['id']))['id']:return False
    # Fog history may still name us as owner after an unseen capture. Only a
    # complete private settlement record can provide current clan resources.
    cities=[c for c in obs['cities'] if c['nation']==n and c.get('clan')==clan
            and 'food' in c and not c.get('stale',False)]
    if not cities:return True
    info=obs.get('map_info',{}).get('clans',{}).get(str(clan),{})
    initial=info.get('initial_home_settlement')
    home=next((c for c in cities if c['id']==initial),None) or min(cities,key=lambda c:(c.get('settlement_type')!='town',c['id']))
    units={u['id']:u for u in obs['units']};g=units.get(home['garrison'],{})
    cap=obs['limits']['party_cap'];slots=obs['limits'].get('clan_party_caps',{}).get(str(clan),obs['limits']['clan_party_cap'])
    ready=(sum(u['healthy']+u['wounded'] for u in parties)*100>=len(parties)*cap*rules['clan_ready_percent'] and
           (g.get('healthy',0)+g.get('wounded',0))*100>obs['limits']['garrison_cap']*rules['home_garrison_percent'])
    if slots>=2 and ready:return False
    besieged={b.get('city') for b in obs.get('battles',[]) if b.get('city')}
    enemy=sum(u['healthy'] for u in obs['units'] if u['nation']>=0 and u['nation']!=n and u['kind']=='party')
    emergency=any(c['id'] in besieged for c in obs['cities'] if c['nation']==n) and enemy>rules['emergency_enemy_ratio']*sum(u['healthy'] for u in own)
    prefix='emergency' if emergency else 'normal'
    return unit['healthy']>=rules[prefix+'_min_healthy'] and unit['healthy']*100>=cap*rules[prefix+'_ready_percent']


def augment_commands(obs,commands):
    """Return commands with legal local ruler support and conditional couriers.

    Input is a planner's full batch. Call once before submitting it. Formation
    membership may change only in assemble commands; support is never remote.
    """
    result=copy.deepcopy(commands);n=obs['nation'];units={u['id']:u for u in obs['units']}
    parties=[u for u in obs['units'] if u['nation']==n and u['kind']=='party']
    reserved={i for c in result if c['type']=='assemble' for i in [c['unit']]+c['units']}
    support_clans={u['clan'] for u in parties if u.get('army')}
    assembling_clans={units[c['unit']]['clan'] for c in result if c['type']=='assemble'}
    # The one-army slot belongs to its host, not every supporting member's
    # clan. Own metadata identifies the host; older views expose a commander
    # or fall back to the first regular party in stable observation order.
    host_clans=set();seen=set()
    for u in parties:
        aid=u.get('army')
        if not aid or aid in seen:continue
        meta=obs.get('army_metadata',{}).get(aid,{})
        commander=units.get(meta.get('commander') or u.get('army_commander'),u)
        host_clans.add(meta.get('clan',commander['clan']));seen.add(aid)
    moves={c['unit']:c for c in result if c['type']=='move'}
    # Existing planned family assemblies may take one lawful strongest party per
    # support clan, but only when its own campaign plan shares the target.
    candidates=list(result)
    for cmd in candidates:
        if cmd not in result:continue
        if cmd['type'] not in ('assemble','move'):continue
        leader=units.get(cmd.get('unit'))
        if not leader or leader.get('army') or leader.get('battle'):continue
        if leader['clan'] in host_clans:continue
        if cmd['type']=='move' and (cmd.get('vanilla_task')!='clan_campaign' or leader['id'] in reserved
                                   or leader['clan'] in assembling_clans):continue
        target=cmd.get('campaign_target') or cmd.get('vanilla_target')
        eligible=[]
        for u in sorted(parties,key=lambda u:(-u['healthy'],u['id'])):
            plan=moves.get(u['id'],u.get('order') or {})
            if u['id'] in reserved or u['clan'] in support_clans or u['clan'] in assembling_clans:continue
            if plan.get('vanilla_target')!=target or not near(u,leader) or not can_support(obs,u,leader):continue
            eligible.append(u);support_clans.add(u['clan']);reserved.add(u['id'])
        if not eligible:continue
        if cmd['type']=='assemble':cmd['units'].extend(u['id'] for u in eligible)
        else:
            assembly=dict(type='assemble',unit=leader['id'],units=[u['id'] for u in eligible],campaign_target=target)
            result.insert(result.index(cmd),assembly);reserved.add(leader['id']);assembling_clans.add(leader['clan'])
        # A member follows its leader; do not overwrite its new formation order.
        ids={u['id'] for u in eligible}
        result=[c for c in result if not (c['type'] in ('move','stop','attack','siege','raid') and c.get('unit') in ids)]

    org=obs.get('organization',{})
    if not org.get('militia_mobilization'):return result
    records=[r for r in obs.get('mobilizations',[]) if r['nation']==n and r['status']!='completed']
    active={r['clan'] for r in records}
    besieged={b.get('city') for b in obs.get('battles',[]) if b.get('city')}
    cities={c['id']:c for c in obs['cities'] if c['nation']==n and 'clan' in c
            and 'food' in c and not c.get('stale',False)}
    stocks={cid:c.get('food',0) for cid,c in cities.items()}
    bodies={cid:units.get(c.get('garrison'),{}).get('healthy',0) for cid,c in cities.items()}
    donor_cities={c.get('garrison'):cid for cid,c in cities.items()}
    reserved=set()
    # Added couriers execute before the planner's batch. They must not consume
    # the mandatory rations or actual troops already promised by that batch.
    per_person=obs['limits']['field_ration']*obs['limits']['carry_days']
    for cmd in result:
        cid=cmd.get('city')
        if cmd['type']=='dispatch' and cid in cities:
            count=cmd.get('troops',0)
            stocks[cid]-=(obs['logistics_limits']['city_crew']+count)*per_person
            bodies[cid]-=count;reserved.add(cid)
        elif cmd['type']=='create' and cid in cities:
            count=cmd.get('count',0);stocks[cid]-=count*per_person
            if cmd.get('source','garrison') in ('garrison',cities[cid]['garrison']):bodies[cid]-=count
            reserved.add(cid)
        elif cmd['type']=='transfer' and cmd.get('unit') in donor_cities:
            cid=donor_cities[cmd['unit']];bodies[cid]-=cmd.get('count',0);reserved.add(cid)
    ration=1000 # One audited grain unit; independent of field ration tuning.
    def courier_ready(city):
        g=units.get(city.get('garrison'),{})
        return city['id'] not in besieged and not g.get('battle') and bodies[city['id']]>=1 and stocks[city['id']]>=ration
    dissolved={units[c['unit']].get('army') for c in result if c['type']=='disband' and c.get('unit') in units}
    armies={u['army'] for u in parties if u.get('army')}
    extra=[]
    for rec in records:
        if rec.get('demobilize_requested'):continue
        if rec['army'] in armies and rec['army'] not in dissolved:continue
        city=cities.get(rec.get('issuer',rec['rally']))
        # Cancellation fans out to multiple independent couriers immediately.
        # Defer it one decision if the issuer already funds another operation,
        # rather than pretending its many messages cost only one grain unit.
        if city and city['id'] not in reserved and city['clan']==rec['clan'] and courier_ready(city):
            extra.append(dict(type='demobilize',clan=rec['clan']));stocks[city['id']]-=ration
    enemy=sum(u['healthy'] for u in obs['units'] if u['nation']>=0 and u['nation']!=n and u['kind']=='party')
    overwhelmed=enemy>sum(u['healthy'] for u in parties)
    planned=[(units[c['unit']],c['unit'],c) for c in result if c['type']=='assemble']
    # Commander is exposed on each own army member, or infer the first regular
    # party in stable observation order when loading older snapshots.
    existing=[];seen=set()
    for u in parties:
        aid=u.get('army')
        if not aid or aid in seen or aid in dissolved:continue
        commander=obs.get('army_metadata',{}).get(aid,{}).get('commander') or u.get('army_commander')
        leader=units.get(commander,u) if commander else u
        seen.add(aid);existing.append((leader,aid,None))
    result=_prepare_mobilization(obs,result,records,existing,cities,courier_ready,overwhelmed)
    for leader,army,assembly in existing+planned:
        clan=leader['clan']
        if clan in active or leader.get('battle'):continue
        threatened=any(c['clan']==clan and c['id'] in besieged for c in cities.values())
        if not (threatened or overwhelmed):continue
        options=[c for c in cities.values() if c['clan']==clan and c.get('settlement_type')=='castle' and near(leader,c) and courier_ready(c)]
        if not options:continue
        city=min(options,key=lambda c:c['id']);command=dict(type='mobilize',city=city['id'],army=army)
        if assembly is None:extra.append(command)
        else:result.insert(result.index(assembly)+1,command)
        active.add(clan);stocks[city['id']]-=ration;bodies[city['id']]-=1
    return (extra+result)[:100]
