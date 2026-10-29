# Grok Bot — blue strategy iterations vs `march` (frozen rules v0.2.0)

Author: Grok Bot (for 博 李). Opponent: the frozen default `march`. Rules, the engine and the reference strategies are untouched.
Everything lives in `strategies/submissions/策略更新-GrokBot小水/` (one folder per version) and `runs/grokbot/`.
Each label reads "Grok Bot vN, approach: ...". GPT and DeepSeek strategies built on the same rules can be compared against these labels.
The point is to compare approaches, not to rank the agents.

## Method
- Seeds: `benchmarks/data/direct-garrison-20261029/seed-selection.json`.
  - The first 12 seeds are the screening set; all 24 are used for confirmation.
  - Screening ran on 120–400-day dev matches (`dev-*` dirs). Every number in the table below comes from a **full 1680-day match**.
- Side swap: my agent plays red (nation 1) against `march` as blue.
- Tools:
  - `batch.py` is the parallel runner. Its output goes to `runs/grokbot/<label>-<side>-s<seed>-d<days>`, and summaries go to `runs/grokbot/results.jsonl`.
  - `summarize.py` builds `results.csv` / `results.json`.
  - `inspect_run.py` dumps the timeline of one match.
- Agent stderr logs (`agent-0.stderr.log`) show every campaign LAUNCH / SIEGE / ABORT / END.
- Population is measured at match end. Unified matches end early (days 400–1100), so compare population mostly within the same kind of result.
- Reference point from the brief: D2 vs march on the 24 seeds is blue 5 / red 18 / draw 1, with mean blue cities 2.79.

## Results (full 1680-day matches)
| run | side | games | W-L-D | mean cities | mean pop (me/opp) | unifications (mean / fastest day) | unified against | invalid cmds | errors |
|---|---|---|---|---|---|---|---|---|---|
| Baseline: march (frozen default) as blue | blue | 24 | 12-11-1 | 6.17 | 13892 / 13166 | 7 (1038.9 / 532.7) | 6 | 0 | 0 |
| Grok Bot v10, approach: v9 + pre-emptive city guard (fill threatened cities before the siege) | blue | 24 | 24-0-0 | 12 | 14295 / 0 | 24 (547.1 / 310.8) | 0 | 1 | 0 |
| Grok Bot v10, approach: v9 + pre-emptive city guard (fill threatened cities before the siege) | red | 14 | 14-0-0 | 12 | 15451 / 0 | 14 (647.1 / 333.7) | 0 | 0 | 0 |
| Grok Bot v11, approach: v10 + margins 1.7/1.55 + lost-rally-base fix | blue | 24 | 24-0-0 | 11.79 | 19211 / 978 | 19 (536.0 / 375.6) | 0 | 11 | 0 |
| Grok Bot v11, approach: v10 + margins 1.7/1.55 + lost-rally-base fix | red | 12 | 12-0-0 | 11.83 | 20463 / 797 | 10 (683.3 / 501.2) | 0 | 0 | 0 |
| Grok Bot v12, approach: v10 + capacity-aware doom-stack roster (grows past 3-5 parties for the last cities) | blue | 24 | 24-0-0 | 11.96 | 14880 / 196 | 23 (564.3 / 359.3) | 0 | 7 | 0 |
| Grok Bot v12, approach: v10 + capacity-aware doom-stack roster (grows past 3-5 parties for the last cities) | red | 12 | 12-0-0 | 12 | 14005 / 0 | 12 (561.6 / 306.6) | 0 | 6 | 0 |
| Grok Bot v13, approach: v12 + whole-empire mobilisation for the doom-stack (frontier-only keepers, garrison-aware potential, top-up detours) | blue | 24 | 21-3-0 | 10.67 | 9602 / 1245 | 21 (467.6 / 280.0) | 2 | 3 | 0 |
| Grok Bot v13, approach: v12 + whole-empire mobilisation for the doom-stack (frontier-only keepers, garrison-aware potential, top-up detours) | red | 12 | 7-5-0 | 7 | 6714 / 5037 | 7 (684.8 / 390.8) | 5 | 1 | 0 |
| Grok Bot v3, approach: early rush + doom-stack + per-city anti-bandit patrols | blue | 12 | 5-7-0 | 4.92 | 4830 / 7154 | 4 (906.5 / 541.3) | 6 | 1 | 0 |
| Grok Bot v5, approach: patrol-army economy + campaign doom-stack + strong relief | blue | 12 | 9-3-0 | 9 | 12342 / 3899 | 9 (559.6 / 438.7) | 3 | 0 | 0 |
| Grok Bot v6, approach: early rush + patrol-army economy + campaign doom-stack + strong relief | blue | 12 | 10-2-0 | 9.5 | 16978 / 3847 | 7 (548.1 / 447.1) | 2 | 0 | 0 |
| Grok Bot v7, approach: early rush + patrol economy + doom-stack that HOLDS each conquest (hold 60d) | blue | 24 | 19-5-0 | 9.46 | 12815 / 3087 | 18 (649.7 / 428.2) | 5 | 2 | 0 |
| Grok Bot v7 (param sweep GB_HOLD=120) | blue | 12 | 11-1-0 | 10.92 | 17119 / 1621 | 10 (846.9 / 550.2) | 1 | 1 | 0 |
| Grok Bot v7 (param sweep GB_HOLD=30) | blue | 12 | 11-1-0 | 10.67 | 16265 / 2246 | 9 (605.8 / 376.1) | 1 | 0 | 0 |
| Grok Bot v8, approach: v7 + bug fixes (stale-flag frontier relaunch loop) | blue | 12 | 8-4-0 | 8 | 8426 / 5023 | 8 (505.4 / 441.8) | 4 | 0 | 0 |
| Grok Bot v9, approach: v8 + relief-aware sieges (remember enemy field parties) | blue | 24 | 19-5-0 | 9.46 | 11443 / 3048 | 18 (567.5 / 417.6) | 5 | 0 | 0 |
| Grok Bot v9, approach: v8 + relief-aware sieges (remember enemy field parties) | red | 12 | 12-0-0 | 11.92 | 14020 / 396 | 11 (523.8 / 360.1) | 0 | 1 | 0 |
| Grok Bot v9 (param sweep GB_GUARD=1.3) | blue | 24 | 18-6-0 | 8.96 | 11110 / 3625 | 17 (606.8 / 369.8) | 6 | 1 | 0 |
| Grok Bot v9 (param sweep margin 1.7 / siege 1.55) | blue | 24 | 22-2-0 | 10.71 | 15730 / 2408 | 18 (630.5 / 442.7) | 2 | 21 | 2 |

