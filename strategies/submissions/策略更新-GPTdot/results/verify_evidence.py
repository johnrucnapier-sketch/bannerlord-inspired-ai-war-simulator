#!/usr/bin/env python3
"""Verify portable evidence file integrity; stdlib only, no games or network."""
import hashlib, json
from pathlib import Path
root = Path(__file__).resolve().parent
manifest = json.loads((root / 'MANIFEST.json').read_text())
failures = []
for name, meta in manifest['files'].items():
    path = root / name
    if not path.is_file() or path.is_symlink():
        failures.append(name + ': missing or symlink')
        continue
    data = path.read_bytes()
    if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
        failures.append(name + ': hash/size mismatch')
expected = set(manifest['files']) | {'MANIFEST.json', 'SHA256SUMS.txt'}
actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for line in (root / 'SHA256SUMS.txt').read_text().splitlines():
    expected_hash, name = line.split('  ', 1)
    path = root / name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        failures.append(name + ': checksum-list mismatch')
failures.extend('Unmanifested file: ' + p for p in sorted(actual - expected))
print(json.dumps({'passed': not failures, 'checked_files': len(manifest['files']), 'failures': failures}, ensure_ascii=False, indent=2))
raise SystemExit(bool(failures))
