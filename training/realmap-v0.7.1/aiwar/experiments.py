"""Reproducible patrol controls; fixture resources are equal across compared arms."""
import time
from .engine import World, dist
from .policies import decision_cycle


def run_scenario(args):
    seed,style,mature,days=args
    w=World(seed,{'days':days,'initial_soldiers':40 if mature else 30})
    if mature:
        # Same 120 field soldiers per clan and same grain on BOTH control arms.
        for c in w.cities.values():
            c['recruits']=80
            for _ in range(2):
                r=w.command(c['nation'],{'type':'create','city':c['id'],'count':40})
                assert r['ok'],r
    started=time.perf_counter()
    population_start=sum(v['population'] for v in w.villages.values())
    max_bandits=0
    while not w.result:
        if w.hour%w.cfg['decision_hours']==0:decision_cycle(w,(style,style))
        w.step()
        if w.hour%24==0:
            w.check()
            max_bandits=max(max_bandits,sum(u['kind']=='bandit' for u in w.units.values()))
    out={'seed':seed,'style':style,'mature':mature,'days':days,'seconds':round(time.perf_counter()-started,2),
         'population':sum(v['population'] for v in w.villages.values()),
         'population_removed':population_start+36*days-sum(v['population'] for v in w.villages.values()),
         'peak_bandits':max_bandits,'ending_bandits':sum(u['kind']=='bandit' for u in w.units.values()),
         'stats':w.stats,'digest':w.digest()}
    return out
