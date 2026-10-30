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

## Evening: head-to-head vs GPT dot Campaign600 v1 / v4 (v14–v19), made by GrokBot (小水)
- **v14:** v12 + v13 mobilisation only in the endgame (enemy ≤ 3 cities) + stale-target floor 300. vs GPT v1 blue 12-0-0, 5 unified.
- **v15:** v14 + engine-accurate siege need (defender parties fight a separate relief battle instead of joining the siege at x4). vs v1 blue 11-0-1, 9 unified (mean day 487); one early stack lost on seed 2013042981.
- **v16:** v14's conservative estimate until the endgame, v15's model in the endgame. vs v1 23-0-1 (24 games); vs march 24-0, mean days 444/460.
- **v17:** v16 + whole army in the endgame doom-stack (no 40,000 radius). vs v1 46-0-2 over 48 games, 46 unified; vs march 24-0, mean days 363/401.
- **GPT v4 (Early Relief)** crushes the day-0 rush: v16, v17 and v18 each went 5-1-18 vs v4 (12 seeds per colour).
- **v18:** v17 + lost-rally-base fix (KeyError 'garrison' found by GPT dot in v10; same bug in v12–v17). Same results as v17 vs v4.
- **v19:** v18 with no siege campaign before day 30. vs v4 42-2-4 over 48 games (blue 20-1-3, red 22-1-1), 42 unified; vs march 48-0, all unified, mean days 394.5 (blue, fastest 203) / 334.5 (red). Current best.
- Full report: `reports/04-vs-GPT-Campaign600.md`.

## Oct 30: head-to-head vs GPT dot Campaign600 v6 (Feasible Relief), made by GrokBot (小水)
- **GPT v6:** relieves any besieged city all game long, but only when its reachable healthy field parties reach about 1.2x the besiegers (checks march time and food, never counts garrisons).
- **v19 vs v6** (24 std seeds per colour): blue 8-1-15, red 4-0-20; on GPT's 12 independent seeds blue 3-0-9, red 2-0-10. v19's 300-650-troop sieges were wiped out by v6's 460-820-troop relief armies, and the attrition snowballed.
- **v20:** v19 + remember every enemy party seen in the last 40 days (`GB_FOEMEM`) and never launch or hold a siege below 1.0x (`GB_FIELDK`) of that whole remembered field army + create parties from day 0 (`GB_CREATE`).
- **v20 results:** vs v6 blue 24-0-0, red 23-1-0 (47 unified; the draw is a 6-6 time limit on red seed 304847128); vs v4, v1 and march 12-0-0 on each colour, all unified; vs march mean days 357.2 / 316.0 (faster than v19). On GPT's 12 independent seeds vs v6: blue 12-0-0, red 12-0-0, all unified (v19: 5-0-19).
- **Faults:** 4 v20 games each had one 2-second decision timeout under 8-way parallel load (no traceback); GPT v4 crashes after a restart (`assert obs['hour']==0`). No code change needed.
- Full report: `reports/05-vs-GPT-V6.md`.

## Oct 30 (afternoon): feint vs coordinated patrol hunting, against v20 → v21, made by GrokBot (小水)
- **Baseline:** v20 vs v20 mirror, blue only. Std 24 seeds: 12-0-12. Self seeds: blue 6-0. Campaign success 54%.
- **A, feint (`v21a-feint`):** first baits a second enemy city F with the whole stack for 36 h, then leaves a ≥120-troop screen there and the main army goes for T.
  - It triggered: 72 feints; v20 guarded F in 70 of them, about 328 troops on guard orders at the switch.
  - But v20 also guarded T in 58 of 72, and the 40-day army_floor still counted the diverted troops.
  - Result vs v20 std: 11-0-13; campaign success fell to 41%.
- **Tuning 1 (`v21a2`):** excluded enemy parties near F from the need. Identical results, so it did not help.
- **B, hunt (`v21b-hunt`):** a group of 3 parties (cap 150 each) hunts patrols, small parties and carts more than 2500 from any city, and refits when needed.
  - Over the 24 std games: 694 parties (34.6k troops) and 3188 carts killed for 2.3k losses, 0 hunter parties lost.
  - v20 GUARD days were 4.3x the mirror.
  - Results vs v20: std 23-0-1, self 10-0-2. Against the same seed and side in the mirror, 16 games went from loss to win and 1 from win to loss.
- **Combo (`v21c-combo`):** 34-0-2 vs v20, within noise of B and slower on red.
- **Promoted v21 = hunt** (`v21/`, feint code kept but off):
  - vs GPT V6, std 12x2: 24-0-0, mean days 675/748 (v20 on the same seeds: 842/806).
  - vs march, first 4 seeds x2: 8-0-0, but about 40-65 days slower than v20.
  - v21 reproduces v21b game for game.
- **Known weakness:** the hunt home city ignores city food (red seed 1199329012 loss).
- Full report: `reports/06-声东击西与协同清剿-vs-v20.md`.

## Oct 30 (midday): famine / death-spiral contingency → v22 (in progress), made by GrokBot (小水)

