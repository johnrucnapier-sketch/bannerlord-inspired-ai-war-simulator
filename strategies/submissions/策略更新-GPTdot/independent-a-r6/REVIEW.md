# A-R6 independent review — accepted for fixed experimental validation

Reviewer scope: own A-R5 source, frozen engine, four recorded own-observation streams, and candidate changes. No Hengyue implementation read; no competitive games run. Acceptance will be scoped to an exact final source hash and focused checks, not a claim of superiority.

## Design verdict

The narrowed A/B/C design is causally justified for an experimental successor: commitment-horizon mobile-enemy uncertainty; physically funded existing-party refit rotation; finite release from stalled rally. Broad anticipatory defense and new escort/patrol mechanics were explicitly deferred.

Independent raw observation at draw h26400 confirms 18 party slots occupied, no party fighting or active paths; nine 19-healthy and one 3-healthy parties at c01 with zero garrison; seven war parties totaling288 at c05 with zero garrison; 150 guard remote; c02/c12/c14 each actually hold500 garrison and2.79M food. This is a delivery/slot utilization failure, not lack of national soldiers or food.

Historical loss h1680 committed400 against a target while six enemy parties totaling418 last seen through h1632 could plausibly return during the attack commitment. Existing fixed24-hour/15km reserve filtering is not a sound arrival guarantee.

## Review requirements

- Only legal observations; enemy orders/path are not exposed.
- Mobile reserve reachability includes elapsed uncertainty, own approach, siege preparation and combat; no duplicate current city-defender counting; updated sightings replace old counts, expiry is uncertainty compromise rather than evidence of kills.
- Per-destination healthy manpower AND full engine30-day refill food must be jointly reserved; resident/earlier recipients cannot be double-promised.
- Depleted parties below20 healthy must be eligible for recovery although excluded from offensive cohort.
- Recovery is real accepted move → actual existing garrison transfer → deployed/supplied force, not renamed waiting or credited future production.
- Lost/besieged/unsafe/unfunded destination invalidates assignment; finite failure release; in-transit refitters excluded from simultaneous offensive orders.
- Historical feasible opening parity, cold restart, command acceptance, no changes to frozen game or previous version.

## Residual design risk

A336-hour full-strength memory envelope is deliberately conservative and may suppress aggression across much of the map. Focused tests can verify implementation and expiration, not establish that this horizon is competitively good. No lowering of siege thresholds is approved merely to force action.

## Final source and checks

Approved exact source SHA-256:
`27969520a45c16c60e4b68f65017e6b4cae6bc0b7992d092c610375bd97e1f88`.

Approval covers starting the parent-approved fixed small test plan, not claiming strength or replacing previous versions. Any source edit voids this hash-scoped approval until affected tests and review repeat.

Independent run of package validator:38 tests passed,0 failures/errors;807 frozen files unchanged; exact initial opening command parity both colors against historical A-R3 (inherited A-R5 opening); two cold protocol subprocesses h0/h1 clean stdout JSON, correct request IDs, empty stderr. Source hash unchanged before/after.

Independent own suite:8 tests passed. Five engine-only tests copied into package `test_ar6_review.py` at builder request; those five are included in the38, not38+8 independent cases. Other three use original own-observation replay snapshots and are private historical branch regressions.

Specific independent coverage:
1. Original h1680 predecision state+observation: original A-R5 emitted six siege commands; candidate emitted none and priced>300 reachable reserve. This is a branch test, not a counterfactual victory claim.
2. Original h26400 state: candidate assigns funded refit routes including the3-healthy party; excludes refitters from offense and sum of promised healthy additions never exceeds currently observed reservoir healthy force.
3. Expired sightings and currently counted city defenders do not double-add reserve.
4. Real engine accepted move, physical arrival and `service_party`: depleted3 becomes150 using existing garrison; combined healthy manpower and city+party food conserved; refit assignment subsequently releases. This is an isolated subsystem fixture, not a complete game.
5. Same-turn dispatched food cannot fund an inbound refit claim.
6. Lost funding invalidates existing route and real accepted stop clears its path.
7. Resident automatic surplus uptake above400 garrison is deducted before promising remote refills.
8. Economic expiry resets rally epoch, allowing recovered force a new scouting opportunity rather than instant repeated timeout.

Issues raised and corrected before approval: same-turn food spending omitted; old invalid refit path not stopped; filled party stale-health rotation; resident auto-service surplus missed; economic-expiry timestamp interacting with new stall gate. Final tests rerun after fixes.

Limitations: no opponent source read, no competitive games run by this reviewer, no win-rate conclusion. Cold restart cannot reconstruct observations seen only before restart. Fixed memory and recovery windows remain strategy choices with possible tempo cost. Defensive relief behavior otherwise remains inherited; this does not establish that every first-wave failure can be recovered.
