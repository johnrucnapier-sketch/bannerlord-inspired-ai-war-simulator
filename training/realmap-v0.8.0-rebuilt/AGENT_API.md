> Historical v0.7.0 baseline document retained for unchanged mechanics. It is not validation of this rebuilt release. For current diplomacy behavior and publication status, see README.md, DIPLOMACY.md and REBUILD_PROVENANCE.md.

# v0.7.0 智能体接口

协议仍为 JSONL v1，规则基线为 v0.7.0 多国真实地图。每个国家一个独立进程；每行输入对应一行输出，标准输出只写协议回复，调试信息写标准错误。每次至多 100 条命令，主机默认每次决策回复预算 2 秒、响应最大 1 MiB。等待策略时模拟时间不推进。进程错误后的清理有单独的有界等待，因此回复预算不是整个调用的严格耗时上限。

## 请求与回复

```json
{"protocol_version":1,"type":"decide","request_id":"0:0","observation":{},"previous_outcomes":[]}
```

`observation` 实际包含下文各项；示例空对象仅展示信封格式。回复必须回传本次 `request_id`：

```json
{"protocol_version":1,"request_id":"0:0","commands":[]}
```

`previous_outcomes` 与上轮该国命令顺序一一对应，成功通常为 `{"ok":true}`，失败为 `{"ok":false,"error":"原因"}`，部分成功回执包含新单位、军团或动员 ID。协议错误/超时会记入日志，本轮按空命令处理。主机清理失败进程，并在其残留 I/O 结束后允许后续决策重启；如果子进程仍持有管道，重启会延后，期间继续记录错误并提交空命令，不保证下一轮立即重启。规则拒绝单条命令不会取消整批其他合法命令。

所有国家的请求来自同一决策时刻、命令应用前的快照；主机收到各国回复后，按记录的国家顺序执行，再推进 3 小时。该快照约束不等于所有命令同时原子提交。

## 私有观察

- `nation` 是本场连续整数 ID；`nations` 为字符串 ID 到 `{id, kingdom, name, culture, region_index, ruler_clan, ...}` 的公开注册表。默认顺序见 [MAP_DATA.md](MAP_DATA.md)。不要使用 `1-nation`、`clan//6` 或固定两国数组。
- `cities` / `villages` 含己方完整状态、敌方已知据点/村庄。敌方信息的 `stale=true` 表示历史最后所见，不能当成当前库存或当前驻军。
- `units` 含己方完整单位与当前可见敌军。敌方命令、路径、粮食、远方军团成员不公开；也不披露依赖隐藏军团成员聚合结果的敌方 `movement_speed`。
- `healthy` / `wounded` 是总人数；`cavalry` / `cavalry_wounded` 是其中骑兵子集，不可再次相加。步兵数 = 总数 − 骑兵数。
- `terrain.kind="navmesh"`。可用同一已校验静态包的 `aiwar.navigation.find_route` / `travel_hours` 做地理计算，不可借此查询隐藏动态状态。
- `map_info` 包含国家注册表、家族资料、地图边界和坐标比例；家族转投后应按当前 `nation` 与 `kingdom` 读取国籍。
- `limits.clan_party_cap` 是兼容字段；**真实每族名额用 `limits.clan_party_caps`**，键为家族 ID 字符串，值为 1/2/3。其他常用限制包括 `party_cap`、`garrison_cap`、`field_ration`、`carry_days`。
- `castle_logistics=true`，`logistics_limits` 声明运输人数/货粮、兵员运输上限、军团携粮天数、`rations_separate=true` 等能力。己方领主队有 `food_capacity`、`can_receive_supply`。
- `organization` 声明 `army_scope="clan"`、`coordination="independent_formations"`、`ruler_support_exception`、`support_rules`、本国国王/元帅家族和 `militia_mobilization`。
- `army_metadata` 仅含本国军团的主家族、`commander` 和援助家族。以指挥官元数据为准，不以列表中碰巧先出现的单位推断。
- `mobilizations` 仅含本国动员记录，包括 `id`、`clan`、`issuer`、`rally`、`army`、`status`、实际队列/信使及待处理任务。`rally_until` 在集结点收令前为 `null`。
- 新单位种类为 `levy`、`mobilization_messenger`。民兵未实际入军团前不能计入远方军团战力/粮食。入军团民兵计入实际耗粮，以半个正规步兵的基础战力估算，但不消耗领主队名额。
- `extinct_nations` 为灭亡国家 ID；`clan_migrations` 只向本国披露迁出/迁入记录。转投不共享历史视野。
- `relations` 是本国关系行，当前自己为 `self`，其他国家为 `war`。`diplomacy={"version":1,"enabled":false,"supported_actions":[],"mode":"free_for_all"}`。没有可执行外交命令。