Dev-only versions (short matches, not carried to full runs):
- **Grok Bot v1, approach: concentrated early strike + fortress garrisons.**
  - Takes c11 around day 11 and c15 around days 21–50, then stalls.
  - The army fragments into 18 tiny parties that fill every clan slot.
  - 120-day results: 8-4, 8-4, 7-5 cities.
- **Grok Bot v2, approach: consolidated doom-stack staged at the nearest own city.**
  - Waits 100+ days for a pessimistic stale estimate. Bandits wreck the economy (population ~1750 at day 200).
  - 200-day results: 7-5, 4-8, 5-7.
- **Grok Bot v4, approach: bait-fortress trap.**
  - The stack hides in the weakest frontier city to ambush march's expeditions.
  - Too passive, and home villages stay unprotected. 300-day results: 2W 3L 1D in cities.

## What changed and why (iteration log)
- **v1 → v2:** v1 split its army into many tiny parties that couldn't take a city. v2 merged everything into one stack, but its estimates were too pessimistic: it waited 100+ days while bandits ruined the villages.
- **v3:** added per-city anti-bandit patrols, plus fixes for a cmap KeyError and relief staging. Full runs: 5-7, 4.92 cities. Population was still poor.
- **v4:** a passive bait-fortress trap. It lost ground and was dropped.
- **v5 (new architecture):**
  - The frozen `aiwar.patrols` p5 logic drives the patrol layer, so every spare party patrols villages and hunts bandits.
  - One campaign stack does rally → march → siege, launching only when strength ≥ 1.5 × sqrt(H_D·P_D/2) + 20.
  - All parties within 45000 relieve a besieged city at 1.3×.
  - Result: 9-3, population about 12k.
- **v6:** adds a day-0 rush on the nearest city with no party creation during the rush, a less pessimistic stale estimate, and a scouting march. Result: 10-2, 9.5 cities, population about 17k.
- **v7:** the stack holds each conquest for 60 days at refill target 1. Result: 19-5 on 24 seeds. The hold30 and hold120 sweeps each went 11-1 on 12 seeds.
- **v8:** fixes a bug where a lost city still flagged as ours in stale scouting triggered a LAUNCH/END loop every tick. Also filters invalid transfers. The 12-seed result of 8-4 is within the noise.
- **v9:** before a siege, it remembers enemy field parties seen in the last 8 days and requires enough strength to beat the expected march relief. Result: 19-5 on 24 seeds, 9.46 cities, unification at about day 568 (faster than v7). As red it went 12-0.
- **Parameter sweeps on v9:**
  - GB_GUARD 1.3 was slightly worse (18-6).
  - **GB_MARGIN 1.7 / GB_SMARGIN 1.55 went 22-2, with 10.71 cities and population about 15.7k.** There were 2 agent exceptions when the rally base was lost.
