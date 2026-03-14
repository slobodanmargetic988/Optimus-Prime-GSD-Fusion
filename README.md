# Optimus Prime GSD Fusion

A deterministic, plan-driven autonomous builder built around the `/op-*` workflow.

This repository currently ships:
- Lane A core cycle control
- Lane B autonomous planning/build execution
- Lane C private-first install/update/release pipeline

Current distribution mode: **private GitHub Releases** (prerelease channel first).

## What You Get

- Deterministic 2-step flow: **plan first, then autonomous build**
- Strict gates for quality, runtime health, and completion evidence
- Install/update/uninstall/doctor commands for local or global usage
- Repo-local and machine-readable artifacts for traceability

## Requirements

- macOS or Linux
- Python 3.11+
- `git`, `bash`
- GitHub access to this private repository
- Auth via one of:
  1. `gh auth login`
  2. `GH_TOKEN`
  3. `GITHUB_TOKEN`

## Install (Private Release)

### 1) Authenticate

```bash
gh auth login
```

### 2) Install Global

```bash
python3 scripts/install/op_install.py \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --mode global \
  --json-pretty
```

### 3) Validate

```bash
~/.local/bin/opctl doctor --json-pretty
~/.local/bin/opctl version --json-pretty
```

### 4) Install Local (project-scoped)

```bash
python3 scripts/install/op_install.py \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --mode local \
  --repo-root /absolute/path/to/project \
  --json-pretty
```

Local install creates launchers under:
- `<repo>/.optimus-prime/bin/opctl`
- `<repo>/.optimus-prime/bin/op`

### 5) Version-Pinned Install

```bash
python3 scripts/install/op_install.py \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --version 0.3.0-rc.2 \
  --mode global \
  --json-pretty
```

## How to Use (Core Workflow)

## 1) Planning Bootstrap

Run one command to prepare planning artifacts:

```bash
opctl /op-initialize --mission "Build X" --scope "Y" --json-pretty
```

File-source mode is also supported:

```bash
opctl /op-initialize \
  --mission-file /abs/path/to/mission.md \
  --scope-file /abs/path/to/scope.txt \
  --json-pretty
```

`/op-initialize` runs:
1. `/op-map-codebase`
2. `/op-new-project`
3. `/op-plan`
4. Codex profile autodetection (`.codex*` with first-level `auth.json`) and writes `reports/optimus-prime/planning/PROFILE_SELECTION.json` for `/op-build` profile/rate wiring.

It does **not** start implementation. It prepares decision-complete planning state.

Planner behavior:
- `/op-plan` is LLM-driven (`codex exec`) and writes a strict planning bundle.
- OP validates parse + schema + recomputed plan-check and retries repair up to 10 attempts.
- Existing planning artifacts require explicit replacement with `--override-old-plan`.
- The planner prompt points LLM to bundled reference templates at `scripts/op/llm/examples/op-plan/reports/optimus-prime/planning`.

## 2) One-Command Build (Initialize + Run)

```bash
opctl /op-build --json-pretty
```

`/op-build` now runs `/op-simple-build` and will run `/op-initialize` first when:
- mission/scope input is provided (`--mission`, `--scope`, `--mission-file`, `--scope-file`),
- `--override-old-plan` is set, or
- required planning baseline artifacts are missing.

Use file inputs directly on `/op-build`:

```bash
opctl /op-build \
  --mission-file /abs/path/to/mission.md \
  --scope-file /abs/path/to/scope.txt \
  --override-old-plan \
  --json-pretty
```

Execution continues with strict gates until:
- done with full evidence, or
- deterministic hard stop condition is reached.

Executor routing flags:
- `--executor-provider codex|openrouter|blackbox` (default: `codex`)
- `--selected-aliases "alias1,alias2,..."` (Codex account/home alias pool for rate/dispatch profile selection)
- `--profile <codex_config_profile_name>` (optional Codex config profile inside selected `CODEX_HOME`; not a provider selector and not an alias selector)
- `--executor-model <model-id>` (optional)
- `--blackbox-lane free|api_key` (default: `free`)
- `--allow-worker-executor-override` (default off)

