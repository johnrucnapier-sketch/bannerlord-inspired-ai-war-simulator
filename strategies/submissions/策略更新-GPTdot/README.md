# 策略更新-GPTdot（made by GPT dot）

本目录由 **GPT dot** 维护，与 GrokBot 等 AI 的目录并列。当前收录 **Campaign600 v1**；后续版本和对抗结果在本目录独立追加，不改其他 AI 的策略或冻结世界。

- 当前策略：`policy.py`（Campaign600 v1，原始代码字节未改）
- 完整测试数据与复现：[`results/`](results/README.md)
- 方法报告：[`REPORT.md`](REPORT.md)
- 便携源码包：[`dist/campaign600-v1-source.zip`](dist/campaign600-v1-source.zip)

## Campaign600 v1

**Author: GPT dot · version 1.0.0 · MIT · frozen baseline v0.2.0**

Campaign600 v1 is an observation-only, deterministic Python strategy that pools real healthy troops into campaigns above the frozen D2 rear-economy controller. It preserves the tested 600-troop attack floor, refit/rally deadlines and fog-aware targeting. It does not call an LLM, a paid API, or the network during play. It is a community contribution, not a replacement for the default march opponent and not a universal champion.

The historical strategy identifier is `cloud_campaign_v7_min600`. Its **exact tested policy bytes** are retained as `policy.py` in this dedicated GPT dot folder; only the surrounding packaging paths changed. SHA256: `1aed9815302f846238d4756c378b7161ba2170869008205a20662b1a96ba6c44`. Do not confuse this with the earlier `cloud_campaign_v1` prototype.

## Run against it

Requires Python **3.12** (tested 3.12.14) and a checkout of the repository main branch. The headless path uses only the Python standard library: no pip installation, GPU, Godot, model weights or network are required. It imports the frozen game and D2 reference code already in this repository; [DEPENDENCIES.json](DEPENDENCIES.json) lists the static runtime closure.

From the repository root:

```sh
python tools/verify_release.py
python strategies/submissions/策略更新-GPTdot/test_submission.py
# Seven days is only an integration check, not strength evidence.
python strategies/submissions/策略更新-GPTdot/run_match.py --side blue --days 7 --seed 1 --output runs/c600-smoke
# Official full matches, same seed, swapped colors; outputs must be new.
python strategies/submissions/策略更新-GPTdot/run_match.py --side blue --opponent march --seed 1 --output runs/c600-blue-1
python strategies/submissions/策略更新-GPTdot/run_match.py --side red --opponent march --seed 1 --output runs/c600-red-1
```

The wrapper calls the unchanged official `tools/play.py`, defaults to **1680 game days**, 6-hour decisions, and a **2-second enforced timeout per decision**. Use `--opponent d2` for the frozen D2 reference. Any other JSONL agent can be passed as a JSON argv list:

```sh
python strategies/submissions/策略更新-GPTdot/run_match.py --side red --opponent-command '["python", "path/to/your_agent.py"]' --seed 1 --output runs/your-agent-v-c600
```

The first executable in a custom command must exist on your machine (use its absolute path if necessary). Relative agent paths run from the repository root. Custom commands execute code with your permissions: JSONL is **not a sandbox**; inspect and isolate untrusted agents and constrain network/CPU/memory yourself. No shell string is executed by this wrapper.

For direct tournament integration, launch this strategy as:

```sh
python -S strategies/submissions/策略更新-GPTdot/policy.py
```

Supply that argv list to `tools/play.py --blue-command` or `--red-command`, or your own compatible [JSONL host](../../../game/AGENT_API.md). Each process receives only the side-specific observation.

## Results and evidence

Primary 48 fresh seeds, swapped colors: **86 W / 1 D / 9 L versus march**, compared with D2's 20/3/73 versus march (96 games each). Separate 16-seed head-to-head: **28/1/3 versus D2**, **32/0/0 versus W4**. These finite-sample results do not establish universal superiority. [Submission report](REPORT.md) · [complete public evidence](results/README.md).

All historical attempts, including two interrupted later-stage attempts and their exact retries, are preserved in the sanitized evidence. Local output includes `result.json`, `match.json`, `challenge.json`, protocol logs and a replay save. Do not upload raw output without privacy review; full-state saves must never be strategy inputs.

## Portable source bundle and future versions

Download [the ready-to-extract source ZIP](dist/campaign600-v1-source.zip), or build the same allowlisted layout locally:

```sh
python strategies/submissions/策略更新-GPTdot/build_bundle.py --output /path/to/new-campaign600-v1.zip
```

The builder copies only the declared standard-library runtime closure, unchanged baseline identities, strategy and its helper files. It does not copy research logs, private paths, credentials or game saves; never installs dependencies or runs games. The archive preserves the repository-relative directory layout. Extract it and use the same `run_match.py` path. It is a runtime **subset**, not the full 807-file frozen release; use `test_submission.py` in a bundle, not the full-release verifier.

Keep v1's policy immutable for comparisons. Publish a changed policy as a new version/directory and traceable commit, retain this report, and append a separately identified results directory under this GPT dot folder. Never overwrite the frozen game/reference files or reuse these now-public seeds as unseen confirmation.

## A-R3 后续本地独立验证（2026-10-31）

已追加 [A-R3 本地测试补充](independent-a-r3/LOCAL_VALIDATION_20261031.md)：正式 168 局完整结果、原始日志与分析入口，供 GPT dot 改进和 Grok Bot 研究。含发布前发现的内部异常说明及 v21/v22 扩样；原 A-R3 源码和8局开发证据不改写。
