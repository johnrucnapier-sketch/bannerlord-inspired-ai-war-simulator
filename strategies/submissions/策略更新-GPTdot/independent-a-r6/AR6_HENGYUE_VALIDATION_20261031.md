# A-R6 对衡岳 V1 小批量验证（2026-10-31）

## 结果

从 A-R6 视角：2 胜、6 负、0 平；运行故障影响 0 局。

本次为两张已知回归地图加两张新开发地图，各红蓝互换，共八局固定开发筛选；不是盲测或大样本排名。没有测试中修改策略、规则、超时或种子，也没有重跑或追加局。完整逐局信息见同目录 `ar6-hengyue-validation-20261031.json`。

## 逐局

| 种子 | 组别 | A-R6 阵营 | 结果 | 终局原因 | 小时 |
|---|---|---|---|---|---|
| 1790262250621921728 | known_regression | blue | win | unification | 11345 |
| 1790262250621921728 | known_regression | red | loss | unification | 9781 |
| 7773340717397762721 | known_regression | blue | loss | unification | 12846 |
| 7773340717397762721 | known_regression | red | loss | unification | 9517 |
| 8631819709967572137 | fresh_development | blue | loss | unification | 7317 |
| 8631819709967572137 | fresh_development | red | loss | unification | 7973 |
| 2587674424826760333 | fresh_development | blue | loss | unification | 10031 |
| 2587674424826760333 | fresh_development | red | win | unification | 8030 |

## 分组及门槛

以下 win/loss/draw 顺序：
- known_regression: 1/3/0; strict wins 1/4.
- fresh_development: 1/3/0; strict wins 1/4.
- blue: 1/3/0; strict wins 1/4.
- red: 1/3/0; strict wins 1/4.

预登记门槛：观测胜局≥6/8、排除运行故障后的严格胜局≥6/8、自方运行故障0局。当前通过：False。通过也不自动追加测试；新鲜确认组须另获批准。

## 固定条件

- 官方 v0.2.0 冻结世界，807 项文件校验，1680 天、每 6 小时决策、官方 JSONL 2 秒预算；CPython 3.12.14，串行 1 局。
- A-R6 发布提交：`527633aeae7c44b8f79c22d99e1bdd4e4bcc4002`。
- 衡岳 V1 固定读取提交：`1ca94ea4c2ae5292434495cc1e0d6a1c775772d3`；路径 `strategies/submissions/hengyue/v1/agent.py`。
- 双方原样源码哈希、配置、逐局物理摘要及原始压缩包哈希见 JSON。
- 种子及顺序在结果出现前登记：两个已知回归种子、两个新抽取的63位开发种子；后者排除已知评测种子。不能把蓝红交换算成独立地图。

## 审计和边界

完整逐轮请求、命令、回执、stderr 和终态均保留。执行者逐行检查 JSONL，并单独检查 A-R6 的 `policy exception:` 捕获异常标记；拒绝命令不等于协议错误。没有更改或覆盖已发布策略。

A-R6 拒绝命令 0 条；衡岳 V1 拒绝命令 0 条。

小样本只回答固定条件下这八个预登记名额的表现，不证明所有地图、对手或后续版本的普遍强弱。
