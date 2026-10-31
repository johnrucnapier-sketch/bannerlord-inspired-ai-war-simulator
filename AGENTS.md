# Repository working agreement

- Read README.md, freeze/POLICY.md and benchmarks/README.md before strategy work.
- v0.2.0 game files, reference snapshots and existing experiment records are frozen. Do not change them to improve a strategy score. Explicit rule-change requests require a new baseline, preserving the old one.
- Add strategies under strategies/submissions/<name>/ and new experiments under benchmarks/community/<id>/.
- Keep march as the default reference opponent. Do not promote an experimental policy silently.
- Preserve every planned test outcome; report rule/config/source hashes, seed selection, side assignments, failure and timeout counts. Distinguish historical-rule evidence from current-rule evidence.
- Run tools/verify_release.py. Do not automatically run untrusted submitted agents or long training jobs as routine review.
- Do not publish credentials, private machine paths, host connection details, game saves or third-party proprietary assets.

## Authorized v0.5.0 exception (2026-10-31)

The owner explicitly approved vanilla_v1 as the default for realmap only and publication of the derived strategic-map JSON and rendered PNGs. Keep duel/rural defaults and the frozen v0.2.0/v0.4.1 directories unchanged. This exception does not authorize game DLLs, full source scenes, original textures, private saves or credentials. See training/realmap-v0.5.0/aiwar/data/west_north/DATA_NOTICE.md for provenance.
