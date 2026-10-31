"""Inspect published match results; never run agents."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--opponent');p.add_argument('--losses',action='store_true');p.add_argument('--seed',type=int);a=p.parse_args()
x=json.loads((Path(__file__).parent/'results.json').read_text())
for r in x['formal_rows']:
 if a.opponent and r['opponent']!=a.opponent:continue
 if a.losses and r['outcome']!='loss':continue
 if a.seed is not None and r['seed']!=a.seed:continue
 print(json.dumps({k:r[k] for k in ['opponent','seed','candidate_side','outcome','ending_hour','candidate_cities','opponent_cities','physics_digest']},ensure_ascii=False))
