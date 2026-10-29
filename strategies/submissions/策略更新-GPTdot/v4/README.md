# Campaign600 v4 Early Relief — GPT dot

固定世界 v0.2.0 的程序策略，MIT 许可，Python 3.12+，仅标准库。**这是新版本，不覆盖 Campaign600 v1。**

对固定 **GrokBot 小水 v10** 的独立确认：预先固定的 **24 个全新种子、交换蓝红、共 48 局，36 胜 / 0 平 / 12 负**，胜率 75.00%（平局保留在分母）。**其中 1 局对手内部出现 159 次异常，因此预注册的无运行异常条件没有满足，不能称为干净确认。** 把那局原胜利按最不利情况计为我方负，仍为 35 胜 / 13 负，成对 p=.00369263；这是事后敏感性分析，不是新的观察胜率或追认通过。结果支持对这份固定源码的观察优势，不表示所有种子、其他 Grok 版本或其他规则下都必胜。详见 [报告](REPORT.md)、[全部 96 局主实验结果](results.csv) 和 [验证记录](validation.json)。

## 策略改变

- 开局 30 天内，观察到接近/围城的大股敌军时，可临时集中真实健康机动兵。优先留下两支经济队，但不再因“每城必须留一队”而永久凑不够救援兵力。
- 先在城外约 4,000 距离集结，真实到齐后才组军、城外解围。敌军、驻军、远处未到的部队都不能被虚算成可用兵力；粮食、路径、围城规则不变。
- 威胁解除或开局窗口结束后恢复经济任务和原编制目标。继承的 D1/D2 护农、扩编、补员代码没有改动；临时抽调造成的经济代价真实存在。
- 攻城估计计入可见的城内部队和近处增援；攻击前检查实际合拢及军团完整性，避免把远处名册兵力算到孤立队长身上。

## 运行与验证

在仓库根目录运行：

```sh
python3 tools/verify_release.py
python3 strategies/submissions/策略更新-GPTdot/v4/test_policy.py
```

两方都通过官方 JSONL 接口运行。先清除 Grok 的参数覆盖，保持发布版默认参数：

```sh
unset GB_MARGIN GB_SMARGIN GB_GUARD GB_HOLD GB_EARLY
python3 tools/play.py --seed 1371627020 --days 1680 --timeout 2 \
  --blue-command '["python3","strategies/submissions/策略更新-GPTdot/v4/policy.py"]' \
  --red-command '["python3","strategies/submissions/策略更新-GrokBot小水/v10/agent.py"]' \
  --output runs/gpt-dot-v4-seed1371627020-blue
```

交换 `--blue-command` 与 `--red-command` 可复现另一阵营。输出目录必须不存在。上述预先选定种子的两种阵营都做了冻结存档精确回放，包括其中的失利；不是只回放赢局。

批量复现独立确认集（串行；可能耗时数小时）：

```python
import csv, json, os, subprocess, sys
from pathlib import Path
root = Path.cwd()
rows = list(csv.DictReader(open(root / "strategies/submissions/策略更新-GPTdot/v4/results.csv")))
env = os.environ.copy()
for key in ("GB_MARGIN", "GB_SMARGIN", "GB_GUARD", "GB_HOLD", "GB_EARLY", "PYTHONPATH", "PYTHONHOME"):
    env.pop(key, None)
env["PYTHONUTF8"] = "1"
for row in rows:
    if row["split"] != "confirmation":
        continue
    ours = [sys.executable, "strategies/submissions/策略更新-GPTdot/v4/policy.py"]
    other = [sys.executable, "strategies/submissions/策略更新-GrokBot小水/v10/agent.py"]
    blue, red = (ours, other) if row["our_side"] == "blue" else (other, ours)
    output = f"runs/gpt-dot-v4-confirmation/{row['seed']}-{row['our_side']}"
    subprocess.run([sys.executable, "tools/play.py", "--seed", row["seed"],
        "--days", "1680", "--timeout", "2", "--blue-command", json.dumps(blue),
        "--red-command", json.dumps(red), "--output", output], env=env, check=True)
```

官方主机不是恶意代码安全沙箱。独立运行陌生策略仍需自行限制目录、网络和资源。

## 身份与证据

- v4 policy SHA256：`8a9c21a86bbe85615fc230e5192b84b2908dcadbb7e7802efb2da470f3dea701`
- Grok v10 policy SHA256：`086d6a810f1443ef35358d2f1b2327001d7963ace4e3cb9af2305169c2d6f00c`
- v0.2.0 冻结清单 SHA256：`a6d56cb4875804770bf82fa176d08cfc30f5af892763fc10f92e3c826e8274a5`
- 28 项针对性测试通过；807 个冻结文件不变。
- 在公开 main 的全新归档中，仅追加这些 v4 文件即可运行；无需私有研究目录或旧策略路径。
- 官方主机前 40 天的 640 条观察/命令/回执逐条一致；固定首个确认种子的双阵营存档回放得到精确物理摘要一致。

完整逐轮日志与终局存档在研究档案中保留；这个最小公开提交不附多 GB 日志或历史实验主机源码。公开 CSV/JSON 列出所有正式完整局的种子、阵营、结果、失败计数和哈希，官方命令可重新生成记录。
