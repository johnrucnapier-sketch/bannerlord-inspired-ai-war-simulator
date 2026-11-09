"""Physical clan militia orders. All lifecycle state is serialized on the world.

Audited Mod code uses ceil(soldiers / 2) grain, not its ten-day prose.
One grain is 1000 simulator food; levy_food_per_two config owns this conversion.
Cancellation uses explicit physical issuer-to-node/cohort couriers (a documented
simplification of the Mod cancellation tree), never remote state changes.
The rally waits the full 72 hours from receipt; early all-arrived departure is
not modeled without a physical acknowledgement protocol for remote sources.
Arrival and army attachment use the engine's existing 500-unit contact radius.
Settlement losses reserve militia capacity, decaying over 180 days.
A captured home cannot accept survivors or couriers. They remain physical units,
consume their normal rations, and can return only when that home is owned again.
"""
import copy

RECOVERY_HOURS = 180 * 24


def enabled(w):
    return bool(w.cfg.get('militia_mobilization'))


def _records(w):
    if not hasattr(w, 'mobilizations'):
        w.mobilizations = {}
    return w.mobilizations


def _near(a, b):
    return (a['x']-b['x'])**2 + (a['y']-b['y'])**2 <= 500**2


def _source(w, sid):
    return w.cities.get(sid) or w.villages.get(sid)


def _owned(w, s, rec):
    if not s or s['nation'] != rec['nation']:
        return False
    c = w.cities.get(s.get('city'), s)
    return c.get('clan') == rec['clan']


def _leader(w, rec):
    ids = w.armies.get(rec['army'], [])
    metadata = getattr(w, 'army_metadata', {}).get(rec['army'], {})
    commander = metadata.get('commander')
    if commander is not None:ids = [commander] if commander in ids else []
    return next((w.units[i] for i in ids
                 if i in w.units and w.units[i]['kind'] == 'party'
                 and w.units[i]['clan'] == rec['clan']
                 and w.units[i]['nation'] == rec['nation']), None)


def _go(w, u, target):
    try:
        w.go(u, target['x'], target['y'])
        return True
    except ValueError:
        u.update(path=[], order=None)
        return False


