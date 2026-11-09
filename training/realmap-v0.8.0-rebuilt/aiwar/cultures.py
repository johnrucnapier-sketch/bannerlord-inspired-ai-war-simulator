"""Deterministic six-culture rules for the multinational baseline.

By default traits follow the CURRENT OWNER NATION: this is an implementation
assumption, not a confirmed cultural-ownership rule. Set ``culture_basis`` to
``origin`` to use each object's ``origin_nation`` instead. Mobile units retain
their origin; settlement garrisons should receive their settlement's origin.
Missing origin metadata falls back to current ownership. Traits are enabled unless ``culture_traits`` is false. Values use integer fixed
point arithmetic; Vlandian recruitment carries tenths on the village so small
weekly recruit batches receive the promised ten percent over time. A remainder
is earned only on eligible harvests and never changes a noneligible harvest.
These helpers do not introduce any troop types beyond infantry and cavalry.
"""


def enabled(w):
    return bool(w.cfg.get('culture_traits', True))


def culture(w, nation):
    """Resolve registry culture without assuming numeric or contiguous nations."""
    lookup = getattr(w, 'culture', None)
    if callable(lookup):
        return lookup(nation)
    registry = getattr(w, 'nations', {})
    entry = registry.get(str(nation), registry.get(nation, {}))
    return entry.get('culture') if isinstance(entry, dict) else None


def trait_nation(w, owner):
    """Select the explicit owner/origin cultural basis; reject unknown modes."""
    basis = w.cfg.get('culture_basis', 'owner')
    if basis not in ('owner', 'origin'):
        raise ValueError('culture_basis must be owner or origin')
    return owner.get('origin_nation', owner.get('nation')) if basis == 'origin' else owner.get('nation')


def _is(w, owner, name):
    nation = trait_nation(w, owner)
    return enabled(w) and culture(w, nation) == name


def militia_cap(w, c):
    return w.cfg['militia_cap'] + (50 if _is(w, c, 'battania') else 0)


def training_hours(w, c):
    """Castle infantry-to-cavalry conversion: seven days, or six for Khuzait."""
    return 144 if c.get('settlement_type') == 'castle' and _is(w, c, 'khuzait') else 168


def city_food_need(w, u, rate):
    """Food for one unit at city rate; Empire discount is garrison-only.

    Fractional food subunits round up, so integer arithmetic never grants more
    than the advertised discount. Healthy and wounded soldiers both eat.
    """
    need = w.size(u) * rate
    return (need * 9 + 9) // 10 if u.get('kind') == 'garrison' and _is(w, u, 'empire') else need


def weekly_yields(w, v):
    """Return this harvest's food/recruits, advancing fractional bonus only."""
    food, recruits = v['population'] * 1000, v['population'] // 100
    linked = w.cities.get(v.get('city'), {})
    if _is(w, v, 'vlandia') and linked.get('settlement_type') == 'castle':
        food = food * 11 // 10
        bonus, remainder = divmod(recruits + v.get('culture_recruit_remainder', 0), 10)
        v['culture_recruit_remainder'] = remainder
        recruits += bonus
    elif _is(w, v, 'sturgia'):
        food = food * 11 // 10
    return food, recruits


def transport_speed(w, u, base):
    """Aserai supply carts only; merchant caravans and village carts unchanged."""
    return base * 11 // 10 if u.get('kind') == 'city_cart' and _is(w, u, 'aserai') else base
