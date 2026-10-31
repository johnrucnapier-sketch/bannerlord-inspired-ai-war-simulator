# 第三种训练形式：真实地图双国对抗 · v0.4.1

这是独立版本的确定性训练环境，`mode=realmap`，目前固定西帝国对北帝国。沿用每家族最多3支领主队，加入城堡骑兵训练和民兵粮食接力。规则核心、无界面训练、JSONL智能体接口及Godot观察界面均包含在本目录。

**第一种单国护农、第二种公平1v1继续使用仓库原有 `game/` v0.2.0；第三种使用本目录 v0.4.1。不要把旧模式成绩与第三模式直接混比。** 这里提供训练环境，不包含现成的机器学习训练器或保证获胜的策略。

- [完整规则介绍](RULES.md)
- [智能体接入与新增指令](AGENT_API.md)
- [地图包格式与本地导入](MAP_DATA.md)
- [验证范围与已知限制](VALIDATION.md)

## 安装与真实地图

仓库通过.gitattributes保留文件原始换行，避免Windows自动CRLF转换破坏冻结哈希。

Python 3.12+，建议单独虚拟环境，避免与v0.2.0同名Python包混用。从本目录运行：

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[maps]"
python tools/import_map.py --source /path/to/local-map-export --render
python -m aiwar --mode realmap --days 7 --seed 1 --styles march march --check --output runs/smoke.json
```

地图导入目录须含 `navigation.json`、`settlements.json`、`clans.json`。它是已转换的战略地图包，不是原游戏安装目录；本工具不读取游戏DLL或远程机器。具体字段见MAP_DATA.md。导入器会验证坐标、共享边、两国数量、村庄绑定及可达性，拒绝覆盖不同地图版本。无界面运行可不安装maps额外依赖，并省略`--render`。

本仓库**不分发原游戏场景、导航网格、定居点数据或其渲染图**；使用者自行准备有权使用的本地地图包。没有地图包时，第三模式会明确报缺失，其他模式仍能启动。已有导出包可直接导入，或设置`AIWAR_MAP_DIR`指向该目录（环境变量方式不自动生成观察底图）。

默认完整训练为840游戏日（10年）；不传`--days`即采用默认值。7天仅用于接入检查，不是策略有效性的证明。

## 外部智能体

```python
import sys
from aiwar.match import run_match
run_match(
    [[sys.executable, '-m', 'aiwar.agent_example'],
     [sys.executable, '-m', 'aiwar.agent_example']],
    'runs/protocol-smoke', seed=1, days=1, timeout=2, mode='realmap')
```

示例智能体只返回空指令。正式比赛替换两侧命令数组；每3游戏小时同时取得双方观察，等待双方回复后依次执行。结果保存完整配置、源码哈希、双方观察/命令回执、最终存档；`python -m aiwar.replay runs/protocol-smoke/final.save.json`可验证重放。输出目录须不存在。

## Godot观察界面

安装Godot 4.7.2，运行`python -m aiwar.server`，再启动本目录`godot/project.godot`。顶部选择“真实地图 · 西北帝国 · 10年”，新局默认暂停。先完成带`--render`的地图导入，再启动Godot。界面只作观察，不提供额外训练情报；未经适配的历史策略不出现在第三模式列表。

## 无游戏数据的公开代码检查

```sh
python tools/make_test_map.py --output runs/test-map
# macOS/Linux:
AIWAR_MAP_DIR="$PWD/runs/test-map" python scripts/check_tests_isolated.py
# Windows PowerShell:
# $env:AIWAR_MAP_DIR="$PWD/runs/test-map"; python scripts/check_tests_isolated.py
```

测试地图为本项目原创的矩形网格，只用于接口及规则回归，**不是西北帝国真实地图，也不能作为真实地图策略基准**。真实地图的几何/桥梁验收仍需本地数据。评测必须同时记录规则基线、三份地图数据哈希、配置、种子及阵营。
