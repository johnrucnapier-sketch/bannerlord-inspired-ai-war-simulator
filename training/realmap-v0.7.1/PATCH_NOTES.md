# v0.7.1 navigation performance patch

This independent package preserves `training/realmap-v0.7.0` and its manifest byte for byte. The simulation rules, map data, strategy sources, JSONL protocol, eight concurrent private agent processes and 2-second viewer decision deadline are unchanged. The older documentation copied with the package describes the unchanged rules; this note describes the patch only.

Changes relative to v0.7.0:
- `aiwar/real_map.py`: calculate immutable directed edge lengths once per Mesh, preserving neighbor iteration order and the exact arithmetic; reuse goal-distance values within each route search. No change to heap ordering, tie-breaking, exclusion handling, cache size or paths.
- `aiwar/__init__.py` and `pyproject.toml`: package version 0.7.1.
- `tests/test_route_cache_v071.py`: compare exact ordered route tuples against the preserved original algorithm for 161 deterministic cases, including exclusions; check every cached edge value and neighbor order.
- This patch note. Other inherited source bytes remain identical.

Reason: Windows v0.7.0 eight-agent viewer tests repeatedly exceeded the original 2-second budget, including three isolated cold trials. Linux profiling located most cold-decision CPU work in repeated fixed navigation geometry calculations. Cold and warm diagnostics are measurements, not campaign results or proof of universal runtime performance.

The original failure remains part of the record. No timeout has been enlarged, no process is silently warmed, and no failed assertion is skipped. Run all inherited lifecycle tests to verify actual timeouts and bounded cleanup, along with the unchanged viewer test on Windows and Linux. Test coverage does not establish long-campaign performance or strategy superiority.

Run from this package: `python scripts/check_tests_isolated.py`. Source identity and preservation checks: `python ../../tools/verify_training_v071.py`.
