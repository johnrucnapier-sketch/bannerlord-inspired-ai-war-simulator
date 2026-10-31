# 衡岳 V1：冻结基线 v0.2.0 的策略对抗记录

**正式结果：45胜、0平、3负；45场胜局全部通过统一地图获胜。** 本报告记录全部预登记正式对局，包含负结果、失败与异常。48个预登记任务已全部完成且记录一致。

实验为4个对手、6个共享且预先抽取、未用于开发对局的种子，每种子交换蓝红阵营，共48局。**独立随机世界只有6个，不是48个。** 每个对手的12局由6个配对种子组成。每局上限1680天，决策时限2秒，使用原官方JSONL宿主；原始决策日志仅作无损gzip流式压缩。

种子数值曾在检查预登记文件时被开发者看到；没有用于开发模拟、策略输入或按这些种子的对局表现选择候选。因此本次不是对开发者盲的实验。候选锁定记录另行披露此事，原预登记文件与哈希保持不变。

| 对手 | 有效完成/预登记 | 胜/平/负 | 配对点数率与95%区间 | 单局分数均值 ± 配对SE | 统一胜/被统一/时限结束 |
|---|---:|---|---|---:|---|
| gptdot-a-r3 | 12/12 | 11/0/1 | 91.7% [75.0%, 100.0%] | 1233.6 ± 106.8 | 11/1/0 |
| grok-v25 | 12/12 | 11/0/1 | 91.7% [75.0%, 100.0%] | 1258.1 ± 110.8 | 11/1/0 |
| grok-v23 | 12/12 | 11/0/1 | 91.7% [75.0%, 100.0%] | 1268.7 ± 110.6 | 11/1/0 |
| march | 12/12 | 12/0/0 | 100.0% [100.0%, 100.0%] | 1393.7 ± 5.2 | 12/0/0 |

点数率为胜1、平0.5、负0；区间对6个种子的红蓝均值进行20,000次配对bootstrap，取2.5%与97.5%分位。它不是单纯胜率。随机重采样仅用于不确定性展示，没有新增地图或对局。6个独立种子很少，区间可能不稳定或退化，不能据此宣称普遍优越或冠军。分数SE按6个种子配对均值计算；分数沿用既有1680天公式。

**若6个种子均双边全胜，bootstrap会退化为[100%, 100%]。这只表示这个小样本未观察到失败，绝不表示未知地图上胜率确定为100%；该退化区间未覆盖尚未观察到的地图风险。**

| 对手 | 候选蓝方 胜/平/负 | 候选红方 胜/平/负 | 完整种子对数 |
|---|---|---|---:|
| gptdot-a-r3 | 5/0/1 | 6/0/0 | 6 |
| grok-v25 | 5/0/1 | 6/0/0 | 6 |
| grok-v23 | 6/0/0 | 5/0/1 | 6 |
| march | 6/0/0 | 6/0/0 | 6 |

## 错误与命令回执

| 对手 | 候选阵营 | 策略 | 宿主超时 | 其他协议/启动错误 | 内部traceback标记 | 内部exception标记 | 命令拒绝 |
|---|---|---|---:|---:|---:|---:|---:|
| gptdot-a-r3 | 蓝 | 衡岳 V1 | 0 | 0 | 0 | 0 | 0 |
| gptdot-a-r3 | 蓝 | gptdot-a-r3 | 0 | 0 | 0 | 0 | 0 |
| gptdot-a-r3 | 红 | 衡岳 V1 | 0 | 0 | 0 | 0 | 0 |
| gptdot-a-r3 | 红 | gptdot-a-r3 | 0 | 0 | 0 | 0 | 0 |
| grok-v25 | 蓝 | 衡岳 V1 | 0 | 0 | 0 | 0 | 0 |
| grok-v25 | 蓝 | grok-v25 | 0 | 0 | 0 | 0 | 10 |
| grok-v25 | 红 | 衡岳 V1 | 0 | 0 | 0 | 0 | 0 |
| grok-v25 | 红 | grok-v25 | 0 | 0 | 0 | 0 | 1 |
| grok-v23 | 蓝 | 衡岳 V1 | 0 | 0 | 0 | 0 | 0 |
| grok-v23 | 蓝 | grok-v23 | 0 | 0 | 0 | 0 | 0 |
| grok-v23 | 红 | 衡岳 V1 | 0 | 0 | 0 | 0 | 0 |
| grok-v23 | 红 | grok-v23 | 0 | 0 | 0 | 0 | 0 |
| march | 蓝 | 衡岳 V1 | 0 | 0 | 0 | 0 | 0 |
| march | 蓝 | march | 0 | 0 | 0 | 0 | 0 |
| march | 红 | 衡岳 V1 | 0 | 0 | 0 | 0 | 0 |
| march | 红 | march | 0 | 0 | 0 | 0 | 0 |

