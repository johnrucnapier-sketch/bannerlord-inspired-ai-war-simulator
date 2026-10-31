# 策略：允许迭代的部分

`reference/v0.2.0/`是已有策略源文件快照，不原地改写。内置默认`march`及P3/P5位于冻结游戏包中，作为固定参考。新增策略放入`submissions/<name>/`，不要改`game/`。

| 参考 | 思路 | 已知边界 |
|---|---|---|
| march | 最初的默认进军、补给和护农 | 继续是默认对手，不因实验结果被替换 |
| P3 / P5 | 环线巡逻；P5让附近可行动部队协调认领盗匪 | 内置演示编制与研究用27/57人编制不是同一配置 |
| E1 定时护送 | 根据运输周期提前接送，优先完成往返 | 历史三队测试运输率很高，但野外匪群存量也很高 |
| H3 分区清剿 | 在负责区域扫荡、持续搜索，协调保护队 | 历史专职清剿效率领先，不等于后方经营/战争最优 |
| D2 | 三队护送发育，三队57后转P5；独立进攻/防御任务 | 当前冻结规则24局为5胜18负1平（固定蓝方），有明显改进空间 |

27、54、57人的意义和损耗必须结合健康兵、食物、伤兵、护送阶段及具体规则理解。研究中“每城三队”的单国实验曾将家族名额改为6；不是冻结单国默认的3队上限。不要把这些数字脱离配置硬套。

## 接入自己的智能体

复制 `strategies/agent_template.py`，实现`decide(observation, previous_outcomes)`。每6游戏小时读取一行JSON，回复同request_id和commands数组；stdout只写协议，调试写stderr。可保留本局记忆；崩溃后进程可能重启。

```sh
python tools/play.py --blue d2 --red march --seed 1 --output runs/reference-1
python tools/play.py --blue-command '["python","strategies/agent_template.py"]' --red march --days 7 --seed 1 --output runs/my-smoke
```

也可在Python里使用 `aiwar.match.run_match` 接入任何可执行程序。规则与接口见 `game/AGENT_API.md`。只能使用输入观察，不访问全知存档、核心World、对手文件、未来随机状态或Godot观察端口。

提交时附源码、依赖、启动命令、训练方法、训练/验证/测试种子、模型与算力预算、完整输赢平和错误数。大模型需要API时只提供环境变量名称，绝不上传密钥。共享失败和负结果同样有价值。


### 衡岳-V1：48局对抗与完整日志（2026-10-31）

[策略、45胜3负报告及无损数据下载](../benchmarks/community/hengyue-v1-validation-20261031/README.md)：对A-R3、Grok v25/v23各11胜1负，对march12胜；6个共享新种子交换阵营。另保留30场开发记录和3场败局复盘。小样本，不代表对A-R5或未来策略的结论；默认march不变。
