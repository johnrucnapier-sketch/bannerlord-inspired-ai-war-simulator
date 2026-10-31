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
with ThreadPoolExecutor(max_workers=2) as pool:
 for name,code,output in pool.map(run,files):
  print(name,'FAIL' if code else 'PASS',flush=True)
  if code:print(output,flush=True);failed.append(name)
print('modules',len(files),'failed',failed)
sys.exit(bool(failed))
