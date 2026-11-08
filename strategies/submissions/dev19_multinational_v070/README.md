# Dev19 multinational v0.7.0 adapter

Optional experimental strategy for the [eight-nation training baseline](../../../training/realmap-v0.7.0/README.md). It does not replace `vanilla_v1` or any frozen reference opponent, and has not been established as a stronger strategy.

## Install and run

Install `training/realmap-v0.7.0` in its own virtual environment and keep this directory at `strategies/submissions/dev19_multinational_v070/`. From the repository root, the JSONL v1 entry point is:

```sh
python strategies/submissions/dev19_multinational_v070/agent.py
```

This command waits for host requests; it does not start a match by itself. To run eight independent copies, save the following as a Python file at the repository root and run it with the same virtual environment:

```python
import sys
from pathlib import Path
from aiwar.match import run_match

entry = Path("strategies/submissions/dev19_multinational_v070/agent.py").resolve()
agent = [sys.executable, str(entry)]
run_match(
    [agent.copy() for _ in range(8)],
    "runs/dev19-eight-nations-smoke",
    seed=1,
    days=3,
    mode="realmap",
)
```

The output directory must not exist. Three days is an integration smoke test, not a strategy benchmark. The Godot viewer also offers this strategy when the companion files are present and match its registered hashes. Missing or changed files do not silently select an older strategy. Private observations segregate fields but do not guarantee adversarial non-inference: globally increasing entity IDs may reveal allocation activity. Independent processes and timeout cleanup are not a malicious-code sandbox.

## Source identity and adaptation

`dev19_original.py` is the included, unchanged source snapshot. Its SHA-256 is:

`92549e49a7be8f721411048c549c3a804ff9249865902d300b46cdeec5f8b1b3`

The identity test uses this included snapshot and expected hash; no unpublished strategy directory is required.

- `dev19_base.py` ports the snapshot to the new runtime. It retains stock reservations, convoy logistics, troop raising, base scoring, food budgeting, recovery helpers and command limits. It uses observed country IDs and actual per-clan party caps, and removes the obsolete fixed-city victory/return-food exception.
- `agent.py` adapts campaign, recovery and rally behavior. Clans form independent armies; eligible ruler/marshal hosts can accept the limited support exception. Parties assemble only after physical co-location. Single-slot clans can act independently.
- Campaigns may share a base, staging point and target. Siege commitments count nearby arrivals, not remote promises. Formations keep independent food, routes and movement state; stale targets are approached and reassessed.
- The strategy retains the original readiness threshold of 25 healthy troops and 14 days of food for mustering. Local family armies do not wait for a national 650-person pool. Combat commitments still require actual local strength and a funded outward, combat and return route.
- Interception, clan-safe relief, food raids and reachable stocked supply stops use private observations. No country-specific tuning or hidden state is used.

## Militia and mobilization

Joined `levy` cohorts count only in their actual army's logistics and food consumption. They contribute half regular-infantry strength, do not use regular-party recruitment slots and do not inflate refill capacity. Traveling levy are not remotely counted. Existing mixed ruler/marshal hosts are retained, commanders come from current metadata, and recruitment follows current clan ownership after migration.

The shared observation-only organization helper runs once per command batch. It can route a threatened family army to its own reachable safe castle, issue a lawful mobilization, then move to the actual family rally. It respects the observed collection deadline, with a seven-day policy wait budget. Combat and emergency food tasks take precedence. Accepted commands dispatch physical couriers; the helper does not bypass population, food, distance or arrival rules.

## Bounded local tasks

Weak formations can protect loaded friendly carts, clear visible catchable bandits, patrol owned village routes or cautiously harass exposed enemy carts. Local assignments last at most 48 hours; a siege rendezvous can fall back after 72 hours without sufficient local strength. Chases stop after 12 hours. Each sortie budgets its own outward, combat and stocked-return food, considering observed enemies, actual movement speeds and protected farmers.

The policy creates no rewards. Deliveries, losses, battles and unit destruction are measured by the host. A successfully escorted trip is not proof that the cargo would otherwise have been lost.

## Verification and limits

From the repository root, with the v0.7.0 environment active:

```sh
python -m unittest discover -s strategies/submissions/dev19_multinational_v070 -p "test_*.py" -v
python tools/verify_training_v070.py
```

