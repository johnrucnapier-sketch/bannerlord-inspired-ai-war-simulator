"""Rebuilt diplomacy: simultaneous snapshot transactions, private offers.

Alliance members bind their whole bloc. No shared intelligence or military
control. Conflicts reject complete transactions, never partial pair updates.
"""
import copy
import itertools

ACTIONS=('hold','propose_peace','propose_nap','propose_alliance','accept','reject','declare_war','leave_alliance')
DEFAULTS=dict(diplomacy_decision_hours=168,diplomacy_event_cooldown_hours=0,
              diplomacy_nap_hours=672,diplomacy_alliance_hours=2016,diplomacy_proposal_hours=168)


def enabled(w):return bool(getattr(w,'cfg',{}).get('diplomacy_enabled',False))
def pair(a,b):return ':'.join(map(str,sorted((a,b))))
def unpair(key):return tuple(map(int,key.split(':')))
def live(w):return set(w.nation_ids())-set(w.extinct_nations)


def initialize(w):
    for key,value in DEFAULTS.items():
        w.cfg.setdefault(key,value)
        if type(w.cfg[key]) is not int or w.cfg[key]<(0 if key=='diplomacy_event_cooldown_hours' else 1):
            raise ValueError(key+' has invalid integer duration')
    w.diplomacy_state=dict(proposals={},treaties={},last_period={},last_hour={},last_signature={},receipts=[],queue=[])


def state(w):
    if not hasattr(w,'diplomacy_state'):initialize(w)
    return w.diplomacy_state


def components(w,relations=None):
    relations=w.relations if relations is None else relations
    remaining=live(w);groups=[]
    while remaining:
        group={min(remaining)}
        while True:
            more={b for a in group for b in remaining if relations[str(a)].get(str(b))=='alliance'}
            if more<=group:break
            group|=more
        remaining-=group;groups.append(sorted(group))
    return groups


def bloc(w,n,relations=None):return next(set(c) for c in components(w,relations) if n in c)


