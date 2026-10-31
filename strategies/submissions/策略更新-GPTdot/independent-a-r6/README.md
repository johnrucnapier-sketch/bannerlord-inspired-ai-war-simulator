# A-R6 Capacity Columns（实验候选）

A-R5 的独立后继版本，保留旧版。**机制验证不等于胜率证据；发布时尚未完成 A-R6 对 Hengyue v1 的竞争验证，不宣称更强。**

- 父版本 A-R5 SHA256：`21f1c90b2ff2dc3844d63ce57ef150aafd729de0dcbe587d82aadbfa10e8ea2c`。
- 本版源码 SHA256：`27969520a45c16c60e4b68f65017e6b4cae6bc0b7992d092c610375bd97e1f88`。
- 38 项机制测试通过，另有 3 项历史反事实／记忆审查；详见 [REVIEW.md](REVIEW.md)。

## 两个已证实的问题

- **看不见不等于敌军消失。** A-R5 看见敌方 418 名机动兵后，用 400 人攻城；固定的 24 小时／15,000 距离筛选忽略了已知主力能在攻城准备期赶到，最终整队被解围军消灭。A-R6 根据最后目击、最快可能抵达时间和攻城承诺窗口计算预备兵力风险。
- **仓库里的兵不等于能用的兵。** 另一局 18 个名额占满，前线残部不足 300 人，后方却积有 1,682 名驻军。A-R6 将残部送到真实有兵、有粮、路线可行的城市，预约人数和粮食，实际补员后退出轮换。不降低攻城门槛，不凭空生产资源。

保留开局动员、快速纵队、已有解围机制。集结长期不能兑现时进入有时限的恢复窗口，到期重新评估。不读对手源码、种子或隐藏状态，不改冻结规则。

## 运行与验证

```sh
python3 strategies/submissions/策略更新-GPTdot/independent-a-r6/agent.py
python3 strategies/submissions/策略更新-GPTdot/independent-a-r6/validate.py --repo .
```

策略只需 Python 标准库，使用官方 `protocol_version=1` JSONL。验证器运行少量确定性引擎测试，不进行完整对局。见 [DESIGN.md](DESIGN.md)、[TEST_REPORT.md](TEST_REPORT.md)、[VALIDATION_RESULT.json](VALIDATION_RESULT.json)。

## 边界

目击最多保留 336 小时，是有界不确定性参数，不是敌人生死证明，也不是胜率搜索所得。最快直线到达下界会偏保守；幽灵威胁可能降低出击频率，过期可能低估远敌。失效补员路线停止或重选。冷启动无法恢复丢失的历史目击。账本只计现有可观察资源，不保证未来运输或补员。
