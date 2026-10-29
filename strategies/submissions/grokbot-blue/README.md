# Grok Bot 蓝方策略（made by GrokBot）

本目录的策略全部由 **GrokBot**（Grok Bot，代号“小水”）在 2026-10-29 自动迭代生成，为博 李而做。
对手为冻结默认策略 `march`，规则冻结在 **v0.2.0**，没有改动任何规则、引擎或冻结文件（`tools/verify_release.py` 校验通过，807 个冻结文件一致）。

版本命名：`Grok Bot vN, approach: ...`，便于和 GPT、DeepSeek 在同一规则下做出的策略按思路对比。目的是比较各种思路能达到的结果，不是给 agent 排名。

## 收录的版本

| 目录 | 标签与思路 | 蓝方对 march（24 种子，完整 1680 天） | 红方对 march（12 种子） |
|---|---|---|---|
| `v10/`（**最佳**） | Grok Bot v10, approach: 开局突袭 + 巡逻队保经济 + 集中大军攻城 + 攻下驻守 + 攻城前估算援军 + 受威胁城市预先增防 | 24-0-0，平均 12.00 城，24 局全部统一，平均第 547 天（最快 311），人口 14295 | 12-0-0，全部统一，平均第 671 天（最快 334） |
| `v12/` | Grok Bot v12, approach: v10 + 按编制容量配置主力（解决最后一城久攻不下） | 24-0-0，平均 11.96 城，23 局统一，平均第 564 天，人口 14880 | 12-0-0，全部统一，平均第 562 天 |
| `v13/` | Grok Bot v13, approach: v12 + 全国动员（最快但不稳） | 21-3-0，平均第 468 天统一，最快第 280 天 | 7-5-0 |
| `v9/` | Grok Bot v9, approach: v8 + 攻城前估算敌方援军 | 19-5-0，平均 9.46 城，18 局统一，平均第 568 天 | 12-0-0 |

对照：`march` 对 `march`（蓝方 24 局）12-11-1，平均 6.17 城；README 中 D2 对 `march` 5-18-1，平均 2.79 城。

注：`results.md` / `results.csv` 中 v10 红方一行为 14 局，包含一次中断补跑的部分种子；正式确认以 12 种子 12-0 为准。

## 运行

```
python tools/play.py --blue-command '[".venv/bin/python","strategies/submissions/grokbot-blue/v10/agent.py"]' --red march --days 1680 --seed <种子> --output <新目录>
```

种子见 `benchmarks/data/direct-garrison-20261029/seed-selection.json`。完整迭代记录（v1–v13）见 `log.md`，全部结果见 `results.md` / `results.csv` / `results.json`。

报告（`reports/`）：
- `01-stage-report-v9.md`：v9 阶段报告
- `02-stage-report-v10.md`：v10 阶段报告
- `03-final-summary.md`：最终总结

批量对局工具：`batch.py`（并行运行）、`summarize.py`（汇总结果）、`inspect_run.py`（查看单局时间线）、`make_md.py`（生成 results.md）。这些脚本里写死了 `/workspace/aiwar` 路径，使用时请改成自己的仓库路径。

## 下一步（未测试）
只在残局（红方剩 3 座城以下）才启用 v12/v13 的动员规则，预计能兼顾稳定与速度。
