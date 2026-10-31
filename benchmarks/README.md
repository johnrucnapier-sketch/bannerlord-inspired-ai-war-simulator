# 基础实验：版本、原始数据与可复现口径

这些资料用于理解世界行为和设计策略。**当前冻结基线是v0.2.0；多数护农曲线在更早的“城市待招募库存”机制下测得，不能当作新规则的重新验证结果。**

- `data/`：每项实验的分析表、清单、完成局原始记录、可获得的冻结源码。
- `reports/`：当时的中文报告；公开整理只添加版本提示、去除机器路径，不重算结果。
- `catalog.json`：实验ID、记录数量、配置及兼容性索引。
- `provenance.json`：原文件与公开文件SHA256。JSONL压缩记录另带原始记录所在文件和SHA256。
- `community/`：未来新增实验放入新的ID目录，使用`EXPERIMENT_TEMPLATE.md`。

## 优先阅读

| 主题 | 数据目录 | 怎样解释 |
|---|---|---|
| 1—150健康兵对20盗匪 | [patrol-strength](data/patrol-strength-20261029/) | 孤立交战150个点；54是零死亡，不是零受伤；无增援、治疗、饥饿 |
| 单队兵力与连续巡逻 | [patrol-endurance](data/patrol-endurance-20261029/) | 305条完成记录；先看具体编制、食物及回城条件 |
| 单队P3/P5，20—60人 | [transport-strength](data/transport-strength-20261029/) | 246局；成功必须送达并返回，途中受袭不自动判失败 |
| 双队P3/P5，20—60人 | [transport-dual](data/transport-dual-20261029/) | 246局；不能把额外队伍的收益只解释为单队人数收益 |
| 三队：巡逻/定时护送/驻点/混合 | [transport-triple](data/transport-triple-20261029/) | 70局；27/27/26起步到30，单国每家族6队是实验设定 |
| 27或57后开始空闲巡剿 | [transport-clearance](data/transport-clearance-20261029/) | 100条比较记录含复用旧结果，不能算100条全新独立样本 |
| 两队P5＋专职清剿 | [transport-hunter](data/transport-hunter-20261029/) | 70局；H3专职效率较高，不表示战争最优 |
| 后方投入1/2队组合 | [rear-allocation](data/rear-allocation-20261029/) | 80局；包含驻军耗粮计数问题的说明与标准重估 |
| 三队护送 vs 三队P5，逐队57 | [triple-growth](data/triple-growth-20261029/) | 40局；旧规则中护送运输率高、P5盗匪存量低 |
| 早期战斗策略与默认胜率 | [war-strategies](data/war-strategies-20261028/)、[default-40](data/winrate40-20261028/)、[default追加60](data/winrate100-20261028/)、[P5对默认100](data/p5-duel100-20261028/) | 默认100=原40＋新增60，不能把两个目录当作140独立局 |
| D1及D2军事调度 | [D1](data/escort-p5-defense-20261029/)、[D2](data/escort-p5-defense-v2-20261029/) | 包含同种子复测；旧规则D2的9/24蓝胜不是当前基线成绩 |
| **当前v0.2.0：兵员直接入驻军** | [direct-garrison](data/direct-garrison-20261029/) | **同24种子，蓝D2对默认红：5胜18负1平；固定阵营、公开开发集** |
| 早期P5迭代与并发性能 | [P3迭代](data/p3-improvement/)、[P5迭代](data/p5-improvement/)、[补充比较](data/early-comparisons/) | 历史来源；硬件吞吐不等于策略强度 |

## 共同口径

- “运输成功”是送达并返回；被抢过但最终完成仍计成功。结束时在途另列，不放进已完成成功率分母。
- “死亡”“伤病事件”“战败移除”“饿死”不同；多次受伤人次不等于死亡人数。
- 部队人数应注明健康兵或含伤兵。54健康兵击溃20盗匪后仍会留下2名伤兵。
- 各局10年/20年、3/4/6家族名额、驻军保留数和巡逻目标不同。**来源配置是判断比较是否公平的依据。**
- 首次易手快照在事件前1小时，此前仍可能有野战、劫掠与耗粮；不是纯生产因果隔离。
- 旧数据有重复对照和复用结果；总记录数不等于独立地图或独立试验数。

## 读取原始记录

```python
import gzip, json
with gzip.open('benchmarks/data/direct-garrison-20261029/runs.jsonl.gz', 'rt', encoding='utf-8') as f:
    runs = [json.loads(line) for line in f]
print(runs[0]['record']['result'])
```

`record`是原始游戏/实验记录，`source_file`及`source_sha256`记录来源。公开包移除了实际主机名、连接/本机路径、日志和失败现场存档；保留完整完成局结果、种子、配置、错误计数、物理摘要及原有时间线。具体字段因历史实验不同而不同。

历史源码保持当时布局。某些早期快照没有包含完整配置文件，索引会显示没有`source_configs`，应结合原报告和结果内规则信息，不应宣称可以不经整理直接重放。原清单的工作机分配字段已去除；运行历史脚本时需生成本机工作分配，保留种子/参数/规则，不改写公开原件。机器专属的安装、远程管理脚本与逐轮完整存档不在公开包中。

追加实验时标明哪些结论在当前基线下验证过。历史18/27/54/57经验可以提出假设，但不是不受条件限制的策略保证。


### 衡岳-V1：48局对抗与完整日志（2026-10-31）

[策略、45胜3负报告及无损数据下载](community/hengyue-v1-validation-20261031/README.md)：对A-R3、Grok v25/v23各11胜1负，对march12胜；6个共享新种子交换阵营。另保留30场开发记录和3场败局复盘。小样本，不代表对A-R5或未来策略的结论；默认march不变。
