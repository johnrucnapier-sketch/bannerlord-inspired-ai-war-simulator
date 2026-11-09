"""Fixed initial observations, fresh processes, unchanged two-second budget.

No world steps or policy commands are applied. Elapsed time includes process
launch and any cleanup; JsonAgent's original timeout result remains authoritative.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

p=argparse.ArgumentParser()
p.add_argument('--package',default='realmap-v0.7.2',choices=['realmap-v0.7.0','realmap-v0.7.1','realmap-v0.7.2'])
p.add_argument('--trials',type=int,default=5)
p.add_argument('--cpus',type=int)
a=p.parse_args()
if a.trials<1 or a.trials>20:p.error('trials must be 1..20')
if a.cpus is not None:
    if not hasattr(os,'sched_setaffinity'):p.error('CPU affinity control is unavailable on this platform')
    available=sorted(os.sched_getaffinity(0))
    if a.cpus<1 or a.cpus>len(available):p.error('requested CPU count exceeds available affinity')
    os.sched_setaffinity(0,available[:a.cpus])
repository=Path(__file__).resolve().parents[3]
package=repository/'training'/a.package
sys.path.insert(0,str(package))
import aiwar
from aiwar.match import JsonAgent
from aiwar.server import Session
from aiwar.strategy_catalog import ADAPTED_SOURCE

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

session=Session(1)
requests=[dict(protocol_version=1,type='decide',request_id=f'{n}:0',
               observation=session.world.observe(n),previous_outcomes=[])
          for n in session.world.nation_ids()]
bootstrap=(f'import sys,runpy;sys.path.insert(0,{str(package)!r});import aiwar;'
           f'runpy.run_path({str(ADAPTED_SOURCE/"agent.py")!r},run_name="__main__")')
argv=[sys.executable,'-I','-c',bootstrap]
topology=[]
if hasattr(os,'sched_getaffinity'):
    for cpu in sorted(os.sched_getaffinity(0)):
        row={'logical_cpu':cpu}
        for key in ('core_id','physical_package_id','thread_siblings_list'):
            try:row[key]=(Path('/sys/devices/system/cpu')/f'cpu{cpu}'/'topology'/key).read_text().strip()
            except OSError:row[key]=None
        topology.append(row)
print(json.dumps(dict(type='environment',package=a.package,version=aiwar.__version__,
    python=platform.python_version(),platform=platform.system(),cpu_count=os.cpu_count(),
    effective_cpu_count=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
    timeout_seconds=2,trials=a.trials,seed=1,world_hours_advanced=0,cpu_topology=topology,
    source_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((package/'aiwar').glob('*.py'))})),flush=True)
failures=0
for trial in range(a.trials):
    agents=[JsonAgent(argv,subprocess.DEVNULL,timeout=2) for _ in requests]
    def call(n):
        started=time.perf_counter()
        commands,error=agents[n].decide(requests[n])
        return dict(nation=n,elapsed_seconds=round(time.perf_counter()-started,6),
                    commands=len(commands),error=error,request_sha256=digest(requests[n]),
                    command_sha256=digest(commands))
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:rows=list(executor.map(call,range(8)))
        failures+=sum(row['error'] is not None for row in rows)
        print(json.dumps(dict(type='cold_trial',trial=trial,rows=rows)),flush=True)
    finally:
        for agent in agents:agent.close()
session.strategy_runtime.close()
print(json.dumps(dict(type='summary',failed_decisions=failures,total_decisions=a.trials*8)),flush=True)
sys.exit(bool(failures))