def signature(w,n):
    owned=sorted(c['id'] for c in w.cities.values() if c['nation']==n)
    forces=sum(u.get('healthy',0) for u in w.units.values() if u['nation']==n and u.get('kind') in ('party','garrison','militia'))//500
    sieges=sorted(bid for bid,b in w.battles.items() if b.get('city') in owned)
    threats=[]
    if hasattr(w,'visible'):
        temporary=not hasattr(w,'_sensors')
        if temporary:w._sensors=w._sensor_index()
        try:
            totals={}
            for u in w.units.values():
                if u['nation']>=0 and w.hostile(n,u['nation']) and u.get('kind') in ('party','garrison','militia') and w.visible(n,u):
                    totals[u['nation']]=totals.get(u['nation'],0)+u.get('healthy',0)
            threats=[[enemy,total//250] for enemy,total in sorted(totals.items()) if total>=250]
        finally:
            if temporary:del w._sensors
    return [owned,[list(v) for v in sorted(w.relations[str(n)].items())],forces,sieges,threats]


def decision_due(w,n):
    if n not in live(w):return False
    s=state(w);key=str(n)
    periodic=s['last_period'].get(key)!=w.hour//w.cfg['diplomacy_decision_hours']
    changed=s['last_signature'].get(key)!=signature(w,n)
    cooled=w.hour-s['last_hour'].get(key,-100000)>=w.cfg['diplomacy_event_cooldown_hours']
    return periodic or (changed and cooled)


def receipt(w,n,action,status,reason='',**extra):
    rec=dict(hour=w.hour,nation=n,action=action,status=status,reason=reason,**extra)
    s=state(w);s['receipts'].append(rec);s['receipts']=s['receipts'][-2048:]
    return rec


def submit(w,n,cmd):
    if not enabled(w):raise ValueError('diplomacy disabled')
    s=state(w);action=cmd.get('action')
    if action not in ACTIONS:raise ValueError('unknown diplomatic action')
    if type(n) is not int or n not in live(w):raise ValueError('country unavailable')
    if action in ('accept','reject'):
        pid=cmd.get('proposal_id')
        if type(pid) is not str:raise ValueError('proposal_id must be str')
        p=s['proposals'].get(pid)
        if not p or p['to_nation']!=n or p['expires_hour']<=w.hour:raise ValueError('proposal unavailable')
    else:
        if not decision_due(w,n):raise ValueError('diplomatic decision not due')
        target=cmd.get('target')
        if action not in ('hold','leave_alliance') and (type(target) is not int or target not in live(w) or target==n):raise ValueError('invalid diplomatic target')
        s['last_period'][str(n)]=w.hour//w.cfg['diplomacy_decision_hours']
        s['last_hour'][str(n)]=w.hour;s['last_signature'][str(n)]=signature(w,n)
    s['queue'].append(dict(nation=n,command=copy.deepcopy(cmd)))
    return dict(ok=True,queued=True)


def _candidate(w,n,action,target,relations):
    a=bloc(w,n,relations);b=bloc(w,target,relations) if target is not None else set();writes={}
    if action=='leave_alliance':
        for other in a-{n}:writes[pair(n,other)]=('peace',None)
        if not writes:raise ValueError('not allied')
        return writes
    if a&b:raise ValueError('same alliance bloc')
    cross={pair(x,y) for x in a for y in b}
    if action in ('peace','nap'):
        for key in cross:
            x,y=unpair(key)
            if action=='peace' and relations[str(x)][str(y)]=='nap':continue
            writes[key]=(action,w.hour+w.cfg['diplomacy_nap_hours'] if action=='nap' else None)
    elif action=='alliance':
        if any(relations[str(x)][str(y)]=='war' for x in a for y in b):raise ValueError('peace required before alliance')
        merged=a|b
        old=[t['expires_hour'] for key,t in state(w)['treaties'].items() if t['kind']=='alliance' and set(unpair(key))<=merged]
        expiry=min([w.hour+w.cfg['diplomacy_alliance_hours']]+old)
        for x,y in itertools.combinations(sorted(merged),2):writes[pair(x,y)]=('alliance',expiry)
        enemies={other for x in merged for other in live(w)-merged if relations[str(x)][str(other)]=='war'}
        enemies=set().union(*(bloc(w,e,relations) for e in enemies)) if enemies else set()
        for x in merged:
            for y in enemies:
                if relations[str(x)][str(y)]=='nap':raise ValueError('synchronized war blocked by non-aggression pact')
                writes[pair(x,y)]=('war',None)
    elif action=='declare_war':
        for key in cross:
            x,y=unpair(key)
            if relations[str(x)][str(y)]=='nap':raise ValueError('war blocked by non-aggression pact')
            writes[key]=('war',None)
    return writes


def resolve(w):
    if not enabled(w):return []
    s=state(w);tick(w);queue=s['queue'];s['queue']=[]
    if not queue:return []
    snapshot=copy.deepcopy(w.relations);proposals=copy.deepcopy(s['proposals'])
    candidates=[];new=[];replies={};results=[]
    for item in sorted(queue,key=lambda i:(i['nation'],str(i['command'].get('action')),str(i['command'].get('target')),str(i['command'].get('proposal_id')))):
        n=item['nation'];cmd=item['command'];action=cmd['action']
        if n not in live(w):continue
        if action=='hold':results.append(receipt(w,n,action,'accepted',copy.deepcopy(cmd.get('reason',''))))
        elif action.startswith('propose_'):
            kind=action[8:];target=cmd['target']
            try:
                _candidate(w,n,kind,target,snapshot)
                groups=[sorted(bloc(w,n,snapshot)),sorted(bloc(w,target,snapshot))]
                pid=f'd{w.hour}:{n}:{target}:{kind}'
                new.append(dict(id=pid,from_nation=n,to_nation=target,kind=kind,created_hour=w.hour,expires_hour=w.hour+w.cfg['diplomacy_proposal_hours'],blocs=groups))
                results.append(receipt(w,n,action,'proposed',proposal_id=pid,target=target))
            except (ValueError,StopIteration) as e:results.append(receipt(w,n,action,'rejected',str(e) or 'country extinct'))
        elif action in ('accept','reject'):replies.setdefault(cmd['proposal_id'],[]).append((n,action))
        else:
            try:candidates.append((n,action,None,_candidate(w,n,action,cmd.get('target'),snapshot)))
            except (ValueError,StopIteration) as e:results.append(receipt(w,n,action,'rejected',str(e) or 'country extinct'))
    for pid,answers in sorted(replies.items()):
        p=proposals.get(pid)
        if not p:continue
        n=p['to_nation'];s['proposals'].pop(pid,None)
        reason='proposal declined' if any(a=='reject' for _,a in answers) else ''
        if not reason:
            try:
                if p['blocs']!=[sorted(bloc(w,p['from_nation'],snapshot)),sorted(bloc(w,n,snapshot))]:raise ValueError('alliance membership changed; propose again')
                candidates.append((n,p['kind'],pid,_candidate(w,p['from_nation'],p['kind'],n,snapshot)))
            except (ValueError,StopIteration) as e:reason=str(e) or 'country extinct'
        if reason:
            for country in (n,p['from_nation']):results.append(receipt(w,country,p['kind'],'rejected',reason,proposal_id=pid))
    conflicts=set()
    for i,left in enumerate(candidates):
        for j in range(i+1,len(candidates)):
            right=candidates[j]
            if left[3]==right[3]:continue
            overlap=left[3].keys()&right[3].keys()
            if any(left[3][k]!=right[3][k] for k in overlap):conflicts.update((i,j))
            if any(v[0]=='alliance' for v in left[3].values()) or any(v[0]=='alliance' for v in right[3].values()):
                ln={n for k in left[3] for n in unpair(k)};rn={n for k in right[3] for n in unpair(k)}
                if ln&rn:conflicts.update((i,j))
    for i,(n,action,pid,writes) in enumerate(candidates):
        status='conflict' if i in conflicts else 'accepted'
        if i not in conflicts:
            for key,(relation,expiry) in writes.items():
                a,b=unpair(key);w.relations[str(a)][str(b)]=w.relations[str(b)][str(a)]=relation
                s['treaties'].pop(key,None)
                if expiry:s['treaties'][key]=dict(kind=relation,expires_hour=expiry)
            w.emit('diplomacy_changed','外交关系变更',nation=n,action=action,pairs=sorted(writes),important=True)
        recipients={n}
        if pid:recipients.add(proposals[pid]['from_nation'])
        for country in sorted(recipients):results.append(receipt(w,country,action,status,'simultaneous transaction conflict' if i in conflicts else '',proposal_id=pid))
    for p in new:s['proposals'][p['id']]=p
    ceased={pair(a,b) for a in live(w) for b in live(w) if a<b and snapshot[str(a)][str(b)]=='war' and not w.hostile(a,b)}
    ceasefires(w,ceased);check(w)
    return results


def tick(w):
    if not enabled(w):return
    s=state(w);living=live(w)
    for pid,p in list(s['proposals'].items()):
        if p['expires_hour']<=w.hour or not {p['from_nation'],p['to_nation']}<=living:
            del s['proposals'][pid]
            for n in (p['from_nation'],p['to_nation']):receipt(w,n,p['kind'],'expired',proposal_id=pid)
    for key,t in list(s['treaties'].items()):
        a,b=unpair(key)
        if t['expires_hour']<=w.hour or not {a,b}<=living:
            del s['treaties'][key];w.relations[str(a)][str(b)]=w.relations[str(b)][str(a)]='peace'
            w.emit('treaty_expired','条约到期或国家灭亡',pairs=[key],important=True)


def ceasefires(w,ceased=()):
    touched={bid for bid,b in w.battles.items() if any(pair(int(a),int(c)) in ceased for a,c in itertools.combinations(b['sides'],2))}
    while True:
        more=touched|{bid for bid,b in w.battles.items() if b.get('relief_for') in touched or b.get('relief_battle') in touched}
        more|={w.battles[bid][k] for bid in touched if bid in w.battles for k in ('relief_for','relief_battle') if w.battles[bid].get(k) in w.battles}
        if more==touched:break
        touched=more
    for u in w.units.values():
        if u.get('battle') in touched:u.update(battle=None,last_battle=w.hour,order=None,path=[])
        order=u.get('order') or {};kind=order.get('type')
        objects=w.units if kind=='attack' else w.cities if kind=='siege' else w.villages if kind=='raid' else {}
        target=objects.get(order.get('target'))
        if target and not w.hostile(u['nation'],target['nation']):u.update(order=None,path=[])
    for bid in sorted(touched):
        w.battles.pop(bid,None);w.emit('battle_cancelled','停战解除交战',battle=bid,reason='ceasefire',important=True)
    for v in w.villages.values():
        if v.get('raid'):
            u=w.units.get(v['raid'].get('unit'))
            if not u or not w.hostile(u['nation'],v['nation']):v['raid']=None


def observe(w,n):
    if not enabled(w):return dict(version=2,enabled=False,supported_actions=[],mode='free_for_all')
    s=state(w)
    return dict(version=2,enabled=True,mode='alliance_blocs',supported_actions=list(ACTIONS),decision_due=decision_due(w,n),
                reply_due=any(p['to_nation']==n for p in s['proposals'].values()),
                incoming=[copy.deepcopy(p) for p in s['proposals'].values() if n is None or p['to_nation']==n],
                outgoing=[copy.deepcopy(p) for p in s['proposals'].values() if n is None or p['from_nation']==n],
                public_relations=copy.deepcopy(w.relations),alliance_components=components(w),treaties=copy.deepcopy(s['treaties']),
                events=[copy.deepcopy(e) for e in s['receipts'] if n is None or e['nation']==n][-50:],
                decision_hours=w.cfg['diplomacy_decision_hours'],nap_hours=w.cfg['diplomacy_nap_hours'],alliance_hours=w.cfg['diplomacy_alliance_hours'])


def check(w):
    if not enabled(w):return
    for a in live(w):
        assert w.relations[str(a)][str(a)]=='self'
        for b in live(w)-{a}:assert w.relations[str(a)][str(b)]==w.relations[str(b)][str(a)]
    for group in components(w):
        for a,b in itertools.combinations(group,2):assert w.relations[str(a)][str(b)]=='alliance'
        for other in live(w)-set(group):assert len({w.hostile(a,other) for a in group})==1
