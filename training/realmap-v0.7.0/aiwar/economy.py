"""Owned-city telemetry; no RNG, rule changes, or enemy information."""
import copy

WINDOW = 336


def ledger(world, city):
    data = world.__dict__.setdefault('economy', {})
    row = data.get(city['id'])
    if row is None or row['nation'] != city['nation']:
        row = dict(nation=city['nation'], since=world.hour, trips={}, events=[], samples=[])
        data[city['id']] = row
    return row


def transport(world, kind, unit):
    if unit['kind'] != 'village_cart':
        return
    village = world.villages.get(unit['home'])
    if not village:
        return
    city = world.cities.get(village['city'])
    if city is None:
        return
    if unit['nation'] != city['nation']:
        return
    row = ledger(world, city)
    uid = unit['id']
    if kind == 'depart':
        row['trips'][uid] = dict(start=world.hour, intercepted=False, delivered=False)
    trip = row['trips'].get(uid)
    if not trip:
        return  # Old save / pre-observation journey has no known denominator.
    if kind == 'intercept':
        if trip['intercepted']:
            return
        trip['intercepted'] = True
    if kind == 'delivered':
        trip['delivered'] = True
    row['events'].append(dict(hour=world.hour, kind=kind, trip_start=trip['start']))
    if kind in ('lost', 'returned'):
        row['trips'].pop(uid, None)
    row['events'] = [e for e in row['events'] if e['hour'] >= world.hour - WINDOW*2]


def sample(world):
    for city in world.cities.values():
        row = ledger(world, city)
        villages = [v for v in world.villages.values() if v['city'] == city['id']]
        population = sum(v['population'] + world.size(world.units[v['cart']])
                         if v.get('cart') in world.units else v['population'] for v in villages)
        row['samples']=[s for s in row['samples'] if s['hour']!=world.hour]
        row['samples'].append(dict(hour=world.hour, population=population, food=city['food'], recruits=city['recruits']))
        row['samples'] = [s for s in row['samples'] if s['hour'] >= world.hour - WINDOW*2]
        row['events'] = [e for e in row['events'] if e['hour'] >= world.hour - WINDOW*2]


def reports(world, nation):
    result = {}
    for cid, row in world.__dict__.get('economy', {}).items():
        if world.cities[cid]['nation'] != nation or row['nation'] != nation:
            continue
        # Only owned transport outcomes and resource records leave this boundary.
        result[cid] = copy.deepcopy(row)
    return result