All 38 adapter tests passed without skips in the latest clean public export. They cover legal assembly, independent singletons, local strength, food and recovery, stale targets, tier caps, snapshot identity, militia and local-task boundaries. The current candidate also ran 313 core tests in 35 isolated modules: 311 executed passes and two intentional historical-fixture skips. The mandatory synthetic all-country fog cases still ran for both policies. All these suites used Linux, Python 3.12.14 and the declared websockets 15.0.1 dependency in an isolated virtual environment. SDK determinism, save/load continuation, replay, eight real default-agent processes, repeated-seed one-day matches, the public CLI and its result checker also passed. The shared environment was unchanged. Actual remote CI and Windows execution remain pending; a configured workflow is not a platform pass. Initial command acceptance is not a completed campaign.

Two same-seed 21-day development runs had zero agent errors, timeouts and invalid commands. Adding local tasks increased delivered food slightly but also increased lost village carts and reduced captures. These mixed diagnostics do not establish a general improvement or a country ranking. A subsequent 84-day development run also completed with zero agent errors, timeouts and invalid commands. It recorded 112 national battle starts, 48 captures, five actual clear-bandit wins and natural militia joining armies, but no militia returns or national extinction. This run predates the final acceptance fixes and does not establish causal cargo savings or country rankings. Constructed and natural evidence are reported separately in [VALIDATION.md](../../../training/realmap-v0.7.0/VALIDATION.md), along with candidate-source checks, long-run evidence boundaries and pending publication checks.

A later r7 match was interrupted at day 632.5. Two independent verification paths reconstructed its full prefix, including 5,060 cycles, 40,480 private requests and 29,459 command outcomes, producing identical endpoint save bytes; all 102 original files were rehashed unchanged. The 49 historical invalid assembly commands remain in the record.

Two branches have now run from that same checkpoint to day 840: the original r7 continuation and a candidate fork changing only the duplicate-host-army and unsent-cancellation fixes. Each executed 207.5 late days, 1,660 cycles and 13,280 private requests. Both complete suffix replays and their linkage to the verified prefix passed, including private requests and previous outcomes, command outcomes, world checks, final full/physics digests and all eight terminal private observations. Replay uses recorded commands rather than rerunning policy decisions. The original continuation used one source version throughout its interrupted/resumed 840-day trajectory, added 34 invalid commands for 83 total, and ended with Aserai holding 41 settlements and Vlandia 37. The candidate suffix had zero new errors, timeouts or invalid commands, retains 49 historical invalid commands, and ended with Vlandia holding 43 settlements and Aserai 33.

The candidate mixed-version trajectory recorded 1,034 national battle starts and 336 captures; 284 starts and 107 captures occurred in its suffix. A new Vlandian mobilization produced 13 cohorts that actually joined an army. At the terminal state, 22 militia cohorts totaling 756 people were attached across the world. These are terminal counts, not cumulative unique arrivals, and neither branch demonstrated a natural successful return home. See [VALIDATION.md](../../../training/realmap-v0.7.0/VALIDATION.md) for initial and final territories, migration and cancellation details.

These are debugging and compatibility branches sharing one historical prefix, not independent seeds or an 840-day candidate run from seed. Different territory outcomes do not establish country/culture rankings or causal strategy improvement. The public file set is frozen by an explicit manifest. The requested bounded 1/2/4 concurrent-match measurement is complete; actual remote CI/Windows execution remains pending.

The seven same-seed 21-day concurrency replicas all completed with eight distinct policy processes, 168 decisions per nation, zero errors/timeouts/invalid commands, and byte-identical results, saves and private journals. Measured throughput was 32.087, 58.270 and 105.463 matches/hour at 1/2/4 concurrent matches, respectively. Four-way throughput was 3.287× single-way, with a 21.0% increase in mean per-match latency. This is one bounded, ordered measurement without independent repeats or cache/order controls; it does not predict full 840-day costs or establish that four long matches fit available disk. Resource and measurement details are in [VALIDATION.md](../../../training/realmap-v0.7.0/VALIDATION.md).

The private historical checkpoint, original logs and complete historical replay inputs are not distributed. The public package can run new matches on the current source and its published regression tests, but cannot reproduce this exact day-632.5 branch by itself. The audited planner rebuilds its state each decision; continuation did not restore arbitrary hidden policy-process state and is not evidence that unaudited stateful agents can resume identically.
