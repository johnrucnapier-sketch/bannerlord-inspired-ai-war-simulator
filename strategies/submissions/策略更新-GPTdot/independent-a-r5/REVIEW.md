# A-R5 independent candidate review

Reviewed 2026-10-31. Candidate `adaptive-ar5/independent-a-r5/agent.py` SHA256:
`21f1c90b2ff2dc3844d63ce57ef150aafd729de0dcbe587d82aadbfa10e8ea2c`.

## Decision

Qualified approval for publication as an **experimental successor for external match testing**. No release-blocking defect found in the locked source and focused fixtures. This is not evidence that A-R5 beats A-R3 or that the strategy is robust against every counterstrategy.

The adaptation is substantive: it cancels infeasible approaches before battle, rejects unfunded recovery destinations across inherited phase paths, remembers failed commitments, selects affordable alternate cities, and can execute finite observed-threat defense or a valuable village raid. It does not depend on opponent source or hidden simulation state. Original A-R3 remains separate.

## Independently executed verification

- `python adaptive-ar-review/test_independent.py`: 3/3 passed (0.087s).
- `PYTHONPATH=a-r3-publication-repo/game python adaptive-ar5/independent-a-r5/test_agent.py`: 23/23 passed (0.627s).
- SHA256 independently checked after tests; matches locked source above.

Reviewer-authored fixtures use the real frozen engine command processor and steps, not merely expected policy labels:
1. Three actual accepted siege approaches are canceled before contact; orders/path are cleared and subsequent steps do not enter battle.
2. Fresh strong defense changes scouting into economic recovery; commands are accepted and troops physically retreat rather than retry the same siege.
3. An isolated empty depot reports stranded without imaginary shelter savings; external food arrival permits actual accepted recovery actions and clears stranded state.

Author fixtures, independently rerun, cover real adjacent convoy arrival, actual raid completion/population loss, actual destruction of an observed corridor threat, real cart supply, two hungry parties competing for a limited refit stock, unsafe old-path cancellation, cold restart during battle, and opening command acceptance. Historical one-step/protocol audit results are separately supplied by the author; they are not full counterfactual matches.

## Material corrections made during review

- Removed false shelter-ration rationale: all troops within an owned city's service radius already consume the city ration, including parties. Transfer to garrison does not halve consumption.
- Replaced nominal partial refill estimates with full 30-day automatic refill claims, including expected replenishment and travel consumption.
- Required shared destination claims and centralized food checks so inherited recovery/rally paths cannot bypass empty-depot rejection.
- Required actual stop on newly unsafe old paths, not simply rejecting a new command while the old march continues.
- Required dispatch crew plus local defense floor and explicit acknowledgment of automatic city-service limitations.

- Final lifecycle fix reviewed: expiration of an economic window can re-enter a new bounded economic evaluation when rally has no selectable city; the new 23rd fixture checks renewed operation commands. It does not itself run a second full raid, while the separate raid fixture validates actual command acceptance and completion.

## Limitations and external test priorities

1. Global rally thresholds (90% of available campaign strength) and economic regroup threshold (80%) remain. Full-cohort full-refit funding is deliberately conservative and may suppress initiative when a smaller useful force could act. Measure idle time, refused profitable commitments, geographic dispersion, and repeat rally/recovery loops.
2. Fixed force margins, coarse battle-duration/loss estimates, local route-threat approximations, and short remembered-threat windows are heuristics, not guarantees. Test moving defenders, reinforcement feints, divided fronts and pursuit traps.
3. Automatic `reserve_refill_target` cannot be lowered by policy; engine overflow service from garrisons above 400 can also replenish troops. The code must not be advertised as guaranteeing a hard reserve floor or exact future stock under every automatic-service event.
4. Disconnected, foodless armies may be irrecoverable. Stopping a doomed march or marking stranded creates no food. Prevention is improved, not universal rescue.
5. Food claims reserve observed stock, not every future delivery/consumption event over a long march. Dispatch acceptance and route feasibility do not guarantee survival against subsequently observed enemies.
6. Warm process memory retains failure/threat information; cold restart reconstructs legal current behavior but cannot recover unpersisted historical sightings/cooldowns. A fresh process is not strategically equivalent to uninterrupted play.
7. No full matches or superiority comparisons were run. External evaluation should retain both old versions and source hashes, test both sides, and report combat losses, food-starvation losses, productive capacity, idle time and win rate, not win rate alone.

Review sources: frozen `a-r3-publication-repo/game/aiwar/engine.py`; old behavior/forensic reports; candidate source and tests; reviewer fixtures. No opponent implementation was consulted.
