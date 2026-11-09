"""Read-only integrity check for this separate optional strategy release."""
from pathlib import Path
import hashlib
import json


def verify():
    here = Path(__file__).resolve().parent
    manifest = json.loads((here/'MANIFEST.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        path = here/name
        if path.parent != here or path.is_symlink():
            raise ValueError('Invalid strategy manifest path')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Changed strategy file: '+name)
    baseline = here.parents[2]/'freeze/v0.7.0.json'
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != manifest['engine_freeze_sha256']:
        raise ValueError('Unexpected v0.7.0 engine freeze')
    print('OK: '+manifest['strategy']+' / '+str(len(manifest['files']))+' files; unchanged v0.7.0 engine freeze')


if __name__ == '__main__':
    verify()
