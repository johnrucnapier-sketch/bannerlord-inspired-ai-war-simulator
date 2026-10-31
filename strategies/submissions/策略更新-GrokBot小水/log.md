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
- **Oct 30 (late night):** 博 李 marked both v23 and v24 as released strong versions. The README now lists both.
- **Oct 31 (early hours): standardized anchor score.** Report 10 and `score_suite.py`.
  - Anchors: v20, v22, c600v4, c600v6; 6 seeds × 2 colours × 4 anchors = 48 games per version.
  - Per-game tiers: unification win 1000–1500, no unification 250–750, unified by the opponent 0–250.
  - Final scores: v23 1180±46, v24 1176±47, v22 1111±43, v21 1091±49, v20 872±56, c600v6 312±6, c600v4 287±10.
  - The score order agrees with 17 of 18 head-to-head pairs (τ = 0.81).

## Resume notes, Oct 31 PM (local, not pushed)
- **Versions:** v25 = pushed e8afaaa (frozen). v26/ = v25 + A-R5 fixes (mass 200/0.5, advancing-only warn, pregather counts walls, protect exemptions, GB_GFEAS guard feasibility). v27/ = v26 + intel gate (GB_GATE) + mobilisation (GB_TMOB, mkeep 5, anchor = nearest other city, no guards under mob) + pinned army (GB_TPIN) + hunt pause under mob (GB_MOBHUNT). FINAL code is in v27/ (former v27dev REV5). v27dev/ was deleted.
- **Run-dir renames:** the old gate-only v27 runs are now `v27gate-vs-*`; REV5 dev runs became `v27-vs-*`. batch_h2h has new opponents ar5, ar6 (A-R6, pulled 527633a) and hy.
- **Dev seeds (5×2) results:**
  - v23: hy 0-10, ar5 2-8.
  - v26: hy 2-8, ar5 5-5.
  - v27gate: hy 2-8, ar5 3-7, v22 11-1 (6 seeds), ar3 10-0.
  - v27dev REV1 mob: hy 4-6. REV4 (+no guards under mob): hy 6-4.
  - v27 (REV5, +hunt pause): hy 6-4, ar5 10-0, v22 8-2, v23 10-0, ar3 10-0.
