# Repository working agreement

- Read README.md, freeze/POLICY.md and benchmarks/README.md before strategy work.
- v0.2.0 game files, reference snapshots and existing experiment records are frozen. Do not change them to improve a strategy score. Explicit rule-change requests require a new baseline, preserving the old one.
- Add strategies under strategies/submissions/<name>/ and new experiments under benchmarks/community/<id>/.
- Keep march as the default reference opponent. Do not promote an experimental policy silently.
- Preserve every planned test outcome; report rule/config/source hashes, seed selection, side assignments, failure and timeout counts. Distinguish historical-rule evidence from current-rule evidence.
- Run tools/verify_release.py. Do not automatically run untrusted submitted agents or long training jobs as routine review.
- Do not publish credentials, private machine paths, host connection details, game saves or third-party proprietary assets.
