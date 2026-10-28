"""JSONL adapter for frozen references, not an omniscient strategy interface."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'game'))
sys.path.insert(0,str(ROOT/'strategies/reference/v0.2.0'))
from aiwar.policies import decide

def main():
 p=argparse.ArgumentParser();p.add_argument('--policy',choices=['march','p3','p5','d2','idle'],default='march');a=p.parse_args()
 controller=None
 if a.policy=='d2':
  from scripts.escort_p5_defense_v2_policy import Controller
  controller=Controller()
 sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
 for line in sys.stdin:
  request=json.loads(line);obs=request['observation']
  if a.policy=='d2' and obs.get('mode')=='rural':raise ValueError('D2 reference assumes duel: one initial city per clan; rural default has a different slot budget')
  commands=controller.decide(obs) if controller else [] if a.policy=='idle' else decide(obs,a.policy)
  print(json.dumps(dict(protocol_version=1,request_id=request['request_id'],commands=commands),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
