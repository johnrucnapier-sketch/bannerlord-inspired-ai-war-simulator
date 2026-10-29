# Strategy report — Campaign600 v1

- **Name / version / author:** Campaign600 v1 / 1.0.0 / GPT dot. The contribution Git commit supplies the publication identity; the tested policy hash below is independent of that packaging commit.
- **Baseline:** v0.2.0, source commit `fc6a0a884fc4dbe28aacd292a8c885c790192f82`. Freeze manifest SHA256 `a6d56cb4875804770bf82fa176d08cfc30f5af892763fc10f92e3c826e8274a5`. Config file SHA256 `6b3c0c4dfb861b68677aa17aad764ca4eb24d302b3d2a59fd00f0ad25d668cd4`.
- **Policy SHA256:** `1aed9815302f846238d4756c378b7161ba2170869008205a20662b1a96ba6c44`. Code, original documentation and results: MIT; inherited D2/reference code retains upstream attribution and license.
- **Launch:** `python -S strategies/submissions/cloud_campaign_v7_min600/policy.py`; portable head-to-head wrapper and dependencies: [README](README.md).
- **Model / budget:** deterministic controller, no learned weights, model calls or network. Decisions every 6 game hours. SDK research measured 2-second exceedances but did not enforce process timeouts; separate official JSONL reproduction enforced them.

## Method

Inherits D2's escort, P5 patrol, growth and replacement economy. Adds pooled campaign rosters, healthy-strength checks, refit and rally deadlines, current ownership/fog checks and narrow resource-command ordering repair. The selected attack floor is 600 healthy troops. Military assignments can reduce rear protection; higher win rates are not evidence of greater production.

## Training and tuning

No machine-learning training. Manual program iterations used public historical research, 4 development seeds and 8 validation seeds; these are selection data, never unseen test data. Variant identities, seed lists and all planned attempts are in [the evidence](../../../benchmarks/community/gpt-dot-campaign600-v1-20261029/README.md). Selected policy was locked before primary testing and not altered afterward. Later offense-window experiments are explicitly separate, not v1 upgrades.

## Preregistered tests

Primary: 48 new seeds × 2 colors × 2 tested strategies against unchanged march, 192 planned games; max 1680 days, unchanged original win/draw rules. Supplemental: 16 other new seeds × 2 colors × 3 matchups, 96 games. Exact seeds, sides, start/end UTC, rule/config/source hashes, counts and outcome records are in `data/all-planned-games.json`; the fixed seed lists and recorded identities are supplied with the evidence.

Python 3.12.14, cloud environment 9 CPUs / about 9.73 GiB RAM. Primary used 8 worker processes, 87.01 elapsed minutes, 39,553.89 total CPU seconds. Supplemental used 9 processes, 55.22 minutes, 22,271.07 CPU seconds. No new paid compute/API purchases; underlying platform cost is not claimed to be zero. Runtime and hardware are historical observations, not requirements or promises.

## Complete results

All counts are W/D/L from the named strategy's perspective; draws remain in the denominator. Score is explicitly W=1 / D=0.5 / L=0.

| Primary vs march | Blue W/D/L | Red W/D/L | Total W/D/L | Completed/planned | Score |
|---|---:|---:|---:|---:|---:|
| Campaign600 v1 | 43/0/5 | 43/1/4 | 86/1/9 | 96/96 | 0.901 |
| D2 | 11/3/34 | 9/0/39 | 20/3/73 | 96/96 | 0.224 |

Primary: 0 failed/missing/excluded games. Candidate and D2 rejected commands: 0; march rejected 7 commands in D2 games, 0 in candidate games. Measured >2-second SDK decisions: 0 on both sides, **not an enforced-timeout claim**. Candidate unified the map in 67 games; mean capped unification time across all 96 games (non-unifications capped at 1680 days) was 968.34 days, vs D2's 1638.61. Paired seed-cluster score improvement 0.677, bootstrap 95% CI [0.578, 0.771].

Supplemental: v1–D2 28/1/3, v1–W4 32/0/0, D2–W4 10/5/17 (32/32 each; no failed/missing games or measured >2-second decisions). Not pooled with primary results.

Separately, 3 full official JSONL v1 reproductions covered both colors and a 1680-day match, with 12,029 candidate decisions / 48,851 commands, 0 errors/timeouts/rejections and exact replay agreement. These are reproduction, not extra independent wins.

Later exploratory 24-seed confirmation: v1 and offense-window each 45/1/2 over 48 logical games, difference 0 with 95% CI [-0.052, +0.042]. **2 initial infrastructure interruptions plus 2 exact-task completed retries** produced 98 attempts for 96 logical games; both originals remain recorded, not reclassified as losses or silently dropped. No superiority or equivalence established.

## Analysis and limitations

The evidence supports strength against these opponents under this frozen world and seed sampling procedure, not a universal optimum. The early economy is not improved: on paired day-84.25 snapshots, candidate population and healthy regular troops are lower. Later resource comparisons mix conquest, losses and early termination; see the full report for correct sampling denominators. Nine primary losses and one draw remained; all nine losses had previously held at least seven cities.

Public data are privacy-reviewed derived per-attempt records, not full observations/actions/saves. Every evaluated manifest attempt and its original-byte provenance hashes are retained, but the original private raw logs are not published. Portable statistics recomputation is supported; historical analysis scripts and variant-source archives are not included. Full new matches can be independently run through the official JSONL host.
