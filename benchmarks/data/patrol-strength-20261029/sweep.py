"""PC isolated combat sweep; legal party sizes, no movement/support/healing."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import sys

p=argparse.ArgumentParser()
p.add_argument('--source',required=True)
p.add_argument('--output',required=True)
a=p.parse_args()
source=Path(a.source)
sys.path.insert(0,str(source))
from aiwar.engine import World

out=Path(a.output);out.mkdir(exist_ok=False)
rows=[]
for count in range(1,151):
    w=World(1,{'bandit_cap':0})
    w.units.clear();w.cities.clear();w.villages.clear()
    own=w.new_unit('party',0,0,count,60000,40000,food=1000000)
    enemy=w.new_unit('bandit',-1,-1,20,60000,40000)
    w.start_battle(own,enemy)
    battle=next(iter(w.battles.values()))
    prepare=battle['prepare_hours'];scale=battle['combat_hours']
    ticks=0;trace=[]
    for hour in range(1000):
        w.hour=hour
        if hour>=prepare:ticks+=1
        w.battle_tick()
        if hour>=prepare:
            trace.append(dict(hour=hour,own_healthy=own['healthy'],own_wounded=own['wounded'],enemy_healthy=enemy['healthy']))
        if not w.battles:break
    assert not w.battles
    won=own['id'] in w.units and own['healthy']>0 and enemy['id'] not in w.units
    row=dict(patrol=count,bandits=20,won=won,own_removed=own['id'] not in w.units,
             healthy=own['healthy'],wounded=own['wounded'],combat_dead=count-own['healthy']-own['wounded'],
             casualties=count-own['healthy'],combat_ticks=ticks,prepare_hours=prepare,end_hour=hour)
    rows.append(row)
    (out/f'trace-{count:03}.json').write_text(json.dumps(trace),encoding='utf-8')

def minimum(predicate):
    return next((r['patrol'] for r in rows if r['won'] and predicate(r)),None)
report=dict(host=platform.node(),platform=platform.platform(),python=sys.version,
            source_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((source/'aiwar').glob('*.py'))},
            rules=World(1).cfg,conditions='20 healthy bandits; healthy party1..150; isolated field skirmish; battle_tick only; no other units, healing, hunger, movement or reinforcements',
            min_victory=minimum(lambda r:True),min_zero_deaths_victory=minimum(lambda r:r['combat_dead']==0),
            min_zero_casualties_victory=minimum(lambda r:r['casualties']==0),rows=rows)
(out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
with (out/'results.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps({k:report[k] for k in ('host','python','min_victory','min_zero_deaths_victory','min_zero_casualties_victory')},ensure_ascii=False))
print(json.dumps([r for r in rows if r['patrol'] in (10,12,13,20,21,22,26,27,30,53,54,150)],ensure_ascii=False))
