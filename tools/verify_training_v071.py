"""Verify the independent v0.7.1 patch and preservation of frozen v0.7.0."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(ROOT / 'tools/verify_training_v070.py')], check=True)
manifest = json.loads((ROOT / 'freeze/v0.7.1.json').read_text(encoding='utf-8'))
for name, expected in manifest['files'].items():
    path = ROOT / name
    if not path.resolve().is_relative_to(ROOT) or not path.is_file():
        raise SystemExit('Missing or invalid patch path: ' + name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit('Changed patch file: ' + name)
for name in manifest['unchanged_from_v070']:
    old = ROOT / 'training/realmap-v0.7.0' / name
    new = ROOT / 'training/realmap-v0.7.1' / name
    if old.read_bytes() != new.read_bytes():
        raise SystemExit('Unexpected inherited change: ' + name)
print('OK: independent v0.7.1 patch; all prior releases preserved; exact inherited source bytes')