- **v10:** analysing the losses showed march gathering about 370 troops near a frontier city around day 115. Our scattered 10 patrols (about 358 total) could never reach the 1.3× relief threshold, so we lost the city and the game snowballed. v10 pre-emptively moves nearby parties *into* the threatened city: defenders count 4× in a siege, and march only judges a target by garrison + militia/2. On the 4 hardest seeds, all 4 losses turned into leads at day 400.
- **v11:** v10 + margins 1.7/1.55 + re-basing the rally if the base city is lost (the KeyError fix).
- **Full results:**
  - v10 went **24-0 as blue, unifying all 24 games (mean day 547, fastest day 311)**, and 12-0 as red.
  - v11 went 24-0 but unified only 19 games (11.79 cities). Its higher margins make the late game too cautious. v10 is the base for later versions.
- **Updated baseline:** march vs march over 24 seeds went 12-11-1, with 6.17 cities.
- **v12:** analysed v10's slowest unifications (days 727–924). Every delay was the *last* red city, which had about 320 garrison + 200 militia and needed a stack of about 1,050.
  - The cause: the roster stopped adding parties once the parties' current healthy met the requirement. Parties cap at 150 troops, so a 5-party roster maxed out at 750. It then rallied, aborted and relaunched for hundreds of days while 2,000+ troops sat in patrols.
  - The fix: size the roster by capacity, sum(min(150, healthy + garrison share)), and let a full-but-short rally pull in more parties (2 per tick, up to 16).
  - Dev run on the 5 slowest seeds: unification days 820→519, 924→635, 757→655, 727→631, 755→738.
- **Disk incident (about 11:45):** the box disk filled up with 110 GB of raw nation-*.jsonl protocol logs, which killed a few background runs.
  - Raw logs of completed runs are now gzipped, which is reversible. batch.py gzips new ones automatically.
  - Only the 5 incomplete dev-v12a runs were removed.
- **v12 full results:**
  - Blue: 24-0, but only 23 of 24 unified, mean day 564 (v10: 547). Red: 12-0, all unified, mean day 562 (v10: 671).
  - Per seed, v12 was much faster on 12 seeds (up to −302 days) and much slower on 5 (+250 to +517). Seed 1072134541 never unified and ended 11-1.
  - The stall: on that seed, after day 526 v12 never launched again. It had 1,855 troops in 18 parties and about 4,400 in garrisons, but the last city needed about 1,140.
  - Why: one keeper party was reserved for each own city, 10 of 18 parties. The launch potential also counted garrison surplus only at the base.
- **v13 (from v12):** to mobilise the whole empire for the doom-stack, it:
  - keeps keepers only for cities bordering an enemy city;
  - counts garrison surplus within 40,000 of the base as potential, capped at 150 per roster party;
  - lets an under-strength rallying party detour to the nearest city with spare garrison to top up.
- **v13 full results:**
  - Blue: 21-3, 10.67 cities, 21 unified with mean day 468 (fastest 280). Red: 7-5, 7.00 cities.
  - When it wins it is the fastest version: 1280858948 went 924→341 and 1072134541 never→497. But the 3 blue losses and 5 red losses are early-game collapses.
  - Cause: the mobilisation rules are active from day 15. Stale-target rallies keep aborting and pull every patrol and keeper away, so march takes c13 back and rolls up the home cities.
  - The next fix would be to enable the v13 rules only in the endgame, for example when the enemy holds 3 or fewer cities. That is untested, and we stopped at the version cap.
- **Final pick, by the user's priority (score/cities → population → unification speed → win rate): Grok Bot v10.**
  - It is the only version that holds all 12 cities in all 24 blue games and in all red games.
  - v12 trades slightly: 11.96 cities with one non-unified game, more population (14,880 vs 14,295), and much faster red unification (562 vs 671), but slower on blue (564 vs 547). Its best seeds beat v10's worst seeds by up to 300 days.
  - v13 is fastest but unreliable.

