# GPT dot — Campaign600 v6 Feasible Relief（实验版）

## 接续更新：3次新尝试，不是恢复旧赛果

**新接续3次：1胜/0平/2负，0项无判决；已完成分母3。所有故障完成局按我方负局的事后敏感性为1胜/0平/2负（分母3）。**

本次协议错误0、决策超时0、traceback 0、恢复记录0；命令拒绝我方0条、Grok 4条，单独保留。

可另作描述性的24槽位视图（21个历史已知结果＋3次新尝试）：20胜/0平/4负，0项无判决；已完成分母24。所有故障完成局按我方负局的事后敏感性为16胜/0平/8负（分母24）。每个槽位的来源在results.json逐行列明；不是原始24局的最终结果，不能当作干净独立确认。

原40行值全部保留，包括21个历史独立赛果和3个原始未知；新增3行后共43次主尝试，其中原独立24＋新接续3＝27次尝试。原始无故障门槛失败、原日志丢失和3项原始未知均未被修复；不作p值通过或普遍获胜声明。命令拒绝与运行故障分开记录，不因拒绝自动判定运行故障。

## 原始中断研究快照（历史口径保留）

**评估未完成，不能称为通过独立验证的冠军。** 对固定 GrokBot 小水 v19 的24局预注册测试，执行器失联前保留了 **21局：19胜、0平、2负；另外3局结果未知**。其中5局受运行超时影响，预注册的无运行故障条件已经失败。不能把未知局当负局、平局或已完成局，也不能把19/21写成完整24局胜率。

将所有5局故障局都按我方负局计算，得到 **15胜6负（仅21局已知结果的事后敏感性分析）**；这不是实际赛果，也不能补救验证失败。原始日志、存档及最终审计随执行器更换不可访问。本目录保留全部40项主试验登记行（基线8、开发8、独立24），缺失字段明确留空。详见 [REPORT.md](REPORT.md) 与 [results.json](results.json)。

## 策略变化

- 不再因超过第30天而停止发现/维持真实战场威胁。
- 调兵前先检查**实际可用健康野战兵力、行军时间与粮食**；不把驻军或未来招募当作已到场援军。
- 足以守城的已到场防守兵不随意抽走；围城后的迟到部队不虚构城防加成。敌军只归属一个威胁目标，规划与执行使用同一口径。
- JSONL进程重启后只从当前观察接管真实部队，不再要求首条请求一定是小时0。历史战略/经济记忆仍会丢失，恢复不等于原轨迹。
- 非军事任务部队沿用原经济方法，但长期抽调确有经济机会成本。未改游戏规则、对手、旧版本或随机种子行为。

## 身份与恢复

本体为冻结v0.2.0，807个文件。固定对手为 `策略更新-GrokBot小水/v19/agent.py`，不是泛指所有Grok版本。

- v6策略 SHA256：`f8e10fca279b479151746c3d324496dfd77ba9f99375b4dc356f10ab73fbae75`
- Grok v19 SHA256：`98197d519160dd29f358e648c069bdae0aad5073edabec634b06bfe2b8349116`
- 冻结清单 SHA256：`a6d56cb4875804770bf82fa176d08cfc30f5af892763fc10f92e3c826e8274a5`

策略文件从已公开v4与作者保留的原始补丁链恢复，**精确匹配失联前预注册SHA256**，49,379字节。测试文件亦按保留补丁重建，但原测试文件最终SHA未保留，不能声称它已独立证明字节相同；恢复后重新运行51项合成测试全部通过。在最初源码恢复阶段没有重跑对抗局；本次另有明确标注的3次接续尝试。依赖仅Python标准库与仓库冻结参考模块；无网络、付费API、模型调用或隐藏世界输入。许可：仓库MIT。

## 官方协议复现

从仓库根目录，使用CPython **3.12.14**：

```sh
python3.12 tools/verify_release.py
python3.12 strategies/submissions/策略更新-GPTdot/v6/test_policy.py
```

单局示例（双方使用同一解释器、独立JSONL进程，清除全部GB_*覆盖）：