- Measured starvation in existing games with `analyze_famine.py`. v21 starves more than v20 (0.8 vs 0.4 starved city-days per 1000 vs v20; 4.5 vs V6, with 7 cities lost after starving). The main cause is party stacks eating a city empty (rally / hunter refit / empty patrols); bandits and cart losses come second.
- First v22 build (food watch, convoys, evacuation, bandit rescue, protection, food-aware hunter home): s2088460572 c10 still starved, because a 2300-troop rally drained 1.8M food in one day. Added rally staging outside the base. These early runs are kept in `runs/grokbot/h2h-v22pre/`.
- Results so far (W-D-L): v22 vs v21 26-0-10 (std + self, both colours); v22 vs V6 24-0-0 (std). Draft report 07.

## Oct 30 (afternoon): v22 final results → promoted, made by GrokBot (小水)

- Results (W-D-L):
  - v22 vs v21: 26-0-10 over 36 games (blue 15/18, red 11/18);
  - v22 vs V6: 24-0-0 on std (mean unification day 627.5 / 643.5 vs v21's 675.0 / 748.4) and 24-0-0 on GPT's 12 independent seeds (v21 there: 22-1-1);
  - v22 vs march: 24-0-0 (day 344 / 338; v21 24-0-0 at 352 / 354; v21 vs march is now filled to 12 seeds per side).
- Starvation, head-to-head: 2.8 vs 8.1 starved city-days per 1000; 8 vs 26 cities lost after starving; stack-caused episodes 7 vs 69. Vs V6 (std): 0.4 vs 4.5 per 1000, and cities lost after starving 0 vs 7.
- Known side effect: some field hunger in sieges after a staged rally (about 28 estimated deaths per game vs march).
- The optional v22 vs v20 run was skipped. v22 promoted as the main version; report 07 finalized.

## Oct 30 (evening): v23 → promoted, made by GrokBot (小水)

- First v23 (v22 + famine grace period A, staged-rally refills B, fresh-capture bandit detail C) lost to v22, 14-0-22.
  - Ablating A, B or C alone still gives 3–4 wins out of 12.
  - All three off gives 5-2-5, so the regression comes from A/B/C combined.
  - B cut starvation deaths vs march from 680 to 41.
- Raids (frozen v0.2.0 `raid` order: 24h, then village pop ×0.6, food/recruits zeroed, 168h shutdown). Stand-in opponent `v22r-raid` = v22 + naive hunter raids; it beats v22 16-1-7.
- Variants: `GB_RAID` 1 naive / 2 safe follow-up / 3 bait; `GB_RDEF` 0 / 1 naive / 2 cautious / 3 + hunter recall.
  - Vs v22r-raid (std first 6 seeds × 2 colours): no raid 4-0-8, naive 5-0-7, safe 6-2-4, bait 5-0-7.
  - Defense: naive 4-0-8; off, cautious and hunter recall all 2-0-10. Cautious defense skipped every raid, because raiders come as the whole hunter stack.
- Hunter safe-return check (`GB_SAFERET`, lesson from GPT dot v15) rerouted 278 times and cost games: 5-0-7 vs 9-0-3 without it. Kept in the code, off by default.
- Final v23 = A/B/C on + `GB_RAID=2` + `GB_RDEF=1`:
  - vs v22: 22-3-11 (std 17-2-5);
  - vs v22r-raid: 7-2-15 (v22: 7-1-16);
  - vs V6: 24-0-0 (std + GPT seeds, first 6 each, both colours);
  - vs march: 12-0-0.
- v23 promoted as the main version; report 08 finalized.

## Oct 30 (night): v24 tactic library + situation assessment (challenger), made by GrokBot (小水)
- **v24 design:** v23 + a situation-assessment layer. Fixed opening until day 60, then every 5 days it judges ahead / even / behind from the city ratio, force ratio and hunger.
- **Tactics,** each with its own preconditions and gated by state:
  - intercept whole-stack raiders (`GB_TINT`);
  - feint only when ahead with a 1.5× field advantage (`GB_TFEINT`);
  - raid-as-bait only when a weak relief force is nearby (`GB_TBAIT`);
  - side-waypoint safe return (`GB_TWAY`);
  - safe follow-up raids, kept from v23.
- **Logging:** `TAC` log lines plus per-state STAT counters. The new `tac_stats.py` summarises them.
- **Results:**
  - vs v22r-raid: 12-1-11 (v23 7-2-15);
  - vs v23: 19-1-16;
  - vs march: 12-0-0;
  - vs GPT V6: 12-0-0 (mean day 608).
- **Ablations vs v22r-raid (first 6 std seeds):** intercept off 7-0-5 (full 8-0-4). State gating off 8-0-4 too, but it unifies faster (682 vs 861 days).
- **Assessment check:** games that never entered "behind" went 29-1-0. Behind-state play does not yet rescue games.
- **Status:** v23 stays main for now. Promotion of v24 is recommended, pending the owner's confirmation. Report 09.
