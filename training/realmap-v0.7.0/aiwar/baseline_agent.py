"""Portable JSONL wrapper for the selected built-in baseline (default: mode-specific)."""
import argparse,json,sys
from .policies import decide

def main():
    p=argparse.ArgumentParser();p.add_argument('--style',default=None);a=p.parse_args()
    sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
    for line in sys.stdin:
        request=json.loads(line)
        commands=decide(request['observation'],a.style)
        print(json.dumps(dict(protocol_version=1,request_id=request['request_id'],commands=commands),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
