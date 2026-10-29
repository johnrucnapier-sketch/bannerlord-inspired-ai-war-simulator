# 策略更新-GrokBot小水（made by GrokBot）

本文件夹由 GrokBot（小水）专属维护，之后的策略更新都放在这里；其他 agent（GPT、DeepSeek 等）使用各自的文件夹。

本目录的策略全部由 **GrokBot**（Grok Bot，代号“小水”）在 2026-10-29 自动迭代生成，为博 李而做。
对手为冻结默认策略 `march`，规则冻结在 **v0.2.0**，没有改动任何规则、引擎或冻结文件（`tools/verify_release.py` 校验通过，807 个冻结文件一致）。

版本命名：`Grok Bot vN, approach: ...`，便于和 GPT、DeepSeek 在同一规则下做出的策略按思路对比。目的是比较各种思路能达到的结果，不是给 agent 排名。

## 收录的版本

| 目录 | 标签与思路 | 蓝方对 march（完整 1680 天，胜-平-负即局数） | 红方对 march |
|---|---|---|---|
| `v19/`（**最新最佳**） | Grok Bot v19, approach: v18 + 取消开局突袭（第 30 天前不发起攻城战役），专门应对 GPT v4 的开局解围 | 24-0-0，平均 12.00 城，24 局全部统一，平均第 394.5 天（最快 203），人口 10746 | 24-0-0，全部统一，平均第 334.5 天（最快 213） |
| `v18/` | Grok Bot v18, approach: v17 + 集结基地丢失时改换基地（修复 KeyError 'garrison'） | 未单独测（对 GPT v4 与 v17 逐局相同） | — |
| `v17/` | Grok Bot v17, approach: v16 + 残局全军编入主力 | 12-0-0，全部统一，平均第 363 天（最快 268） | 12-0-0，全部统一，平均第 401 天 |
| `v16/` | Grok Bot v16, approach: 前中期保守攻城估算，残局（敌 ≤3 城）用引擎精确的解围战模型 | 12-0-0，全部统一，平均第 444 天 | 12-0-0，全部统一，平均第 460 天 |
| `v15/` | Grok Bot v15, approach: v14 + 引擎精确的攻城需求（解围战模型），全程使用 | 只测了对 GPT v1 | — |
| `v14/` | Grok Bot v14, approach: v12 + 只在残局启用 v13 的动员 + 过期目标下限 300 | 只测了对 GPT v1 | — |
| `v10/`（v13 之前的最佳） | Grok Bot v10, approach: 开局突袭 + 巡逻队保经济 + 集中大军攻城 + 攻下驻守 + 攻城前估算援军 + 受威胁城市预先增防 | 24-0-0，平均 12.00 城，24 局全部统一，平均第 547 天（最快 311），人口 14295 | 12-0-0，全部统一，平均第 671 天（最快 334） |
| `v12/` | Grok Bot v12, approach: v10 + 按编制容量配置主力（解决最后一城久攻不下） | 24-0-0，平均 11.96 城，23 局统一，平均第 564 天，人口 14880 | 12-0-0，全部统一，平均第 562 天 |
| `v13/` | Grok Bot v13, approach: v12 + 全国动员（最快但不稳） | 21-3-0，平均第 468 天统一，最快第 280 天 | 7-5-0 |
| `v9/` | Grok Bot v9, approach: v8 + 攻城前估算敌方援军 | 19-5-0，平均 9.46 城，18 局统一，平均第 568 天 | 12-0-0 |

对照：`march` 对 `march`（蓝方 24 局）12-11-1，平均 6.17 城；README 中 D2 对 `march` 5-18-1，平均 2.79 城。

注：`results.md` / `results.csv` 中 v10 红方一行为 14 局，包含一次中断补跑的部分种子；正式确认以 12 种子 12-0 为准。

## 运行

```
python tools/play.py --blue-command '[".venv/bin/python","strategies/submissions/策略更新-GrokBot小水/v19/agent.py"]' --red march --days 1680 --seed <种子> --output <新目录>
```

种子见 `benchmarks/data/direct-garrison-20261029/seed-selection.json`。完整迭代记录（v1–v19）见 `log.md`，全部结果见 `results.md` / `results.csv` / `results.json`。

报告（`reports/`）：
- `01-stage-report-v9.md`：v9 阶段报告
- `02-stage-report-v10.md`：v10 阶段报告
- `03-final-summary.md`：最终总结（对 march，v10）
- `04-vs-GPT-Campaign600.md`：对战 GPT dot Campaign600 v1 / v4（v14–v19）

批量对局工具：`batch.py`（并行运行）、`summarize.py`（汇总结果）、`inspect_run.py`（查看单局时间线）、`make_md.py`（生成 results.md）。这些脚本里写死了 `/workspace/aiwar` 路径，使用时请改成自己的仓库路径。

## 对战 GPT dot Campaign600（v1 / v4）

完整报告：`reports/04-vs-GPT-Campaign600.md`；逐局结果：`results-h2h/h2h-vs-gptdot.{md,csv,json}`。

| 我方 | 对手 | 蓝方（我执蓝） | 红方（我执红） |
|---|---|---|---|
| v19 | GPT Campaign600 v4 | 24 局 20-1-3，20 局统一 | 24 局 22-1-1，22 局统一 |
| v16 / v17 / v18 | GPT Campaign600 v4 | 12 局 1-1-10 | 12 局 4-0-8 |
| v17 | GPT Campaign600 v1 | 24 局 23-0-1，23 局统一，平均第 523 天 | 24 局 23-0-1，23 局统一，平均第 441 天 |
| v16 | GPT Campaign600 v1 | 12 局 12-0-0 | 12 局 11-0-1 |
| v10 | GPT Campaign600 v1 | 24 局 21-0-3 | 24 局 23-0-1 |

基准：GPT v4 对 march 蓝 12-0-0（全部统一，平均第 776 天）、红 12-0-0；GPT v1 对 march 蓝 9-2-1、红 12-0-0。

v16–v18 的开局突袭会被 v4 的开局紧急解围全歼，v19 把第一次攻城推迟到第 30 天以后，对 v4 从 5-1-18 变成 42-2-4，对 march 也更快。GPT 发现的 v10 `KeyError 'garrison'`（集结基地被占后报错）在 v18 修复，v19 沿用。

对战工具：`batch_h2h.py`（`batch_h2h.py <我方> <对手> --seeds i:j --sides blue,red -j N`，对手名 `c600` = GPT v1，`c600v4` = GPT v4，`march` 等内置策略；`v19@GB_EARLY=60` 形式可传环境参数）、`gpt_adapter.py`（把 GPT v1 从提交 02966b3 原样取到 `/workspace/gpt-campaign600`，不复制进本文件夹）、`summarize_h2h.py`（汇总）。
