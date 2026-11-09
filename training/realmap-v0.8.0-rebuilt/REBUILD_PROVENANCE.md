# Reconstruction provenance

Identity: `0.8.0+rebuilt.1`, displayed as v0.8.0-rebuilt.1.

Source basis: the verified delivered `realmap-v070-dev20-delivery/repository/training/realmap-v0.7.0` source. Its original location is not required to run this package. The validated source input and historical frozen directories are not edited.

Reason: two execution-environment losses removed the previous working repository; no verified backup of the lost v0.8.0 source was available. This directory reconstructs the approved diplomacy semantics from retained implementation context. It is **not claimed byte-identical** to the lost implementation. The v0.7.1 source and its optimization patches were unavailable, so equivalence with that base is not asserted.

New/reconstructed modules: diplomacy.py; engine command/observation/tick/combat changes; SDK/match batch adjudication; succession treaty cleanup; organization/relief hostility filters; coalition-safe battle spoils; focused core and independent tests. Policy adapters are separately rebuilt and explicitly experimental.

Validation must be fresh: preserve complete test outcomes, failures and timeouts, configuration/source hashes, seeds and side assignments. Development checkpoint ZIPs are recovery aids, not final benchmark provenance. Full source must be backed up before long simulation batches. Prior 12-seed or fuzz results do not apply to reconstructed bytes.

Initial reconstruction did not authorize publication. The owner subsequently explicitly requested publication of the performance and diplomacy code. This independent draft publishes the reconstructed diplomacy snapshot without merging either candidate; performance PR #4 remains separate.
