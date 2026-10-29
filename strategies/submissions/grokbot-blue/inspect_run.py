import json,sys,collections
out=sys.argv[1];me=int(sys.argv[2]) if len(sys.argv)>2 else 0
r=json.load(open(out+'/result.json'));print(r['result']);print([(c['hour']//24,c['city'],c['from'],c['to']) for c in r['captures']])
errs=collections.Counter();cmdlist=[]
for line in open(f'{out}/nation-{me}.jsonl'):
    d=json.loads(line)
    for c,o in zip(d.get('commands') or [],((d.get('request') or {}).get('previous_outcomes') or [])):pass
    for o in ((d.get('request') or {}).get('previous_outcomes') or []):
        if isinstance(o,dict) and not o.get('ok'):errs[o.get('error')]+=1
    if d.get('agent_error'):errs['AGENT:'+str(d['agent_error'])[:80]]+=1
print(errs.most_common(10))
for t in r['totals']:print(t)