内部异常按原stderr的已知标记分别计数；两类标记没有被假定为互斥的唯一事件。协议故障、超时、内部捕获异常和引擎命令拒绝分别报告，故障局不删除。逐局结果保留蓝红归属及双方错误计数。

## 完整性与来源

- 预登记任务：48；唯一匹配任务：48；缺失：0；重复：0；计划外记录：0。
- 每局核对候选、对手、冻结清单及游戏源码哈希，并检查种子、阵营与1680天配置。候选冻结记录与预登记哈希关联；存在不一致时结果保留但标为审计无效。
- 批次附带赛前完整verify_release校验日志的摘要和哈希，并核对批次结束源码未变化的记录；这不等于重放全部48局或真实用户验收。
- experiment.json保存脱敏预登记、候选/对手/冻结清单/核心文件哈希及输入结果文件哈希；results.json与results.csv逐项覆盖计划，失败、缺失和重复不会由较好的重跑结果替换。

## 开发集（不计入正式成绩）

| 候选源码哈希前12位 | 对手 | 记录局数 | 完成 胜/平/负 | 游戏天数 |
|---|---|---:|---|---|
| 236e8a28d1cf | gptdot-a-r3 | 2 | 0/0/2 | 1680 |
| 570b969ae01f | gptdot-a-r3 | 2 | 0/0/2 | 1680 |
| 570b969ae01f | grok-v25 | 2 | 1/0/1 | 1680 |
| 5c250d6aa543 | gptdot-a-r3 | 2 | 1/0/1 | 1680 |
| 5c250d6aa543 | grok-v23 | 2 | 2/0/0 | 1680 |
| 5c250d6aa543 | grok-v25 | 2 | 2/0/0 | 1680 |
| 5c250d6aa543 | march | 2 | 2/0/0 | 1680 |
| 6d0bd4778c74 | gptdot-a-r3 | 4 | 4/0/0 | 1680 |
| 6d0bd4778c74 | grok-v25 | 4 | 4/0/0 | 1680 |
| fc6c8bacb01b | gptdot-a-r3 | 4 | 4/0/0 | 1680 |
| fc6c8bacb01b | grok-v25 | 4 | 4/0/0 | 1680 |

这些种子曾用于开发和候选选择，可能复用地图；不能与正式留出集相加，也不构成独立泛化证据。

## 设计与局限

衡岳采用独立编写的观察策略，以“可持续投入战场的健康兵力”组织任务：小型经济警戒、同步独立纵队、按预计抵达时机解围、有利野战截击、同时核算城防与外援的攻城、攻城不合算时压制村庄生产，以及有粮目的地与普通整补预算。借鉴了同步独立队机动与生产竞争的思想，但不导入、继承或读取对手实现，不按对手身份或种子选择打法。无机器学习训练或模型API调用。源码与详细边界见[策略说明](../../../strategies/submissions/hengyue/README.md)。

内部C01–C06共30场完整开发局，包含初版对A-R3的0胜2负；C04只有机制回归，未另跑完整局。C06修正经真实引擎微实验发现的“把较晚到达时间误作敌军持续受损时间”问题，作为衡岳-V1冻结。正式开始后未修改策略。这里的收益解释仍属于代码支持的设计意图，没有逐模块消融证明。

三场败局揭示不同的未解决边界：

- [对A-R3：固定集结点错过救援窗口](FAILURE_ANALYSIS.md)。420名主力有粮、未受损，却未到达等待点650范围，未进入最后出击判断；不能据此断言换位置必胜。
- [对v25：攻城消耗后被赶到的援军击溃](FAILURE_V25.md)。进攻时当前视野没有敌方领主，随后城防与援军改变了兵力关系；不是部队饿死。
- [对v23：野战追击转成攻城](FAILURE_V23.md)。攻击目标退回城市后形成城防战，绕过了主动siege预算，五支主力战败移除。

其他局限包括驻军超过400时的强制扩编可能突破普通补给预算、视野外增援不确定性、单个战役群对多线威胁的响应，以及经济投入尚未消融。上述固定样本实验仅描述这些对手、源码版本与6个世界种子；无样本追加、无成绩筛选，不宣称冠军。
正式留出结果一旦被检查，后续策略改动应使用新版本、新预登记和新种子；当前记录继续保留。


## 验证补充

8项针对性回归通过；807项冻结文件清单核验通过。开发快评、流式gzip正式宿主与直接官方JSONL宿主的短局物理摘要一致，gzip解压后原始记录逐字节一致；故障注入可记录超时与内部异常。另对一场Mac败局和一场RIG胜局在Mac重放，物理状态一致。RIG取回的504个正式/开发记录文件逐字节SHA256核验通过。没有声称重放全部48局。

