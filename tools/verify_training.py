"""Check the separately frozen v0.4.1 training source without executing policies."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'freeze/v0.4.1.json').read_text(encoding='utf-8'))
errors=[]
for name,expected in manifest['files'].items():
    p=(root/name).resolve()
    if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append(name)
actual={str(p.relative_to(root)) for p in (root/'training/realmap-v0.4.1/aiwar').glob('*.py')}
errors.extend(sorted(actual-set(manifest['files'])))
if errors:print('FAILED:',errors);sys.exit(1)
print('OK:',manifest['baseline'],len(manifest['files']),'source files; external map data is separately identified per run')
