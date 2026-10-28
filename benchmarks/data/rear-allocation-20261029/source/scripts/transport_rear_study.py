"""Fixed 12-city/36-party rural resource experiment; real resources and battle telemetry."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from aiwar.engine import World
from scripts.transport_rear_policy import Controller
from aiwar import economy

_original_transport=economy.transport
def tracked_transport(world,kind,unit):
    if hasattr(world,"_trips") and unit["kind"]=="village_cart":
        uid=unit["id"]
        if kind=="depart":
            assert uid not in world._trips
            world._trips[uid]={"delivered":False}
            world._transport["departed"]+=1
        trip=world._trips.get(uid)
        if trip is not None:
            if kind=="delivered":trip["delivered"]=True
            if kind in ("returned","lost"):
                success=kind=="returned" and trip["delivered"]
                world._transport["success" if success else "failed"]+=1
                world._transport[kind]+=1
                del world._trips[uid]
    _original_transport(world,kind,unit)
economy.transport=tracked_transport


class MeasuredWorld(World):
    def __init__(self,seed,floor):
        self._active_ids=set();self._hunter_ids=set();self._trips={};self._transport=Counter();self._removed=Counter();self._measure=Counter();self._observed_battles={};self._floor=floor;self._examples=[]
        super().__init__(seed,{'mode':'rural','clan_party_cap':4})
        # Experimental per-clan cap: two cities times three squads.
        # Initialization itself is identical; production constructor/menu remain unchanged.
        self.cfg['clan_party_cap']=6

    def state(self):
        state=super().state()
        for key in ('_measure','_observed_battles','_floor','_examples','_trips','_transport','_removed','_hunter_ids','_active_ids'):state.pop(key,None)
        return state

    def remove(self,uid,reason='removed'):
        u=self.units.get(uid)
        if u and u['kind']=='garrison':self._measure['garrison_removed_remaining_'+reason]+=self.size(u)
        if u and u['kind']=='party' and u['nation']==0:
            self._removed['removed_remaining_'+reason]+=self.size(u)
            if uid in self._hunter_ids:self._measure['hunter_removed_remaining_'+reason]+=self.size(u)
            self._removed['parties_'+reason]+=1
        super().remove(uid,reason)

    def join(self,b,u):
        previous=u['battle'];healthy=u['healthy']
        super().join(b,u)
        if previous is None and u['battle']==b['id']:
            self._observed_battles.setdefault(b['id'],{})[u['id']]=dict(unit=u,healthy=healthy,kind=u['kind'],nation=u['nation'],hunter=u['id'] in self._hunter_ids)
            if u['kind']=='party' and u['nation']==0:
                self._measure['party_engagements']+=1
                if healthy<(54 if u.get('refill_target',0)==57 else self._floor):self._measure['engagements_below_health_floor']+=1

    def battle_tick(self):
        before=dict(self.battles)
        super().battle_tick()
        for bid,b in before.items():
            if bid in self.battles:continue
            records=self._observed_battles.pop(bid,{})
            bandits=sum(r['healthy'] for r in records.values() if r['nation']==-1)
            kind=b['kind']
            friendly=[r for r in records.values() if r['nation']==0]
            hunters=[r for r in friendly if r.get('hunter')]
            kills=sum(r['nation']==-1 and r['unit']['id'] not in self.units for r in records.values())
            if hunters and kills:
                self._measure['hunter_participated_bandit_kills']+=kills
                if len(friendly)==1 and len(hunters)==1:self._measure['hunter_solo_bandit_kills']+=kills
                else:self._measure['hunter_assisted_bandit_kills']+=kills
            for r in records.values():
                if r['kind']=='garrison' and r['nation']==0:
                    loss=r['unit']['war_losses'];self._measure['garrison_combat_dead']+=loss//4;self._measure['garrison_wound_events']+=loss-loss//4
                if r['kind']!='party' or r['nation']!=0:continue
                u=r['unit'];loss=u['war_losses'];dead=loss//4
                self._measure['patrol_combat_dead']+=dead
                if r.get('hunter'):
                    self._measure['hunter_combat_dead']+=dead
                    self._measure['hunter_wound_events']+=loss-dead
                self._measure['patrol_wound_events']+=loss-dead
                self._measure['engagements_'+kind]+=1
                self._measure['deaths_'+kind]+=dead
                if bandits>20:self._measure['multi_bandit_engagements']+=1;self._measure['deaths_multi_bandit']+=dead
                if u['id'] not in self.units:self._measure['patrols_destroyed']+=1
                if dead==0:self._measure['zero_death_engagements']+=1
                if dead and len(self._examples)<20:
                    self._examples.append(dict(hour=self.hour,kind=kind,start_healthy=r['healthy'],bandits=bandits,dead=dead,wounded=loss-dead))

    def weekly(self):
        self._measure['generated_recruits']+=sum(v['population']//100 for v in self.villages.values() if self.hour>=v['disabled_until'])
        super().weekly()

    def eat(self,members,rate,city=None):
        parties=[u for u in members if u['kind']=='party' and u['nation']==0]
        garrisons=[u for u in members if u['kind']=='garrison' and u['nation']==0]
        before_g=[(u,self.size(u)) for u in garrisons]
        self._measure['garrison_food_demand']+=sum(self.size(u)*rate for u in garrisons)
        self._measure['deployed_food_demand']+=sum(self.size(u)*rate for u in parties if u['id'] in self._active_ids)
        self._measure['retiring_food_demand']+=sum(self.size(u)*rate for u in parties if u['id'] not in self._active_ids)
        self._measure['patrol_food_demand']+=sum(self.size(u)*rate for u in parties)
        self._measure['hunter_food_demand']+=sum(self.size(u)*rate for u in parties if u['id'] in self._hunter_ids)
        before=[(u,self.size(u)) for u in parties]
        super().eat(members,rate,city)
        self._measure['garrison_starved']+=sum(n-self.size(u) for u,n in before_g)
        self._measure['patrol_starved']+=sum(n-self.size(u) for u,n in before)
        self._measure['hunter_starved']+=sum(n-self.size(u) for u,n in before if u['id'] in self._hunter_ids)
        self._measure['hungry_party_days']+=sum(bool(u['hungry']) for u in parties)


def write(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)


def run(args):
    j,out=args;start=time.perf_counter();path=Path(out)/j['id'];path.mkdir()
    world=MeasuredWorld(j['seed'],j['floor']);controller=Controller(j['target'],j['floor'],j['style']);errors=Counter();timeline=[];first_switch_pre_digest=None
    try:
        while not world.result:
            cmds=controller.decide(world.observe(0))
            if first_switch_pre_digest is None and controller.phase_events:first_switch_pre_digest=world.physics_digest()
            world._hunter_ids=set(controller.hunter_ids)
            world._active_ids=set(controller.active_ids)
            for cmd in cmds:
                result=world.command(0,cmd)
                if not result['ok']:
                    errors[result['error']]+=1
                    raise RuntimeError((world.hour,cmd,result))
            world.step(6)
            if world.hour%24==0:
                world._measure['deployed_soldier_days']+=sum(world.size(u) for u in world.units.values() if u['id'] in world._active_ids)
                world._measure['garrison_soldier_days']+=sum(world.size(u) for u in world.units.values() if u['kind']=='garrison')
                world._measure['retiring_soldier_days']+=sum(world.size(u) for u in world.units.values() if u['kind']=='party' and u['id'] not in world._active_ids)
                bandits=sum(u['kind']=='bandit' for u in world.units.values())
                world._measure['full57_party_days']+=sum(u['kind']=='party' and u['healthy']>=57 for u in world.units.values())
                world._measure['population_days']+=world.rural_score()['population']
                world._measure['bandit_daily_sum']+=bandits
                world._measure['bandit_daily_samples']+=1
                world._measure['bandit_peak']=max(world._measure['bandit_peak'],bandits)
                world._measure['bandit_cap_days']+=int(bandits>=world.cfg['bandit_cap'])
                world.check();assert sum(u['kind']=='party' for u in world.units.values())<=36
            if world.hour%2016==0:
                timeline.append(dict(year=world.hour//2016,population=world.rural_score()['population'],metrics=dict(world._measure),policy_metrics=dict(controller.metrics),transport=dict(world._transport,pending=len(world._trips)),stats=dict(world.stats),parties=sum(u['kind']=='party' for u in world.units.values())))
                write(path/'progress.json',dict(year=world.hour//2016,status='running'))
        assert all(j['floor']<=int(n)<=j['target'] for n in controller.departure_health)
        assert world._transport['departed']==world._transport['success']+world._transport['failed']+len(world._trips)
        row=dict(first_switch_pre_digest=first_switch_pre_digest,phase_events=controller.phase_events,retiring_remaining=len(controller.retiring),role_events=controller.role_events,upgrade_events=getattr(controller,'upgrade_events',[]),transport=dict(world._transport,pending=len(world._trips)),removed=dict(world._removed),job=j,status='complete',seconds=time.perf_counter()-start,score=world.result['score'],hour=world.hour,
                 command_errors=dict(errors),battle_metrics=dict(world._measure),policy_metrics=dict(controller.metrics),
                 departure_health=dict(controller.departure_health),death_examples=world._examples,
                 stats=world.stats,timeline=timeline,config=world.cfg,physics_digest=world.physics_digest())
        write(path/'result.json',row);write(path/'progress.json',dict(year=10,status='complete'));return row
    except Exception:
        import traceback
        write(path/'error.json',dict(job=j,hour=world.hour,traceback=traceback.format_exc()));raise


def hashes():
    files=list((ROOT/'aiwar').glob('*.py'))+[ROOT/'aiwar/config.json',ROOT/'scripts/transport_triple_policy.py',ROOT/'scripts/transport_growth_policy.py',ROOT/'scripts/transport_hunter_policy.py',ROOT/'scripts/transport_rear_policy.py',ROOT/'scripts/transport_rear_study.py']
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--host',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    m=json.loads(Path(a.manifest).read_text(encoding='utf-8'));assert hashes()==m['source_sha256']
    jobs=[j for j in m['jobs'] if j['host']==a.host];out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();report=dict(status='running',host=a.host,python=sys.version,platform=platform.platform(),source_sha256=hashes(),results=[],failures=[])
    write(out/'summary.json',report)
    with ProcessPoolExecutor(max_workers=m['workers'][a.host]) as pool:
        fs={pool.submit(run,(j,str(out))):j for j in jobs}
        for f in as_completed(fs):
            try:report['results'].append(f.result())
            except Exception as e:report['failures'].append(dict(job=fs[f],error=repr(e)))
            report['seconds']=time.perf_counter()-start;write(out/'summary.json',report)
            print(json.dumps(dict(host=a.host,done=len(report['results']),failed=len(report['failures']),total=len(jobs))),flush=True)
    report['status']='complete' if len(report['results'])==len(jobs) and not report['failures'] else 'failed'
    report['seconds']=time.perf_counter()-start;write(out/'summary.json',report)
    if report['status']!='complete':raise SystemExit(1)


if __name__=='__main__':main()
