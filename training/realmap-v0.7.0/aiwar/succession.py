"""End-of-hour extinction and reproducible, independent clan allegiance draws.

Only castle/town ownership sustains a country. All extinctions in an hour use
one survivor snapshot. Migration changes allegiance, never bodies or supplies.
Historical vision stays with its old country; ordinary visibility is refreshed
by the caller afterwards. Mobilized soldiers retain their physical source and
may deposit only under mobilization._owned's same-country AND same-clan check.
"""
import hashlib
import json
import random


def _cancel_battles(w, migrated):
    # Cancel the whole connected siege/relief engagement, with no winner,
    # capture, loot or casualty. This avoids dangling suspended formations.
    touched = {bid for bid, b in w.battles.items()
               if any(uid in migrated for ids in b['sides'].values() for uid in ids)}
    touched.update(u['battle'] for uid, u in w.units.items()
                   if uid in migrated and u.get('battle') in w.battles)
    while True:
        expanded = touched | {bid for bid, b in w.battles.items()
                              if bid in touched or b.get('relief_for') in touched
                              or b.get('relief_battle') in touched}
        expanded |= {w.battles[bid][key] for bid in touched if bid in w.battles
                     for key in ('relief_for', 'relief_battle')
                     if w.battles[bid].get(key) in w.battles}
        if expanded == touched:break
        touched = expanded
    for u in w.units.values():
        if u.get('battle') in touched:
            u.update(battle=None, last_battle=w.hour, order=None, path=[])
    for bid in sorted(touched):
        w.battles.pop(bid, None)
        if hasattr(w, 'emit'):
            w.emit('battle_cancelled', '国家灭亡后家族转投，交战解除', battle=bid, reason='clan_migration', important=True)


def resolve(w):
    """Resolve new extinctions once; return only this call's migration records.

    Call after all captures for an hour and before visibility/termination. The
    world serializer persists both lists without special RNG serialization.
    """
    if not hasattr(w, 'extinct_nations'):w.extinct_nations = []
    if not hasattr(w, 'clan_migrations'):w.clan_migrations = []
    owned = {int(c['nation']) for c in w.cities.values()
             if c.get('settlement_type', 'town') in ('town', 'castle')}
    extinct = set(w.extinct_nations)
    newly = {int(n) for n in w.nations if int(n) not in owned and int(n) not in extinct}
    survivors = sorted((int(n) for n in w.nations if int(n) in owned and int(n) not in extinct),
                       key=lambda n: w.nations[str(n)]['kingdom'])
    if not newly:return []
    if not survivors:raise ValueError('Extinction cannot migrate clans: no surviving country owns a town or castle')
    w.extinct_nations = sorted(extinct | newly)
    for n in newly:w.nations[str(n)]['extinct_hour'] = w.hour
    changes = []
    for key, clan in sorted(w.map_clans.items(), key=lambda item: str(item[1].get('id', item[0]))):
        old = clan['nation']
        if old not in newly:continue
        source = clan.get('id', key)
        material = json.dumps([w.seed, w.hour, source], separators=(',', ':'), ensure_ascii=True)
        rng = random.Random(int.from_bytes(hashlib.sha256(material.encode()).digest(), 'big'))
        dest = survivors[rng.randrange(len(survivors))]
        clan.setdefault('origin_nation', old)
        clan.setdefault('original_kingdom', clan.get('kingdom', w.nations[str(old)]['kingdom']))
        clan.update(nation=dest, kingdom=w.nations[str(dest)]['kingdom'])
        changes.append(dict(hour=w.hour, clan=int(key), source_clan=source, from_nation=old, to_nation=dest))
    moved = {e['clan']:e['to_nation'] for e in changes}
    migrated = {uid for uid,u in w.units.items() if u.get('clan') in moved}
    _cancel_battles(w, migrated)
    for aid, ids in list(w.armies.items()):
        if any(uid in migrated for uid in ids) or getattr(w, 'army_metadata', {}).get(aid, {}).get('clan') in moved:
            for uid in ids:
                if uid in w.units:w.units[uid].update(army=None, order=None, path=[])
            del w.armies[aid]
            getattr(w, 'army_metadata', {}).pop(aid, None)
    for uid in migrated:
        u = w.units[uid]
        u.setdefault('origin_nation', u['nation'])
        u.update(nation=moved[u['clan']], army=None, battle=None)
        # Remote levies/couriers keep physical orders until they discover the
        # invalid source/army through the existing mobilization lifecycle.
        if u['kind'] not in ('levy', 'mobilization_messenger'):
            u.update(order=None, path=[])
    for rec in getattr(w, 'mobilizations', {}).values():
        if rec['clan'] in moved:
            rec.setdefault('origin_nation', rec['nation'])
            rec['nation'] = moved[rec['clan']]
    # Save/load breaks initial dictionary aliasing; explicitly repair metadata.
    if hasattr(w, 'map_info'):
        w.map_info['clans'] = w.map_clans
        w.map_info['nation_registry'] = w.nations
    w.clan_migrations.extend(changes)
    if hasattr(w, 'emit'):
        for e in changes:
            w.emit('clan_migrated', '亡国家族随机转投其他国家', nation=e['to_nation'], **{k:v for k,v in e.items() if k != 'hour'})
    return changes
