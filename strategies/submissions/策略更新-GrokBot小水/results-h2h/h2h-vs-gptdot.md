# Head-to-head results (Grok Bot 小水 vs GPT dot Campaign600 v1, v4 and v6, plus baselines vs march)

Full 1680-day matches, frozen rules v0.2.0, seeds from `benchmarks/data/direct-garrison-20261029/seed-selection.json`. 
Campaign600 v1 = branch `gpt-dot/campaign600-v1-20261029`, commit `02966b3`, `strategies/submissions/cloud_campaign_v7_min600/policy.py` (unmodified, loaded via `gpt_adapter.py`). 
Campaign600 v4 / v6 = `strategies/submissions/策略更新-GPTdot/v4/policy.py` (f8e10d6) / `v6/policy.py` (16e67a6, SHA256 f8e10fca...ae75) on main, unmodified, run in place. Seed set `std` = the benchmark seeds; `gpt-v6-indep` = the 12 independent seeds listed in GPT dot v6 results.json. `vN@GB_EARLY=30` = Grok vN with that environment parameter.

| me | opponent | my side | seed set | games | W-D-L | win rate | mean cities | mean pop (me/opp) | unifications (mean / fastest day) | unified against | games with runtime faults (W/L among clean games) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GPT dot Campaign600 v1 | march (frozen default) | blue | std | 12 | 9-2-1 | 75% | 9.75 | 15785 / 4793 | 7 (866.3 / 492.6) | 0 | 0 (9/1) |
| GPT dot Campaign600 v1 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 11.75 | 16187 / 817 | 9 (505.0 / 379.1) | 0 | 0 (12/0) |
| GPT dot Campaign600 v4 Early Relief | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 16782 / 0 | 12 (776.2 / 383.8) | 0 | 0 (12/0) |
| GPT dot Campaign600 v4 Early Relief | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 11.42 | 20377 / 2242 | 6 (485.6 / 384.9) | 0 | 0 (12/0) |
| Grok Bot v10 | GPT dot Campaign600 v1 | blue | std | 24 | 21-0-3 | 88% | 10.12 | 23880 / 3286 | 12 (894.3 / 658.0) | 3 | 3 (19/2) |
| Grok Bot v10 | GPT dot Campaign600 v1 | red | std | 24 | 23-0-1 | 96% | 11.29 | 22858 / 1140 | 18 (978.7 / 357.2) | 1 | 1 (22/1) |
| Grok Bot v12 | GPT dot Campaign600 v1 | blue | std | 12 | 12-0-0 | 100% | 11.33 | 30789 / 2969 | 4 (805.4 / 519.0) | 0 | 0 (12/0) |
| Grok Bot v12 | GPT dot Campaign600 v1 | red | std | 12 | 11-0-1 | 92% | 11 | 18893 / 808 | 11 (985.2 / 414.0) | 1 | 1 (10/1) |
| Grok Bot v14 | GPT dot Campaign600 v1 | blue | std | 12 | 12-0-0 | 100% | 11.42 | 24292 / 2364 | 5 (659.0 / 427.5) | 0 | 1 (11/0) |
| Grok Bot v15 | GPT dot Campaign600 v1 | blue | std | 12 | 11-0-1 | 92% | 10.67 | 14000 / 1911 | 9 (487.1 / 431.6) | 1 | 1 (10/1) |
| Grok Bot v16 | GPT dot Campaign600 v1 | blue | std | 12 | 12-0-0 | 100% | 11.58 | 22937 / 1795 | 7 (486.1 / 353.4) | 0 | 0 (12/0) |
| Grok Bot v16 | GPT dot Campaign600 v1 | red | std | 12 | 11-0-1 | 92% | 10.83 | 15624 / 1519 | 9 (588.5 / 422.0) | 1 | 0 (11/1) |
| Grok Bot v16 | GPT dot Campaign600 v4 Early Relief | blue | std | 12 | 1-1-10 | 8% | 1.92 | 3327 / 11778 | 1 (1036.2 / 1036.2) | 9 | 0 (1/10) |
| Grok Bot v16 | GPT dot Campaign600 v4 Early Relief | red | std | 12 | 4-0-8 | 33% | 3.42 | 7348 / 10343 | 1 (911.9 / 911.9) | 8 | 0 (4/8) |
| Grok Bot v16 | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 11551 / 0 | 12 (444.3 / 309.4) | 0 | 0 (12/0) |
| Grok Bot v16 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 12 | 10944 / 0 | 12 (459.7 / 290.8) | 0 | 0 (12/0) |
| Grok Bot v17 | GPT dot Campaign600 v1 | blue | std | 24 | 23-0-1 | 96% | 11.5 | 9392 / 600 | 23 (522.9 / 310.1) | 1 | 0 (23/1) |
| Grok Bot v17 | GPT dot Campaign600 v1 | red | std | 24 | 23-0-1 | 96% | 11.5 | 9778 / 368 | 23 (440.9 / 319.0) | 1 | 0 (23/1) |
| Grok Bot v17 | GPT dot Campaign600 v4 Early Relief | blue | std | 12 | 1-1-10 | 8% | 1.92 | 3261 / 11778 | 1 (918.9 / 918.9) | 9 | 0 (1/10) |
| Grok Bot v17 | GPT dot Campaign600 v4 Early Relief | red | std | 12 | 4-0-8 | 33% | 3.67 | 6274 / 9446 | 3 (1109.6 / 815.7) | 8 | 0 (4/8) |
| Grok Bot v17 | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 9407 / 0 | 12 (362.7 / 268.3) | 0 | 1 (11/0) |
| Grok Bot v17 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 12 | 9106 / 0 | 12 (401.4 / 269.8) | 0 | 0 (12/0) |
| Grok Bot v18 | GPT dot Campaign600 v4 Early Relief | blue | std | 12 | 1-1-10 | 8% | 1.92 | 3261 / 11778 | 1 (918.9 / 918.9) | 9 | 0 (1/10) |
| Grok Bot v18 | GPT dot Campaign600 v4 Early Relief | red | std | 12 | 4-0-8 | 33% | 3.67 | 6274 / 9446 | 3 (1109.6 / 815.7) | 8 | 0 (4/8) |
| Grok Bot v18@GB_EARLY=30 | GPT dot Campaign600 v4 Early Relief | blue | std | 6 | 5-0-1 | 83% | 10.17 | 13118 / 4380 | 5 (864.3 / 481.4) | 0 | 0 (5/1) |
| Grok Bot v18@GB_EARLY=30 | GPT dot Campaign600 v4 Early Relief | red | std | 6 | 6-0-0 | 100% | 12 | 13842 / 0 | 6 (741.4 / 587.5) | 0 | 0 (6/0) |
| Grok Bot v18@GB_EARLY=60 | GPT dot Campaign600 v4 Early Relief | blue | std | 6 | 5-0-1 | 83% | 10.17 | 13118 / 4380 | 5 (864.3 / 481.4) | 0 | 0 (5/1) |
| Grok Bot v18@GB_EARLY=60 | GPT dot Campaign600 v4 Early Relief | red | std | 6 | 6-0-0 | 100% | 12 | 13842 / 0 | 6 (741.4 / 587.5) | 0 | 0 (6/0) |
| Grok Bot v19 | GPT dot Campaign600 v4 Early Relief | blue | std | 24 | 20-1-3 | 83% | 10.29 | 11318 / 3070 | 20 (666.4 / 273.7) | 2 | 0 (20/3) |
| Grok Bot v19 | GPT dot Campaign600 v4 Early Relief | red | std | 24 | 22-1-1 | 92% | 11.25 | 12940 / 1162 | 22 (739.4 / 254.6) | 1 | 0 (22/1) |
| Grok Bot v19 | GPT dot Campaign600 v6 Feasible Relief | blue | std | 24 | 8-1-15 | 33% | 4.08 | 7551 / 13705 | 5 (946.7 / 479.8) | 12 | 0 (8/15) |
| Grok Bot v19 | GPT dot Campaign600 v6 Feasible Relief | red | std | 24 | 4-0-20 | 17% | 2.21 | 4236 / 13478 | 4 (1215.6 / 732.5) | 19 | 0 (4/20) |
| Grok Bot v19 | march (frozen default) | blue | std | 24 | 24-0-0 | 100% | 12 | 10746 / 0 | 24 (394.5 / 203.0) | 0 | 0 (24/0) |
| Grok Bot v19 | march (frozen default) | red | std | 24 | 24-0-0 | 100% | 12 | 10433 / 0 | 24 (334.5 / 213.2) | 0 | 0 (24/0) |
| Grok Bot v20 | GPT dot Campaign600 v1 | blue | std | 12 | 12-0-0 | 100% | 12 | 12118 / 0 | 12 (426.8 / 242.6) | 0 | 1 (11/0) |
| Grok Bot v20 | GPT dot Campaign600 v1 | red | std | 12 | 12-0-0 | 100% | 12 | 12998 / 0 | 12 (471.3 / 309.2) | 0 | 0 (12/0) |
| Grok Bot v20 | GPT dot Campaign600 v4 Early Relief | blue | std | 12 | 12-0-0 | 100% | 12 | 15489 / 0 | 12 (647.3 / 244.7) | 0 | 1 (11/0) |
| Grok Bot v20 | GPT dot Campaign600 v4 Early Relief | red | std | 12 | 12-0-0 | 100% | 12 | 17160 / 0 | 12 (690.5 / 358.7) | 0 | 0 (12/0) |
| Grok Bot v20 | GPT dot Campaign600 v6 Feasible Relief | blue | std | 24 | 24-0-0 | 100% | 12 | 21917 / 0 | 24 (915.0 / 646.5) | 0 | 1 (23/0) |
| Grok Bot v20 | GPT dot Campaign600 v6 Feasible Relief | red | std | 24 | 23-1-0 | 96% | 11.75 | 19423 / 867 | 23 (755.6 / 255.6) | 0 | 1 (22/0) |
| Grok Bot v20 | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 11362 / 0 | 12 (357.2 / 227.6) | 0 | 0 (12/0) |
| Grok Bot v20 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 12 | 10623 / 0 | 12 (316.0 / 240.7) | 0 | 0 (12/0) |
| Grok Bot v9 | GPT dot Campaign600 v1 | blue | std | 12 | 12-0-0 | 100% | 11.25 | 27714 / 3132 | 3 (957.4 / 665.5) | 0 | 3 (9/0) |
| Grok Bot v9 | GPT dot Campaign600 v1 | red | std | 12 | 11-0-1 | 92% | 10.67 | 25250 / 2303 | 7 (1202.1 / 970.3) | 1 | 0 (11/1) |
