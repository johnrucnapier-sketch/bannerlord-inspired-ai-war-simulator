"""Experimental reconstructed policy, not byte recovery of the lost v0.8 source.

Observation-only, deterministic, with all durable scheduling state in the engine.
No shared vision, negotiation text, coordinated goals, or military rule changes.
"""
PARAMETERS = dict(front_cost=1.4, low_food_days=14, severe_food_days=7,
                  peace_threshold=1.5, alliance_threshold=1.0,
                  dominant_land_share=.30, declaration_readiness=.7,
                  deploy_min_healthy=25, deploy_max_wound_fraction=.35,
                  deploy_food_days=7)
VERSION = 'diplomacy-policy-v080-rebuilt-experimental'


def relation(obs, a, b):
    if a == b:
        return 'self'
    if a < 0 or b < 0:
        return 'war'
    d = obs.get('diplomacy', {})
    if not d.get('enabled'):
        return 'war'
    matrix = d.get('public_relations', {})
    row = matrix.get(str(a), matrix.get(a, {}))
    return row.get(str(b), row.get(b, 'peace'))


def assessment(obs):
    n = obs['nation']; cities = obs.get('cities', []); units = obs.get('units', [])
    nations = sorted({c['nation'] for c in cities if c['nation'] >= 0} - set(obs.get('extinct_nations', [])))
    own = [c for c in cities if c['nation'] == n and 'food' in c and not c.get('stale')]
    byid = {c['id']: c for c in cities}
    land = {k: sum(c['nation'] == k for c in cities) for k in nations}
    borders = {k: sum(any(byid.get(i, {}).get('nation') == k for i in c.get('neighbors', [])) for c in own) for k in nations if k != n}
    field = [u for u in units if u['nation'] == n and u['kind'] in ('party', 'levy')]
    healthy = sum(u.get('healthy', 0) for u in field)
    wounded = sum(u.get('wounded', 0) for u in field)
    capacity = sum(obs.get('limits', {}).get('party_cap', 150) if u['kind'] == 'party' else u.get('healthy', 0)+u.get('wounded', 0) for u in field)
    ration = obs.get('limits', {}).get('field_ration', 100)
    def deployable(u):
        size = u.get('healthy', 0)+u.get('wounded', 0)
        minimum = PARAMETERS['deploy_min_healthy'] if u['kind'] == 'party' else 1
        return (u.get('healthy', 0) >= minimum
                and u.get('wounded', 0)/max(1, size) <= PARAMETERS['deploy_max_wound_fraction']
                and u.get('food', 0)/max(1, size*ration) >= PARAMETERS['deploy_food_days'])
    ready = sum(deployable(u) for u in field)/max(1, len(field))
    food_days = sum(u.get('food', 0) for u in field)/max(1, (healthy+wounded)*ration)
    reserve = sum(u.get('healthy', 0) for u in units if u['nation'] == n and u['kind'] == 'garrison')
    replenishment = min(1., reserve/max(1, capacity-healthy))
    wars = [k for k in nations if k != n and relation(obs, n, k) == 'war']
    fronts = sum(borders.get(k, 0) > 0 for k in wars)
    visible = {k: sum(u.get('healthy', 0)*(.5 if u['kind'] == 'levy' else 1) for u in units if u['nation'] == k and u['kind'] in ('party', 'levy') and not u.get('stale')) for k in nations}
    proxy = {k: max(visible[k], land[k]*100.) for k in nations}
    strength = max(healthy, land.get(n, 0)*100.)
    pressure = (max(0, fronts-1)*PARAMETERS['front_cost'] + max(0, .75-ready)*3
                + (1.5 if food_days < PARAMETERS['severe_food_days'] else .7 if food_days < PARAMETERS['low_food_days'] else 0)
                + max(0, .5-replenishment))
    return dict(nations=nations, land=land, borders=borders, wars=wars, fronts=fronts,
                own_strength=strength, visible_strength=visible, capacity_proxy=proxy,
                readiness=ready, reinforcement_fill=healthy/max(1,capacity), food_days=food_days,
                replenishment=replenishment, pressure=pressure, own_healthy=healthy)


