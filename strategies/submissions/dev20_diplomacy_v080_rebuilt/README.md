# Dev20 diplomacy v0.8.0-rebuilt — experimental reconstruction

This is a **new implementation reconstructed from retained requirements**, not
recovery of the lost v0.8.0 source, its hashes, or its validation artifacts.
Historical diagnostic numbers are not results for this implementation. The
recovered v0.7 Dev20 military source is vendored byte-for-byte in
`military_baseline/`; `MANIFEST.json` records those source identities.
No v0.7 file is changed. The historical military thresholds, cavalry,
recruitment, logistics and formation methods are reused without modification.

## Information and policy

The policy consumes only its own observation. There is no World import, enemy
true-army total, enemy stock lookup, shared vision, free-text negotiation,
shared target, or strategic/tactical collaboration mechanism. Reasons are
private diagnostic records, not messages revealing private resources to peers.

Own field health, wounds, carried food, own garrison replenishment and known
city adjacency are assessed. **Readiness is deployability, not full reinforcement:**
regular parties need at least 25 healthy troops, levy need positive healthy
troops, wounded share must be at most 35%, and carried food at least seven days.
The fraction meeting these conditions is readiness. Healthy/full roster
capacity is reported separately as reinforcement fill. A 40-man healthy party
must not be falsely treated as an emergency merely because its cap is 150.

Enemy strength is a proxy: max(visible current party strength plus half visible
levy strength, 100 times known/last-seen holdings). Unseen forces and stale
ownership remain explicitly unknown. Own replenishment is min(1, own garrison
reserve / missing field troops); it is not invented future income.

Experimental scoring, fixed before the original-twelve campaign:

- Pressure: 1.4 per extra active border front, plus 3 times readiness shortfall
  below .75, food stress (1.5 below seven days, .7 below fourteen days), and
  replenishment shortfall below .5.
- Peace: pressure plus .6 times capped-at-two enemy/own proxy ratio, plus .8
  for a nonborder war. Subtract 1.2 when at most one war remains, readiness is
  at least .7 and food at least fourteen days. Threshold: 1.5.
- Alliance: .35 per shared enemy; +1.2 if a shared enemy holds at least 30% of
  known holdings; +min(1, pressure×.25); −1.25 per imported war; −.5 for a
  neighbor. Threshold: 1.0. Bloc and third-party NAP compatibility is checked.
- NAP: propose under pressure≥1.4; accept under pressure≥.7 or without a border.
- Declaration: only with no existing wars, a peaceful neighboring target,
  readiness≥.7, food≥14 days and own/enemy capacity proxy≥1.1.

All existing and future alliance wars are synchronized by the engine; the
policy cannot selectively opt out. There is no forced minimum number of wars:
full peace is permitted when justified by the observation and thresholds.

## Timing, state and repeated proposals

The ordinary strategic cycle is tentatively 168 hours. Meaningful events can
open an immediate opportunity; the rebuilt engine uses **zero event cooldown**.
This is distinct from an early discarded 24-hour-cooldown draft. Incoming
proposals receive prompt accept/reject replies independently of that cycle.
At most one initiative is emitted per opportunity; a no-action opportunity
emits `hold` so the engine consumes it. A live incoming or outgoing proposal
blocks another initiative to that same country. Expired proposals are ignored.

The policy is stateless between calls. All gates, signatures, proposals and
receipts must be serialized by the engine. Identical observations produce
identical output. A genuinely new event after rejection can cause a new offer;
zero cooldown is not a promise of weekly-only proposal counts. Preflight must
report repeated offers/rejections rather than hiding possible event churn.

## Military adapter and command budget

With diplomacy disabled, call the recovered military `decide` directly.
Otherwise filter nonenemy units, villages and frontier targets while preserving
known city geometry. Never relabel allies as owned assets or grant access to
their food, troops or transports. Audit attack/siege/raid and campaign metadata;
stop obsolete neutral-target offensive approach/scouting while preserving
homeward recovery and supply moves.

Diplomatic replies come first. Remaining command capacity is filled using an
exact prefix of **whole** military transactions. `disband→assemble→move` and
`assemble→move` stay intact; never slice the combined command list blindly.
Neither command filtering nor this budget changes combat rules.

The adapter is self-contained with its vendored Python files and honors the
host's `PYTHONPATH` engine. Repository fallback is `realmap-v0.8.0-rebuilt`.

Test command:

`PYTHONPATH=training/realmap-v0.8.0-rebuilt python -m unittest discover -s strategies/submissions/dev20_diplomacy_v080_rebuilt -p 'test_*.py' -v`

Freeze and persist source, parameter manifest, tests and hashes before long
runs. Preserve all seeds, invalids, errors, timeouts and failures. Do not compare
historical results as if they came from this rebuilt implementation.
