"""Local demonstration catalog; frozen game and submitted policy bytes stay intact."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / 'artifacts/strategy-history-20261030'
SOURCE = ARCHIVE / 'source'

BUILTINS = [
    ('march', '标准进军 march', 'duel'),
    ('march_p5', '进军＋P5护农', 'duel'),
    ('w1', 'W1 保底集中', 'duel'), ('w2', 'W2 风险抽调', 'duel'),
    ('w3', 'W3 轮换出征', 'duel'), ('w4', 'W4 战区预备', 'duel'),
    ('guard', '标准巡逻清剿', 'rural'),
    ('p1', 'P1 驻点守护', 'rural'), ('p2', 'P2 随车护送', 'rural'),
    ('p3', 'P3 环线巡防', 'rural'), ('p4', 'P4 就近救援', 'rural'),
    ('p5', 'P5 分区协巡', 'rural'),
    ('manual', '静置对照', 'both'),
]
EXTERNAL = {
    'd1': ('D1 护送巡逻防守', 'strategies/reference/v0.2.0/scripts/escort_p5_defense_policy.py'),
    'd2': ('D2 军事任务持续', 'strategies/reference/v0.2.0/scripts/escort_p5_defense_v2_policy.py'),
}
GROK_NAMES = {9:'援军估算',10:'提前增防',12:'按容量集结',13:'全国动员',14:'残局动员',
              15:'解围战估算',16:'分阶段估算',17:'残局全军',18:'基地丢失修复',19:'避开开局解围'}
for version, label in GROK_NAMES.items():
    EXTERNAL[f'grok_v{version}'] = (f'Grok v{version} · {label}',
        f'strategies/submissions/策略更新-GrokBot小水/v{version}/agent.py')
for version,label in [(1,'600兵战役'),(4,'开局解围'),(6,'可行解围〔实验〕')]:
    EXTERNAL[f'gpt_v{version}'] = (f'GPT v{version} · {label}',
        'strategies/submissions/策略更新-GPTdot/' + ('' if version==1 else f'v{version}/') + 'policy.py')

def catalog(mode):
    builtin_mode='duel' if mode=='realmap' else mode
    rows=[dict(id=i,label=l,external=False) for i,l,m in BUILTINS if m in (builtin_mode,'both')]
    if mode=='realmap':rows.insert(0,dict(id='vanilla_v1',label='原版风味基准 v1〔默认〕',external=False))
    if mode=='duel' and (ARCHIVE/'manifest.json').is_file():
        rows[1:1]=[dict(id=i,label=l,external=True) for i,(l,_) in EXTERNAL.items()]
    return rows

def valid(style,mode):
    return any(r['id']==style for r in catalog(mode))

def verify_source(style):
    rel=EXTERNAL[style][1]
    manifest=json.loads((ARCHIVE/'manifest.json').read_text())
    actual=hashlib.sha256((SOURCE/rel).read_bytes()).hexdigest()
    if actual!=manifest['files'][rel]:raise ValueError(f'历史策略源码校验失败：{style}')
    return actual
