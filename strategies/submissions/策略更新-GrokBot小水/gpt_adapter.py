"""Adapter (Grok Bot / 小水): load GPT dot's Campaign600 v1 as an opponent WITHOUT copying or modifying it.
Source: branch gpt-dot/campaign600-v1-20261029, commit 02966b3,
path strategies/submissions/cloud_campaign_v7_min600/policy.py (SHA256 1aed9815...6c44).
The policy is extracted byte-for-byte with `git show` into a scratch dir outside the repo, which gets
symlinks to this checkout's frozen game/ and strategies/reference/ so its ROOT=parents[3] imports resolve."""
import hashlib, os, subprocess
from pathlib import Path
COMMIT = '02966b3555315eb5955499799d7bcefba390fd10'
REL = 'strategies/submissions/cloud_campaign_v7_min600/policy.py'
SHA = '1aed9815302f846238d4756c378b7161ba2170869008205a20662b1a96ba6c44'
ROOT = Path(__file__).resolve().parents[3]
SCRATCH = Path(os.environ.get('C600_DIR', '/workspace/gpt-campaign600'))
def policy_path():
    p = SCRATCH / REL
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(subprocess.run(['git', 'show', f'{COMMIT}:{REL}'], cwd=ROOT, capture_output=True, check=True).stdout)
        (SCRATCH / 'strategies').mkdir(exist_ok=True)
        for link, target in (('game', ROOT / 'game'), ('strategies/reference', ROOT / 'strategies/reference')):
            if not (SCRATCH / link).exists(): os.symlink(target, SCRATCH / link)
    if hashlib.sha256(p.read_bytes()).hexdigest() != SHA: raise SystemExit('Campaign600 v1 policy hash mismatch')
    return p
if __name__ == '__main__': print(policy_path())
