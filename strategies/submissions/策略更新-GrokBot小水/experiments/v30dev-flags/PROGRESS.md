# v30 进度检查点（防中断）— 更新 21:53 UTC+8
- v30dev/agent.py = v29 + 插桩(PREY/STAT100) + 默认关闭开关：GB_MINCREATE, GB_AMERGE(1/2), GB_HOLDALLR, GB_PURSUE,
  GB_SWR, GB_SWALERT, GB_AVIDLE（野外驻停小队也做避险）, GB_AVSHELTER（无安全路线时奔向能先到的己方城）。默认=v29（逐局相同）。
- 工具：/workspace/v30log/screen.sh tag opp seeds variants...；an.py "ver|opp|a|b"（W-D-L/前100天失城/前100天被吃PREY）。
- 诊断：对衡岳负局前100天被吃≈113人/局，胜局≈23人/局；PREY角色 sweep_refit 34、avoid 27、sweep_hit 5、pregather 2。
  经济：一局负局中我方驻军+野战 d0 480→d100 321，衡岳 480→670（被吃+增长慢）。
## 筛选 vs hy 0:12（24局，基线 v29=v30dev 12-0-12，prey 1.79/78hp，失城100=0.29）
| 变体 | W-D-L | 失城100 | prey100 |
|---|---|---|---|
| MINCREATE60+AMERGE2 | 12-0-12 | 0.21 | 1.54/58 |
| SWALERT1.5 | 14-0-10 | 0.21 | 1.33/51 |
| HOLDALLR1.5 | 9-0-14(23) | 0.43 | 2.04/86 |
| PURSUE1 | 12-0-12（与基线逐局相同） | 0.29 | 1.79/78 |
| 全开(MC60,AM2,SWA1.5,HAR1.5,PUR) | 13-0-11 | 0.38 | 2.00/71 |
| TSWEEP=0 | 10-0-14 | 0.38 | 1.25/59 |
| SWEEPD=40 | 4-0-8(12) | 0.50 | 2.50/131 |
| TSWEEP0+MC60+AM2 | 11-0-13 | 0.33 | 1.12/80 |
| SWALERT1+SWR15000 | 13-0-11 | 0.25 | 1.46/68 |
| AVIDLE+AVSHELTER | 12-0-12 | 0.25 | 1.62/58 |
## 进行中 s4（hy 0:24，48局）
- C1 = AVIDLE+AVSHELTER+SWALERT1+SWR15000+MINCREATE60+AMERGE2：中途 9-0-4（13局），prey 0.54/24hp
- C2 = AVIDLE+AVSHELTER+SWALERT1+SWR15000：排队
- 22:12 结果：C1 vs hy 0:24 = **29-0-19**（v29 同种子 23-0-25），失城100 0.27，prey100 0.73/32hp。
- 已排队：s4 C2(无MC/AM) hy 0:24 → s5 C1 vs ar6 0:12 → s5b C1 vs ar5 0:12 → s6 C1+FKEEP=20 hy 0:24
- 22:25 C2（AVIDLE+AVSHELTER+SWALERT1+SWR15000，不含 MC/AM）hy 0:24 中途 28-0-9（37局）。改队列：chain5 = C2 vs ar6 0:12 → C2 vs ar5 0:12 → C2+FKEEP20 hy 0:24（C1 的 ar6/ar5 取消）。
- 22:34 **C2 vs hy 0:24 = 36-0-12**（v29 23-0-25；配对：负→胜 14，胜→负 1），失城100 0.19，prey100 0.83/34hp。C2 = v30 候选。
- 22:40 建立 v30/agent.py = v30dev，默认 AVIDLE=1 AVSHELTER=1 SWALERT=1 SWR=15000（其余新开关默认关）。头注释待补。
  C2 子集：hy 0:12 19-0-5，12:24 17-0-7（v29 12:24 11-0-13）。C1(含MC60/AM2) 0:12 仅 13-0-11 → MC/AM 不采用。
  队列 chain6（等 s5 C2 vs ar6 完）：v30 hy 0:2（验证与C2逐局一致）→ C2 ar5 0:12 → v30 vs ar3/v22/v23/v29 0:6 → 消融 hy 12:24（v30dev、AVIDLE+SHELTER、SWALERT+SWR）→ C2+FKEEP20 hy 0:24
