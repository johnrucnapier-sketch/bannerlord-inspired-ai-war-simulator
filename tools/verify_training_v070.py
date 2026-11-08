"""Verify the explicit fourth-mode release, without importing submitted agents.

Default: read-only SHA-256 checks for all frozen baselines and public payload.
--write-manifest: maintainer-only generation from the reviewed publication list.
--smoke: additionally execute the shipped default agents and short SDK checks.
--check-match: check an existing eight-country default-agent JSONL smoke result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "training/realmap-v0.7.0"
ADAPTER = "strategies/submissions/dev19_multinational_v070"
ALLOWLIST = "freeze/v0.7.0-publication.json"
MANIFEST = "freeze/v0.7.0.json"
OLD_VERSIONS = ("v0.2.0", "v0.4.1", "v0.5.0", "v0.6.0")
NATIONS = ("empire_w", "empire", "empire_s", "khuzait", "battania", "vlandia", "sturgia", "aserai")
GENERATED_PARTS = {"__pycache__", ".godot", ".venv", ".tools", "build", "dist", "artifacts", "runs"}
PRIVATE_PATH = re.compile(r"/(?:workspace|home|Users|opt/codex)/[^\s\"'<>]+|[A-Za-z]:[\\/](?:Users|workspace)[\\/]")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(name: str) -> Path:
    if not isinstance(name, str) or "\\" in name:
        raise ValueError(f"Not a portable relative path: {name!r}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or str(pure) != name:
        raise ValueError(f"Not a canonical relative path: {name!r}")
    path = ROOT.joinpath(*pure.parts)
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError(f"Path escapes repository: {name}")
    if path.is_symlink():
        raise ValueError(f"Symlink is outside this release format: {name}")
    return path


def publication():
    data = read_json(ROOT / ALLOWLIST)
    frozen = data["frozen_files"]
    indexes = data["mutable_indexes"]
    all_names = frozen + indexes + [MANIFEST]
    if frozen != sorted(set(frozen)) or indexes != sorted(set(indexes)):
        raise ValueError("Publication lists must be sorted and unique")
    if len(all_names) != len(set(all_names)) or ALLOWLIST not in frozen:
        raise ValueError("Publication scopes overlap or omit their own allowlist")
    for name in all_names:
        safe_path(name)
        if any(part in GENERATED_PARTS for part in PurePosixPath(name).parts):
            raise ValueError(f"Generated content in publication list: {name}")
        if name.endswith((".log", ".save.json", ".jsonl", ".gz", ".pyc", ".dll", ".exe", ".xml", ".import")):
            raise ValueError(f"Non-public artifact in publication list: {name}")
    return frozen, indexes


def verify_manifest(name: str, expected_names=None):
    manifest = read_json(safe_path(name))
    files = manifest["files"]
    if expected_names is not None and set(files) != set(expected_names):
        raise ValueError(f"Manifest/list mismatch: {name}")
    for rel, expected in files.items():
        path = safe_path(rel)
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Missing or changed: {rel}")
    print(f"OK: {manifest['baseline']} / {len(files)} frozen files", flush=True)
    return files


def check_public_boundaries(frozen, indexes):
    allowed = set(frozen + indexes + [MANIFEST])
    # Only repository-tracked files are release candidates. Local validation and
    # experiment data may coexist, but must never be swept into a Git commit.
    if (ROOT / ".git").exists():
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
        prefixes = ("training/realmap-v0.7.0/", ADAPTER + "/")
        extras = sorted(name for name in tracked if name.startswith(prefixes) and name not in allowed)
        if extras:
            raise ValueError("Tracked outside publication allowlist: " + ", ".join(extras))
    # New source files must be reviewed and deliberately added to the list;
    # generated caches and local evidence are not interpreted as source.
    for directory, pattern in ((PACKAGE / "aiwar", "*.py"), (PACKAGE / "tests", "*.py"),
                               (ROOT / ADAPTER, "*.py")):
        extras = [p.relative_to(ROOT).as_posix() for p in directory.glob(pattern)
                  if p.relative_to(ROOT).as_posix() not in allowed]
        if extras:
            raise ValueError("Source missing from publication allowlist: " + ", ".join(sorted(extras)))
    for name in frozen + indexes:
        path = safe_path(name)
        if not path.is_file():
            raise ValueError(f"Missing publication file: {name}")
        if path.suffix in {".py", ".json", ".md", ".yml", ".gd", ".tscn", ".godot", ".toml"}:
            content = path.read_text(encoding="utf-8")
            if PRIVATE_PATH.search(content):
                raise ValueError(f"Private machine path in publication file: {name}")
            if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", content):
                raise ValueError(f"Private key in publication file: {name}")
    # This is a narrow publication guard, not a general-purpose secret scanner
    # and not a grant to distribute third-party source assets.


def verify_map():
    directory = PACKAGE / "aiwar/data/west_north"
    manifest = read_json(directory / "MAP_MANIFEST.json")
    expected = {"navigation.json", "settlements.json", "clans.json", "clan_tiers.json"}
    if set(manifest["files"]) != expected or manifest["runtime_nations"] != list(NATIONS):
        raise ValueError("Unexpected v0.7.0 map scope")
    for name, digest in manifest["files"].items():
        if sha256(directory / name) != digest:
            raise ValueError(f"Map data mismatch: {name}")
    print("OK: four derived map JSON files / eight default nations", flush=True)


def check_match(directory: Path):
    manifest = read_json(directory / "match.json")
    report = read_json(directory / "result.json")
    if manifest["status"] != "completed" or manifest["mode"] != "realmap":
        raise ValueError("JSONL smoke match is not a completed realmap match")
    if manifest["command_order"] != list(range(8)) or report["config"]["nations"] != list(NATIONS):
        raise ValueError("Unexpected default eight-country match order")
    for field in ("agent_errors", "agent_timeouts", "invalid_commands"):
        if manifest[field] != [0] * 8:
            raise ValueError(f"Nonzero default-agent {field}: {manifest[field]}")
    if len(manifest["agents"]) != 8:
        raise ValueError("Expected eight default agents")
    for command in manifest["agents"]:
        if command[1:] != ["-m", "aiwar.baseline_agent", "--style", "vanilla_v1"]:
            raise ValueError("Expected vanilla_v1 default JSONL agent command")
    expected_steps = report["hour"] // report["config"]["decision_hours"]
    if expected_steps < 1 or manifest["decisions"] != [expected_steps] * 8:
        raise ValueError("Missing decisions in completed smoke match")
    for nation in range(8):
        rows = [json.loads(line) for line in (directory / f"nation-{nation}.jsonl").read_text(encoding="utf-8").splitlines()]
        if len(rows) != expected_steps + 1 or rows[-1].get("type") != "terminal":
            raise ValueError(f"Incomplete private log for nation {nation}")
        for index, row in enumerate(rows):
            observation = row["observation"] if index == expected_steps else row["request"]["observation"]
            if observation["nation"] != nation or "observer_totals" in observation or "observer_events" in observation:
                raise ValueError(f"Invalid private view for nation {nation}")
            if index != expected_steps and (row["agent_error"] is not None or any(not r.get("ok") for r in row["outcomes"])):
                raise ValueError(f"Unaccepted default command for nation {nation}")
    print(f"OK: eight completed private JSONL streams / {expected_steps} decisions each / zero errors", flush=True)
    return report


def smoke():
    import os
    import tempfile
    import threading
    from unittest.mock import patch

    sys.path.insert(0, str(PACKAGE))
    from aiwar.engine import World
    from aiwar.match import JsonAgent, run_match
    from aiwar.replay import replay
    from aiwar.sdk import Environment

    if Path(sys.modules["aiwar"].__file__).resolve().parent != PACKAGE / "aiwar":
        raise ValueError("Smoke imported the wrong aiwar version")
    original_cwd = Path.cwd()
    os.chdir(PACKAGE)
    try:
        with tempfile.TemporaryDirectory(prefix="aiwar-v070-smoke-") as tmp:
            root = Path(tmp)
            env = Environment(1, {"mode": "realmap", "days": 2})
            again = Environment(1, {"mode": "realmap", "days": 2})
            if [o["nation"] for o in env.observations()] != list(range(8)):
                raise ValueError("SDK does not return eight independent observations")
            for _ in range(3):
                env.step([[] for _ in range(8)])
                again.step([[] for _ in range(8)])
            if env.world.physics_digest() != again.world.physics_digest():
                raise ValueError("SDK seed reproduction mismatch")
            env.export(root / "sdk")
            saved = root / "sdk/final.save.json"
            if replay(saved).physics_digest() != env.world.physics_digest():
                raise ValueError("SDK replay mismatch")
            loaded = World.load(saved)
            loaded.step(3)
            env.world.step(3)
            if loaded.physics_digest() != env.world.physics_digest():
                raise ValueError("Save/load continuation mismatch")
            print("OK: SDK deterministic initialization/steps, save/load continuation and replay", flush=True)

            # Observe real PIDs without replacing transport or policy behavior.
            pids = set()
            lock = threading.Lock()
            original_decide = JsonAgent.decide
            def observe_process(agent, request):
                result = original_decide(agent, request)
                if agent.process is not None:
                    with lock:
                        pids.add(agent.process.pid)
                return result
            command = [sys.executable, "-m", "aiwar.baseline_agent", "--style", "vanilla_v1"]
            with patch.object(JsonAgent, "decide", observe_process):
                first = run_match([command.copy() for _ in range(8)], root / "match", seed=1, days=1, timeout=15, mode="realmap")
            if len(pids) != 8:
                raise ValueError(f"Expected eight independent live agent processes, saw {len(pids)}")
            check_match(root / "match")
            if replay(root / "match/final.save.json").physics_digest() != first["physics_digest"]:
                raise ValueError("Eight-country match replay mismatch")
            second = run_match([command.copy() for _ in range(8)], root / "repeat", seed=1, days=1, timeout=15, mode="realmap")
            check_match(root / "repeat")
            if first["physics_digest"] != second["physics_digest"]:
                raise ValueError("Repeated eight-process default match is nondeterministic")
            print("OK: eight real processes / default match replay / repeated-seed digest", flush=True)
    finally:
        os.chdir(original_cwd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write-manifest", action="store_true")
    group.add_argument("--print-allowlist", action="store_true")
    group.add_argument("--smoke", action="store_true")
    group.add_argument("--check-match", type=Path)
    args = parser.parse_args()
    frozen, indexes = publication()
    if args.print_allowlist:
        print("\n".join(sorted(frozen + indexes + [MANIFEST])))
        return
    for version in OLD_VERSIONS:
        verify_manifest(f"freeze/{version}.json")
    check_public_boundaries(frozen, indexes)
    verify_map()
    if args.write_manifest:
        data = {"baseline": "v0.7.0", "date": "2026-11-08", "training_form": 4,
                "mode": "realmap", "default_policy": "vanilla_v1", "default_nations": list(NATIONS),
                "world_rule_baseline": "v0.7.0-multinational", "default_days": 840,
                "decision_hours": 3, "culture_basis_default": "owner (configurable modeling assumption)",
                "diplomacy_enabled": False, "process_isolation_is_security_sandbox": False,
                "prior_snapshots_preserved": list(OLD_VERSIONS), "map_data_distributed": True,
                "publication_allowlist": ALLOWLIST,
                "validation_scope": "See training/realmap-v0.7.0/VALIDATION.md; a file hash is not a performance claim.",
                "files": {name: sha256(safe_path(name)) for name in frozen}}
        (ROOT / MANIFEST).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"WROTE: {MANIFEST} / {len(frozen)} frozen files; review before publication")
    else:
        verify_manifest(MANIFEST, frozen)
        if args.check_match:
            check_match(args.check_match.resolve())
        if args.smoke:
            smoke()
        print("OK: fourth-mode package and all previous frozen file hashes")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"FAILED: {exc}") from exc
