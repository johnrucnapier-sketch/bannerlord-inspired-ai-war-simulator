# 基于骑马砍杀二的AI战争策略研究模拟器

**欢迎AI爱好者、策略研究者和游戏玩家，一起挑战同一个固定世界：更好地保护生产、调动兵力，最终统一地图。**

这是受《骑马与砍杀II》宏观战争与后勤关系启发的独立研究模拟器。不是骑砍Mod，不使用原游戏代码、美术或地图，不需要购买或安装原游戏，也不代表其开发商。Python负责确定性规则计算，Godot提供二维观察界面。策略可以是普通程序、搜索算法、强化学习或调用大模型的智能体。

**当前冻结基线：v0.2.0 · 2026-10-29。代码、文档和本项目原创数据采用MIT许可。**

## 三个板块

| 板块 | 内容 | 后续约定 |
|---|---|---|
| [游戏本体 game/](game/) | 世界、战斗、生产、运输、迷雾、SDK、观察界面，以及固定的默认对手 | v0.2.0不原地改规则；必要修正另发基线版本 |
| [基础实验 benchmarks/](benchmarks/) | 兵力阈值、单/双/三队护农、清剿、战争对照的报告、原始结果和历史源码 | 已有实验保留；新增实验用新ID追加，并注明规则与配置 |
| [策略 strategies/](strategies/) | P3/P5及护送、清剿、D2等参考实现；社区策略与训练报告 | 允许持续迭代，但不能修改基线来提高成绩 |

**原默认策略 `march` 继续是默认对手。** D2等实验策略没有替代默认策略，也不是已证明的最优解。

## 五分钟开始

需要Python 3.12或更新版本。无界面比赛不需要GPU、游戏本体或Godot。

```sh
git clone https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator.git
cd bannerlord-inspired-ai-war-simulator
python -m venv .venv
# macOS/Linux：source .venv/bin/activate
# Windows PowerShell：.venv\Scripts\Activate.ps1
python -m pip install -e ./game
python tools/verify_release.py
python tools/play.py --blue march --red march --days 7 --seed 1 --output runs/demo
```

上面7天仅检查接入。完整1v1使用默认1680天（20游戏年）：

```sh
python tools/play.py --blue d2 --red march --seed 1 --output runs/d2-1
```

输出含最终结果、每轮观察和命令、命令回执、最终存档、配置哈希和物理摘要。目录不能已存在，防止覆盖实验。

可选观察界面：安装Godot 4.7.2并导入 `game/godot/project.godot`；另开终端运行 `python -m aiwar.server`，再启动Godot工程。界面是全知观察者，不是策略输入接口。也可把自行下载的Godot放到 `game/.tools/` 后运行 `python game/scripts/launch.py`。仓库不分发Godot或Python运行时。

## 冻结世界的关键规则

- 双国各6城、6家族，每城3村；每家族最多3队，每队最多150人，驻军上限500。
- 一年84天、一周7天；每小时推进，每6小时决策。默认20年，到期按城市数判胜，或提前统一；人口不作平局破局条件。
- 村庄每天人口+1；每周按村内人口产生粮食及 `floor(人口/100)` 兵员，兵员产生不扣人口。
- **兵员必须实际运到城里，送达即变成健康驻军，没有城内待招募库存。** 回城部队从驻军抽调；满驻军时超额兵员随原运输队回村。
- 健康驻军超过400时，回城机动队逐步吸收超出部分、扩至150并保留提高后的目标；之后驻军继续积累至500。
- 健康兵输出战力，伤兵占编制。粮食、距离、围城、迷雾和实际集结决定军队能做什么。

完整说明：[规则](game/RULES.md) · [智能体接口](game/AGENT_API.md) · [冻结约定](freeze/POLICY.md)。内部存档/协议仍使用兼容标记 `0.1.6`；**公开评测必须记录v0.2.0及冻结清单哈希，不能只记录该旧标记。**

## 先看数据，再下结论

[基础实验索引](benchmarks/README.md)区分**当前冻结规则**与**历史规则**。例如，孤立的20人盗匪战中，54健康兵是零死亡阈值，并不是零受伤阈值；单队、双队和三队护农的经济结论也不能直接等同于战争胜率。

当前规则已公开的一组24种子固定蓝方D2对默认红方：蓝5胜、红18胜、平1。首次易手前蓝方平均人口与正规军更多，仍没有取得更高胜率。这是一个值得继续研究的问题，不是排行榜冠军。样本未交换阵营，种子已经公开，应视为开发参考集。

## 参加挑战

1. 读规则和数据版本说明，以JSONL协议接入自己的策略：[策略指南](strategies/README.md)。
2. 固定源码、基线、种子、时限和算力预算，至少交换蓝红阵营，保存完整结果；报告失败和无效命令，不只贴赢的局。
3. 提交PR，把策略放入 `strategies/submissions/<你的策略名>/`，附训练/测试报告；或用Issue分享方案和数据。
4. 新发现的基础实验可追加到 `benchmarks/community/<实验ID>/`。不要覆盖旧结果或修改冻结游戏来改善成绩。

详见 [贡献指南](CONTRIBUTING.md)。目前没有宣称官方排名，也没有自动执行陌生策略的服务。外部智能体进程不是安全沙箱，评测不可信代码时请自行隔离文件、网络和资源。

[English overview](README.en.md) · [MIT License](LICENSE)


### 衡岳-V1：48局对抗与完整日志（2026-10-31）

[策略、45胜3负报告及无损数据下载](benchmarks/community/hengyue-v1-validation-20261031/README.md)：对A-R3、Grok v25/v23各11胜1负，对march12胜；6个共享新种子交换阵营。另保留30场开发记录和3场败局复盘。小样本，不代表对A-R5或未来策略的结论；默认march不变。
