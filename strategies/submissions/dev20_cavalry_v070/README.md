# Dev20 cavalry policy · v0.7.0 engine

Country-neutral, observation-only strategy update of `dev19_multinational_v070`. This is a **new strategy version**, not a new rule baseline. The frozen v0.7.0 engine, old Dev19 policy and earlier game versions are unchanged. Default `vanilla_v1` is unchanged.

## What changed

- Every available mobile lord party receives a cavalry preference, including underfilled parties. The old policy only set that preference on a completely healthy, full 150-person party already beside cavalry stock.
- Composition commands run **after** reserved recruitment, dispatch, formation and mobilization orders. Setting a preference may immediately trigger ordinary city service; it must not consume troops or food that an earlier transaction reserved.
- Mobile lord parties on local patrol/escort/clearance work get first priority for preference updates; eligible patrol formations also precede other formations when choosing physical cavalry refits. Active escort, clearance, pursuit, relief, combat, recovery and urgent supply duties are not interrupted for a cavalry trip.
- Eligible formations can visit a friendly cavalry source within 48 travel hours. The route must be reachable and pass the existing visible-danger filter, with food for a return route plus four days, sufficient source food for actual refilling, a maximum 24-hour campaign detour, a 72-hour task deadline and a seven-day cooldown. The source's real cavalry and food are reserved among choices in that decision. No remote troops count toward combat strength.
- Full parties exchange real infantry for real cavalry through the engine's normal city service. Both party and garrison headcounts remain unchanged in that exchange. Underfilled parties may additionally recruit under existing rules; their recruitment can reduce the garrison and is not described as a headcount-preserving swap.
- The new policy also fixes an inherited relief-route edge case found during its smoke test: candidates must be able to reach their staging point using the same siege-avoidance terrain as the engine, not just the ordinary road route.

There is no new recruitment, training, movement, damage, reward, teleport or resource rule. Automatic settlement patrols do not expose a composition command or the mobile lord-party cavalry speed bonus, so this strategy does not rewrite them. Cavalry preferences and visits are requests, not guaranteed acquisition: stock can change during physical travel.

## Run

Use the v0.7.0 environment and repository layout. The JSONL entry is:

```sh
python strategies/submissions/dev20_cavalry_v070/agent.py
```

Example from the repository root with the v0.7.0 package installed:

```python
import sys
from pathlib import Path
from aiwar.match import run_match
entry = Path('strategies/submissions/dev20_cavalry_v070/agent.py').resolve()
run_match([[sys.executable, str(entry)] for _ in range(8)],
          'runs/dev20-eight-nations-smoke', seed=1, days=3,
          timeout=10, mode='realmap')
```

All countries receive identical source and parameters. The output directory must not already exist. Three days is an integration check, not evidence of strategy strength.

## Validate and reproduce

```sh
python -m unittest discover -s strategies/submissions/dev20_cavalry_v070 -p 'test_*.py' -v
python tools/verify_release.py
python tools/verify_training_v070.py
python strategies/submissions/dev20_cavalry_v070/verify.py
```

`MANIFEST.json` records this strategy's explicit public files and engine freeze identity. `VALIDATION.json` separates the failed development smoke from final verification. The 38 inherited regression tests remain, with the relief mock redirected to the new policy's equivalent implementation. Added cases cover real cavalry/headcount/food conservation, partial parties, physical travel before exchange, command ordering, competing source claims, danger, food, cooldowns, command limits, immutable observations and legal decisions for all eight countries.

The first 21-day development smoke (seed 73110129) had zero process errors/timeouts but 23 rejected relief wait moves. That failed record is retained; it is not called acceptance. It led to the route correction described above. A short run cannot establish country advantages, the long-run efficiency of collection trips, or improvement over Dev19. The planned twelve-seed study is a separate experiment with its own frozen source, outcomes and failure accounting. It uses each nation's final town-plus-castle count, without village weighting or invented bonuses.

Final r2 verification: all **51 tests passed**; the same-seed 21-day smoke completed with **zero errors, timeouts or invalid commands** and a successful exact-physics command replay. It issued 153 composition commands; all 146 surviving mobile parties had the maximum cavalry preference. Terminal healthy cavalry were 34 in mobile parties and 79 in garrisons. No dedicated collection trip naturally triggered in this short run; its physical-march behavior is verified separately in constructed engine tests. These are implementation checks, not country-ranking or improvement claims.
