# v0.7.2 cold-viewer performance candidate

This is an independent candidate, not an edit to main's v0.7.0 or v0.7.1 source or manifests. It retains the game rules, map, Dev19/Dev20 sources, eight concurrent private processes, cold starts and the actual two-second JsonAgent deadline. No campaign was run to create this patch.

## Why another patch

After v0.7.1 passed its pre-merge checks, main run 42547397215 failed the Ubuntu cold viewer test; Windows passed. The merged tree was identical to the tested head. Local fixed-input diagnostics showed little margin under two available CPUs. Earlier success is preserved as evidence, not treated as a guarantee.

## Exact changes from v0.7.1

- `aiwar/real_map.py`: bind invariant search references locally and read a node's current cost once per expansion. Heap tuples, arithmetic, neighbor order, relaxation and ties are unchanged.
- Cache only interior portal-to-portal paths, keyed by the preceding/current/following face IDs, bounded to 8,192 entries. Mesh geometry is immutable. Cache values are tuples, copied back to fresh nested lists for each result. Dynamic first/final segments, numeric coordinate types and exclusion handling are unchanged.
- Package version metadata becomes 0.7.2.
- Extended initial-command comparison includes v0.7.0, v0.7.1 and this candidate. New tests compare every portal transition and 120 complete routes with fractional endpoints, exclusions and deliberate mutation of returned lists.
- `scripts/profile_cold_viewer.py` records each nation's elapsed time, actual timeout/error, request and command digests, source hashes and available CPU count. It uses fixed initial observations, advances zero world hours and starts new agents for every trial. Elapsed time includes launch/cleanup; the original JsonAgent timeout result is authoritative.
- This note replaces the inherited patch note. Other inherited files, including timeout/lifecycle code and viewer tests, remain byte-identical.

## Validation and limits

The existing 161 ordered-route cases remain. Cold viewer tests retain their original assertions and two-second limit. Existing lifecycle negatives must continue to fail genuinely slow/blocked agents and pass their bounded-cleanup assertions. CI records a fixed five-trial sample without retry-until-success; any candidate error fails its step. Linux additionally tests with two CPUs where affinity control is available.

Exploratory stale-heap pruning did not create sufficient margin (one of three two-CPU trials still timed out) and was discarded. A shared heuristic-cache experiment did not clearly improve the final candidate and was also discarded. No failed run was erased or represented as a pass.

Reported samples do not prove arbitrary-load reliability, long-campaign performance or strategic superiority. The prior main failure remains valid. The copied rules documents describe inherited behavior; copied historical validation notes are not new v0.7.2 evidence.

## First remote candidate results retained

Commit 30af397 passed the five default-four-logical-CPU trials on both Linux and Windows. Its Linux two-logical-CPU tests genuinely failed: push run 42552332410 had 40/40 timeout decisions and PR run 42552368895 had 26/40. No rerun was requested. This candidate is not recommended as a completed reliability fix. Those runners did not record CPU topology, so their physical-core arrangement cannot be inferred from the failure.

The diagnostic-only follow-up records topology for new Linux runners and runs the full regression and integration stages even after stress failure. Any stress failure still makes the whole job fail. It does not change navigation code, remove the two-CPU gate, increase the budget or retry until passing.