策略不应收到 `World`、全知观察、全局事件/总计、其他国家日志或最终存档。`Environment` 是可信主机 API，不是策略输入对象。

这里的私有观察是**字段级信息隔离**，不是针对对抗性推断的强保密保证。实体 ID 由全局递增分配，可见 ID 的变化可能泄漏其他位置的分配活动；不能声称完全无法推断隐藏世界。独立进程也不会自动限制恶意程序的文件、网络和系统访问，进程清理不等于安全沙箱。执行不可信策略需另设安全隔离。

## 命令

示例 ID 都须替换成当前观察中的真实 ID。坐标和粮食均用整数内部单位，1000 粮食单位 = 1 粮。

### 移动与战斗

```json
{"type":"move","unit":"领主队ID","x":100000,"y":200000}
{"type":"stop","unit":"领主队ID"}
{"type":"attack","unit":"领主队ID","target":"可见敌单位ID"}
{"type":"siege","unit":"领主队ID","target":"可见敌据点ID"}
{"type":"raid","unit":"领主队ID","target":"可见敌村ID"}
```

移动点须可达；攻击/围城/劫掠目标须当前可见、非过期且敌对。围城还须满足己方据点陆路相邻的前沿限制。军团通过其领主队接收共同移动/战斗命令；正在交战的成员不能随意改令。`siege` 可选 `award_clan` 指定本国受封家族。

### 编制与调拨

```json
{"type":"create","city":"友据点ID","clan":0,"count":30,"source":"garrison","troop_type":"infantry"}
{"type":"transfer","unit":"驻军ID","target":"领主队ID","count":10,"troop_type":"cavalry"}
{"type":"set_strength","unit":"领主队ID","target":110}
{"type":"set_composition","unit":"领主队ID","cavalry_target":20}
{"type":"assemble","unit":"指挥官队ID","units":["同族队ID"],"campaign_target":"目标据点ID"}
{"type":"disband","unit":"军团内领主队ID"}
```

- `create` 默认从据点驻军抽人；也可用现场己方领主队 ID 作为 `source` 拆分，原队必须留有人。受实际兵源、容量和当前家族名额限制。
- `transfer` 在未被围的友方据点完成，双方须在场；可选 `wounded:true` 调拨伤员。`troop_type` 可为 `infantry`/`cavalry`，省略则按来源构成分配。
- `set_strength` 是后续整补目标，不免费补兵，也不降低已有近满扩编保留目标。`set_composition` 是健康骑兵目标，自动整补时用实际驻军等人数交换，不改变总容量。
- `assemble` 至少两支有效领主队，均未交战、未入军团，距指定指挥官不超过 500。除 [规则](RULES.md) 的国王/元帅援军例外外须同族，每族最多一个主军团。不能把民兵塞进 `units`；其加入由实体动员流程处理。
- `recruit` 仍在兼容协议中，但本基线取消城内待招募池，因此会被规则拒绝。请使用实际驻军调拨/建队。

### 运输与粮食

```json
{"type":"dispatch","city":"源据点ID","destination":"相邻友据点ID","mission":"deliver","food":500000,"troops":20}
{"type":"dispatch","city":"源据点ID","destination":"相邻友据点ID","mission":"fetch","food":500000}
{"type":"dispatch","city":"源据点ID","destination":"友军团ID","mission":"supply","food":500000}
{"type":"supply","unit":"运输队ID","target":"友军团或领主队ID"}
{"type":"discard","unit":"领主队ID","food":10000}
```

