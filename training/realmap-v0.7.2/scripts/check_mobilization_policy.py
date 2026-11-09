"""Constructed physical mobilization policy scenario, not natural-match evidence.
Only legal transfer/assembly/move commands after the initial map; no teleports.
"""
import sys,math,json,copy,time,argparse
from pathlib import Path
R=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(R/'training/realmap-v0.7.0'))
from aiwar.engine import World
from aiwar.organization_policy import augment_commands,_travel_days
from aiwar.navigation import find_route
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',default='runs/mobilization-policy.json',help='New scenario trace file; parent directories are created')
output=Path(parser.parse_args().output)
if output.exists():raise SystemExit('Refusing to overwrite an existing scenario trace')
w=World(1,{'mode':'realmap','bandit_cap':0,'auto_city_service':False,'days':40})
n=3;clan=w.nations[str(n)]['ruler_clan'];ps=[u for u in w.units.values() if u['kind']=='party' and u['clan']==clan];leader=ps[0];members=ps[:2];keep={u['id'] for u in members}
log=[]
def command(n,c):
 r=w.command(n,c)
 assert r['ok'],(w.hour,n,c,r)
 log.append(dict(hour=w.hour,n=n,command=c,result=r))
 return r
# Reassign initial bodies to their local garrisons, not remove/fabricate them.
for u in list(w.units.values()):
 if u['kind']!='party' or u['nation']!=n:continue
 c=w.city_at(u);count=u['healthy']-(1 if u['id'] in keep else 0)
 command(n,dict(type='transfer',unit=u['id'],target=c['garrison'],count=count))
command(n,dict(type='assemble',unit=leader['id'],units=[members[1]['id']]))
castle=next(c for c in w.cities.values() if c['clan']==clan and c['settlement_type']=='castle')
home=w.city_at(leader)
enemy=w.units['u00052'];target=w.cities['castle_K9']
# Follow the real navmesh route to a point 5,000 route units outside the city.
path=find_route(w.terrain,enemy,target['x'],target['y']);points=[(enemy['x'],enemy['y'])]+path;remaining=5000
while len(points)>1 and remaining>0:
 a,b=points[-2:];d=math.dist(a,b)
 if d<=remaining:remaining-=d;points.pop()
 else:
  f=(d-remaining)/d;points[-1]=(round(a[0]+(b[0]-a[0])*f),round(a[1]+(b[1]-a[1])*f));remaining=0
x,y=points[-1];command(enemy['nation'],dict(type='move',unit=enemy['id'],x=x,y=y))
first_prepare=None;first_mobilize=None;first_rally=None;resumed=None;lastphase=None
for _ in range(720):
 obs=w.observe(n);old=copy.deepcopy(obs)
 # A competing, legal ordinary move tests whether detour owns movement only while needed.
 original=dict(type='move',unit=leader['id'],x=home['x'],y=home['y'],west_task='clan_campaign',west_target=obs['frontier_targets'][0])
 cmds=augment_commands(obs,[original]);assert obs==old
 for c in cmds:
  command(n,c)
  phase=c.get('vanilla_task')
  if phase!=lastphase and c.get('unit')==leader['id']:
   print('PHASE',w.hour,phase,(leader['x'],leader['y']),flush=True);lastphase=phase
  if phase=='mobilization_prepare' and first_prepare is None:first_prepare=w.hour
  if c['type']=='mobilize' and first_mobilize is None:first_mobilize=w.hour
  if phase=='mobilization_rally' and first_rally is None:first_rally=w.hour
  if first_rally is not None and phase is None and c.get('unit')==leader['id']:resumed=w.hour
 if resumed is not None:break
 w.step()
 if leader['id'] not in w.units or leader['battle']:
  print('BLOCKED',w.hour,leader.get('battle'));break
w.check()
rec=list(w.mobilizations.values())
report=dict(first_prepare=first_prepare,first_mobilize=first_mobilize,first_rally=first_rally,resumed=resumed,hour=w.hour,position=[leader['x'],leader['y']],castle=castle['id'],home=home['id'],records=[{k:r[k] for k in ('id','started','rally','rally_until','status')} for r in rec],levies=[dict(id=u['id'],healthy=u['healthy'],phase=u['phase'],army=u['army']) for u in w.units.values() if u['kind']=='levy' and u['nation']==n],commands=len(log))
print(json.dumps(report,indent=2),flush=True)
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(dict(report=report,commands=log),indent=2),encoding='utf-8')
