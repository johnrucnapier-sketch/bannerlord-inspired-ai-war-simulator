import json,glob,re,collections
from pathlib import Path
rows=collections.defaultdict(dict)
for f in glob.glob('res/*.json'):
    m=re.match(r'res/(.+)_(\d+)\.json',f)
    if not m:continue
    r=json.loads(Path(f).read_text());c=r['result']['cities']
    rows[m[1]][int(m[2])]=(int(c.get('1',c.get(1))),int(c.get('0',c.get(0))))
names={'base_v':'v0 原版基准(北方用vanilla_v1)'}
for v in sorted(rows):
    d=rows[v];w=sum(a>b for a,b in d.values());l=sum(a<b for a,b in d.values());dr=len(d)-w-l
    print(f"| {names.get(v,v)} | "+" | ".join(f"{d[s][0]}:{d[s][1]}" if s in d else "—" for s in range(1,7))+f" | {w}-{dr}-{l} | {sum(a for a,b in d.values())/len(d):.1f} |")