def levy_food_required(w, count):
    return ((count + 1) // 2) * w.cfg.get('levy_food_per_two', 1000)


def _queue(rec, sender, target, mission):
    key = mission + ':' + target
    if key not in rec['dispatches']:
        rec['dispatches'][key] = dict(sender=sender, target=target, mission=mission,
                                     status='pending', unit=None)
        rec['pending_dispatches'].append(key)
    return key


def _dispatch_target(w, rec, task):
    if task['mission'] == 'leader':return _leader(w, rec) or rec['last_known_leader']
    if task['mission'] == 'cancel_unit':return w.units.get(task['target'])
    return _source(w, task['target'])


def _dispatch(w, rec):
    for key in list(rec['pending_dispatches']):
        task = rec['dispatches'][key]
        sender = w.cities.get(task['sender'])
        if task['mission'] not in ('cancel_source', 'cancel_unit') and task['sender'] in rec['cancelled_sources']:
            task['status'] = 'cancelled';rec['pending_dispatches'].remove(key);continue
        target = _dispatch_target(w, rec, task)
        if not target:
            task['status'] = 'cancelled';rec['pending_dispatches'].remove(key);continue
        if not _owned(w, sender, rec) or w.besieged(sender['id']):continue
        g = w.units[sender['garrison']]
        if g['battle'] or g['healthy'] < 1 or sender['food'] < 1000:continue
        if w.route(g, target['x'], target['y']) is None:continue
        cavalry = int(g.get('cavalry', 0) == g['healthy'])
        g['healthy'] -= 1
        if 'cavalry' in g:g['cavalry'] -= cavalry
        sender['food'] -= 1000
        u = w.new_unit('mobilization_messenger', rec['nation'], rec['clan'], 1,
                       sender['x'], sender['y'], home=sender['id'], food=1000)
        u.update(mobilization=rec['id'], mission=task['mission'], dispatch_key=key,
                 target=task['target'], phase='orders', courier_cavalry=cavalry)
        rec['messengers'].append(u['id'])
        task.update(status='enroute', unit=u['id'])
        rec['pending_dispatches'].remove(key)
        _go(w, u, target)


def _rally(w, c):
    home = getattr(w, 'map_clans', {}).get(str(c['clan']), {}).get('initial_home_settlement')
    target = w.cities.get(home)
    if target and target['nation'] == c['nation'] and target['clan'] == c['clan']:return target
    return min((t for t in w.cities.values() if t['nation'] == c['nation'] and t['clan'] == c['clan']),
               key=lambda t:((t['x']-c['x'])**2+(t['y']-c['y'])**2, t['id']))


def command(w, nation, cmd):
    if not enabled(w):raise ValueError('民兵动员未启用')
    records = _records(w)
    if cmd['type'] == 'mobilize':
        c = w.cities.get(cmd.get('city'))
        if not c or c['nation'] != nation or c.get('settlement_type') != 'castle' or w.besieged(c['id']):
            raise ValueError('需己方安全城堡发出家族动员')
        army = cmd.get('army')
        if army in w.units:army=w.units[army].get('army')
        rec = dict(id=None, nation=nation, clan=c['clan'], issuer=c['id'], rally=_rally(w,c)['id'],
                   army=army, started=w.hour, rally_until=None, cohorts={}, messengers=[], losses=[],
                   dispatches={}, pending_dispatches=[], pending_sources=[], received_sources=[],
                   raised_sources=[], cancelled_sources=[], status='mobilizing')
        leader = _leader(w, rec)
        if not leader or leader['battle'] or not _near(leader,c):
            raise ValueError('需本家族军团指挥官身处发令城堡')
        if any(r['clan']==rec['clan'] and r['status']!='completed' for r in records.values()):
            raise ValueError('本家族仍有动员部队、传令兵或损失恢复未结束')
        rec['last_known_leader']=dict(x=leader['x'],y=leader['y'])
        rec['id']=w.ident('mob');records[rec['id']]=rec
        _queue(rec,c['id'],rec['rally'],'leader')
        _dispatch(w,rec)
        return {'ok':True,'mobilization':rec['id'],'unit':next(iter(rec['messengers']),None)}
    if cmd['type'] != 'demobilize':raise ValueError('未知动员命令')
    found=[r for r in records.values() if r['nation']==nation and r['status']!='completed'
           and (r['army']==cmd.get('army') if cmd.get('army') is not None else r['clan']==cmd.get('clan'))]
    if len(found)!=1:raise ValueError('需指定一个己方动员军团或家族')
    rec=found[0];rec['demobilize_requested']=True;rec['status']='demobilizing'
    _cancel_orders(w,rec);_dispatch(w,rec)
    return {'ok':True,'mobilization':rec['id']}


def _retire_phantom_cancellations(w, rec):
    """Retire only unsent cancellations after the physical order tree closes.

    Older records can contain cancellations for later-acquired settlements
    which never received this mobilization. This uses receipt/dispatch history
    and surviving units, never a remote settlement's current ownership. Real
    couriers, local raising orders and the 180-day loss ledger remain intact.
    """
    if rec['pending_sources'] or any(i in w.units for i in rec['cohorts']):return False
    if any(i in w.units for i in rec['messengers']):return False
    received = set(rec['received_sources'])
    if not received.issubset(rec['cancelled_sources']):return False
    for task in rec['dispatches'].values():
        if task['status'] == 'enroute':return False
        if task['mission'] in ('leader', 'source') and task['status'] not in ('delivered', 'cancelled', 'failed'):
            return False
    pending = [rec['dispatches'][key] for key in rec['pending_dispatches']]
    if any(task['mission'] != 'cancel_source' or task['status'] != 'pending'
           or task['unit'] is not None or task['target'] in received for task in pending):
        return False
    for task in pending:task['status'] = 'obsolete'
    rec['pending_dispatches'].clear()
    return True


def _cancel_orders(w, rec):
    # A closed tree needs no cancellation at unrelated, later-acquired fiefs.
    # Loss recovery still blocks completion in tick(), even after this cleanup.
    if _retire_phantom_cancellations(w, rec):return
    # Source receipt, not command issuance, prevents raising and local dispatch.
    for s in sorted(list(w.cities.values())+list(w.villages.values()),key=lambda s:s['id']):
        if _owned(w,s,rec):_queue(rec,rec['issuer'],s['id'],'cancel_source')
    for uid in rec['cohorts']:
        if uid in w.units and w.units[uid]['phase']!='return':
            _queue(rec,rec['issuer'],uid,'cancel_unit')


def _receive(w, rec, s, rally=False):
    if not _owned(w,s,rec) or s['id'] in rec['cancelled_sources']:return
    if s['id'] not in rec['received_sources']:
        rec['received_sources'].append(s['id']);rec['pending_sources'].append(s['id'])
    if rally and rec['rally_until'] is None:
        rec['rally_until']=w.hour+72
        for c in sorted(w.cities.values(),key=lambda c:c['id']):
            if c['id']!=s['id'] and _owned(w,c,rec):_queue(rec,s['id'],c['id'],'source')
    if s['id'] in w.cities:
        for v in sorted(w.villages.values(),key=lambda v:v['id']):
            if v['city']==s['id'] and _owned(w,v,rec):_queue(rec,s['id'],v['id'],'source')


def _detach(w, u):
    aid = u.get('army')
    if aid in w.armies:
        w.armies[aid] = [i for i in w.armies[aid] if i != u['id']]
        if not w.armies[aid]:
            del w.armies[aid]
            if hasattr(w,'army_metadata'):w.army_metadata.pop(aid,None)
    u.update(army=None, path=[], order=None)


def _return(w, u):
    _detach(w, u)
    u['phase'] = 'return'


def _extract(w, rec, s):
    if not _owned(w, s, rec):return
    village = s['id'] in w.villages
    if village:
        if s.get('raid') or w.hour < s.get('disabled_until', 0):return
        count = s['population'] // 5
    else:
        m = w.units[s['militia']]
        if w.besieged(s['id']) or m['battle']:return
        count = m['healthy'] * 7 // 10
    if not count:return False
    food = levy_food_required(w, count)
    if s['food'] < food:return
    # No remote spawn: caller only executes after courier physically arrives.
    if village:s['population'] -= count
    else:m['healthy'] -= count
    s['food'] -= food
    u = w.new_unit('levy', rec['nation'], rec['clan'], count, s['x'], s['y'], home=s['id'], food=food)
    u.update(mobilization=rec['id'], phase='bound' if village else 'rally',
             levy_source=s['id'], levy_source_type='village' if village else 'settlement')
    rec['cohorts'][u['id']] = dict(source=s['id'], village=village, last_size=count, returned=False)
    rec['raised_sources'].append(s['id'])
    return True


def _reserve(w, rec, cohort, count):
    if count > 0 and not cohort['village']:
        rec['losses'].append(dict(source=cohort['source'], count=count, hour=w.hour))


def on_remove(w, u, reason):
    if not enabled(w) or not u.get('mobilization'):return
    rec = _records(w).get(u['mobilization'])
    if not rec:return
    key=u.get('dispatch_key')
    if key in rec.get('dispatches',{}) and rec['dispatches'][key]['status']=='enroute':
        rec['dispatches'][key].update(status='pending',unit=None)
        if key not in rec['pending_dispatches']:rec['pending_dispatches'].append(key)
    cohort = rec['cohorts'].get(u['id'])
    if cohort and not cohort['returned']:
        _reserve(w, rec, cohort, cohort['last_size'])
        cohort['last_size'] = 0
        cohort['removed'] = True


def _deposit(w, u, s, rec, cohort=None):
    if not _owned(w, s, rec) or not _near(u, s):return False
    if s['id'] in w.cities and (w.besieged(s['id']) or w.units[s['militia']]['battle']):return False
    if s['id'] in w.villages:
        s['population'] += w.size(u)
    else:
        g = w.units[s['militia'] if cohort else s['garrison']]
        if not cohort and w.size(g)+w.size(u)>w.cfg['garrison_cap']:return False
        g['healthy'] += u['healthy'];g['wounded'] += u['wounded']
        if not cohort and u.get('courier_cavalry') and 'cavalry' in g:
            g['cavalry'] += u['healthy'];g['cavalry_wounded'] += u['wounded']
    # Capacity overflow is explicitly lost, never silently generated.
    n = min(u['food'], max(0, w.cfg['warehouse']-s['food']))
    s['food'] += n;u['food'] -= n
    if cohort:cohort.update(returned=True, last_size=0)
    w.remove(u['id'], 'demobilized')
    return True


def _messenger_tick(w, u, rec):
    if u['phase']=='return':
        c=w.cities.get(u['home'])
        if c:
            if not _near(u,c):_go(w,u,c)
            elif not _deposit(w,u,c,rec):u.update(path=[],order=None)
        return
    task=rec['dispatches'][u['dispatch_key']]
    target = _source(w,rec['rally']) if u['phase']=='rally_order' else _dispatch_target(w,rec,task)
    if target and not _near(u,target):_go(w,u,target);return
    if task['mission']=='leader' and u['phase']!='rally_order':
        if not _leader(w,rec):
            # Empty last-known coordinates are physical failure, not receipt.
            task['status']='failed';_return(w,u);return
        u['phase']='rally_order';_go(w,u,w.cities[rec['rally']]);return
    if target:
        if task['mission'] in ('leader','source'):
            _receive(w,rec,target,rally=task['mission']=='leader')
        elif task['mission']=='cancel_source':
            if not _owned(w,target,rec):return
            if _owned(w,target,rec):
                sid=target['id']
                if sid not in rec['cancelled_sources']:rec['cancelled_sources'].append(sid)
                if sid in rec['pending_sources']:rec['pending_sources'].remove(sid)
        elif task['mission']=='cancel_unit' and target.get('mobilization')==rec['id']:
            _return(w,target)
    task['status']='delivered'
    _return(w,u)


def _try_sources(w,rec,only=None):
    for sid in list(rec['pending_sources']):
        if only is not None and sid!=only:continue
        if sid in rec['cancelled_sources'] or sid in rec['raised_sources']:
            rec['pending_sources'].remove(sid);continue
        source=_source(w,sid)
        if source and _extract(w,rec,source):rec['pending_sources'].remove(sid)


def pre_departure(w, village):
    """Attempt locally received raising, then reserve real grain before cart loading.

    Caller must subtract the returned reservation from loadable village food.
    This permits small weekly production batches to accumulate without minting food.
    """
    if not enabled(w):return 0
    reserve=0
    for rec in _records(w).values():
        if village['id'] not in rec['pending_sources']:continue
        _try_sources(w,rec,only=village['id'])
        if village['id'] in rec['pending_sources'] and _owned(w,village,rec):
            reserve=max(reserve,min(village['food'],levy_food_required(w,village['population']//5)))
    return reserve


def tick(w):
    if not enabled(w):return
    for rec in _records(w).values():
        if rec['status']=='completed':continue
        leader = _leader(w, rec)
        if leader:rec['last_known_leader'] = dict(x=leader['x'], y=leader['y'])
        rec['losses'] = [r for r in rec['losses'] if w.hour-r['hour'] < RECOVERY_HOURS]
        for uid, cohort in rec['cohorts'].items():
            u = w.units.get(uid)
            if not u:continue
            current = w.size(u)
            _reserve(w, rec, cohort, max(0, cohort['last_size']-current))
            cohort['last_size'] = current
        for uid in list(rec['messengers']):
            u = w.units.get(uid)
            if u and not u['battle']:_messenger_tick(w, u, rec)
        _try_sources(w,rec)
        if rec.get('demobilize_requested'):_cancel_orders(w,rec)
        _dispatch(w,rec)
        for uid, cohort in list(rec['cohorts'].items()):
            u = w.units.get(uid)
            if not u or u['battle']:continue
            if u['phase'] == 'return':
                s = _source(w, cohort['source'])
                if s:
                    if not _near(u,s):_go(w,u,s)
                    elif not _deposit(w,u,s,rec,cohort):u.update(path=[],order=None)
                continue
            if not _leader(w, rec) and u['phase'] == 'serving':
                # Members witness their own army dissolving. Remote levies do not.
                _return(w, u);continue
            if u['phase'] == 'bound':
                s = w.villages[cohort['source']]
                target = w.cities[s['city']]
                if not _near(u,target):_go(w,u,target);continue
                if not _owned(w,target,rec):_return(w,u);continue
                u['phase']='rally'
            if u['phase'] == 'rally':
                target = w.cities[rec['rally']]
                if not _near(u,target):_go(w,u,target);continue
                if not _owned(w,target,rec):_return(w,u);continue
                u.update(path=[], order=None)
                if rec['rally_until'] is None or w.hour < rec['rally_until']:continue
                u['phase'] = 'joining'
            if u['phase'] == 'joining':
                leader = _leader(w, rec)
                if not leader:
                    target = rec['last_known_leader']
                    if _near(u, target):_return(w, u)
                    else:_go(w, u, target)
                    continue
                if _near(u, leader) and not leader['battle']:
                    w.armies[rec['army']].append(uid)
                    u.update(army=rec['army'], phase='serving', x=leader['x'], y=leader['y'],
                             path=copy.deepcopy(leader['path']), order=copy.deepcopy(leader['order']))
                else:_go(w, u, leader)
            elif u['phase'] == 'serving' and u.get('army') != rec['army']:
                _return(w, u)
        if not any(i in w.units for i in rec['messengers']) and not any(i in w.units for i in rec['cohorts']) and not rec['losses'] and not rec['pending_dispatches'] and not rec['pending_sources']:
            rec['status'] = 'completed'


def away_militia(w, c):
    if not enabled(w):return 0
    total = 0
    missing_numerator = 0
    for rec in _records(w).values():
        if not _owned(w, c, rec):continue
        total += sum(w.size(w.units[i]) for i, p in rec['cohorts'].items()
                     if not p['village'] and p['source'] == c['id'] and i in w.units)
        missing_numerator += sum(r['count'] * max(0, RECOVERY_HOURS-(w.hour-r['hour']))
                                 for r in rec['losses'] if r['source'] == c['id'])
    # Round once per source, not once per casualty event. Otherwise one-person
    # losses reserve a full slot until expiry and batching changes recovery.
    return total + (missing_numerator + RECOVERY_HOURS - 1) // RECOVERY_HOURS


def observe(w, nation):
    return copy.deepcopy([r for r in _records(w).values() if nation is None or r['nation'] == nation]) if enabled(w) else []
