# GPT dot A-R3：独立纵队（Initiative Columns）

**实验版，尚未完成独立验证。** 这是 2026-10-30 通宵研究中原样锁定的 A-R3，不是后来的 A-R4 修复版，不替换 v6、默认 march 或其他已发布版本。

- 作者：GPT dot；许可：MIT；冻结世界：v0.2.0。
- Python 3.12+，历史测试为 CPython 3.12.14；仅标准库，无 GPU、模型权重、外部 API、网络或额外依赖。
- 源码 SHA256：`818d5834ec12545cd632163a0dd5986ababf79fc893cbdb896d3cfe7c0f6e65e`。
- 现有八局开发测试：对固定 Grok v24 **6 胜 2 负**；其中一场胜局发生自身超时，预设保守计分为 **5 胜 3 负**。未通过进入新种子验证的门槛，不能据此宣布稳定更强。
- 按项目所有者安排，本次仅发布源码及已有结果，后续独立验证和大量对局由其他执行者开展；发布时没有追加对局。

## 方法

有限村庄驻点保护生产，把可动用正规军组成纵队，向前沿补给城集中；侦察可见目标后评估攻城，随后返城补给、整补、重新集结。使用己方可见观察和跨决策状态记忆，不读取全知存档、隐藏状态或地图种子。代码按公开规则独立实现，不以 Grok 策略源码为底稿；不声称整个协调过程从未接触对手资料。

## 接入与复现

在仓库根目录执行：

```sh
python tools/verify_release.py
# 智能体启动命令，供任意兼容官方 JSONL 协议的宿主调用：
python -S strategies/submissions/策略更新-GPTdot/independent-a-r3/agent.py
```

下面是历史开发种子的蓝红互换完整对局命令，供外部评测者运行，**本次发布没有执行它们**：

```sh
python tools/play.py --blue-command '["python","-S","strategies/submissions/策略更新-GPTdot/independent-a-r3/agent.py"]' --red-command '["python","-S","strategies/submissions/策略更新-GrokBot小水/v24/agent.py"]' --seed 520119416 --days 1680 --timeout 2 --output runs/a-r3-blue-520119416
python tools/play.py --blue-command '["python","-S","strategies/submissions/策略更新-GrokBot小水/v24/agent.py"]' --red-command '["python","-S","strategies/submissions/策略更新-GPTdot/independent-a-r3/agent.py"]' --seed 520119416 --days 1680 --timeout 2 --output runs/a-r3-red-520119416
```

按本机情况替换 argv 中的 Python 可执行文件。输出目录必须是新目录。历史对手固定在提交 `b0e84dfdfde320a6f972fa2835a4460e486ecb8e`，其 agent.py SHA256 必须为 `a8cd2dabd2d66e98f96e4246bae4f562f2f2a95b1b5b64d0453a73cdfb669c67`；若当前目录文件不同，请在独立检出中取该固定版本，不覆盖别人的源码。历史运行还有进程资源包装和最多两局并发，上述便携命令不重建这些宿主条件，超时表现可能不同。

重新评测应预先登记未用于开发的新种子、交换阵营，保持规则和判胜条件一致，保存所有失败、超时、中断和命令拒绝，不能用新结果覆盖旧记录。JSONL 不是恶意代码沙箱，请自行限制权限、网络及资源。

## 文件

- `agent.py`：未经修改的已测 A-R3。
- `REPORT.md`：完整开发样本与局限。
- `results.json`：八个样本的历史结果、时间与故障标记。
- `MANIFEST.json`：固定世界、策略、对手哈希和测试参数。
- `SHA256SUMS`：本目录内容校验。

原始逐轮记录另行留存；本目录没有发布全知游戏存档或机器专属路径。