- 22:44 C2 vs ar6 0:12 = 16-0-8（v29 21-0-3）→ 回退，需定位。已并行启动 s7：AVIDLE+SHELTER 与 SWALERT+SWR 分别 vs ar6 0:12。chain6 在跑（v30 hy 0:2 验证中）。
- 22:48 验证：v30 vs hy 0:2 四局与 C2 逐局完全一致（胜者+结束小时相同）→ C2 结果即 v30 结果。chain6 进入 C2 vs ar5；s7（ar6 组件）在跑。
- 22:57 C2 vs ar5 中途 16-0-1（17局）；AVIDLE+SHELTER 单独 vs ar6 中途 16-0-4 → ar6 回退主要来自"野外驻停也避险"。
  新增 GB_AVIDLEMIN（驻停避险只针对 ≥N 人的大集团），s8：C2+AVIDLEMIN=200 vs ar6 0:12 已启动。
- 23:02 C2(=v30) vs ar5 0:12 = **22-0-2**（v29 23-0-1）✓。AVIDLE+SHELTER 单独 vs ar6 0:12 = 17-0-7（ar6 回退来源确认）。
  C2+AVIDLEMIN200 vs ar6 中途 10-0-3（13局）。v30 vs ar3 中途 11-0-0。
  精彩回放候选：红 1241774772（v29 d26 150人队"avoid→away"在野外被404人吃掉；v30 d27 同一局面"→c15"进城避险；d118 解围 B 550→1；胜于 d1310）；
  红 1479552164（v29 扫荡组 d14-16 反复出/回补撞 400 主力，d32 180人被吃；v30 扫荡组 d10-d67 留家；d60-64 解围 c13 B 411→4；胜于 d711）。
- 23:21 AVIDLEMIN=200 vs ar6 16-0-6（22局）→ 不能修复 ar6，放弃；其 hy 批次（18局时 13-0-5）已停止（未完成目录作废）。v30 维持 = C2。
  v30 vs ar3 0:6 = 12-0-0；v22 中途 9-0-0。

## 23:23 checkpoint
- s7 SWALERT=1,SWR=15000 alone vs ar6 0:12: 18-0-2 (n=20, still running) — so the ar6 regression is from AVIDLE/AVSHELTER, not SWALERT.
- SWEEPD=40 vs hy 0:12 finished: 7-1-16 (prey 1.96/94). HOLDALLR1.5 final 9-0-15.
- v30 vs v22 0:6: 10-0-0 (n=10, running); v23, v29 queued in chain6.
- v29 prey breakdown hy 0:12 (d<=100): sweep_refit 19/870, avoid 15/506, sweep_hit 5/298, other 4/187; loss games avg 132 men, win games 24.
- v30 hy 0:24: lost-city-by-d100 games 7 (0 wins) vs v29 11 (0 wins); took-city-by-d100 19 (19 wins) vs 17 (13).
- Report 13 draft at /workspace/v30log/report13.md (placeholders for v22/v23/v29/ablation).

## 23:33 checkpoint
- s7 SWALERT=1,SWR=15000 alone vs ar6 0:12 FINAL 21-0-3 (= v29). ar6 regression is entirely AVIDLE/AVSHELTER.
- v30 vs v22 0:6 FINAL 12-0-0 (v29 11-0-1); v30 vs v23 0:6 FINAL 11-0-1 (v29 11-1-0).
- v30 vs v29 0:6 running: 4-0-2 after 6.
- Next: one cheap gated-AVIDLE variant (general rule) on ar6 0:12; if it recovers ar6 run hy 0:24, else release C2.
- 23:34 added GB_AVCONC (default 0): idle evacuation only when the threatening group >= AVCONC x total recently-seen enemy field strength (general "concentrated main force" gate, not opponent ID). chain6 killed (ablation hy 12:24 skipped). chain7 (setsid): C2+AVCONC=0.6 vs ar6 0:12 then hy 0:24, log /workspace/v30log/s10.log.
- 23:38 v30 vs v29 0:6 FINAL 5-1-6 (self-play vs predecessor ≈ even). AVCONC0.6 vs ar6: 9-0-2 after 11.
- 23:40 AVCONC=0.6 vs ar6: game-for-game IDENTICAL to C2 on the 21 finished games (15-0-6 on those; C2 same) → the gate never fires (A-R6's threatening group is also its dominant one). Fix failed; stopped (3 unfinished dirs removed). DECISION: release v30 = C2 and document the A-R6 trade-off. No batches running.
