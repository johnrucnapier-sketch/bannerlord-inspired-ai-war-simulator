"""Family army boundary and an explicit ruler/marshal support exception.

The game has no named hero simulation: authority is represented by a host clan.
Initial ruler clans were verified by matching kingdom and clan owner heroes in
the vanilla scenario data (all happen to have suffix 1). Marshals
may be supplied explicitly through cfg.marshal_clans. These are organizational
roles, not diplomatic alliances. The one-slot dead end in the source Mod is
corrected: a clan unable to form a two-party army may offer its strongest party.
Emergency checks use the receiving country's visible information, never global
hidden opponent strength.
"""


def home(w,clan):
    owned=[c for c in w.cities.values() if c['clan']==clan and c['nation']==w.clan_nation(clan)]
    initial=w.map_clans[str(clan)].get('initial_home_settlement')
    return next((c for c in owned if c['id']==initial),None) or next(iter(sorted(owned,key=lambda c:(c.get('settlement_type')!='town',c['id']))),None)


def ready(w,clan):
    parties=[u for u in w.units.values() if u['kind']=='party' and u['clan']==clan]
    base=home(w,clan)
    return bool(parties and base and sum(w.size(u) for u in parties)*5>=len(parties)*w.cfg['party_cap']*4 and w.size(w.units[base['garrison']])*2>w.cfg['garrison_cap'])


def army_clan(w,aid):
    meta=getattr(w,'army_metadata',{}).get(aid)
    if meta:return meta['clan']
    ids=w.armies.get(aid,[])
    return w.units[ids[0]]['clan'] if ids else None


def can_support(w,unit,leader):
    if unit['kind']!='party' or leader['kind']!='party' or unit['nation']!=leader['nation']:return False
    nation=w.nations[str(leader['nation'])]
    hosts={nation.get('ruler_clan'),w.cfg.get('marshal_clans',{}).get(str(leader['nation']))}
    if leader['clan'] not in hosts:return False
    clan=unit['clan']
    if clan==leader['clan']:return True
    if unit.get('army') or unit.get('battle'):return False
    if any(army_clan(w,aid)==clan for aid in w.armies):return False
    # No second detachment from the same source clan in another clan's army.
    if any(u['clan']==clan and u.get('army') for u in w.units.values() if u['kind']=='party'):return False
    candidates=[u for u in w.units.values() if u['kind']=='party' and u['clan']==clan and not u['battle'] and not u['army']]
    if not candidates or unit['id']!=max(candidates,key=lambda u:(u['healthy'],u['id']))['id']:return False
    if home(w,clan) is None:return True # Original landless, non-mercenary exception.
    if w.clan_party_limit(clan)>=2 and ready(w,clan):return False
    own=sum(u['healthy'] for u in w.units.values() if u['nation']==unit['nation'] and u['kind']=='party')
    seen_enemy=sum(u['healthy'] for u in w.units.values() if u['nation']>=0 and w.hostile(unit['nation'],u['nation']) and u['kind']=='party' and w.visible(unit['nation'],u))
    emergency=any(c['nation']==unit['nation'] and w.besieged(c['id']) for c in w.cities.values()) and seen_enemy>2*own
    minimum=50 if emergency else 100
    numerator=35 if emergency else 70
    return unit['healthy']>=minimum and unit['healthy']*100>=w.cfg['party_cap']*numerator


def validate_assembly(w,leader,members):
    clan=leader['clan']
    if any(army_clan(w,aid)==clan for aid in w.armies):raise ValueError('同一家族最多拥有一个军团')
    foreign=set()
    for u in members:
        if u['clan']==clan:continue
        if u['clan'] in foreign or not can_support(w,u,leader):raise ValueError('跨家族仅允许符合条件的单支援军加入国王或元帅军团')
        foreign.add(u['clan'])


def check(w):
    hosts=[]
    for aid,ids in w.armies.items():
        host=army_clan(w,aid);hosts.append(host)
        foreign={}
        for uid in ids:
            u=w.units[uid]
            if u['clan']!=host:
                assert u['kind']=='party', '民兵只跟随本家军团'
                foreign[u['clan']]=foreign.get(u['clan'],0)+1
        assert all(count==1 for count in foreign.values())
    assert len(hosts)==len(set(hosts)), '同一家族只能有一个军团'