源码与轻量结果保存在本目录及策略目录；完整原始记录以数据Release附件公开。

## 策略动作核查

完整扫描48局本方决策日志，确认截击、劫掠、围城与城外解围都实际触发过：记录到对村车的attack命令30957条、对敌领主7807条、对运粮队19条；siege命令2916条、raid命令4316条。己方观察中出现29场保卫本国城市的独立城外解围战，以及5场本方围城军遭对方解围的外战。**命令次数不是击杀、完成劫掠或占城次数；可见战斗计数也只是采样下界。**

本方命令拒绝为0，但补给仍有未解决现象：出现96次“领主队随身粮为0”的队伍观测、100次带hungry标记的领主队观测。它们可能重复记录同一队同一事件，且个人粮为0不等同城内无法共享供粮；不能把它们直接当成饥荒次数或死亡人数。原始证据留在研究档案，汇总见action-analysis-summary.json。


## 直接给其他智能体使用：无需重新对局

先读results.json/results.csv、三份FAILURE分析和[轻量逐局目录](games/)，需要完整上下文再下载[无损数据Release](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/hengyue-v1-validation-20261031)。本批只测A-R3、Grok v25/v23和march；发布时主分支已有A-R5，本数据不代表对A-R5的测试。

| 无损包 | 局数 | 压缩MiB | 解包GiB | 用途 |
|---|---:|---:|---:|---|
| [hengyue-v1-gptdot-a-r3-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/download/hengyue-v1-validation-20261031/hengyue-v1-gptdot-a-r3-20261031.tar.zst) | 12 | 22.01 | 2.59 | formal |
| [hengyue-v1-grok-v25-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/download/hengyue-v1-validation-20261031/hengyue-v1-grok-v25-20261031.tar.zst) | 12 | 19.93 | 2.28 | formal |
| [hengyue-v1-grok-v23-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/download/hengyue-v1-validation-20261031/hengyue-v1-grok-v23-20261031.tar.zst) | 12 | 18.40 | 2.04 | formal |
| [hengyue-v1-march-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/download/hengyue-v1-validation-20261031/hengyue-v1-march-20261031.tar.zst) | 12 | 16.73 | 1.80 | formal |
| [hengyue-v1-development-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/download/hengyue-v1-validation-20261031/hengyue-v1-development-20261031.tar.zst) | 30 | 2.07 | 0.03 | development |
| [hengyue-v1-three-losses-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/download/hengyue-v1-validation-20261031/hengyue-v1-three-losses-20261031.tar.zst) | 3 | 4.66 | 0.50 | failure_subset |

三场败局包是48场正式集的子集，不能额外计为3局。开发30局另包、不计正式成绩。正式日志保留双方每轮观察、命令、回执、stderr、终局结果和本独立模拟器生成的终局快照；不包含第三方游戏存档或资产。开发快评原本只保存时间线、回执异常、结果和终态，没有逐轮双边观察；发布保留实际已有资料，不补造日志。

```sh
python benchmarks/community/hengyue-v1-validation-20261031/inspect_results.py --losses
python benchmarks/community/hengyue-v1-validation-20261031/download_data.py --package three-losses --output ./hengyue-download
python benchmarks/community/hengyue-v1-validation-20261031/extract_data.py --archive ./hengyue-download/hengyue-v1-three-losses-20261031.tar.zst --output ./hengyue-losses
```

`--package`还支持gptdot-a-r3、grok-v25、grok-v23、march、development、all。直接链接下载完整包；下载脚本使用16 MiB分片，复用已验证分片，验证拼接后的完整SHA256，不自动执行策略或模拟。解压需要系统zstd或Python zstandard。全量数据展开约9 GiB，空间有限时先取败局包或单一对手。

原nation JSONL从gzip解出后字节不变，再用Zstandard归档；`file-manifest.json`同时记录本地原文件哈希、归档内文件哈希、字节数与转换类型。只有含私人路径的协议元数据/文本被规范化；观察、命令、回执和模拟器终态不改写。原summary中的raw_log_sha256指发布前文件；公开包校验以file-manifest.json为准。既有复盘行号继续对应解压后的nation-N.jsonl。全知终态仅用于离线复盘，不能作为策略运行输入。

每个批次附当时agent.source.py/opponent.source.py，可直接读取冻结对手与候选；当前策略目录另附C01–C06开发快照。run_dev.py/run_formal.py是复现实验宿主，显式运行才会启动新对局；阅读已有结果不需要运行它们。
