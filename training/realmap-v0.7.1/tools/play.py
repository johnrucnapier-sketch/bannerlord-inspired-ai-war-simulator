"""Run an eight-nation JSONL match with one shared or explicit agent per country."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aiwar.match import run_match

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--style',default='vanilla_v1',choices=['vanilla_v1','march','march_p5','manual'])
    p.add_argument('--agents',help='JSON array of 8 argv arrays; overrides --style')
    p.add_argument('--days',type=int,default=None);p.add_argument('--seed',type=int,default=1)
    p.add_argument('--timeout',type=float,default=2);p.add_argument('--output',required=True)
    a=p.parse_args()
    commands=json.loads(a.agents) if a.agents else [[sys.executable,'-m','aiwar.baseline_agent','--style',a.style] for _ in range(8)]
    report=run_match(commands,a.output,seed=a.seed,days=a.days,timeout=a.timeout,mode='realmap')
    print(json.dumps(report['result'],ensure_ascii=False))
if __name__=='__main__':main()