- **Validation (SEEDS 0:12) so far:** v27 vs hy 11-13 (blue 6-6, red 5-7); v27 vs ar6 21-1-2.
- **Eval script:** /workspace/v25log/final.sh (cached results are reused). Run it with -j 4: a video render shares the box.
- **Remaining:** finish the eval → write reports/11 (Chinese) → commit v26/, v27/, batch_h2h.py and report 11 → verify_release → single push.
- 16:40 (UTC+8): restarted the eval as /workspace/v25log/final3.sh (-j 4, nice; trimmed: v26 has no v20/c600 anchors; v23 baselines use seeds 0:6). Output goes to /workspace/v25log/final3.log. On resume: check `pgrep -af final3.sh`, delete run dirs without result.json, then rerun the script (cached games are skipped).
- v27 validation: ar5 22-2 (blue 11-1, red 11-1).
- v27 validation: ar3 24-0 (one red win on cities at the time limit), v22 11-1, v23 11-1, v20 12-0 (seeds 0:6 for v22/v23/v20).
- 17:25 (UTC+8): final3 eval paused after the v27 anchors (c600v4/v6 12-0 each). The v26 part is not done yet: rerun final3.sh later. Now: v28 development vs HengYue.
- 17:45 (UTC+8): v28dev = v27 + TAC merge (mobilised: small idle parties in one city merge into the largest, freeing slots) + TAC refit (a depleted pregather member detours via a city with garrison ≥ 70). Snapshot v28a vs hy seeds 0:12 → /workspace/v25log/v28a-hy.log. Losses vs hy were mostly cities lost before day 90 with no relief GO; we had 1100 soldiers in rear garrisons but only ~260 in the field (slots full of 20-man parties).
- 18:15 (UTC+8): v28a (merge+refit) vs hy 0:12 = 11-13 (blue 5-7, red 6-6), the same as v27, with many per-seed flips both ways (high variance). v28b = v28a + mob hysteresis (stay ON down to 0.6×field). Running → /workspace/v25log/v28b-hy.log.
- 18:45 (UTC+8): v28b vs hy 0:12 = 12-12 (blue 7-5, red 5-7). Running /workspace/v25log/v28chk.sh: v28b and v27 vs hy on seeds 12:24, then v28b regression checks (ar5/ar6 0:12; v22/v23/ar3 0:6). Log: /workspace/v25log/v28chk.log.
- 18:12 (UTC+8, real clock; the 17:45/18:15/18:45 stamps above were estimates and are about 30-60 min too late): v28chk.sh is still running (v28b vs hy 12:24). git fetch found 39345dd: A-R6 vs HengYue went 2-6 on GPT's 8-game check; pulled, no new agent.
- 18:25 (UTC+8): v28b vs hy seeds 12:24 = 11-13 (blue 5-7, red 6-6); 24-seed total 23-25. Now running v27 vs hy 12:24.
- 18:38 (UTC+8): v27 vs hy 12:24 = 10-14, so v27 is 21-27 over 24 seeds and v28b 23-25. v28b vs ar5 0:12 = 21-3. final4.sh (nohup) waits for v28chk, then runs: v26 vs hy/ar5 (0:12) and v22/v23/ar3 (0:6); v23 vs hy/ar5/ar6 (0:6); v28b anchors v20/c600v4/c600v6 → /workspace/v25log/final4.log.
- 19:02 (UTC+8): resumed. v28chk is running v28b vs ar6; final4 is queued behind it. Nothing lost.
- 19:02 (UTC+8): drafted reports/11-v26-v27-v28-情报门控与动员.md (placeholders for the validation table and commits).
- 19:16 (UTC+8): v28b vs ar6 0:12 = 21-3 (v27: 21-1-2); v28b vs v22 0:6 = 11-1 (the same as v27). Next: v23, then ar3.
- 19:29 (UTC+8): v28b vs v23 0:6 = 12-0 and vs ar3 0:6 = 12-0. DECISION: v28 = v28b (no regressions; vs hy +2 over 48 games). v26 vs hy 0:12 = 5-19. final4 continues (v26 ar5...). At the end: create v28/ from v28b with a header, rename v28b-vs-* run dirs to v28-vs-*, and delete the v28a/v28b/v28dev folders.
- 19:32 (UTC+8): v28/agent.py written (v28b plus a header; code identical). Deleted v28a/ and v28dev/; v28b/ is kept until final4 finishes.
- 19:55 (UTC+8): v26 vs ar5 0:12 = 13-11. final4 is now running v26 vs v22. Explicit instruction: do NOT push anything this round.
- 19:53 (UTC+8): stopped final4.sh after the running v26-vs-v22 batch. Still TODO from final4: v26 vs v23/ar3 (0:6), v23 vs hy/ar5/ar6 (0:6), v28 anchors v20/c600v4/c600v6. New v29dev = v28 + TAC strike-main (the pre-gathered force in its anchor attacks a visible enemy mass in the open within 15000, not within 2500 of an enemy city, when ours >= 1.25 x max(visible, remembered 24h) within 7000 of the target; 48h commitment). Snapshot v29a vs hy seeds 0:24 → /workspace/v25log/v29a.log (v28 baseline over the same 24 seeds: 23-25).
- 20:04 (UTC+8): v26 vs v22 0:6 = blue 5-1, red 1-1-4 → 6-1-5 (v25 earlier was the regression case; v27/v28 11-1). Killed the orphaned v26-vs-v23 batch to keep -j 4 (incomplete dirs removed).
- correction: v26 vs v23 0:6 had already finished: 8-4 (blue 4-2, red 4-2).
- 20:17 (UTC+8): v29a (v28+strike-main) vs hy 0:24 = 23-25 (blue 12-12, red 11-13), identical to v28 except 2 seeds (+1327243828 blue, −2088460572 blue). Strikes fire rarely (12 in 48 games), only vs small 108-261 groups, never the main 400+ mass → neutral; not adopted as-is.
- 20:18 (UTC+8): v29dev += TAC hold (GB_MHOLD=1, GB_HOLDK=0.75): under mob, a city under an advancing-mass warning is held by feeding reachable free parties into the garrison when that can reach g+m/2 >= 0.75 x mass (empirical: our sieges with D/B>=0.6 fell 34/150, >=0.8 never; D/B<0.25 fell 154/217). Snapshot v29b vs hy 0:24 running → /workspace/v25log/v29b.log.
- 20:29 (UTC+8): v29b aborted (bug: guards stayed as parties - parties inside a besieged city don't fight - and mob creation re-stripped the garrison). v29dev fix: held cities (48h) skip party creation; guards at a held city transfer into the garrison (cap 500). Snapshot v29c vs hy 0:24 → /workspace/v25log/v29c.log.
- 20:42 (UTC+8): v29c vs hy partial 44/48 = 26-18 (v28 on the same 44: 21-23; 12 seeds gained, 7 lost). TAC hold looks like the first real gain. Queued /workspace/v25log/v29reg.sh after the v29c run: v29c vs ar6/ar5 0:12, v22/v23/ar3 0:6, then the final4 leftovers (v26 ar3, v23 hy/ar5/ar6 0:6, v28b v20/c600v4/c600v6 0:6).
- 20:52 (UTC+8): RESULT v29c vs hy 0:24 = 28-20 (blue 15-9, red 13-11), first version above 50% on full seeds (v28 23-25, v27 21-27). Regression batch v29reg running.
- 21:06 (UTC+8): REGRESSION v29c vs ar6 0:12 = 15-9 (v28 21-3; 6 seeds lost, 0 gained). Diagnosing.
- 21:06 (UTC+8): diagnosis vs ar6: hold fires again and again on a mass staging near our border that never besieges → parties locked in garrisons for 100+ days, tempo lost. v29dev += hold episode limits: feed only if the mass is visible within 20000 (>= GB_HOLDNEAR 0.5 x thr), give up after GB_HOLDMAX=8 days without a siege (then 8-day cooldown, garrison re-extracted by normal creation). Snapshot v29d: vs ar6 0:12 then hy 0:24 → /workspace/v25log/v29d.log. Killed v29reg.sh after v29c-vs-ar5 (still running); v22/v23/ar3 + final4 leftovers to be re-queued.
- 21:32 (UTC+8): v29c vs ar5 0:12 = 22-2 (v28 21-3) OK. v29d vs ar6 partial 4-5 after 9 (v28 7-2 on same) → episode limits don't fix the ar6 regression.
- 21:51 (UTC+8): v29d vs ar6 0:12 = 16-8 (blue 6-6, red 10-2); v28 21-3, v29c 15-9 → regression persists. Seed s1555985896 blue diverges from v28 at d23 with no hold logged (creation blocked by 'held'? / strike?). Queued isolation after v29d-hy: v29a (strike only) vs ar6 0:12, v29c@GB_TSTRIKE=0 (hold only) vs ar6 0:12 → /workspace/v25log/v29iso.log.
- 21:51 (UTC+8): diagnosis (v29c ar6): strikes never fire vs ar6; losses = many holds. e.g. red-s1241774772: c13 held, ar6 retargets the unheld c15 (lost d46) while our men sit in c13; v28 lost nothing until d421. v29dev += committed-target test (GB_HOLDCOMMIT 0.5: hold only if mass is ≤0.5× as far from this city as from any other own city; warn tuple now stores mass x,y). Snapshot v29e queued after v29iso: ar6 0:12 then hy 0:24 → /workspace/v25log/v29e.log.
- 21:52: dropped v29iso (strike shown irrelevant vs ar6 by logs); v29e now waits directly on v29d.sh.
- 22:05 (UTC+8): v29d vs hy partial 25: 10-15 (v29c 15-10, v28 13-12 on same) → episode limits (HOLDMAX/HOLDNEAR) hurt vs hy; v29d rejected. Now: v29e ar6 0:12 running (limits+commit); then v29e@GB_HOLDMAX=999,GB_HOLDNEAR=0 (= v29c + commit only) ar6 0:12 then hy 0:24 → /workspace/v25log/v29f.log. v29e hy dropped.
- 22:05: queue fixed (an accidental overlap was killed and its incomplete dirs removed): /workspace/v25log/v29ef.sh waits on v29d.sh, then commit-only (v29e@GB_HOLDMAX=999,GB_HOLDNEAR=0) ar6 0:12, v29e ar6 0:12, commit-only hy 0:24 → v29ef.log.
- 22:19 (UTC+8): v29d vs hy stopped at 27/48 = 10-17 (v28 14-13 on same) → v29d rejected (episode limits hurt vs hy, didn't fix ar6: 16-8). Freed slots for v29ef.  [correction: v29d hy had actually finished all 48 when killed; see next line]
- v29d vs hy 0:24 FULL = 22-26 (v28 23-25, v29c 28-20) → rejected.
- 22:35 (UTC+8): commit-only (v29e@GB_HOLDMAX=999,GB_HOLDNEAR=0) vs ar6 partial 17/24 = 13-4 (v28 14-3 on same; v29c lost 6 seeds in full set) → looks close to v28. Waiting for the rest + hy.
- 22:37 (UTC+8): commit-only vs ar6 23/24 = 17-6 (v28 20-3 on same) → still -3 vs A-R6. hy 0:24 run continues in background. Owner priority: pause tweaking → deep HengYue analysis → reports/12-衡岳头脑风暴.md.
- 22:38 (UTC+8): commit-only (v29e@GB_HOLDMAX=999,GB_HOLDNEAR=0) vs ar6 0:12 FINAL = 17-1-6 (v28 21-3, v29c 15-9). v29ef continues: v29e ar6, then commit-only hy 0:24.
- 22:43 (UTC+8) DEEP ANALYSIS (owner priority) — key findings:
  * HengYue architecture: logistics strips every garrison into 150-man parties (garrison < 45); 4 x 20-man village guards that flee; ONE war group (all other parties) rallies at a frontier base (>= 82% of total, >= 180), probes to a 7000 stage, field_target = best visible party/cart within 10000 (parties weighted 3x, needs local superiority), else siege if affordable, else raid villages; defense(): all war parties wait at a 4500 stage and relieve only when predicted attrition makes them superior; 72h rest for wounded.
  * 96 games (v28b+v29c vs hy): losing a city by d100 -> 3/31 wins; none lost by d100 -> 48/65 wins. v29c captured >=1 city by d100 in 20 games (15 wins) vs v28 5.
  * Replays (6 games, 120 d, non-LITE in /workspace/v25log/ana): WINS = HY sieges a held city d6-15 and its field army collapses 480 -> 80-150, never recovers by d110. LOSSES = HY never breaks itself; its 6-party mass (~400) catches our lone parties 12-150 men again and again (22 field battles in 3 losses, 0 in 3 wins), and our regulars fall 490 -> 245 by d30 while HY grows 490 -> 520+. Almost every victim was moving as gb=guard / pregather / sweep_refit / rally toward a threatened city, i.e. INTO the mass's reach. STAT lost_battles: losses 0.8, wins 0.1-0.2 (all 96 games).
  * Report: reports/12-衡岳头脑风暴.md
  * reports/12 written; hypotheses ranked: H1 danger-zone movement filter (strongest) > H2 commit-only hold + safe feeding > H3 fewer/bigger detachments > H4 pursuit window after a failed enemy siege > H5 counter-threat on stripped rear cities.
- 22:55 (UTC+8): owner approved H1+H2. v29dev/v29f = v29e with commit-only hold as default (GB_HOLDMAX 999, GB_HOLDNEAR 0, GB_HOLDCOMMIT 0.5) + TAC avoid (GB_TAVOID=1, AVR 8000, AVH 24h, AVQ 1.0): support moves (guard/hold/pregather/rally/refit/sweep/patrol/supply) never pass within 8000 of a fresh enemy group >= travelling group+10 -> stay in own city / nearest safe own city / step away. Offensive & relief modules exempt; bandits ignored. Offline smoke on the recorded red-464809217 obs: fires on exactly the d10-12 guard victims (to 72000,12000). H3 not added (merge already merges idle parties stuck in cities).
  Queue /workspace/v25log/v29f.sh (waits for v29ef): v29f hy+ar6 dev 0:5, then 0:12. Ablation baseline = commit-only (v29ef).
- 23:05 (UTC+8): v29e (episode limits HOLDMAX 8 + HOLDNEAR 0.5 + commit 0.5) vs ar6 0:12 = 20-4 (blue 9-3, red 11-1) — close to v28 21-3. Its hy result is NOT run yet (v29d, limits without commit, was 22-26 vs hy). Commit-only hy 0:24 now running.
- 23:31 (UTC+8): commit-only hold vs hy 0:24 FINAL = 25-23 (blue 13-11, red 12-12); v29c 28-20, v28 23-25. Commit-only keeps about half the hy gain; ar6 17-1-6. v29ef DONE. v29f (commit-only + avoid) dev batch started.
- 23:36 (UTC+8): v29f dev (0:5) — hy 4-6 (blue 3-2, red 1-4; same seeds v29c 4-6, commit-only 3-7, v28 7-3), ar6 9-1 (v28 8-1 on 9 done). lost_battles still ~0.7/game vs hy: e.g. red-1479552164 d32 a 180-man sweep group that was already inside the mass's reach on refit got caught (3/3 dead). v29dev refinement (not yet tested): a party already inside the reach falls back to an own city whose path doesn't close on the threat. v29f.sh is still running (pid 2587167, 0:12 stage); the 4 run dirs without result.json are games in progress, not stale.
- 23:52 (UTC+8): v29f (commit-only + avoid) vs hy 0:12 = 12-12 (blue 7-5, red 5-7). Same seeds: v29c 13-11, commit-only 13-11, v28 12-12 → avoid gives no gain on hy so far. Early-city stats on 0:12 (lost >=1 city by d100 / won any of those; captured >=1 by d100 / wins): v29f 7/0, 7/6; v29c 8/0, 10/7; commit-only 6/0, 8/7; v28 8/2, 1/1.
  CORRECTION to report 12: the STAT lost_battles counter only counts HB (hunt/sweep) mission battles, NOT the guard/pregather victims found in the replays; the "losses 0.8 vs wins 0.1" figure is about sweep/hunt groups. The replay prey evidence (22 vs 0) still stands, but it comes from 6 games only. v29f vs hy loss games still average 0.83 lost mission battles by d120 (avoid redirects sweep refit/back moves; possibly unhelpful).
  Noted (not implemented): /workspace/rearan/report.md — day-10 field share 60-74% (ours) vs 98% (HY), gap mainly frontline garrison floor GB_TPOST/FKEEP 50 + hold; owner may redirect rear-city posture.
- 00:07 (UTC+8, Nov 1): v29f vs ar6 0:12 FINAL = 21-3 (blue 9-3, red 12-0) = v28 level (21-3); commit-only without avoid 17-1-6, v29c 15-9 → avoid removes the A-R6 hold regression. vs hy 0:12 12-12 (v29c 13-11, v28 12-12). Running /workspace/v25log/v29f2.sh (pid 2999634): v29f@GB_HOLDMAX=8,GB_HOLDNEAR=0.5 (v29e+avoid) ar6 0:12 → hy 0:12 → v29f hy 0:24 (12:24 part). Untested in v29dev: retreat refinement for parties already inside the reach.
- 02:05 (UTC+8, Nov 1): v29e+avoid (v29f@GB_HOLDMAX=8,GB_HOLDNEAR=0.5) vs ar6 0:12 = 17-7 (blue 7-5, red 10-2), worse than v29f 21-3. Dropped; its hy run was stopped at 11 games (4 partial dirs removed; the 11 finished games are kept but unused).
  v29g = v29f + retreat refinement (a party already inside the reach falls back to an own city whose path doesn't close on the threat). /workspace/v25log/v29g.sh launched with setsid+nohup (pid 3352689): v29f hy 0:24 (cached 0:12 reused) → v29g hy 0:24 → v29g ar6 0:12. Log /workspace/v25log/v29g.log.
- 02:23 (UTC+8, Nov 1): v29f vs hy 0:24 FINAL = 23-0-25 (blue 12-12, red 11-13) = v28 (23-25); v29c 28-20. ar6 0:12 21-3 = v28. Owner wrap-up: v29g dropped (never run). Release candidate v29 = v29f (header notes only). Regression v29 vs ar5 0:12, ar3/v22/v23 0:6 running (/workspace/v25log/v29reg2.sh, setsid).
- 03:06 (UTC+8, Nov 1): v29 regression DONE: ar5 0:12 23-0-1 (v28 21-3), ar3 0:6 10-0-2 (v28 12-0; 2 red losses, within noise but noted), v22 0:6 11-0-1 (v28 11-1), v23 0:6 11-1-0 (v28 12-0). Wrap-up: v29/ = v29f + header; v29c code kept as experiments/v29c-hold-all (labelled not released); snapshots v28b/v29a/c/d/e/f/g/v29dev deleted; reports 11/12 filled (lost_battles correction applied); README + results-h2h updated. v29g never run (owner: wrap up).
