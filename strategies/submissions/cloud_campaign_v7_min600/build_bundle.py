#!/usr/bin/env python3
"""Create an allowlisted, portable Campaign600 v1 runtime ZIP; no games/network."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import run_match

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new ZIP path; no overwrite')
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        parser.error('output already exists')
    run_match.verify_identity()
    dependencies = json.loads((HERE / 'DEPENDENCIES.json').read_text())
    selected = set(dependencies['local_python_files'])
    selected.update(['game/aiwar/config.json', 'freeze/v0.2.0.json', 'freeze/POLICY.md',
                     'game/AGENT_API.md', 'game/RULES.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md'])
    for name in ['README.md', 'REPORT.md', 'VERSION', 'DEPENDENCIES.json', 'run_match.py',
                 'test_submission.py', 'build_bundle.py']:
        selected.add(str((HERE / name).relative_to(ROOT)))
    payload = {relative: (ROOT / relative).read_bytes() for relative in sorted(selected)}
    manifest = dict(name='Campaign600 v1', author='GPT dot', baseline='v0.2.0',
                    policy_sha256=run_match.POLICY_SHA256, freeze_manifest_sha256=run_match.FREEZE_SHA256,
                    scope='runtime subset, not the complete frozen release',
                    files={p:dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest()) for p,b in payload.items()})
    payload['BUNDLE_MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    payload['README-BUNDLE.md'] = b'Campaign600 v1 by GPT dot. Runtime subset; standard library only.\nRun python strategies/submissions/cloud_campaign_v7_min600/test_submission.py\nThen see that directory README for official JSONL head-to-head invocation.\nEvidence links in copied docs refer to the full GitHub contribution, not this runtime subset.\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, data in sorted(payload.items()):
            info = zipfile.ZipInfo(relative, date_time=(2026, 10, 29, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    print(json.dumps(dict(files=len(payload), sha256=hashlib.sha256(output.read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()
