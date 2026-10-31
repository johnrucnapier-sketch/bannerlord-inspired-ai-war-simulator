"""Portable, read-only integrity check for the v0.4.1 source and old v0.2.0 baseline."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
errors=[]
for version,prefix in [('v0.2.0','game'),('v0.4.1','training/realmap-v0.4.1/aiwar')]:
    manifest=json.loads((root/'freeze'/f'{version}.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():
        p=(root/name).resolve()
        if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append(name)
    if version=='v0.2.0':
        actual={p.relative_to(root).as_posix() for p in (root/prefix).rglob('*') if p.is_file() and not any(x in p.relative_to(root).parts for x in ('__pycache__','.godot','.tools','.venv','build')) and not any(x.endswith('.egg-info') for x in p.parts)}
    else:
        actual={p.relative_to(root).as_posix() for p in (root/prefix).glob('*.py')}
    errors.extend(sorted(actual-set(manifest['files'])))
    print(version,len(manifest['files']),'files checked')
if errors:print('FAILED:',errors);sys.exit(1)
print('OK: both baselines match; external map data is separately identified per run')
