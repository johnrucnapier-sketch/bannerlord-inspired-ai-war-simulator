"""Verify original baselines and the ready-to-run v0.5.0 source/map package."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(root/'tools/verify_training.py')],check=True)
m=json.loads((root/'freeze/v0.5.0.json').read_text(encoding='utf-8'));errors=[]
for name,expected in m['files'].items():
    p=(root/name).resolve()
    if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append(name)
package=root/'training/realmap-v0.5.0'
actual={p.relative_to(root).as_posix() for p in (package/'aiwar').glob('*.py')}
errors.extend(sorted(actual-set(m['files'])))
if errors:print('FAILED:',errors);sys.exit(1)
map_manifest=json.loads((package/'aiwar/data/west_north/MAP_MANIFEST.json').read_text(encoding='utf-8'))
for name,expected in map_manifest['files'].items():
    if hashlib.sha256((package/'aiwar/data/west_north'/name).read_bytes()).hexdigest()!=expected:raise SystemExit('Map mismatch: '+name)
print('OK: v0.5.0',len(m['files']),'files, bundled map, vanilla_v1 default; prior baselines unchanged')
