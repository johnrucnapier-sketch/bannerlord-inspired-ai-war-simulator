# Bannerlord-inspired AI War Strategy Research Simulator

A standalone deterministic Python war/economy simulator with an optional Godot viewer. Inspired by Mount & Blade II; not a mod, not affiliated with its creators, and does not include the game executable or full original scenes. The v0.5.0 extension includes derived strategic-map data and rendered backgrounds with a separate provenance notice. The Chinese project title is **基于骑马砍杀二的AI战争策略研究模拟器**.

Frozen original baseline: **v0.2.0 (2026-10-29)**; ready-to-run real-map package: **v0.5.0**. Original code is MIT licensed; derived map data has a separate notice.

- `game/`: frozen world, SDK, viewer and reference default opponent (`march`).
- `benchmarks/`: immutable historical experiments, reports, raw outcomes and source snapshots; append new studies, never mix rule versions.
- `strategies/`: reference policies and independently versioned community submissions.

Install Python 3.12+, run `python -m pip install -e game`, then `python tools/verify_release.py` and `python tools/play.py --blue march --red march --days 7 --seed 1 --output runs/demo`.

Agents communicate over UTF-8 JSONL. They receive fog-of-war observations every six simulation hours. The normal match horizon is 20 years (84 days per year); territory determines the winner. Delivered recruits become garrison soldiers immediately; no city recruitment pool remains. Garrison cap is 500, mobile party cap 150.

The released 24-seed D2-vs-default experiment has 5 blue wins, 18 red wins and 1 draw. It is a public development dataset, not a hidden test set or proof of optimality. Earlier patrol studies used older recruitment rules and/or special force caps; consult their provenance before comparing numbers.

AI researchers, programmers and players are welcome to submit strategies, training reports, negative results and reproducible experiments through pull requests or issues. Read `CONTRIBUTING.md`, `game/AGENT_API.md`, `benchmarks/README.md` and `freeze/POLICY.md`. Untrusted agent programs need your own sandbox; the protocol process boundary is not a security boundary.

## Historical third training form (v0.4.1; superseded by v0.5.0 below)

[Real-map two-nation training](training/realmap-v0.4.1/) adds castle cavalry conversion and militia food logistics, with 3-hour decisions and a 10-year default horizon. This separate source package preserves the frozen v0.2.0 game. Users must import their own local map export; proprietary game map data is not distributed. An original synthetic fixture is available for public code tests, not real-map benchmarking.

## Ready-to-run real-map baseline (v0.5.0)

[Third training form v0.5.0](training/realmap-v0.5.0/) now includes the derived strategic map data and rendered map backgrounds, with vanilla_v1 as the realmap default for both countries. No separate import is required. World rules remain v0.4.1; the v0.2.0 and v0.4.1 source snapshots are preserved. Derived map assets are outside the original-code MIT grant; see the package DATA_NOTICE.md.