```sh
python3.12 - 2068903524 0 runs/v6-example-blue <<'PY'
import json, os, platform, subprocess, sys
from pathlib import Path
assert platform.python_version() == '3.12.14'
seed, side, output = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
assert side in (0, 1) and not Path(output).exists()
ours = [sys.executable, 'strategies/submissions/策略更新-GPTdot/v6/policy.py']
grok = [sys.executable, 'strategies/submissions/策略更新-GrokBot小水/v19/agent.py']
cmds = [ours, grok] if side == 0 else [grok, ours]
env = dict(PATH=os.path.dirname(sys.executable)+os.pathsep+os.defpath,
           LANG='C.UTF-8', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
subprocess.run([sys.executable, 'tools/play.py', '--seed', str(seed), '--days', '1680',
    '--timeout', '2', '--blue-command', json.dumps(cmds[0]),
    '--red-command', json.dumps(cmds[1]), '--output', output], env=env, check=True)
PY
```

`results.json` 独立阶段的24行列明全部12种子与蓝红交换。完整重测须逐行使用新输出目录、最多2局并发，保留所有退出状态、双方stderr及失败。下述用户接续仅执行3个未知项目，必须作为新的接续批次单独保留，不能冒充失联进程的原始结果。本例不实现研究时每进程2400秒CPU、2GiB地址空间和整局2700秒墙钟限制；需要等价资源契约时另加外部包装。

官方每6小时决策、1680天、原统一/城数判胜不变。**墙钟超时依赖调度，同源同种子重跑不保证再现原超时、赛果或物理摘要。** 协议错误为0也不足以排除对手捕获后吞掉的异常，仍需检查stderr。JSONL进程隔离并非恶意代码安全沙箱。此版不替换默认参考策略，也不宣称普遍获胜。

## 用户接续命令存档：仅3个原始未知槽位（再次运行仍是新尝试）

用户可运行下面的固定小批次：**1232181665我方蓝、785517304我方蓝、785517304我方红**。这会启动新的比赛进程，不会恢复失联进程；保留原24行中的“未知”，新输出单独标注为接续尝试。已有超时故障不会因此消失，不能将接续后数据称作原预注册的干净确认。代码不改策略、对手或世界，最多2局并发，双方2秒；仍不包含研究资源限制包装。

```sh
python3.12 - <<'PY_RESUME'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib, json, os, platform, subprocess, sys
assert platform.python_version() == '3.12.14'
ours = 'strategies/submissions/策略更新-GPTdot/v6/policy.py'
grok = 'strategies/submissions/策略更新-GrokBot小水/v19/agent.py'
for name, expected in ((ours, 'f8e10fca279b479151746c3d324496dfd77ba9f99375b4dc356f10ab73fbae75'),
                       (grok, '98197d519160dd29f358e648c069bdae0aad5073edabec634b06bfe2b8349116')):
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected
subprocess.run([sys.executable, 'tools/verify_release.py'], check=True)
pending = [(1232181665, 0), (785517304, 0), (785517304, 1)]
output = Path('runs/v6-user-continuation-3')
output.mkdir(parents=True, exist_ok=False)
env = dict(PATH=os.path.dirname(sys.executable)+os.pathsep+os.defpath,
           LANG='C.UTF-8', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
def play(item):
    seed, side = item
    name = 'seed-%d-side-%d' % item
    a, b = [sys.executable, ours], [sys.executable, grok]
    if side == 1: a, b = b, a
    cmd = [sys.executable, 'tools/play.py', '--seed', str(seed), '--days', '1680',
           '--timeout', '2', '--blue-command', json.dumps(a), '--red-command', json.dumps(b),
           '--output', str(output/name)]
    with (output/(name+'.host.stdout.log')).open('x') as out, (output/(name+'.host.stderr.log')).open('x') as err:
        result = subprocess.run(cmd, env=env, stdout=out, stderr=err, check=False)
    return dict(seed=seed, our_side=side, returncode=result.returncode,
                provenance='new user continuation attempt; not recovered original outcome')
with ThreadPoolExecutor(max_workers=2) as pool:
    rows = list(pool.map(play, pending))
(output/'continuation-status.json').write_text(json.dumps(rows, indent=2))
print('Keep all outputs and both agents stderr; original unknown outcomes remain unknown.')
PY_RESUME
```

本次逐局官方摘要见 [continuation-records/](continuation-records/)；资源与审计边界见REPORT。
