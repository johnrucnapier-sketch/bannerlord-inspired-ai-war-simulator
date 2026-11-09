"""Verify candidate identity and exact preservation of both earlier packages."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'tools/verify_training_v071.py')],check=True)
manifest=json.loads((ROOT/'freeze/v0.7.2.json').read_text(encoding='utf-8'))
for name,expected in manifest['files'].items():
    path=ROOT/name
    if not path.resolve().is_relative_to(ROOT) or not path.is_file():raise SystemExit('Missing/invalid path: '+name)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise SystemExit('Changed candidate file: '+name)
for name in manifest['unchanged_from_v071']:
    if (ROOT/'training/realmap-v0.7.1'/name).read_bytes()!=(ROOT/'training/realmap-v0.7.2'/name).read_bytes():
        raise SystemExit('Unexpected inherited change: '+name)
print('OK: independent v0.7.2 candidate; previous packages and unchanged inherited bytes preserved')
