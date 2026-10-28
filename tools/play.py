"""Portable protocol match launcher. Outputs go outside frozen directories."""
import argparse,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'game'))
from aiwar.match import run_match

def main():
 p=argparse.ArgumentParser();p.add_argument('--blue',default='march',choices=['march','p3','p5','d2','idle']);p.add_argument('--red',default='march',choices=['march','p3','p5','d2','idle'])
 p.add_argument('--blue-command');p.add_argument('--red-command');p.add_argument('--seed',type=int,default=1);p.add_argument('--days',type=int,default=1680);p.add_argument('--timeout',type=float,default=2);p.add_argument('--mode',choices=['duel','rural'],default='duel');p.add_argument('--output',required=True);a=p.parse_args()
 if a.mode=='rural' and a.blue=='d2' and not a.blue_command:p.error('D2 reference is configured for duel; rural needs its own slot allocation')
 output=Path(a.output).resolve()
 for frozen in ['game','benchmarks/data','benchmarks/reports','strategies/reference','freeze']:
  if output.is_relative_to((ROOT/frozen).resolve()):p.error('output must not be inside frozen directories')
 commands=[]
 for name,custom in [(a.blue,a.blue_command)]+([(a.red,a.red_command)] if a.mode=='duel' else []):
  commands.append(json.loads(custom) if custom else [sys.executable,str(ROOT/'strategies/agent.py'),'--policy',name])
 report=run_match(commands,str(output),seed=a.seed,days=a.days,timeout=a.timeout,mode=a.mode)
 manifest=ROOT/'freeze/v0.2.0.json'
 (output/'challenge.json').write_text(json.dumps(dict(baseline='v0.2.0',baseline_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),seed=a.seed,days=a.days,mode=a.mode,development_run=a.days!=1680 or a.mode!='duel',builtin_blue=a.blue if not a.blue_command else None,builtin_red=a.red if not a.red_command else None),indent=2))
 print(json.dumps(report['result'],ensure_ascii=False))
if __name__=='__main__':main()