Alias vs profile quick rule:
1. Use `--executor-provider` to choose backend (`codex`, `openrouter`, `blackbox`).
2. Use `--selected-aliases` to choose Codex alias homes (for example `nine,ten`).
3. Use `--profile` only when you need a specific Codex config profile name inside those alias homes.
4. Do not pass alias names to `--profile`.

Blackbox canary docs:
- [docs/runbooks/BLACKBOX_CANARY_RUNBOOK.md](docs/runbooks/BLACKBOX_CANARY_RUNBOOK.md)
- [docs/runbooks/BLACKBOX_CANARY_VALIDATION_TEMPLATE.md](docs/runbooks/BLACKBOX_CANARY_VALIDATION_TEMPLATE.md)

Build cycle manager order (OP Simple runtime):
1. `BOSS`
2. `watchdog` (pre-dispatch stale/near-stale evaluation)
3. `rate-gate` (only when BOSS is healthy and watchdog is non-terminal)
4. `work-dispatcher` (uses reserved slots in `merge_recovery` mode)
5. `merge-engine` (deterministic fan-in/lane/run merge progression)
6. `summary` (+ `wrapup-manager` on terminal/project-done exits)

Canonical runtime task statuses:
- `pending`, `in_progress`, `done`, `blocked`

### Monitor / Recover

```bash
opctl /op-status --json-pretty
opctl /op-health --json-pretty
opctl /op-resume --json-pretty
```

### Operator Controls (Stop / Recovery Files)

Use these file-based controls when a run is active:

| Runtime | File path (relative to repo root) | Purpose | Consumed by |
|---|---|---|---|
| `/op-simple-build` | `terminate_run.json` | Immediate loop stop signal (presence-only; content ignored for stop check) | runtime code |
| `/op-simple-build` | `recovery_instructions.md` | Operator recovery nudge for next BOSS cycle; BOSS should apply or explain and rename to `recovery_instructions_CONSUMED.md` | BOSS manager prompt |

Related runtime state files:
- `/op-simple-build`: `.op-simple/current/watchdog_exit_signal.json` (written when watchdog stop condition triggers).
- `/op-simple-build`: `.op-simple/current/terminal_capsule.json` (terminal-stop forensic summary).
- `/op-simple-build`: `.op-simple/current/mergeability_report.json` (lane/run mergeability state).

Resume after stop:

```bash
opctl /op-resume --repo-root /absolute/path/to/project --json-pretty
```

`/op-resume` preflight requirement:
- `.op-simple/current/initialize_state.json` must exist.
- If missing, runtime returns `op_simple_resume_unavailable` and you must run `/op-build` first.
- Legacy `/op-resume` fallback to old non-`.op-simple` state is removed.

### Multi-Profile Codex Setup

If you run OP with multiple Codex accounts/profiles, use the bundled `create-codex-profile` skill to create profile homes like `~/.codex-second` while preserving separate usage/account files.

Example:

```bash
python3 "$CODEX_HOME/skills/create-codex-profile/scripts/create_codex_profile.py" \
  --profile second \
  --json-pretty
```

Behavior:
- copies per-profile items: `auth.json`, `sessions/`
- symlinks all other top-level `.codex` items (shared skills/agents/state backend)
- Note: `create_codex_profile.py --profile <name>` defines alias/home suffix (`~/.codex-<name>`). It is different from `opctl --profile`, which sets Codex config profile name inside a selected alias home.

