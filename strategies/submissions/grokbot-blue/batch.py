"""Grok Bot batch runner: run many matches in parallel, append summaries to runs/grokbot/results.jsonl."""
import argparse,json,subprocess,sys,os,time,gzip
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path('/workspace/aiwar');PY=str(ROOT/'.venv/bin/python')
SEEDS=json.load(open(ROOT/'benchmarks/data/direct-garrison-20261029/seed-selection.json'))['seeds']
def summarize(out,label,side,seed,days):
    r=json.load(open(out/'result.json'));res=r['result'] or {}
    me=0 if side=='blue' else 1
    tot={t['nation']:t for t in r['totals']}
    caps=r.get('captures',[])
    errs=0;inval=0
    f=out/f'nation-{me}.jsonl'
    for line in (open(f) if f.exists() else gzip.open(str(f)+'.gz','rt')):
        try:d=json.loads(line)
        except:continue
        if d.get('agent_error'):errs+=1
        for o in (d.get('outcomes') or []):
            if isinstance(o,dict) and o.get('ok') is False:inval+=1
    return dict(label=label,side=side,seed=seed,days=days,winner=res.get('winner'),win=None if res.get('winner') is None else res['winner']==me,
        reason=res.get('reason'),hour=res.get('hour'),cities_me=res.get('cities',{}).get(str(me)),cities_opp=res.get('cities',{}).get(str(1-me)),
        pop_me=tot[me]['population'],pop_opp=tot[1-me]['population'],mil_me=tot[me]['military'],mil_opp=tot[1-me]['military'],
        first_loss=next((c['hour'] for c in caps if c['from']==me),None),captures_me=sum(c['to']==me for c in caps),
        agent_errors=errs,invalid_cmds=inval,out=str(out))
def run(job):
    label,cmd,side,seed,days=job
    out=ROOT/'runs/grokbot'/f'{label}-{side}-s{seed}-d{days}'
    if out.exists():
        if (out/'result.json').exists():return summarize(out,label,side,seed,days)
        k=2
        while (out.parent/f'{out.name}-r{k}').exists() and not (out.parent/f'{out.name}-r{k}'/'result.json').exists():k+=1
        out=out.parent/f'{out.name}-r{k}'
        if (out/'result.json').exists():return summarize(out,label,side,seed,days)
    args=[PY,str(ROOT/'tools/play.py'),'--seed',str(seed),'--days',str(days),'--output',str(out)]
    if side=='blue':args+=(['--blue',cmd] if cmd in('march','d2','p5','p3','idle') else ['--blue-command',cmd])+['--red','march']
    else:args+=(['--red',cmd] if cmd in('march','d2','p5','p3','idle') else ['--red-command',cmd])+['--blue','march']
    p=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
    if p.returncode:return dict(label=label,side=side,seed=seed,error=p.stderr[-800:])
    subprocess.run(f'gzip -1 {out}/nation-*.jsonl',shell=True)  # raw protocol logs ~400MB/run; keep them compressed
    return summarize(out,label,side,seed,days)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('label');a.add_argument('cmd');a.add_argument('--seeds',default='0:12');a.add_argument('--days',type=int,default=1680)
    a.add_argument('--sides',default='blue');a.add_argument('-j',type=int,default=6);x=a.parse_args()
    i,j=map(int,x.seeds.split(':'));seeds=SEEDS[i:j]
    if x.cmd not in ('march','d2','p5','p3','idle'):x.cmd=json.dumps([PY,str(ROOT/'strategies/submissions/grokbot-blue'/x.cmd/'agent.py')])
    jobs=[(x.label,x.cmd,s,seed,x.days) for s in x.sides.split(',') for seed in seeds]
    t=time.time()
    with ThreadPoolExecutor(x.j) as ex:
        res=list(ex.map(run,jobs))
    with open(ROOT/'runs/grokbot/results.jsonl','a') as f:
        for r in res:f.write(json.dumps(r)+'\n')
    ok=[r for r in res if 'error' not in r]
    for s in x.sides.split(','):
        rs=[r for r in ok if r['side']==s]
        if not rs:continue
        w=sum(r['win']==True for r in rs);l=sum(r['win']==False for r in rs);dr=len(rs)-w-l
        print(f"{x.label} {s} days={x.days}: W{w} L{l} D{dr} cities_me={sum(r['cities_me'] for r in rs)/len(rs):.2f} pop_me={sum(r['pop_me'] for r in rs)/len(rs):.0f} pop_opp={sum(r['pop_opp'] for r in rs)/len(rs):.0f} unif={[r['hour']//24 for r in rs if r['reason']=='unification' and r['win']]} inval={sum(r['invalid_cmds'] for r in rs)} err={sum(r['agent_errors'] for r in rs)}")
    for r in res:
        if 'error' in r:print('ERROR',r)
    print('elapsed',round(time.time()-t))
