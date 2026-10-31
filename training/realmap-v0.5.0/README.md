# 第三种训练形式：西北帝国真实地图 · v0.5.0

**地图已随仓库提供，下载后无需另外导入。第三模式默认双方使用“原版风味基准 v1”（vanilla_v1）。** 这是模拟器的独立策略，不是官方AI代码的复制品。

本包包含真实坐标、陆路通行与桥梁连通、定居点与家族数据、二维底图、Python规则核心、JSONL智能体接口及Godot观察界面。首轮国家为西帝国和北帝国。世界规则沿用v0.4.1（城堡骑兵、50民兵运粮、每3小时决策、默认10年），本次新增地图分发和默认策略，不更改兵种、经济或战斗机制。

| 训练形式 | 推荐入口 | 默认策略 |
|---|---|---|
| 单国护农 | 原game/，mode=rural | 保持原版入口设置 |
| 公平1v1 | 原game/，mode=duel | march |
| 真实地图双国 | 本目录，mode=realmap | vanilla_v1 对 vanilla_v1 |

旧game/v0.2.0和training/realmap-v0.4.1保持冻结，可继续复现旧结果。

## 下载即用

Python 3.12+。从仓库根目录进入本目录，在独立虚拟环境运行，避免与旧版同名Python包混用：

```sh
cd training/realmap-v0.5.0
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
python ../../tools/verify_training_v050.py
python -m aiwar --mode realmap --days 7 --seed 1 --check --output runs/smoke.json
```

默认已是vanilla_v1对vanilla_v1。不传`--days`时运行840天（10年）。明确对照旧策略可加`--styles vanilla_v1 march`，再交换两侧复测。7天只验证接入，不说明策略胜率。

## 保存完整训练记录

```sh
python tools/play.py --days 7 --seed 1 --output runs/baseline-1
python -m aiwar.replay runs/baseline-1/final.save.json
```

play默认真实地图、双方vanilla_v1，通过JSONL独立进程运行。输出每轮观察、指令与回执、最终存档、源码/配置及地图哈希。输出目录须不存在。`--blue march --red vanilla_v1`可换基准；`--blue-command`、`--red-command`接收自定义JSON argv数组。超时默认2现实秒，等待期间游戏不前进。

## Godot观察

安装Godot 4.7.2，运行`python -m aiwar.server`，再启动本目录`godot/project.godot`。顶部选择第三项“真实地图 · 西北帝国 · 10年”，新局暂停，双方自动选原版风味基准。仍可切换march和其他内置对照；重开同模式保留用户选择。底图已经附带，无需Pillow或原游戏运行时。

[规则手册](RULES.md) · [策略原理及适配](STRATEGY.md) · [智能体接口](AGENT_API.md) · [地图说明](MAP_DATA.md) · [验证记录](VALIDATION.md)

地图是从游戏数据派生的二维研究数据，来源及权利范围见[数据声明](aiwar/data/west_north/DATA_NOTICE.md)。本包不包含原游戏DLL、完整场景源文件、美术材质或私人存档。
