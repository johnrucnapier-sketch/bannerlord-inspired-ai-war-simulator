"""Inspect published match metadata without running agents or downloading large files."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--opponent',choices=['v20','v21','v22','v23','v24']);p.add_argument('--losses',action='store_true');a=p.parse_args()
rows=json.loads((Path(__file__).parent/'results.json').read_text())['rows']
for r in rows:
 if a.opponent and r['opponent']!=a.opponent:continue
 if a.losses and r['win'] is not False:continue
 print(json.dumps({k:r[k] for k in ['run_id','opponent','seed','side','win','result','score_gpt','agent_errors','internal_exceptions','asset']},ensure_ascii=False))