def alliance_feasible(obs, other):
    n = obs['nation']; d = obs.get('diplomacy', {})
    def bloc(country):
        return next((set(group) for group in d.get('alliance_components', []) if country in group), {country})
    a, b = bloc(n), bloc(other)
    if a & b or any(relation(obs,x,y) == 'war' for x in a for y in b):
        return False
    merged = a | b
    nations = {int(k) for k in d.get('public_relations', {})} - set(obs.get('extinct_nations', []))
    enemies = {y for x in merged for y in nations-merged if relation(obs,x,y) == 'war'}
    return not any(relation(obs,x,y) == 'nap' for x in merged for y in enemies)


def scores(obs, a, other):
    wars = a['wars']; ratio = a['capacity_proxy'].get(other, 0)/max(1,a['own_strength'])
    peace = a['pressure'] + min(2.,ratio)*.6 + (.8 if not a['borders'].get(other) else 0)
    if len(wars) <= 1 and a['readiness'] >= .7 and a['food_days'] >= 14:
        peace -= 1.2
    shared = [k for k in wars if k != other and relation(obs,other,k) == 'war']
    imported = [k for k in a['nations'] if k not in (obs['nation'],other) and relation(obs,other,k) == 'war' and k not in wars]
    outside = max((a['land'].get(k,0)/max(1,sum(a['land'].values())) for k in shared), default=0)
    alliance = (len(shared)*.35 + (1.2 if outside >= PARAMETERS['dominant_land_share'] else 0)
                + min(1.,a['pressure']*.25) - len(imported)*1.25 - (.5 if a['borders'].get(other) else 0))
    return dict(peace=round(peace,3), alliance=round(alliance,3), shared_wars=shared, imported_wars=imported)


def reason(a,s,decision):
    return dict(policy=VERSION,decision=decision,fronts=a['fronts'],own_readiness=round(a['readiness'],3),
                own_reinforcement_fill=round(a['reinforcement_fill'],3),own_food_days=round(a['food_days'],2),
                own_replenishment=round(a['replenishment'],3),pressure=round(a['pressure'],3),**s,
                enemy_estimate='visible field strength plus known/last-seen settlement capacity proxy; unseen strength and ownership changes unknown')


def decide(obs):
    d = obs.get('diplomacy', {})
    if not d.get('enabled'):
        return []
    a = assessment(obs); n = obs['nation']; commands = []
    incoming = [p for p in d.get('incoming', []) if p.get('expires_hour',obs['hour']+1) > obs['hour']]
    outgoing = [p for p in d.get('outgoing', []) if p.get('expires_hour',obs['hour']+1) > obs['hour']]
    for p in sorted(incoming,key=lambda p:(p['created_hour'],p['id'])):
        other = p['from_nation']; s = scores(obs,a,other); kind = p['kind']
        if kind == 'peace':
            accept = s['peace'] >= PARAMETERS['peace_threshold']
        elif kind == 'nap':
            accept = a['pressure'] >= .7 or not a['borders'].get(other)
        else:
            accept = s['alliance'] >= PARAMETERS['alliance_threshold'] and alliance_feasible(obs,other)
        action = 'accept' if accept else 'reject'
        commands.append(dict(type='diplomacy',action=action,proposal_id=p['id'],reason=reason(a,s,kind+'_'+action)))
    if not d.get('decision_due'):
        return commands
    busy = {p['to_nation'] for p in outgoing} | {p['from_nation'] for p in incoming}
    choices = []
    for other in a['nations']:
        if other == n or other in busy:
            continue
        rel = relation(obs,n,other); s = scores(obs,a,other)
        if rel == 'war' and s['peace'] >= PARAMETERS['peace_threshold']:
            choices.append((s['peace'],-other,'propose_peace',other,s))
        elif rel in ('peace','nap') and s['alliance'] >= PARAMETERS['alliance_threshold'] and alliance_feasible(obs,other):
            choices.append((s['alliance'],-other,'propose_alliance',other,s))
        elif rel == 'peace' and a['pressure'] >= 1.4:
            choices.append((.8,-other,'propose_nap',other,s))
        elif rel == 'peace' and not a['wars'] and a['borders'].get(other) and a['readiness'] >= PARAMETERS['declaration_readiness'] and a['food_days'] >= 14:
            advantage = a['own_strength']/max(1,a['capacity_proxy'][other])
            if advantage >= 1.1:
                choices.append((advantage,-other,'declare_war',other,s))
    if choices:
        _,_,action,other,s = max(choices)
        commands.append(dict(type='diplomacy',action=action,target=other,reason=reason(a,s,action)))
    else:
        commands.append(dict(type='diplomacy',action='hold',reason=reason(a,{},'hold')))
    return commands
