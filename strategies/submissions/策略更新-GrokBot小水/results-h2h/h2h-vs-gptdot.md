# Head-to-head results (Grok Bot 小水 vs GPT dot Campaign600 v1, v4 and v6, plus baselines vs march)

Full 1680-day matches, frozen rules v0.2.0, seeds from `benchmarks/data/direct-garrison-20261029/seed-selection.json`. 
Campaign600 v1 = branch `gpt-dot/campaign600-v1-20261029`, commit `02966b3`, `strategies/submissions/cloud_campaign_v7_min600/policy.py` (unmodified, loaded via `gpt_adapter.py`). 
Campaign600 v4 / v6 = `strategies/submissions/策略更新-GPTdot/v4/policy.py` (f8e10d6) / `v6/policy.py` (16e67a6, SHA256 f8e10fca...ae75) on main, unmodified, run in place. Seed set `std` = the benchmark seeds; `gpt-v6-indep` = the 12 independent seeds listed in GPT dot v6 results.json; `self` = Grok 6 self-chosen seeds 20261030, 31415926, 27182818, 16180339, 14142135, 17320508 (report 06). `vN@GB_EARLY=30` = Grok vN with that environment parameter.

| me | opponent | my side | seed set | games | W-D-L | win rate | mean cities | mean pop (me/opp) | unifications (mean / fastest day) | unified against | games with runtime faults (W/L among clean games) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GPT dot Campaign600 v1 | march (frozen default) | blue | std | 12 | 9-2-1 | 75% | 9.75 | 15785 / 4793 | 7 (866.3 / 492.6) | 0 | 0 (9/1) |
| GPT dot Campaign600 v1 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 11.75 | 16187 / 817 | 9 (505.0 / 379.1) | 0 | 0 (12/0) |
| GPT dot Campaign600 v4 Early Relief | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 16782 / 0 | 12 (776.2 / 383.8) | 0 | 0 (12/0) |
| GPT dot Campaign600 v4 Early Relief | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 11.42 | 20377 / 2242 | 6 (485.6 / 384.9) | 0 | 0 (12/0) |
| Grok Bot v10 | GPT dot Campaign600 v1 | blue | std | 24 | 21-0-3 | 88% | 10.12 | 23880 / 3286 | 12 (894.3 / 658.0) | 3 | 0 (21/3) |
| Grok Bot v10 | GPT dot Campaign600 v1 | red | std | 24 | 23-0-1 | 96% | 11.29 | 22858 / 1140 | 18 (978.7 / 357.2) | 1 | 0 (23/1) |
| Grok Bot v12 | GPT dot Campaign600 v1 | blue | std | 12 | 12-0-0 | 100% | 11.33 | 30789 / 2969 | 4 (805.4 / 519.0) | 0 | 0 (12/0) |
| Grok Bot v12 | GPT dot Campaign600 v1 | red | std | 12 | 11-0-1 | 92% | 11 | 18893 / 808 | 11 (985.2 / 414.0) | 1 | 0 (11/1) |
| Grok Bot v14 | GPT dot Campaign600 v1 | blue | std | 12 | 12-0-0 | 100% | 11.42 | 24292 / 2364 | 5 (659.0 / 427.5) | 0 | 0 (12/0) |
| Grok Bot v15 | GPT dot Campaign600 v1 | blue | std | 12 | 11-0-1 | 92% | 10.67 | 14000 / 1911 | 9 (487.1 / 431.6) | 1 | 0 (11/1) |
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
| Grok Bot v17 | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 9407 / 0 | 12 (362.7 / 268.3) | 0 | 0 (12/0) |
| Grok Bot v17 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 12 | 9106 / 0 | 12 (401.4 / 269.8) | 0 | 0 (12/0) |
| Grok Bot v18 | GPT dot Campaign600 v4 Early Relief | blue | std | 12 | 1-1-10 | 8% | 1.92 | 3261 / 11778 | 1 (918.9 / 918.9) | 9 | 0 (1/10) |
| Grok Bot v18 | GPT dot Campaign600 v4 Early Relief | red | std | 12 | 4-0-8 | 33% | 3.67 | 6274 / 9446 | 3 (1109.6 / 815.7) | 8 | 0 (4/8) |
| Grok Bot v18@GB_EARLY=30 | GPT dot Campaign600 v4 Early Relief | blue | std | 6 | 5-0-1 | 83% | 10.17 | 13118 / 4380 | 5 (864.3 / 481.4) | 0 | 0 (5/1) |
| Grok Bot v18@GB_EARLY=30 | GPT dot Campaign600 v4 Early Relief | red | std | 6 | 6-0-0 | 100% | 12 | 13842 / 0 | 6 (741.4 / 587.5) | 0 | 0 (6/0) |
| Grok Bot v18@GB_EARLY=60 | GPT dot Campaign600 v4 Early Relief | blue | std | 6 | 5-0-1 | 83% | 10.17 | 13118 / 4380 | 5 (864.3 / 481.4) | 0 | 0 (5/1) |
| Grok Bot v18@GB_EARLY=60 | GPT dot Campaign600 v4 Early Relief | red | std | 6 | 6-0-0 | 100% | 12 | 13842 / 0 | 6 (741.4 / 587.5) | 0 | 0 (6/0) |
| Grok Bot v19 | GPT dot Campaign600 v4 Early Relief | blue | std | 24 | 20-1-3 | 83% | 10.29 | 11318 / 3070 | 20 (666.4 / 273.7) | 2 | 0 (20/3) |
| Grok Bot v19 | GPT dot Campaign600 v4 Early Relief | red | std | 24 | 22-1-1 | 92% | 11.25 | 12940 / 1162 | 22 (739.4 / 254.6) | 1 | 0 (22/1) |
| Grok Bot v19 | GPT dot Campaign600 v6 Feasible Relief | blue | gpt-v6-indep | 12 | 3-0-9 | 25% | 3.17 | 7711 / 10772 | 3 (1426.8 / 1310.7) | 8 | 0 (3/9) |
| Grok Bot v19 | GPT dot Campaign600 v6 Feasible Relief | blue | std | 24 | 8-1-15 | 33% | 4.08 | 7551 / 13705 | 5 (946.7 / 479.8) | 12 | 0 (8/15) |
| Grok Bot v19 | GPT dot Campaign600 v6 Feasible Relief | red | gpt-v6-indep | 12 | 2-0-10 | 17% | 1.92 | 4592 / 14004 | 1 (1561.8 / 1561.8) | 10 | 0 (2/10) |
| Grok Bot v19 | GPT dot Campaign600 v6 Feasible Relief | red | std | 24 | 4-0-20 | 17% | 2.21 | 4236 / 13478 | 4 (1215.6 / 732.5) | 19 | 0 (4/20) |
| Grok Bot v19 | march (frozen default) | blue | std | 24 | 24-0-0 | 100% | 12 | 10746 / 0 | 24 (394.5 / 203.0) | 0 | 0 (24/0) |
| Grok Bot v19 | march (frozen default) | red | std | 24 | 24-0-0 | 100% | 12 | 10433 / 0 | 24 (334.5 / 213.2) | 0 | 0 (24/0) |
| Grok Bot v20 | GPT dot Campaign600 v1 | blue | std | 12 | 12-0-0 | 100% | 12 | 12118 / 0 | 12 (426.8 / 242.6) | 0 | 1 (11/0) |
| Grok Bot v20 | GPT dot Campaign600 v1 | red | std | 12 | 12-0-0 | 100% | 12 | 12998 / 0 | 12 (471.3 / 309.2) | 0 | 0 (12/0) |
| Grok Bot v20 | GPT dot Campaign600 v4 Early Relief | blue | std | 12 | 12-0-0 | 100% | 12 | 15489 / 0 | 12 (647.3 / 244.7) | 0 | 1 (11/0) |
| Grok Bot v20 | GPT dot Campaign600 v4 Early Relief | red | std | 12 | 12-0-0 | 100% | 12 | 17160 / 0 | 12 (690.5 / 358.7) | 0 | 0 (12/0) |
| Grok Bot v20 | GPT dot Campaign600 v6 Feasible Relief | blue | gpt-v6-indep | 12 | 12-0-0 | 100% | 12 | 20276 / 0 | 12 (842.2 / 513.5) | 0 | 0 (12/0) |
| Grok Bot v20 | GPT dot Campaign600 v6 Feasible Relief | blue | std | 24 | 24-0-0 | 100% | 12 | 21917 / 0 | 24 (915.0 / 646.5) | 0 | 1 (23/0) |
| Grok Bot v20 | GPT dot Campaign600 v6 Feasible Relief | red | gpt-v6-indep | 12 | 12-0-0 | 100% | 12 | 24987 / 0 | 12 (1070.8 / 323.6) | 0 | 1 (11/0) |
| Grok Bot v20 | GPT dot Campaign600 v6 Feasible Relief | red | std | 24 | 23-1-0 | 96% | 11.75 | 19423 / 867 | 23 (755.6 / 255.6) | 0 | 1 (22/0) |
| Grok Bot v20 | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 11362 / 0 | 12 (357.2 / 227.6) | 0 | 0 (12/0) |
| Grok Bot v20 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 12 | 10623 / 0 | 12 (316.0 / 240.7) | 0 | 0 (12/0) |
| Grok Bot v20 | Grok Bot v20 | blue | self | 6 | 6-0-0 | 100% | 12 | 13890 / 0 | 6 (524.7 / 251.6) | 0 | 0 (6/0) |
| Grok Bot v20 | Grok Bot v20 | blue | std | 24 | 12-0-12 | 50% | 6.21 | 6312 / 7539 | 12 (481.9 / 252.6) | 11 | 0 (12/12) |
| Grok Bot v21 | GPT dot Campaign600 v6 Feasible Relief | blue | gpt-v6-indep | 12 | 11-0-1 | 92% | 11 | 13974 / 946 | 11 (658.4 / 370.2) | 1 | 2 (10/0) |
| Grok Bot v21 | GPT dot Campaign600 v6 Feasible Relief | red | gpt-v6-indep | 12 | 11-1-0 | 92% | 11.5 | 13991 / 726 | 11 (613.5 / 327.7) | 0 | 0 (11/0) |
| Grok Bot v21 | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 9667 / 0 | 12 (351.9 / 291.2) | 0 | 0 (12/0) |
| Grok Bot v21 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 12 | 9207 / 0 | 12 (354.0 / 282.0) | 0 | 0 (12/0) |
| Grok Bot v21 | Grok Bot v20 | blue | std | 2 | 2-0-0 | 100% | 12 | 19040 / 0 | 2 (820.2 / 697.0) | 0 | 0 (2/0) |
| Grok Bot v21 | Grok Bot v20 | red | std | 2 | 2-0-0 | 100% | 12 | 17594 / 0 | 2 (712.4 / 645.3) | 0 | 0 (2/0) |
| Grok Bot v21a-feint | march (frozen default) | blue | std | 3 | 3-0-0 | 100% | 12 | 9936 / 0 | 3 (337.1 / 241.0) | 0 | 0 (3/0) |
| Grok Bot v21a-feint | march (frozen default) | red | std | 3 | 3-0-0 | 100% | 12 | 12752 / 0 | 3 (377.2 / 306.5) | 0 | 0 (3/0) |
| Grok Bot v21a-feint | Grok Bot v20 | blue | std | 12 | 5-0-7 | 42% | 5 | 5581 / 8511 | 5 (546.6 / 257.5) | 7 | 0 (5/7) |
| Grok Bot v21a-feint | Grok Bot v20 | red | std | 12 | 6-0-6 | 50% | 6 | 6854 / 6066 | 6 (686.8 / 489.2) | 6 | 0 (6/6) |
| Grok Bot v21a2-feint | Grok Bot v20 | blue | std | 12 | 5-0-7 | 42% | 5 | 5595 / 8511 | 5 (549.0 / 257.5) | 7 | 0 (5/7) |
| Grok Bot v21a2-feint | Grok Bot v20 | red | std | 12 | 6-0-6 | 50% | 6 | 6854 / 6066 | 6 (686.8 / 489.2) | 6 | 0 (6/6) |
| Grok Bot v21b-hunt | GPT dot Campaign600 v6 Feasible Relief | blue | std | 12 | 12-0-0 | 100% | 12 | 14737 / 0 | 12 (675.0 / 322.5) | 0 | 0 (12/0) |
| Grok Bot v21b-hunt | GPT dot Campaign600 v6 Feasible Relief | red | std | 12 | 12-0-0 | 100% | 12 | 16924 / 0 | 12 (748.4 / 340.5) | 0 | 0 (12/0) |
| Grok Bot v21b-hunt | Grok Bot v20 | blue | self | 6 | 6-0-0 | 100% | 12 | 12269 / 0 | 6 (524.4 / 296.8) | 0 | 0 (6/0) |
| Grok Bot v21b-hunt | Grok Bot v20 | blue | std | 12 | 12-0-0 | 100% | 12 | 15128 / 0 | 12 (600.5 / 377.6) | 0 | 0 (12/0) |
| Grok Bot v21b-hunt | Grok Bot v20 | red | self | 6 | 4-0-2 | 67% | 8 | 7338 / 3666 | 4 (467.6 / 381.5) | 2 | 0 (4/2) |
| Grok Bot v21b-hunt | Grok Bot v20 | red | std | 12 | 11-0-1 | 92% | 11 | 14677 / 1018 | 11 (658.2 / 260.3) | 1 | 0 (11/1) |
| Grok Bot v21c-combo | Grok Bot v20 | blue | self | 6 | 6-0-0 | 100% | 12 | 13839 / 0 | 6 (602.8 / 346.2) | 0 | 0 (6/0) |
| Grok Bot v21c-combo | Grok Bot v20 | blue | std | 12 | 12-0-0 | 100% | 12 | 15088 / 0 | 12 (594.3 / 378.9) | 0 | 0 (12/0) |
| Grok Bot v21c-combo | Grok Bot v20 | red | self | 6 | 4-0-2 | 67% | 8 | 7393 / 3394 | 4 (477.9 / 356.6) | 2 | 0 (4/2) |
| Grok Bot v21c-combo | Grok Bot v20 | red | std | 12 | 12-0-0 | 100% | 12 | 15428 / 0 | 12 (739.8 / 260.3) | 0 | 0 (12/0) |
| Grok Bot v22 | ar5 | blue | gpt-v6-indep | 5 | 0-1-4 | 0% | 2.2 | 3357 / 6454 | 0 (None / None) | 3 | 0 (0/4) |
| Grok Bot v22 | ar5 | red | gpt-v6-indep | 5 | 2-0-3 | 40% | 4 | 2521 / 4556 | 0 (None / None) | 2 | 0 (2/3) |
| Grok Bot v22 | GPT dot Campaign600 v6 Feasible Relief | blue | gpt-v6-indep | 12 | 12-0-0 | 100% | 12 | 13918 / 0 | 12 (623.1 / 305.3) | 0 | 0 (12/0) |
| Grok Bot v22 | GPT dot Campaign600 v6 Feasible Relief | blue | std | 12 | 12-0-0 | 100% | 12 | 14377 / 0 | 12 (627.5 / 369.2) | 0 | 0 (12/0) |
| Grok Bot v22 | GPT dot Campaign600 v6 Feasible Relief | red | gpt-v6-indep | 12 | 12-0-0 | 100% | 12 | 14309 / 0 | 12 (602.3 / 365.5) | 0 | 0 (12/0) |
| Grok Bot v22 | GPT dot Campaign600 v6 Feasible Relief | red | std | 12 | 12-0-0 | 100% | 12 | 14974 / 0 | 12 (643.5 / 350.8) | 0 | 0 (12/0) |
| Grok Bot v22 | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 9522 / 0 | 12 (344.4 / 274.6) | 0 | 0 (12/0) |
| Grok Bot v22 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 12 | 9886 / 0 | 12 (337.8 / 263.6) | 0 | 0 (12/0) |
| Grok Bot v22 | Grok Bot v20 | red | std | 1 | 1-0-0 | 100% | 12 | 15276 / 0 | 1 (573.0 / 573.0) | 0 | 0 (1/0) |
| Grok Bot v22 | Grok Bot v21 | blue | self | 6 | 6-0-0 | 100% | 12 | 13136 / 0 | 6 (810.5 / 423.2) | 0 | 0 (6/0) |
| Grok Bot v22 | Grok Bot v21 | blue | std | 12 | 9-0-3 | 75% | 9 | 10004 / 2673 | 9 (1001.7 / 388.4) | 3 | 0 (9/3) |
| Grok Bot v22 | Grok Bot v21 | red | self | 6 | 3-0-3 | 50% | 6 | 6364 / 6090 | 3 (628.7 / 437.1) | 3 | 0 (3/3) |
| Grok Bot v22 | Grok Bot v21 | red | std | 12 | 8-0-4 | 67% | 7.58 | 9280 / 4409 | 7 (1001.8 / 644.3) | 4 | 0 (8/4) |
| Grok Bot v22 | v22r-raid | blue | std | 12 | 2-1-9 | 17% | 3.58 | 5059 / 11101 | 2 (1002.8 / 783.2) | 6 | 0 (2/9) |
| Grok Bot v22 | v22r-raid | red | std | 12 | 5-0-7 | 42% | 5 | 4938 / 5982 | 4 (710.6 / 525.2) | 6 | 0 (5/7) |
| Grok Bot v23 | ar3 | blue | gpt-v6-indep | 5 | 3-0-2 | 60% | 6.4 | 3163 / 2920 | 2 (803.0 / 477.4) | 2 | 0 (3/2) |
| Grok Bot v23 | ar3 | red | gpt-v6-indep | 5 | 0-0-5 | 0% | 0 | 0 / 5898 | 0 (None / None) | 5 | 0 (0/5) |
| Grok Bot v23 | ar5 | blue | gpt-v6-indep | 5 | 1-0-4 | 20% | 3.2 | 2685 / 4757 | 1 (356.2 / 356.2) | 3 | 0 (1/4) |
| Grok Bot v23 | ar5 | red | gpt-v6-indep | 5 | 1-0-4 | 20% | 3.2 | 2485 / 5441 | 1 (881.4 / 881.4) | 3 | 0 (1/4) |
| Grok Bot v23 | GPT dot Campaign600 v6 Feasible Relief | blue | gpt-v6-indep | 12 | 12-0-0 | 100% | 12 | 14647 / 0 | 12 (640.5 / 368.7) | 0 | 0 (12/0) |
| Grok Bot v23 | GPT dot Campaign600 v6 Feasible Relief | blue | std | 12 | 12-0-0 | 100% | 12 | 13665 / 0 | 12 (605.1 / 406.8) | 0 | 0 (12/0) |
| Grok Bot v23 | GPT dot Campaign600 v6 Feasible Relief | red | gpt-v6-indep | 12 | 12-0-0 | 100% | 12 | 15083 / 0 | 12 (641.5 / 323.7) | 0 | 0 (12/0) |
| Grok Bot v23 | GPT dot Campaign600 v6 Feasible Relief | red | std | 12 | 12-0-0 | 100% | 12 | 16256 / 0 | 12 (704.4 / 344.4) | 0 | 1 (11/0) |
| Grok Bot v23 | hy | blue | gpt-v6-indep | 5 | 0-0-5 | 0% | 0 | 0 / 3837 | 0 (None / None) | 5 | 0 (0/5) |
| Grok Bot v23 | hy | red | gpt-v6-indep | 5 | 0-0-5 | 0% | 0 | 0 / 3994 | 0 (None / None) | 5 | 0 (0/5) |
| Grok Bot v23 | march (frozen default) | blue | std | 12 | 12-0-0 | 100% | 12 | 9609 / 0 | 12 (338.1 / 251.8) | 0 | 0 (12/0) |
| Grok Bot v23 | march (frozen default) | red | std | 12 | 12-0-0 | 100% | 12 | 9704 / 0 | 12 (349.0 / 263.1) | 0 | 0 (12/0) |
| Grok Bot v23 | v22 | blue | self | 6 | 3-0-3 | 50% | 6 | 4316 / 6292 | 3 (654.3 / 357.1) | 3 | 0 (3/3) |
| Grok Bot v23 | v22 | blue | std | 12 | 7-0-5 | 58% | 6.42 | 7132 / 6371 | 5 (758.6 / 330.2) | 4 | 0 (7/5) |
| Grok Bot v23 | v22 | red | self | 6 | 0-0-6 | 0% | 0 | 0 / 11918 | 0 (None / None) | 6 | 0 (0/6) |
| Grok Bot v23 | v22 | red | std | 12 | 4-0-8 | 33% | 4.42 | 5057 / 9125 | 4 (814.2 / 482.1) | 7 | 0 (4/8) |
| Grok Bot v23 | v22r-raid | blue | std | 12 | 2-0-10 | 17% | 2.25 | 2480 / 8012 | 2 (1038.7 / 782.7) | 9 | 0 (2/10) |
| Grok Bot v23 | v22r-raid | red | std | 12 | 3-0-9 | 25% | 3 | 3360 / 9196 | 3 (911.0 / 626.6) | 9 | 0 (3/9) |
| Grok Bot v23@GB_FAMDAY=0 | v22 | blue | std | 6 | 2-0-4 | 33% | 4 | 5714 / 5360 | 2 (997.2 / 600.5) | 4 | 0 (2/4) |
| Grok Bot v23@GB_FAMDAY=0 | v22 | red | std | 6 | 2-0-4 | 33% | 4.83 | 8105 / 10154 | 1 (626.3 / 626.3) | 2 | 0 (2/4) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0 | v22 | blue | std | 6 | 3-1-2 | 50% | 6 | 9790 / 7295 | 1 (702.0 / 702.0) | 2 | 0 (3/2) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0 | v22 | red | std | 6 | 2-1-3 | 33% | 6 | 7295 / 9790 | 2 (577.8 / 564.3) | 1 | 0 (2/3) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0,GB_RAID=2 | v22 | blue | std | 6 | 4-0-2 | 67% | 7.5 | 8266 / 7107 | 3 (627.6 / 433.6) | 2 | 0 (4/2) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0,GB_RAID=2 | v22 | red | std | 6 | 5-0-1 | 83% | 10.83 | 12965 / 2342 | 5 (791.9 / 477.0) | 0 | 0 (5/1) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0,GB_RAID=2 | v22r-raid | blue | std | 6 | 2-0-4 | 33% | 3.33 | 3785 / 8576 | 1 (443.7 / 443.7) | 4 | 0 (2/4) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0,GB_RAID=2 | v22r-raid | red | std | 6 | 0-1-5 | 0% | 1 | 2255 / 11196 | 0 (None / None) | 5 | 1 (0/4) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0,GB_RAID=2,GB_SAFERET=1 | v22 | blue | std | 6 | 2-0-4 | 33% | 3.5 | 4340 / 8358 | 1 (616.5 / 616.5) | 4 | 0 (2/4) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0,GB_RAID=2,GB_SAFERET=1 | v22 | red | std | 6 | 3-0-3 | 50% | 5.83 | 7555 / 5420 | 2 (765.1 / 701.7) | 3 | 1 (2/3) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0,GB_RAID=2,GB_SAFERET=1 | v22r-raid | blue | std | 6 | 2-1-3 | 33% | 4.17 | 5664 / 8639 | 1 (917.5 / 917.5) | 3 | 0 (2/3) |
| Grok Bot v23@GB_FAMDAY=0,GB_SREF=0,GB_FRESH=0,GB_RAID=2,GB_SAFERET=1 | v22r-raid | red | std | 6 | 0-0-6 | 0% | 0 | 0 / 10453 | 0 (None / None) | 6 | 0 (0/6) |
| Grok Bot v23@GB_FRESH=0 | v22 | blue | std | 6 | 2-0-4 | 33% | 3.17 | 3392 / 9611 | 1 (655.2 / 655.2) | 4 | 0 (2/4) |
| Grok Bot v23@GB_FRESH=0 | v22 | red | std | 6 | 1-0-5 | 17% | 3.17 | 3856 / 11335 | 1 (550.0 / 550.0) | 3 | 0 (1/5) |
| Grok Bot v23@GB_RAID=1 | v22 | blue | std | 12 | 10-0-2 | 83% | 10 | 8552 / 1425 | 10 (790.5 / 381.7) | 2 | 0 (10/2) |
| Grok Bot v23@GB_RAID=1 | v22 | red | std | 12 | 7-0-5 | 58% | 7.42 | 7732 / 4285 | 7 (643.5 / 529.4) | 4 | 0 (7/5) |
| Grok Bot v23@GB_RAID=1 | v22r-raid | blue | std | 6 | 2-0-4 | 33% | 4.83 | 3654 / 6642 | 2 (1070.9 / 609.5) | 3 | 0 (2/4) |
| Grok Bot v23@GB_RAID=1 | v22r-raid | red | std | 6 | 3-0-3 | 50% | 6 | 4521 / 3680 | 3 (516.1 / 484.0) | 3 | 0 (3/3) |
| Grok Bot v23@GB_RAID=2 | GPT dot Campaign600 v6 Feasible Relief | blue | gpt-v6-indep | 6 | 6-0-0 | 100% | 12 | 12673 / 0 | 6 (519.8 / 297.7) | 0 | 0 (6/0) |
| Grok Bot v23@GB_RAID=2 | GPT dot Campaign600 v6 Feasible Relief | blue | std | 6 | 6-0-0 | 100% | 12 | 13961 / 0 | 6 (604.5 / 330.9) | 0 | 0 (6/0) |
| Grok Bot v23@GB_RAID=2 | GPT dot Campaign600 v6 Feasible Relief | red | gpt-v6-indep | 6 | 6-0-0 | 100% | 12 | 13078 / 0 | 6 (587.9 / 276.9) | 0 | 0 (6/0) |
| Grok Bot v23@GB_RAID=2 | GPT dot Campaign600 v6 Feasible Relief | red | std | 6 | 6-0-0 | 100% | 12 | 13992 / 0 | 6 (671.8 / 444.6) | 0 | 0 (6/0) |
| Grok Bot v23@GB_RAID=2 | march (frozen default) | blue | std | 6 | 6-0-0 | 100% | 12 | 9882 / 0 | 6 (381.3 / 340.7) | 0 | 0 (6/0) |
| Grok Bot v23@GB_RAID=2 | march (frozen default) | red | std | 6 | 6-0-0 | 100% | 12 | 9670 / 0 | 6 (329.4 / 289.8) | 0 | 0 (6/0) |
| Grok Bot v23@GB_RAID=2 | v22 | blue | self | 6 | 3-1-2 | 50% | 7 | 8053 / 5970 | 3 (982.7 / 580.7) | 2 | 1 (2/2) |
| Grok Bot v23@GB_RAID=2 | v22 | blue | std | 12 | 9-2-1 | 75% | 10 | 8580 / 2786 | 9 (813.6 / 323.3) | 1 | 0 (9/1) |
| Grok Bot v23@GB_RAID=2 | v22 | red | self | 6 | 2-0-4 | 33% | 4 | 5838 / 8371 | 2 (1382.1 / 1341.6) | 4 | 0 (2/4) |
| Grok Bot v23@GB_RAID=2 | v22 | red | std | 12 | 8-0-4 | 67% | 7.58 | 9793 / 4559 | 7 (965.1 / 678.5) | 4 | 0 (8/4) |
| Grok Bot v23@GB_RAID=2 | v22r-raid | blue | std | 12 | 3-1-8 | 25% | 3.5 | 1943 / 5369 | 3 (811.3 / 567.2) | 8 | 0 (3/8) |
| Grok Bot v23@GB_RAID=2 | v22r-raid | red | std | 12 | 4-1-7 | 33% | 4.17 | 3695 / 6118 | 3 (866.1 / 713.5) | 7 | 0 (4/7) |
| Grok Bot v23@GB_RAID=3 | v22 | blue | std | 6 | 3-1-2 | 50% | 7 | 6133 / 5055 | 3 (559.2 / 426.0) | 2 | 0 (3/2) |
| Grok Bot v23@GB_RAID=3 | v22 | red | std | 6 | 5-0-1 | 83% | 10 | 8742 / 1564 | 5 (616.6 / 409.2) | 1 | 0 (5/1) |
| Grok Bot v23@GB_RAID=3 | v22r-raid | blue | std | 6 | 1-0-5 | 17% | 2 | 1048 / 8796 | 1 (843.0 / 843.0) | 5 | 0 (1/5) |
| Grok Bot v23@GB_RAID=3 | v22r-raid | red | std | 6 | 4-0-2 | 67% | 8 | 7030 / 3775 | 4 (788.8 / 495.3) | 2 | 0 (4/2) |
| Grok Bot v23@GB_RDEF=0 | v22r-raid | blue | std | 6 | 0-0-6 | 0% | 0 | 0 / 9849 | 0 (None / None) | 6 | 0 (0/6) |
| Grok Bot v23@GB_RDEF=0 | v22r-raid | red | std | 6 | 2-0-4 | 33% | 4 | 4047 / 7414 | 2 (733.5 / 665.8) | 4 | 0 (2/4) |
| Grok Bot v23@GB_RDEF=2 | v22r-raid | blue | std | 6 | 0-0-6 | 0% | 0 | 0 / 9849 | 0 (None / None) | 6 | 0 (0/6) |
| Grok Bot v23@GB_RDEF=2 | v22r-raid | red | std | 6 | 2-0-4 | 33% | 4 | 4051 / 6969 | 2 (725.3 / 665.8) | 4 | 0 (2/4) |
| Grok Bot v23@GB_RDEF=3 | v22r-raid | blue | std | 6 | 0-0-6 | 0% | 0 | 0 / 9849 | 0 (None / None) | 6 | 0 (0/6) |
| Grok Bot v23@GB_RDEF=3 | v22r-raid | red | std | 6 | 2-0-4 | 33% | 4 | 4051 / 7414 | 2 (725.4 / 665.8) | 4 | 0 (2/4) |
| Grok Bot v23@GB_SREF=0 | v22 | blue | std | 6 | 3-0-3 | 50% | 5.33 | 5898 / 8043 | 2 (934.2 / 635.4) | 3 | 0 (3/3) |
| Grok Bot v23@GB_SREF=0 | v22 | red | std | 6 | 1-0-5 | 17% | 2 | 1790 / 11987 | 1 (482.1 / 482.1) | 5 | 0 (1/5) |
| Grok Bot v24 | GPT dot Campaign600 v6 Feasible Relief | blue | std | 6 | 6-0-0 | 100% | 12 | 13372 / 0 | 6 (620.4 / 421.5) | 0 | 0 (6/0) |
| Grok Bot v24 | GPT dot Campaign600 v6 Feasible Relief | red | std | 6 | 6-0-0 | 100% | 12 | 13283 / 0 | 6 (595.5 / 415.4) | 0 | 0 (6/0) |
| Grok Bot v24 | march (frozen default) | blue | std | 6 | 6-0-0 | 100% | 12 | 9180 / 0 | 6 (388.5 / 285.8) | 0 | 0 (6/0) |
| Grok Bot v24 | march (frozen default) | red | std | 6 | 6-0-0 | 100% | 12 | 9443 / 0 | 6 (327.8 / 253.2) | 0 | 0 (6/0) |
| Grok Bot v24 | v22r-raid | blue | std | 12 | 6-1-5 | 50% | 6.08 | 3810 / 3726 | 5 (856.4 / 382.0) | 5 | 0 (6/5) |
| Grok Bot v24 | v22r-raid | red | std | 12 | 6-0-6 | 50% | 5.17 | 5433 / 6692 | 3 (689.7 / 659.1) | 6 | 1 (5/6) |
| Grok Bot v24 | v23 | blue | self | 6 | 4-0-2 | 67% | 8.17 | 7879 / 2389 | 3 (881.6 / 760.7) | 1 | 0 (4/2) |
| Grok Bot v24 | v23 | blue | std | 12 | 5-0-7 | 42% | 4.75 | 3698 / 5306 | 4 (587.9 / 406.8) | 7 | 1 (4/7) |
| Grok Bot v24 | v23 | red | self | 6 | 1-1-4 | 17% | 3 | 5732 / 8572 | 1 (1665.5 / 1665.5) | 4 | 0 (1/4) |
| Grok Bot v24 | v23 | red | std | 12 | 9-0-3 | 75% | 9 | 6526 / 2162 | 9 (729.2 / 418.8) | 3 | 1 (9/2) |
| Grok Bot v24@GB_TINT=0 | v22r-raid | blue | std | 6 | 3-0-3 | 50% | 6 | 4023 / 2760 | 3 (685.4 / 383.1) | 3 | 0 (3/3) |
| Grok Bot v24@GB_TINT=0 | v22r-raid | red | std | 6 | 4-0-2 | 67% | 7.33 | 7866 / 4803 | 3 (1220.3 / 724.3) | 2 | 0 (4/2) |
| Grok Bot v24@GB_TSTATE=0 | v22r-raid | blue | std | 6 | 4-0-2 | 67% | 8 | 5854 / 1904 | 4 (677.6 / 383.1) | 2 | 0 (4/2) |
| Grok Bot v24@GB_TSTATE=0 | v22r-raid | red | std | 6 | 4-0-2 | 67% | 6.5 | 6221 / 6536 | 2 (691.7 / 659.1) | 2 | 0 (4/2) |
| Grok Bot v25 | ar3 | blue | gpt-v6-indep | 16 | 16-0-0 | 100% | 12 | 5836 / 0 | 16 (423.8 / 312.2) | 0 | 0 (16/0) |
| Grok Bot v25 | ar3 | red | gpt-v6-indep | 16 | 16-0-0 | 100% | 12 | 5365 / 0 | 16 (507.1 / 323.0) | 0 | 0 (16/0) |
| Grok Bot v25 | ar5 | blue | gpt-v6-indep | 5 | 2-0-3 | 40% | 5.8 | 2984 / 4151 | 2 (676.9 / 474.4) | 2 | 0 (2/3) |
| Grok Bot v25 | ar5 | red | gpt-v6-indep | 5 | 2-0-3 | 40% | 4.8 | 1615 / 3771 | 2 (704.7 / 543.9) | 3 | 0 (2/3) |
| Grok Bot v25@GB_REV=2 | ar3 | blue | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 6965 / 0 | 5 (355.0 / 288.7) | 0 | 0 (5/0) |
| Grok Bot v25@GB_REV=2 | ar3 | red | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 6133 / 0 | 5 (372.3 / 341.0) | 0 | 0 (5/0) |
| Grok Bot v25@GB_REV=2 | ar5 | blue | gpt-v6-indep | 5 | 3-0-2 | 60% | 7.8 | 4483 / 2275 | 3 (684.3 / 444.3) | 1 | 0 (3/2) |
| Grok Bot v25@GB_REV=2 | ar5 | red | gpt-v6-indep | 5 | 3-0-2 | 60% | 6.2 | 2422 / 4126 | 2 (867.4 / 326.2) | 2 | 0 (3/2) |
| Grok Bot v25@GB_REV=2 | v22 | blue | std | 6 | 5-0-1 | 83% | 10 | 5956 / 1728 | 5 (610.2 / 372.5) | 1 | 0 (5/1) |
| Grok Bot v25@GB_REV=2 | v22 | red | std | 6 | 2-0-4 | 33% | 4.17 | 2057 / 3536 | 2 (609.5 / 508.6) | 3 | 0 (2/4) |
| Grok Bot v25@GB_REV=3 | ar5 | blue | gpt-v6-indep | 1 | 0-0-1 | 0% | 3 | 3770 / 6225 | 0 (None / None) | 0 | 0 (0/1) |
| Grok Bot v26 | ar5 | blue | gpt-v6-indep | 5 | 3-0-2 | 60% | 7.8 | 4107 / 2506 | 3 (531.6 / 498.3) | 1 | 0 (3/2) |
| Grok Bot v26 | ar5 | blue | std | 12 | 5-0-7 | 42% | 5.58 | 2905 / 3431 | 4 (753.1 / 460.2) | 4 | 0 (5/7) |
| Grok Bot v26 | ar5 | red | gpt-v6-indep | 5 | 2-0-3 | 40% | 5 | 2252 / 3175 | 2 (455.4 / 441.1) | 2 | 0 (2/3) |
| Grok Bot v26 | ar5 | red | std | 12 | 8-0-4 | 67% | 8 | 3372 / 1944 | 8 (640.8 / 346.0) | 4 | 0 (8/4) |
| Grok Bot v26 | hy | blue | gpt-v6-indep | 5 | 2-0-3 | 40% | 4.8 | 2610 / 2680 | 2 (435.5 / 348.0) | 3 | 1 (2/2) |
| Grok Bot v26 | hy | blue | std | 12 | 4-0-8 | 33% | 4 | 2041 / 2425 | 4 (411.9 / 345.3) | 8 | 0 (4/8) |
| Grok Bot v26 | hy | red | gpt-v6-indep | 5 | 0-0-5 | 0% | 0 | 0 / 3495 | 0 (None / None) | 5 | 2 (0/3) |
| Grok Bot v26 | hy | red | std | 12 | 1-0-11 | 8% | 1 | 463 / 3420 | 1 (415.1 / 415.1) | 11 | 0 (1/11) |
| Grok Bot v26 | v22 | blue | std | 6 | 5-0-1 | 83% | 10 | 6460 / 1473 | 5 (529.2 / 372.9) | 1 | 0 (5/1) |
| Grok Bot v26 | v22 | red | std | 6 | 1-1-4 | 17% | 3.83 | 1194 / 3793 | 1 (508.6 / 508.6) | 2 | 1 (1/3) |
| Grok Bot v26 | v23 | blue | std | 6 | 4-0-2 | 67% | 8 | 4908 / 2760 | 4 (576.0 / 424.8) | 2 | 0 (4/2) |
| Grok Bot v26 | v23 | red | std | 6 | 4-0-2 | 67% | 8 | 4039 / 2396 | 4 (777.8 / 484.1) | 2 | 1 (4/1) |
| Grok Bot v27 | ar3 | blue | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 6567 / 0 | 5 (357.8 / 287.6) | 0 | 0 (5/0) |
| Grok Bot v27 | ar3 | blue | std | 12 | 12-0-0 | 100% | 12 | 6252 / 0 | 12 (404.7 / 281.8) | 0 | 0 (12/0) |
| Grok Bot v27 | ar3 | red | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 6641 / 0 | 5 (376.7 / 318.1) | 0 | 0 (5/0) |
| Grok Bot v27 | ar3 | red | std | 12 | 12-0-0 | 100% | 11.92 | 5156 / 4 | 11 (356.2 / 286.0) | 0 | 0 (12/0) |
| Grok Bot v27 | ar5 | blue | gpt-v6-indep | 5 | 1-0-4 | 20% | 3.2 | 1778 / 5168 | 1 (482.5 / 482.5) | 3 | 0 (1/4) |
| Grok Bot v27 | ar5 | blue | std | 12 | 11-0-1 | 92% | 11.08 | 5466 / 726 | 11 (485.3 / 355.8) | 0 | 0 (11/1) |
| Grok Bot v27 | ar5 | red | gpt-v6-indep | 5 | 2-0-3 | 40% | 4.8 | 2346 / 3105 | 2 (634.6 / 534.3) | 3 | 0 (2/3) |
| Grok Bot v27 | ar5 | red | std | 12 | 11-0-1 | 92% | 11.08 | 5939 / 339 | 11 (482.1 / 266.3) | 0 | 0 (11/1) |
| Grok Bot v27 | ar6 | blue | std | 12 | 10-1-1 | 83% | 9.58 | 7435 / 1362 | 7 (747.6 / 353.8) | 1 | 0 (10/1) |
| Grok Bot v27 | ar6 | red | std | 12 | 11-0-1 | 92% | 11 | 5091 / 357 | 11 (472.4 / 285.3) | 1 | 0 (11/1) |
| Grok Bot v27 | GPT dot Campaign600 v4 Early Relief | blue | std | 6 | 6-0-0 | 100% | 12 | 9552 / 0 | 6 (401.6 / 324.2) | 0 | 0 (6/0) |
| Grok Bot v27 | GPT dot Campaign600 v4 Early Relief | red | std | 6 | 6-0-0 | 100% | 12 | 9656 / 0 | 6 (489.6 / 380.1) | 0 | 0 (6/0) |
| Grok Bot v27 | GPT dot Campaign600 v6 Feasible Relief | blue | std | 6 | 6-0-0 | 100% | 12 | 10009 / 0 | 6 (443.3 / 278.6) | 0 | 0 (6/0) |
| Grok Bot v27 | GPT dot Campaign600 v6 Feasible Relief | red | std | 6 | 6-0-0 | 100% | 12 | 10172 / 0 | 6 (598.6 / 456.8) | 0 | 0 (6/0) |
| Grok Bot v27 | hy | blue | gpt-v6-indep | 5 | 2-0-3 | 40% | 4.8 | 2630 / 2207 | 2 (436.1 / 327.2) | 3 | 0 (2/3) |
| Grok Bot v27 | hy | blue | std | 24 | 10-0-14 | 42% | 5 | 2477 / 2339 | 10 (624.7 / 360.3) | 14 | 0 (10/14) |
| Grok Bot v27 | hy | red | gpt-v6-indep | 5 | 0-0-5 | 0% | 0 | 0 / 3569 | 0 (None / None) | 5 | 0 (0/5) |
| Grok Bot v27 | hy | red | std | 24 | 11-0-13 | 46% | 5.62 | 2489 / 2415 | 10 (608.5 / 285.5) | 11 | 0 (11/13) |
| Grok Bot v27 | Grok Bot v20 | blue | std | 6 | 6-0-0 | 100% | 12 | 9270 / 0 | 6 (420.2 / 253.7) | 0 | 0 (6/0) |
| Grok Bot v27 | Grok Bot v20 | red | std | 6 | 6-0-0 | 100% | 12 | 9773 / 0 | 6 (430.9 / 296.3) | 0 | 0 (6/0) |
| Grok Bot v27 | v22 | blue | std | 6 | 6-0-0 | 100% | 12 | 8836 / 0 | 6 (656.0 / 461.0) | 0 | 0 (6/0) |
| Grok Bot v27 | v22 | red | std | 6 | 5-0-1 | 83% | 10 | 7065 / 969 | 5 (524.1 / 439.3) | 1 | 0 (5/1) |
| Grok Bot v27 | v23 | blue | std | 6 | 6-0-0 | 100% | 12 | 9216 / 0 | 6 (572.8 / 308.6) | 0 | 0 (6/0) |
| Grok Bot v27 | v23 | red | std | 6 | 5-0-1 | 83% | 10 | 7431 / 702 | 5 (725.8 / 574.7) | 1 | 0 (5/1) |
| Grok Bot v27dev | hy | blue | gpt-v6-indep | 5 | 3-0-2 | 60% | 7.2 | 3780 / 1677 | 3 (797.7 / 424.6) | 2 | 0 (3/2) |
| Grok Bot v27dev | hy | red | gpt-v6-indep | 5 | 1-0-4 | 20% | 2.4 | 847 / 3044 | 1 (552.3 / 552.3) | 4 | 0 (1/4) |
| Grok Bot v27dev@GB_MOBANC=0 | hy | blue | gpt-v6-indep | 5 | 3-0-2 | 60% | 7.2 | 3901 / 1630 | 3 (363.2 / 321.9) | 2 | 0 (3/2) |
| Grok Bot v27dev@GB_MOBANC=0 | hy | red | gpt-v6-indep | 5 | 0-0-5 | 0% | 0 | 0 / 3662 | 0 (None / None) | 5 | 0 (0/5) |
| Grok Bot v27dev@GB_REV=2 | hy | blue | gpt-v6-indep | 5 | 3-0-2 | 60% | 7.2 | 3676 / 1682 | 3 (522.1 / 424.6) | 2 | 0 (3/2) |
| Grok Bot v27dev@GB_REV=2 | hy | red | gpt-v6-indep | 5 | 1-0-4 | 20% | 2.4 | 1122 / 2952 | 1 (614.0 / 614.0) | 4 | 0 (1/4) |
| Grok Bot v27dev@GB_REV=3 | hy | blue | gpt-v6-indep | 5 | 3-0-2 | 60% | 7.2 | 3502 / 2241 | 3 (719.6 / 408.8) | 2 | 0 (3/2) |
| Grok Bot v27dev@GB_REV=3 | hy | red | gpt-v6-indep | 5 | 0-0-5 | 0% | 0 | 0 / 3901 | 0 (None / None) | 5 | 0 (0/5) |
| Grok Bot v27dev@GB_REV=4 | hy | blue | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 5801 / 0 | 5 (617.2 / 279.7) | 0 | 0 (5/0) |
| Grok Bot v27dev@GB_REV=4 | hy | red | gpt-v6-indep | 5 | 1-0-4 | 20% | 2.4 | 793 / 2590 | 1 (337.6 / 337.6) | 4 | 0 (1/4) |
| Grok Bot v27dev@GB_X=1 | hy | red | gpt-v6-indep | 1 | 0-0-1 | 0% | 0 | 0 / 3195 | 0 (None / None) | 1 | 0 (0/1) |
| Grok Bot v27dev@GB_X=3 | hy | red | gpt-v6-indep | 1 | 0-0-1 | 0% | 0 | 0 / 4820 | 0 (None / None) | 1 | 0 (0/1) |
| Grok Bot v27r5 | ar3 | blue | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 6140 / 0 | 5 (354.6 / 333.3) | 0 | 0 (5/0) |
| Grok Bot v27r5 | ar3 | red | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 5655 / 0 | 5 (381.4 / 290.6) | 0 | 0 (5/0) |
| Grok Bot v27r5 | ar5 | blue | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 6271 / 0 | 5 (506.5 / 383.5) | 0 | 0 (5/0) |
| Grok Bot v27r5 | ar5 | red | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 5449 / 0 | 5 (628.5 / 497.2) | 0 | 0 (5/0) |
| Grok Bot v27r5 | hy | blue | gpt-v6-indep | 5 | 4-0-1 | 80% | 9.6 | 4380 / 803 | 4 (476.9 / 282.0) | 1 | 0 (4/1) |
| Grok Bot v27r5 | hy | red | gpt-v6-indep | 5 | 2-0-3 | 40% | 4.8 | 1914 / 2598 | 2 (381.7 / 337.6) | 3 | 0 (2/3) |
| Grok Bot v27r5 | v22 | blue | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 8489 / 0 | 5 (589.3 / 501.8) | 0 | 0 (5/0) |
| Grok Bot v27r5 | v22 | red | gpt-v6-indep | 5 | 3-0-2 | 60% | 7.2 | 4812 / 2820 | 3 (515.8 / 330.9) | 2 | 0 (3/2) |
| Grok Bot v27r5 | v23 | blue | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 9264 / 0 | 5 (734.1 / 512.6) | 0 | 0 (5/0) |
| Grok Bot v27r5 | v23 | red | gpt-v6-indep | 5 | 5-0-0 | 100% | 12 | 8167 / 0 | 5 (638.9 / 400.2) | 0 | 0 (5/0) |
| Grok Bot v28a | hy | blue | std | 12 | 5-0-7 | 42% | 5 | 2532 / 2466 | 5 (578.2 / 310.9) | 7 | 0 (5/7) |
| Grok Bot v28a | hy | red | std | 12 | 6-0-6 | 50% | 6 | 2824 / 1887 | 6 (526.3 / 307.7) | 6 | 0 (6/6) |
| Grok Bot v28b | ar3 | blue | std | 6 | 6-0-0 | 100% | 12 | 5632 / 0 | 6 (364.4 / 283.8) | 0 | 0 (6/0) |
| Grok Bot v28b | ar3 | red | std | 6 | 6-0-0 | 100% | 12 | 5836 / 0 | 6 (338.3 / 237.9) | 0 | 0 (6/0) |
| Grok Bot v28b | ar5 | blue | std | 12 | 10-0-2 | 83% | 10 | 5518 / 952 | 10 (414.1 / 277.3) | 2 | 0 (10/2) |
| Grok Bot v28b | ar5 | red | std | 12 | 11-0-1 | 92% | 11 | 5629 / 358 | 11 (397.6 / 319.6) | 1 | 0 (11/1) |
| Grok Bot v28b | ar6 | blue | std | 12 | 10-0-2 | 83% | 9.83 | 5440 / 1238 | 9 (530.8 / 249.3) | 2 | 1 (9/2) |
| Grok Bot v28b | ar6 | red | std | 12 | 11-0-1 | 92% | 10.58 | 6931 / 611 | 10 (555.8 / 312.7) | 1 | 0 (11/1) |
| Grok Bot v28b | hy | blue | std | 24 | 12-0-12 | 50% | 6 | 3002 / 2308 | 12 (556.5 / 317.2) | 12 | 0 (12/12) |
| Grok Bot v28b | hy | red | std | 24 | 11-0-13 | 46% | 5.54 | 2517 / 2101 | 11 (600.1 / 307.7) | 12 | 0 (11/13) |
| Grok Bot v28b | v22 | blue | std | 6 | 6-0-0 | 100% | 12 | 8891 / 0 | 6 (656.1 / 461.0) | 0 | 0 (6/0) |
| Grok Bot v28b | v22 | red | std | 6 | 5-0-1 | 83% | 10 | 7003 / 924 | 5 (523.4 / 439.2) | 1 | 0 (5/1) |
| Grok Bot v28b | v23 | blue | std | 6 | 6-0-0 | 100% | 12 | 9194 / 0 | 6 (608.4 / 308.6) | 0 | 0 (6/0) |
| Grok Bot v28b | v23 | red | std | 6 | 6-0-0 | 100% | 12 | 8304 / 0 | 6 (704.8 / 574.7) | 0 | 0 (6/0) |
| Grok Bot v29 | ar3 | blue | std | 6 | 6-0-0 | 100% | 12 | 6092 / 0 | 6 (470.6 / 298.5) | 0 | 0 (6/0) |
| Grok Bot v29 | ar3 | red | std | 6 | 4-0-2 | 67% | 8 | 4246 / 1957 | 4 (408.9 / 354.8) | 2 | 0 (4/2) |
| Grok Bot v29 | ar5 | blue | std | 12 | 12-0-0 | 100% | 12 | 6257 / 0 | 12 (498.8 / 279.4) | 0 | 0 (12/0) |
| Grok Bot v29 | ar5 | red | std | 12 | 11-0-1 | 92% | 11 | 5017 / 305 | 11 (493.5 / 257.3) | 1 | 0 (11/1) |
| Grok Bot v29 | v22 | blue | std | 6 | 6-0-0 | 100% | 12 | 9162 / 0 | 6 (549.4 / 413.0) | 0 | 0 (6/0) |
| Grok Bot v29 | v22 | red | std | 6 | 5-0-1 | 83% | 10 | 8179 / 1544 | 5 (641.2 / 439.6) | 1 | 0 (5/1) |
| Grok Bot v29 | v23 | blue | std | 6 | 6-0-0 | 100% | 12 | 8639 / 0 | 6 (647.9 / 421.9) | 0 | 0 (6/0) |
| Grok Bot v29 | v23 | red | std | 6 | 5-1-0 | 83% | 11 | 8196 / 2128 | 5 (757.0 / 421.1) | 0 | 0 (5/0) |
| Grok Bot v29a | hy | blue | std | 24 | 12-0-12 | 50% | 6 | 2947 / 2322 | 12 (527.8 / 293.0) | 12 | 0 (12/12) |
| Grok Bot v29a | hy | red | std | 24 | 11-0-13 | 46% | 5.5 | 2510 / 2038 | 11 (599.8 / 306.7) | 13 | 0 (11/13) |
| Grok Bot v29c | ar5 | blue | std | 12 | 11-0-1 | 92% | 11 | 6108 / 608 | 11 (556.5 / 376.5) | 1 | 0 (11/1) |
| Grok Bot v29c | ar5 | red | std | 12 | 11-0-1 | 92% | 10.67 | 5254 / 591 | 10 (455.8 / 292.3) | 1 | 0 (11/1) |
| Grok Bot v29c | ar6 | blue | std | 12 | 8-0-4 | 67% | 7.58 | 4100 / 2181 | 6 (810.5 / 523.2) | 4 | 1 (8/3) |
| Grok Bot v29c | ar6 | red | std | 12 | 7-0-5 | 58% | 7.08 | 3442 / 2449 | 7 (569.3 / 394.3) | 4 | 0 (7/5) |
| Grok Bot v29c | hy | blue | std | 24 | 15-0-9 | 62% | 7.5 | 3947 / 1456 | 15 (458.2 / 321.4) | 9 | 0 (15/9) |
| Grok Bot v29c | hy | red | std | 24 | 13-0-11 | 54% | 6.5 | 3180 / 1791 | 13 (440.0 / 288.2) | 11 | 0 (13/11) |
| Grok Bot v29d | ar6 | blue | std | 12 | 6-0-6 | 50% | 5.83 | 4190 / 2854 | 5 (925.2 / 440.6) | 5 | 0 (6/6) |
| Grok Bot v29d | ar6 | red | std | 12 | 10-0-2 | 83% | 9.75 | 5122 / 1104 | 9 (395.1 / 283.5) | 2 | 1 (10/1) |
| Grok Bot v29d | hy | blue | std | 24 | 10-0-14 | 42% | 5.08 | 2681 / 2648 | 9 (475.2 / 305.5) | 13 | 0 (10/14) |
| Grok Bot v29d | hy | red | std | 24 | 12-0-12 | 50% | 6 | 3095 / 1931 | 12 (456.3 / 272.7) | 12 | 0 (12/12) |
| Grok Bot v29e | ar6 | blue | std | 12 | 9-0-3 | 75% | 7.75 | 6476 / 2075 | 5 (510.2 / 391.1) | 3 | 0 (9/3) |
| Grok Bot v29e | ar6 | red | std | 12 | 11-0-1 | 92% | 10.83 | 5663 / 813 | 10 (454.9 / 283.5) | 1 | 0 (11/1) |
| Grok Bot v29e@GB_HOLDMAX=999,GB_HOLDNEAR=0 | ar6 | blue | std | 12 | 9-0-3 | 75% | 8.92 | 6187 / 1534 | 8 (849.9 / 523.7) | 3 | 0 (9/3) |
| Grok Bot v29e@GB_HOLDMAX=999,GB_HOLDNEAR=0 | ar6 | red | std | 12 | 8-1-3 | 67% | 8.58 | 4225 / 1666 | 8 (500.1 / 393.8) | 2 | 0 (8/3) |
| Grok Bot v29e@GB_HOLDMAX=999,GB_HOLDNEAR=0 | hy | blue | std | 24 | 13-0-11 | 54% | 6.5 | 3464 / 1944 | 13 (450.6 / 320.4) | 11 | 0 (13/11) |
| Grok Bot v29e@GB_HOLDMAX=999,GB_HOLDNEAR=0 | hy | red | std | 24 | 12-0-12 | 50% | 6 | 2901 / 1984 | 12 (437.9 / 266.8) | 12 | 0 (12/12) |
| Grok Bot v29f | ar6 | blue | std | 12 | 9-0-3 | 75% | 8.5 | 4275 / 2080 | 7 (679.0 / 461.9) | 3 | 0 (9/3) |
| Grok Bot v29f | ar6 | red | std | 12 | 12-0-0 | 100% | 11.17 | 6062 / 537 | 9 (597.9 / 253.1) | 0 | 0 (12/0) |
| Grok Bot v29f | hy | blue | std | 24 | 12-0-12 | 50% | 6 | 2954 / 2132 | 12 (528.6 / 328.3) | 12 | 0 (12/12) |
| Grok Bot v29f | hy | red | std | 24 | 11-0-13 | 46% | 5.5 | 2419 / 2273 | 11 (476.8 / 301.8) | 13 | 2 (11/11) |
| Grok Bot v29f@GB_HOLDMAX=8,GB_HOLDNEAR=0.5 | ar6 | blue | std | 12 | 7-0-5 | 58% | 7.17 | 4006 / 2748 | 7 (656.2 / 347.2) | 4 | 0 (7/5) |
| Grok Bot v29f@GB_HOLDMAX=8,GB_HOLDNEAR=0.5 | ar6 | red | std | 12 | 10-0-2 | 83% | 9.33 | 5021 / 1182 | 8 (604.5 / 289.2) | 2 | 0 (10/2) |
| Grok Bot v9 | GPT dot Campaign600 v1 | blue | std | 12 | 12-0-0 | 100% | 11.25 | 27714 / 3132 | 3 (957.4 / 665.5) | 0 | 0 (12/0) |
| Grok Bot v9 | GPT dot Campaign600 v1 | red | std | 12 | 11-0-1 | 92% | 10.67 | 25250 / 2303 | 7 (1202.1 / 970.3) | 1 | 0 (11/1) |
