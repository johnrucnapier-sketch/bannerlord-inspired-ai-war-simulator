"""Run test modules in isolated processes: historical study imports patch telemetry."""
from pathlib import Path
import subprocess,sys
from concurrent.futures import ThreadPoolExecutor
root=Path(__file__).resolve().parent.parent
files=sorted((root/'tests').glob('test_*.py'))
def run(path):
 result=subprocess.run([sys.executable,'-m','unittest','tests.'+path.stem,'-q'],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 return path.name,result.returncode,result.stdout
failed=[]
# The viewer already launches eight cold agents concurrently. Do not add an
# unrelated test workload to its strict wall-clock budget. No agent timeout,
# assertion or process concurrency changes; all failures remain fatal.
timed=[path for path in files if path.name=='test_dev19_viewer_v7.py']
files=[path for path in files if path not in timed]
for path in timed:
 name,code,output=run(path)
 print(name,'FAIL' if code else 'PASS',flush=True)
 if code:print(output,flush=True);failed.append(name)
with ThreadPoolExecutor(max_workers=2) as pool:
 for name,code,output in pool.map(run,files):
  print(name,'FAIL' if code else 'PASS',flush=True)
  if code:print(output,flush=True);failed.append(name)
print('modules',len(files)+len(timed),'failed',failed)
sys.exit(bool(failed))
