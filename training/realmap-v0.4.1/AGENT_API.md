# 第三模式智能体接口

沿用协议v1与[原有JSONL接口](../../game/AGENT_API.md)，以本文件和[RULES.md](RULES.md)中的第三模式差异为准：每3小时决策、默认10年、导航网格地形、真实地图范围、18家族及新增兵种/物流。不要直接把旧接口的6小时、40×60网格或12城写死到策略中。

SDK：`Environment(seed, {"mode":"realmap"})`，`step([blue_commands, red_commands])`。外部进程用`run_match(..., mode="realmap")`。每次最多100条指令，默认2现实秒超时；回复必须携带原request_id和protocol_version=1。等待推理期间模拟不推进。

## 新观察

- `terrain`为`kind=navmesh`描述字典；静态地图可通过同一已校验本地包及`aiwar.navigation.find_route/travel_hours`查询。
- `castle_logistics=true`和`logistics_limits`标记本规则能力。
- 据点`settlement_type`为town/castle；`supply_neighbors`给正常运粮允许的目的地ID。
- 单位`healthy/wounded`仍是总人数；`cavalry/cavalry_wounded`是其中骑兵子集，不能再次加到总人数。步兵数量=healthy-cavalry，步兵伤员=wounded-cavalry_wounded。
- `movement_speed`为内部坐标每小时的实际当前速度。己方运输队`militia_convoy=true`、`mission`、`phase`、`home`、`destination`、`cargo_food`描述任务状态。
- 国别通过nation和公开归属识别；不要用clan//6推断国家。城堡训练进度仅在己方完整状态里读取，不读取隐藏对手状态。

## 指令示例

ID须替换成观察内真实ID。粮食使用千分之一粮的整数，500000表示500粮。

```json
{"type":"dispatch","city":"源据点ID","destination":"邻近据点ID","mission":"deliver","food":500000}
{"type":"dispatch","city":"本据点ID","destination":"供粮据点ID","mission":"fetch","food":500000}
{"type":"transfer","unit":"驻军ID","target":"领主队ID","count":10,"troop_type":"cavalry"}
{"type":"create","city":"据点ID","count":10,"troop_type":"infantry"}
{"type":"set_composition","unit":"领主队ID","cavalry_target":20}
```

mission省略为deliver；food省略为1850000。取粮在抵达时按实际库存、剩余携带容量和请求量决定，不预留远端粮食。只允许从自己的据点出发。`troop_type`可为infantry/cavalry；省略按来源构成分配。不可用兵种或数量不足会返回失败，不免费转化。

`set_composition`存储健康骑兵目标0..150，在正常自动整补时用实际驻军作等人数兵种交换；目标0意味着尽可能换回步兵。若关闭auto_city_service，应使用显式transfer调拨。驻军不足时可能只能部分满足。兵种目标不提高队伍编制上限，也不覆盖独立的set_strength规则。

基础移动、攻击、围城、劫掠、集结、解散、兵力调拨、supply/discard等仍沿用原接口。新增规则和完整地图哈希随环境导出的配置保存；正式评测使用JSONL赛程的完整记录，不只保存界面截图。
