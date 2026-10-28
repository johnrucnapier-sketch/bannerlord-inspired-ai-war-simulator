"""Read-only integrity check. Does not import or execute a submitted policy."""
import argparse,hashlib,json,sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--manifest',type=Path);p.add_argument('--scope',choices=['all','core','evidence','reference'],default='all');a=p.parse_args();root=a.root.resolve()
 m=json.loads((a.manifest or root/'freeze/v0.2.0.json').read_text());errors=[]
 prefixes={'core':('game/',),'evidence':('benchmarks/',),'reference':('strategies/reference/',)}
 selected={rel:digest for rel,digest in m['files'].items() if a.scope=='all' or rel.startswith(prefixes[a.scope])}
 for rel,expected in selected.items():
  path=(root/rel).resolve()
  if not path.is_relative_to(root):errors.append('outside root: '+rel);continue
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:errors.append('missing or changed: '+rel)
 actual={str(f.relative_to(root)) for f in (root/'game').rglob('*') if f.is_file() and '__pycache__' not in f.parts and '.godot' not in f.parts and '.tools' not in f.parts and '.venv' not in f.parts and not any(x.endswith('.egg-info') for x in f.parts) and 'build' not in f.parts}
 expected={r for r in m['files'] if r.startswith('game/')}
 if a.scope in ('all','core'):errors.extend('untracked core file: '+r for r in sorted(actual-expected))
 if errors:print('\n'.join(errors));sys.exit(1)
 print(f"OK: {m['baseline']} / {len(selected)} frozen files ({a.scope}) / core and evidence match")
if __name__=='__main__':main()