`mission` 默认 `deliver`；`food` 默认本局 `logistics_limits.city_cargo`（本基线 2000000）。运兵仅限 `deliver` 的 `troops:0..20`，可指定兵种；运输队的真实出发口粮另外支付。城际运粮/取粮限 `supply_neighbors` 中未被围的友方据点。取粮不提前预留远端库存，实际抵达时按可用粮和余量取得。

`mission="supply"` 可送到实际友方领主队/军团，`supply` 可改派已有且无正规运兵载荷的运输队。接收受交战阶段和物理距离限制。`discard` 对领主队/军团丢弃已有携粮，对运输队丢弃已有货粮。

### 动员与撤销

```json
{"type":"mobilize","city":"本族安全城堡ID","army":"本族军团ID"}
{"type":"demobilize","clan":0}
{"type":"demobilize","army":"本族军团ID"}
```

`mobilize.army` 可用军团 ID，或该军团成员领主队 ID。指挥官须在发令城堡附近且未交战；每族不能有另一项未完成动员。成功回执含 `mobilization`，`unit` 可能为 `null`：这表示命令已登记、但缺当地资源等条件而暂未派出首封信使，不是免费生成或瞬间送达。

`demobilize` 用 `clan` 或 `army` 定位一个己方未完成记录。命令接受后只是派发实体撤销信使，远处来源/队列收到时才改变任务。完整路线、粮食公式和取消简化见 [RULES.md](RULES.md)。民兵和信使不支持领主队的自由 `move`/`assemble` 指令。

## 运行和记录

八国默认进程命令见 [README](README.md)。自定义比赛可将下例保存为本目录下的 `run_custom.py`，然后运行 `python run_custom.py`。它为所选两国分别启动独立进程，关闭文化特性：

```python
import sys
from aiwar.match import run_match

agent = [sys.executable, "-m", "aiwar.baseline_agent", "--style", "vanilla_v1"]
run_match(
    [agent.copy(), agent.copy()],
    "runs/two-country-1",
    seed=1,
    days=3,
    timeout=2,
    mode="realmap",
    config={
        "nations": ["battania", "vlandia"],
        "culture_traits": False,
        "culture_basis": "owner",
    },
)
```

省略 `nations` 时默认八国，必须提供八个 argv 数组，例如 `[agent.copy() for _ in range(8)]`。每个数组都可以指向不同的本地策略入口；数组顺序与国家 ID 一致。argv 不经 shell 解释，`sys.executable` 保证子进程使用当前虚拟环境。

也可使用 `python -m aiwar.match --help` 所列的 `--agents` JSON 数组、`--nations`、`--config` 参数。不同终端的引号转义可能不同，复杂设置建议使用上述 Python API。`--timeout` 或 `timeout` 设置现实秒决策预算，公平比较时各方必须一致。输出目录必须不存在。

可信主机可直接使用 `Environment(seed, config)` 和 `env.observations()` 做测试；策略只接收本国观察，不能把主机对象作为捷径传入策略。

`Environment.step([commands_0, ..., commands_n])` 返回各国新观察、各国回执、终局奖励与结果。唯一赢家得 +1，其余 −1；未结束或最高领土并列时均为 0，没有策略专用奖励塑形。

`match.json` 保存代理参数、命令执行顺序、源码哈希、错误/超时/无效命令/决策次数与运行状态；`nation-N.jsonl` 保存该国请求、回复和回执；`result.json` 保存配置、哈希、终局与全知统计；`final.save.json` 为重放材料。最终存档和全知结果仅用于离线审计，不可作为在线策略输入。

`rule_version: "0.1.6"` 是兼容标记。比较必须同时保存 `local_baseline`、完整配置、地图四文件哈希、策略源码和主机源码；旧版的两国数量、固定家族分组和粮量默认值不可直接套用。
