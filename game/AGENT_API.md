> 2026-10-29：新局启用`direct_garrison_delivery`。城市`recruits`字段仅为旧接口兼容而保留0，不表示可用库存；村庄`recruits`及运输队`cargo_recruits`仍代表尚未送达的兵员。送达直接加入驻军，回城机动队直接从驻军抽调；新局禁止recruit命令。驻军超过400后自动提高回城部队编制，`reserve_refill_target`记录已提高的最低整补目标（上限150）。

# 智能体开发接口 v1

公开冻结基线：v0.2.0（内部协议兼容标记0.1.6）。先读[冻结规则手册](RULES.md)，本文件代替早期接口说明。新增入口不启用内置进军/巡逻控制器，也不改变Godot当前对局。

## 快速运行一个接入测试

在项目根目录，使用已安装项目依赖的Python（Mac `.venv/bin/python`，PC `.venv\Scripts\python.exe`）：

```sh
python -m aiwar.match --agent0 '["python","-m","aiwar.agent_example"]' --agent1 '["python","-m","aiwar.agent_example"]' --days 7 --seed 1 --output artifacts/sdk-match-1
python -m aiwar.replay artifacts/sdk-match-1/final.save.json
```

将上述数组中的python换成当前虚拟环境解释器绝对路径，避免PATH差异。各shell对引号处理不同，也可以直接使用下述Python API。输出目录必须不存在，避免覆盖旧数据。示例智能体只返回空列表，用于验证接入，不提供策略。接入自己的程序时，将argv数组改为该程序的启动命令；没有shell展开。C++、Java、Python或调用模型API的包装程序均可使用同一协议。

```python
import sys
from aiwar.match import run_match
report = run_match(
    [[sys.executable, '-m', 'aiwar.agent_example'],
     [sys.executable, '-m', 'aiwar.agent_example']],
    'artifacts/sdk-match-2', seed=2, days=7, timeout=2)
```

默认每次决策2现实秒，可用`--timeout 60`给模型包装器更长预算；模拟在等待决策时不前进。每局进程独立启动，局内进程持续存在，可自行维护记忆。批量评估可循环run_match，使用不同目录/种子并交换agent0/agent1；并行时由调用方安排独立进程。相同种子、配置和智能体版本都应保留；有随机性的智能体还须保存自己的随机种子。

## JSONL协议

标准输入/输出均UTF-8，每行一个JSON，回复必须带换行并flush。stdout只能输出协议；调试信息写stderr。每6游戏小时收到：

```json
{"protocol_version":1,"type":"decide","request_id":"0:0","observation":{"hour":0,"nation":0},"previous_outcomes":[]}
```

上面observation仅示意，实际字段见下表。应回复：

```json
{"protocol_version":1,"request_id":"0:0","commands":[]}
```

request_id必须原样返回；每次最多100命令、回复行最多1MiB。超时、退出、非法JSON、错误版本/请求ID或非法命令列表时，本次视为不下新指令，原有行动继续，进程结束，下次决策重新启动，进程内记忆会丢失。每条命令执行结果通过下一次previous_outcomes传回，顺序对应上次commands；协议错误另存agent_error。末次执行结果和终局观察保存在数据文件，**不会再向进程发送额外终局请求**。

双方观察先统一取得，然后同时请求两个进程；都完成/超时后核心依次执行0、1国命令。进程是接入边界而非恶意代码沙箱：同机程序仍可访问文件/网络。只能运行可信策略；竞技环境需另设容器/权限/网络隔离。不要把对手日志和存档路径提供给参赛进程。Godot的全知WebSocket端口不是本协议的智能体接口。

## 观察对象

| 字段 | 含义 |
|---|---|
| hour、nation、rule_version | 游戏小时、己方0/1、规则版本 |
| result | 未结束为null；结束含winner（0/1/null）、reason、cities、hour |
| terrain | 40×60整数地形数组，索引[y][x] |
| cities、villages | 己方完整状态；敌方最后已知情报，有seen/stale |
| units | 己方完整实体；当前可见敌方的有限字段 |
| battles | 可见战斗：id、x/y、start、days、city、kind、prepare_hours；可能有paused_hours、relief_battle、relief_for |
| limits、speeds | 编制/粮耗关键限制、各类型速度 |
| frontier_targets | 按己方当前控制城市计算的可攻城ID列表；仍需目标当前可见 |
| relief_requests | 本国受围城市的求援：city、battle、x/y、start、assault_at、phase、relief_battle |
| events | 目前固定空列表，不能依靠它获取战况 |

己方城市常用字段：id/name/nation/clan/x/y、food、recruits、garrison、militia、convoy、neighbors。村庄：id/name/city/nation/x/y、population、food、recruits、disabled_until、cart、raid。单位：id/kind/nation/clan/x/y、healthy/wounded、food、battle、army、order、path、home；运输队另有phase、cargo_food、cargo_recruits/destination等。不要假定所有类型都有同样扩展字段；ID作为不透明字符串使用，不依赖生成顺序。观察是副本，修改它不会修改世界。

