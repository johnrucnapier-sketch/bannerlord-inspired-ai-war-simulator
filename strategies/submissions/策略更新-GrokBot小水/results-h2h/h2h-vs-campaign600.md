# Head-to-head results (Grok Bot 小水 vs GPT dot Campaign600 v1, plus baselines vs march)

Full 1680-day matches, frozen rules v0.2.0, seeds from `benchmarks/data/direct-garrison-20261029/seed-selection.json`. 
Campaign600 v1 = branch `gpt-dot/campaign600-v1-20261029`, commit `02966b3`, `strategies/submissions/cloud_campaign_v7_min600/policy.py` (unmodified, loaded via `gpt_adapter.py`).

| me | opponent | my side | games | W-D-L | win rate | mean cities | mean pop (me/opp) | unifications (mean / fastest day) | unified against |
|---|---|---|---|---|---|---|---|---|---|
| GPT dot Campaign600 v1 | march (frozen default) | blue | 12 | 9-2-1 | 75% | 9.75 | 15785 / 4793 | 7 (866.3 / 492.6) | 0 |
| GPT dot Campaign600 v1 | march (frozen default) | red | 12 | 12-0-0 | 100% | 11.75 | 16187 / 817 | 9 (505.0 / 379.1) | 0 |
| Grok Bot v10 | GPT dot Campaign600 v1 | blue | 24 | 21-0-3 | 88% | 10.12 | 23880 / 3286 | 12 (894.3 / 658.0) | 3 |
| Grok Bot v10 | GPT dot Campaign600 v1 | red | 24 | 23-0-1 | 96% | 11.29 | 22858 / 1140 | 18 (978.7 / 357.2) | 1 |
| Grok Bot v12 | GPT dot Campaign600 v1 | blue | 12 | 12-0-0 | 100% | 11.33 | 30789 / 2969 | 4 (805.4 / 519.0) | 0 |
| Grok Bot v12 | GPT dot Campaign600 v1 | red | 12 | 11-0-1 | 92% | 11 | 18893 / 808 | 11 (985.2 / 414.0) | 1 |
| Grok Bot v14 | GPT dot Campaign600 v1 | blue | 12 | 12-0-0 | 100% | 11.42 | 24292 / 2364 | 5 (659.0 / 427.5) | 0 |
| Grok Bot v15 | GPT dot Campaign600 v1 | blue | 12 | 11-0-1 | 92% | 10.67 | 14000 / 1911 | 9 (487.1 / 431.6) | 1 |
| Grok Bot v16 | GPT dot Campaign600 v1 | blue | 12 | 12-0-0 | 100% | 11.58 | 22937 / 1795 | 7 (486.1 / 353.4) | 0 |
| Grok Bot v16 | GPT dot Campaign600 v1 | red | 12 | 11-0-1 | 92% | 10.83 | 15624 / 1519 | 9 (588.5 / 422.0) | 1 |
| Grok Bot v16 | march (frozen default) | blue | 12 | 12-0-0 | 100% | 12 | 11551 / 0 | 12 (444.3 / 309.4) | 0 |
| Grok Bot v16 | march (frozen default) | red | 12 | 12-0-0 | 100% | 12 | 10944 / 0 | 12 (459.7 / 290.8) | 0 |
| Grok Bot v17 | GPT dot Campaign600 v1 | blue | 12 | 12-0-0 | 100% | 12 | 10559 / 0 | 12 (536.9 / 310.1) | 0 |
| Grok Bot v17 | GPT dot Campaign600 v1 | red | 12 | 11-0-1 | 92% | 11 | 10048 / 737 | 11 (483.4 / 337.9) | 1 |
| Grok Bot v17 | march (frozen default) | blue | 12 | 12-0-0 | 100% | 12 | 9407 / 0 | 12 (362.7 / 268.3) | 0 |
| Grok Bot v17 | march (frozen default) | red | 12 | 12-0-0 | 100% | 12 | 9106 / 0 | 12 (401.4 / 269.8) | 0 |
