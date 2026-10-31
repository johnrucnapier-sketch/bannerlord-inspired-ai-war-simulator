# A-R5 Adaptive Columns（实验候选）

A-R3 的独立后继版本，不覆盖 A-R3。**尚无 A-R5 对局胜率证据，不宣称更强。**

- 来源：原始 A-R3，SHA256 `818d5834ec12545cd632163a0dd5986ababf79fc893cbdb896d3cfe7c0f6e65e`。
- 本版 `agent.py`：`21f1c90b2ff2dc3844d63ce57ef150aafd729de0dcbe587d82aadbfa10e8ea2c`。
- A-R4 是未发布的失败试验，未作为本版父代码；因此使用独立 A-R5 名称。
- 规则：冻结基线 v0.2.0（内部规则标记 0.1.6），不改世界、引擎、接口或对手。
- 策略只读取官方 observation 和本进程记忆，不读种子、不导入游戏、不读对手源码。

## 运行

```sh
python3 strategies/submissions/策略更新-GPTdot/independent-a-r5/agent.py
```

标准输入/输出使用官方 protocol_version=1 JSONL；每行一次决定，回传原 request_id。运行策略本身仅依赖 Python 标准库。

从仓库根目录执行小规模验证：

```sh
python3 strategies/submissions/策略更新-GPTdot/independent-a-r5/validate.py --repo .
```

验证器导入冻结引擎，运行 26 项确定性机制/行为测试、开局一致性、文件哈希和短协议检查，**不会运行完整对局**。`agent.py` 不依赖这些测试文件。测试使用合成初始状态但不修改规则；`test_independent.py` 是独立审查者的三项回归测试。

## 改动概要

保留 A-R3 独立快纵队、低成本哨兵和快开核心。增加接敌前重新评估、真实可达且有粮的整补选择、共享补粮预算、先保运输人员再动员，以及受阻后的有限生产保护/袭村与改换可负担目标。不是“第一波失败便投降”，也不是固定留守比例。

详见 [DESIGN.md](DESIGN.md)、[TEST_REPORT.md](TEST_REPORT.md)、[EXTERNAL_VALIDATION.md](EXTERNAL_VALIDATION.md)、[REVIEW.md](REVIEW.md)。

主要代价：更严格的完整补粮与集结条件可能降低进攻频率；局部威胁和收益仍是估计；已断粮且运输、行军都不可行时不能凭空救援。真正强弱交由外部成对对局验证。