生成真实字段样本：

```python
import json
from aiwar.sdk import Environment
obs = Environment(seed=1).observations()[0]
print(json.dumps(obs, ensure_ascii=False, indent=2))
```

## 命令表

每条为JSON对象，必有`type`。表内字段除标注可选外必填。所有人数、粮食、坐标均整数；目标ID为字符串。常见失败返回`{"ok":false,"error":"原因"}`，成功`{"ok":true}`，创建/集结另返回unit/army ID。错误文字不作为稳定机器错误码使用。

| type | 字段 | 作用与约束 |
|---|---|---|
| move | unit,x,y | 领主/其军团移动到可达坐标 |
| stop | unit | 停止非交战领主/军团行动 |
| attack | unit,target | 攻击当前可见敌方单位 |
| siege | unit,target；可选award_clan | 围攻当前可见前沿敌城，指定占领后家族 |
| raid | unit,target | 劫掠当前可见敌村 |
| create | city,count；可选clan,source | 新建领主；新局source默认garrison，也可同城领主ID；无待招募库存 |
| recruit | 旧存档兼容接口 | 新局已取消并拒绝该命令；改用transfer从驻军调拨 |
| transfer | unit,target,count；可选wounded | 同城转移人员，wounded默认false；不能转民兵 |
| assemble | unit,units；可选campaign_target | 集结500范围内至少2支无军团、未交战同国领主；units是ID列表 |
| disband | unit | 解散该领主所属军团，粮食按容量分配 |
| set_strength | unit,target | target为1–150整数，设置回城自动整补目标，不凭空增减兵 |
| dispatch | city,destination；可选food | 派城际运粮队，仅相邻己方城；food是原始整数粮食 |
| supply | unit,target | 城市运粮队给1000范围内己方领主/军团补粮 |
| discard | unit,food | 城市运粮队丢弃指定货粮 |

例如`{"type":"create","city":"c00","count":30,"source":"garrison"}`。被围城市不能创建、征募、派运粮或转移人员。战斗中单位不能接受普通行动。核心仍会检查归属、兵源、容量、距离、可见性、地形等，不必由智能体保证成功。列表中前一条成功不会因后一条失败而回滚。

兼容现有控制器的move可选元数据：`relief_action:"wait"`与`relief_city:城市ID`请求围城周边避让路径；这不强迫出击。策略可以不用。campaign_target也是军团目标元数据。

## Python训练接口

```python
from aiwar.sdk import Environment
env = Environment(seed=7, config={'days': 7})
observations = env.observations()  # [0方观察, 1方观察]
while True:
    actions = [[], []]  # 用各自观察分别调用你的智能体
    transition = env.step(actions)
    observations = transition['observations']
    if transition['terminated']:
        break
env.export('artifacts/python-episode')
observations = env.reset(seed=8)
```

step返回新observations、两方outcomes、rewards、terminated、result。终局胜+1/负-1/平0，非终局0；没有额外塑造策略偏好的奖励。last_transition保留上一步观察/动作/结果，训练器可自行采集。结束后再次step会报错。非法双边列表包在改变世界前拒绝；包内单条错误仅拒绝该条。自定义config改变实验规则，必须报告并对双方一致应用。它不是Gymnasium/PettingZoo兼容类，可在此之上自行包装。此对象包含world，属于可信宿主；不要把它直接传给参赛策略。

## 对局数据与重放

JSONL宿主每局生成：

- `nation-0.jsonl` / `nation-1.jsonl`：该方每轮request（含观察及上轮回执）、commands、agent_error、outcomes，最后一行terminal观察和reward。适合行为克隆/离线分析；没有跨方隐藏观察混入单方记录。
- `agent-0.stderr.log` / `agent-1.stderr.log`：智能体调试输出。
- `match.json`：协议版本、启动argv、超时预算、错误次数、结算顺序、完成标记、宿主Python源文件hash。需由实验管理者另记录模型/策略代码版本，不能只凭文件名判断。
- `result.json`：完整规则配置及其hash、种子、胜负、最终人口兵力、累计统计、占城历史、物理状态摘要。
- `final.save.json`：全知最终状态、随机状态和完整有效格式命令日志，供事后分析及确定性回放；不能作为对局中策略输入。核心保留的events可能是有限历史，逐轮记录不承诺完整事件流。

`python -m aiwar.replay 路径/final.save.json`无需智能体即可验证物理状态。SDK包格式校验拒绝的命令不会进入核心命令日志，但已记录在各方JSONL；不影响回放。异常中止会保留已flush的JSONL，缺少completed manifest表示不能算完整对局。不要用全知事后字段当作当时可见特征。

Python Environment.export仅保存终态/结果；需要逐步训练数据时自行采集last_transition，或使用JSONL宿主。SDK目前不负责模型更新、排名服务、远程账号或GPU调度。无界面运行不依赖Godot，也不会因界面断线暂停。
