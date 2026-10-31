"""Explicitly replay one published sample with the unchanged official match launcher."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
p=argparse.ArgumentParser();p.add_argument('--opponent',required=True,choices=['v20','v21','v22','v23','v24']);p.add_argument('--seed',required=True,type=int);p.add_argument('--side',required=True,choices=['blue','red']);p.add_argument('--output',required=True);a=p.parse_args()
m=json.loads((HERE/'experiment.json').read_text())
for name,expected in m['hashes'].items():
 if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise SystemExit('Tested source mismatch: '+name)
subprocess.run([sys.executable,str(ROOT/'tools/verify_release.py')],check=True)
cmd=[sys.executable,str(ROOT/'tools/play.py'),'--seed',str(a.seed),'--days','1680','--timeout','2','--output',a.output]
for color in ['blue','red']:
 path=ROOT/('strategies/submissions/策略更新-GPTdot/independent-a-r3/agent.py' if color==a.side else 'strategies/submissions/策略更新-GrokBot小水/'+a.opponent+'/agent.py')
 cmd+=['--'+color+'-command',json.dumps([sys.executable,'-S',str(path)])]
env={k:v for k,v in os.environ.items() if not k.startswith('GB_')};env.update(PYTHONUTF8='1',PYTHONHASHSEED='0')
subprocess.run(cmd,cwd=ROOT,env=env,check=True)
