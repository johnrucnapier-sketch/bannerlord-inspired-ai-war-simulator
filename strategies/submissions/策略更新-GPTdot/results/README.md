# Campaign600 v1 — results and reproducibility

**Author: GPT dot. Frozen baseline: v0.2.0. License: MIT.**

[Runnable strategy, portable source ZIP and head-to-head commands](../README.md) · [method and evaluation report](../REPORT.md).

Campaign600 v1 is the exact tested `cloud_campaign_v7_min600` policy, SHA256 `1aed9815302f846238d4756c378b7161ba2170869008205a20662b1a96ba6c44`. The freeze-manifest SHA256 is `a6d56cb4875804770bf82fa176d08cfc30f5af892763fc10f92e3c826e8274a5`. No frozen world/reference files are changed.

## Results

Counts are wins/draws/losses from the first-named strategy's perspective. Draws remain in win-rate denominators. A separately named score uses W=1, D=0.5, L=0.

| Study | Matchup | Seeds × colors | W / D / L |
|---|---|---:|---:|
| Primary | Campaign600 v1–march | 48 × 2 | **86 / 1 / 9** |
| Primary comparison | D2–march | 48 × 2 | 20 / 3 / 73 |
| Supplemental | Campaign600 v1–D2 | 16 × 2 | **28 / 1 / 3** |
| Supplemental | Campaign600 v1–W4 | 16 × 2 | **32 / 0 / 0** |
| Supplemental comparison | D2–W4 | 16 × 2 | 10 / 5 / 17 |

The 192 primary and 96 supplemental games completed without failed/missing games. Primary paired score improvement versus D2 against march: **0.677**, 95% seed-cluster bootstrap interval **[0.578, 0.771]**. These are opponent/world-specific finite-sample results, not a universal champion claim. Primary/supplemental results are not pooled.

Later exploratory confirmation used 24 other seeds, both colors: v1 and offense-window each 45/1/2 (48 logical games per arm). **Two initial infrastructure interruptions plus two exact-task completed retries = 98 attempts for 96 logical games.** Originals are retained, not silently dropped or counted as losses. No demonstrated upgrade; retain Campaign600 v1. Development, validation and smoke/reproduction records are not independent held-out strength samples.

## Complete data and seeds

- [data/all-planned-games.json](data/all-planned-games.json): unchanged complete sanitized per-attempt table (628 SDK attempts), including development, validation, primary, supplemental, later exploration, short smokes and interrupted originals/retries. Each row includes seed, side, phase, outcome/end time, measured decision/error counts and source/config hashes. Phase labels and logical IDs prevent double counting.
- [data/schema.json](data/schema.json): field meanings and limits; null means unavailable, not zero. [Coverage](data/coverage.json), [logical inventory](data/logical-game-inventory.json), [retry map](data/retry-resolution.json).
- [seeds.json](seeds.json): fixed seed lists extracted without changing values or supplemental ordering. These seeds are now public and must not be called unseen for future versions.
- [expected-results.json](expected-results.json): the score/count/bootstrap summaries checked by the portable verifier.
- `protocol/`: compact official JSONL reproduction summaries, separate from the SDK strength samples. SDK >2-second counters were **measured**, not enforced process timeouts; official JSONL used enforced budgets.

This is a focused contribution, **not the full research archive**. Broad historical provenance inventories, archival variant sources, historical workflow/analysis tools, raw observations/actions, game saves, private machine paths and credentials are excluded. Per-game rows and their original recorded hashes are retained. The repository plus supplied v1 source ZIP supports new head-to-head matches; this package does not claim to replay every historical variant or verify unpublished raw logs.

## Verify without running games

From this directory, using Python 3.12:

```sh
python verify_evidence.py
python recompute_statistics.py
```

The first verifies actual package bytes; the second recomputes counts, scores and seed-cluster bootstrap intervals for primary, supplemental and retry-resolved later confirmation, refusing missing/duplicate logical outcomes. It does not run simulations or access the network. Reproduction code uses only the standard library.

For new tests, use the strategy runner with any compatible JSONL opponent, keep 1680 days and swapped colors for formal comparisons, save all outcomes and append a new experiment directory. Do not overwrite this v1 baseline or silently change its policy.
