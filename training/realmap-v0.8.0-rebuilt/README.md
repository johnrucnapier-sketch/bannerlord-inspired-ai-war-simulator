# 八国外交重建基线 · v0.8.0-rebuilt.1

Python package version: `0.8.0+rebuilt.1`.

This is a **new reconstruction from verified v0.7.0 source**, not recovery of the lost v0.8.0 bytes. The unavailable v0.7.1 optimizations are not assumed present. Previous simulation results do not validate this reconstruction. See [REBUILD_PROVENANCE.md](REBUILD_PROVENANCE.md).

The strategic world retains 120 settlements, 273 villages and eight countries. Diplomacy adds war, peace, non-aggression pacts and alliances; alliances synchronize existing and new wars. Military control, logistics and fog of war remain country-private. No free-form international communication or joint strategic/tactical planning is added.

Enable rules with configuration `diplomacy_enabled: true`; the initial state remains all-at-war. Disabled diplomacy retains the previous free-for-all mode. `vanilla_v1` remains the default realmap policy; the diplomacy policy is a separately selected experimental submission, not a silent default replacement.

## Run and validate

From this directory:

- `python -m aiwar.match --help` for external-agent JSONL matches; provide configuration containing `diplomacy_enabled: true`.
- `python -m unittest discover -s tests -p 'test_diplomacy*.py' -v` for focused reconstruction tests.
- `python scripts/check_tests_isolated.py` for all test modules in isolated processes.

From repository root: `python tools/verify_release.py` checks the original frozen release.

[Diplomacy specification](DIPLOMACY.md) defines durations, command API, simultaneous conflicts, private observations and combat simplifications. Existing v0.7.0 rules still govern unchanged economics, terrain, mobilization and clan migration. [README_BASELINE_v070.md](README_BASELINE_v070.md) preserves historical documentation; its old validation claims and release labels are **not rebuilt-version evidence**.

## Draft publication status

This diplomacy snapshot is independent of [performance PR #4](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/pull/4), whose v0.7.2 optimizations are not integrated here. That PR remains draft and unmerged; its single-physical-core pressure checks failed. Neither candidate is represented as merged into main.

The rebuilt development suite initially passed 36 of 37 modules; the existing eight-process viewer integration exceeded its original two-second limit. The first isolated retry also failed; a subsequent unchanged-code retry passed. These records are not described as an all-green first run or a universal timing guarantee. Publication checks are reported in the draft PR separately.

The formal twelve-seed evolution campaign was still running at publication preparation. This PR contains source, rules and necessary tests/documentation only: no experiment logs, training results, checkpoints or saved games. Its source is copied independently from the frozen campaign snapshot; publication documentation edits do not modify the running simulation.