Runtime reliability notes:
- `/op-build` and `/op-resume` both execute the OP Simple runtime (`/op-simple-build`).
- Legacy op-core autonomous build paths and legacy `/op-resume` fallback behavior are removed from active execution.
- Watchdog runs pre-dispatch and sets `cycle_mode` as `normal`, `merge_recovery`, or `terminal_stale`.
- In `merge_recovery`, dispatcher reserves exactly 2 worker slots for merge/fan-in work while allowing other active workers to continue.
- BOSS timeout handling is fail-closed per cycle with forensic evidence and timeout streak tracking (`timeout_adaptation_state.json`).
- After 2 consecutive BOSS timeouts, next-cycle profile rotation is required when eligible candidates exist, with explicit rotation evidence in cycle artifacts.
- Merge progression is deterministic: done-worker commit ingestion -> lane fan-in -> full-lane gate -> lane-to-run merge.
- Runtime emits minimal per-cycle artifacts even on unhappy paths (for example `cycle_summary.json`, `cycle_manager_decision.json`, `terminal_capsule.json`).
- Wrapup runs for `project_done` and watchdog-terminal stop reasons, with merge/fan-in snapshot evidence.

Operator stop behavior:
- See `Operator Controls (Stop / Recovery Files)` above.
- Create `terminate_run.json` at repo root to stop the active OP Simple loop on the next cycle boundary.
- Runtime persists terminal evidence into `.op-simple/current` and per-cycle snapshots in `.op-simple/history/cycle-*`.
- `/op-resume` continues from `.op-simple/current` state when preflight markers are present.

## Command Reference

Workflow commands:
- `/op-map-codebase` — map current codebase and generate planning context artifacts
- `/op-new-project` — initialize baseline project artifacts
- `/op-plan` — generate plan artifacts via strict LLM bundle + validation loop
- `/op-initialize` — map + new-project + plan chain
- `/op-build` — initialize-if-needed + OP Simple execution loop
- `/op-status` — deterministic status snapshot
- `/op-health` — strict readiness/integrity check
- `/op-resume` — resume OP Simple state safely (requires `.op-simple/current/initialize_state.json`)

Lifecycle commands:
- `opctl doctor`
- `opctl update`
- `opctl uninstall`
- `opctl version`

## Update

```bash
opctl update \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --mode global \
  --json-pretty
```

Or pin version:

```bash
opctl update \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --version 0.3.0-rc.2 \
  --mode global \
  --json-pretty
```

## Uninstall

Global:

```bash
opctl uninstall --mode global --json-pretty
```

Local:

```bash
opctl uninstall --mode local --repo-root /absolute/path/to/project --json-pretty
```

## Fallback: Install from Local Bundle Directory

If you already downloaded and extracted a release bundle:

```bash
python3 scripts/install/op_install.py \
  --bundle-dir /absolute/path/to/optimus-prime-<version> \
  --mode global \
  --json-pretty
```

## Troubleshooting (Deterministic Error Codes)

- `auth_error`: no valid GitHub auth token found
- `release_not_found`: no matching release for channel/version
- `asset_missing`: release is missing required assets
- `download_error`: release metadata or asset download failed
- `checksum_mismatch`: downloaded release integrity mismatch
- `doctor_blocked`: readiness/integrity checks failed
- `managed_checksum_mismatch`: installed files differ from manifest checksums

Detailed guides:
- [QUICKSTART](docs/install/QUICKSTART.md)
- [UPGRADE](docs/install/UPGRADE.md)
- [TROUBLESHOOTING](docs/install/TROUBLESHOOTING.md)
- [TERMINAL DEBUG OUTPUT POLICY](docs/contracts/TERMINAL_DEBUG_OUTPUT_POLICY.md)

## Key Paths

Planning/build artifacts:
- `reports/optimus-prime/planning/`

Runtime artifacts:
- `reports/optimus-prime/runtime/`

Install state:
- global: `~/.optimus-prime/install/INSTALL_STATE.json`
- local: `<repo>/.optimus-prime/install/INSTALL_STATE.json`

## Release / Maintainer Notes

Release checklist:
- `docs/release/LANE_C_RELEASE_CHECKLIST.md`

Lane status docs:
- `docs/plans/LANE_B_IMPLEMENTATION_STATUS.md`
- `docs/plans/LANE_C_IMPLEMENTATION_STATUS.md`
- `docs/plans/PROGRAM_LANES_OVERVIEW.md`
