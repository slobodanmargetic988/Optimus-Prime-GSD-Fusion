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

Build cycle manager order:
1. `profile-manager`
2. `production-line-manager`
3. `gap-consumption-manager`
4. `branch-merge-manager`
5. `workstation-manager`
6. controller tick
7. `production-line-manager` (post-directive reconcile)
8. `gap-consumption-manager` (post-directive reconcile)
9. `work-dispatcher`

Canonical runtime task statuses:
- `pending`, `dev_working`, `dev_done`, `testing`, `tests_done`, `reviewing`, `review_done`, `blocked`

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
| `/op-build` | `reports/optimus-prime/control/OPERATOR_STOP.json` | Stop active autonomous `/op-build` workers and exit loop safely | runtime code |

Related runtime state files:
- `/op-build`: `reports/optimus-prime/control/OPERATOR_STOP_STATE.json` (written by runtime after operator stop; reconciled by `/op-resume`).
- `/op-simple-build`: `.op-simple/current/watchdog_exit_signal.json` (written when watchdog stop condition triggers).

Resume after stop:

```bash
opctl /op-resume --repo-root /absolute/path/to/project --json-pretty
```

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

Runtime reliability notes:
- Runtime decisions are now based on task-embedded gaps (`tasks[].gaps_that_need_patching`); external `GAPS.json` / `GAP_CLOSURE_PLAN_PACKETS.json` are not decision inputs.
- Planner/runtime use an explicit per-task `verification_contract` (`tdd_red|implementation_green|hardening`) and evidence summary expectation fields (`expectation`, `expectation_met`, `failure_class`).
- For TDD red stages, `expect_fail` with `failure_class=expected_red` is treated as progress (not false blocking).
- Handoff is non-authoritative for task blocking; evidence sync is authoritative for state transitions.
- Strict completion requires merge evidence: `review_done` tasks must be merged into `RAB-BASE` with verification pass data.
- Branch manager merge completion now also requires explicit merge proof (`source_branch` ancestor of `RAB-BASE` HEAD) before a task is marked merged.
- On post-merge verification failure, branch manager now rolls back deterministically to captured pre-merge HEAD (never `HEAD~1`).
- Branch manager retries are eligibility-aware and stop early when merge eligibility is lost (`merge_candidate_lost_eligibility`) or when verification contract mismatch is non-retriable (`merge_verification_contract_invalid`).
- Dispatcher is assignment-driven from `WORK_DISPATCH_PLAN.json`; tasks not present in assignments are not dispatched in that cycle.
- Empty-assignment cycles are reported deterministically as `dispatch_plan_no_assignments`.
- Controller `dispatch_filter` is enforced per assignment alias (hard-gated aliases are skipped, non-hard-gated aliases can still dispatch in the same cycle).
- Dispatch packets use workstation-prepared slot context (`worktree_root`, `branch`) from `WORKER_REGISTRY.json`.
- `/op-build` response data now includes current-cycle `assignment_observations` (same signal persisted to `DISPATCH_ASSIGNMENT_OBSERVATIONS.jsonl`).
- Dispatcher supports same-lane thread continuation (`codex resume`) with deterministic fallback to fresh dispatch on resume failure.
- Worker branch templates are run-aware in active build loops: `codex/<run_id>/<slot>/<task_slug>` (test/review suffixes still apply).
- Branch/workstation managers run LLM-first action loops with strict validators and bounded retries (max 10); retry exhaustion blocks only the affected task/lane.
- Workstation manager accepts only `prepare_command` values that resolve to the bundled `skills/workstation-preparation/scripts/prepare_workstation.py` path.
- Workstation manager enforces slot-specific worktree names (`workstation-dev-*`, `workstation-test-*`, `workstation-review-*`), requires prepared `target_path` to match exact deterministic slot path, and skips destructive prep only for same-lane in-progress slots with valid slot-prefixed branches (`codex/<slot>/...`).
- Artifact fan-in is config-gated (`workflow.enable_artifact_fan_in`) and defaults to `false`; when disabled OP emits `artifact_fan_in_disabled` and skips worktree fan-in.
- Workstation manager deterministically enforces `<worktree>/reports/optimus-prime -> <repo>/reports/optimus-prime` symlink after validation (delete-and-replace if a non-symlink path exists), so worker artifacts land in canonical reports without fan-in.
- Embedded gaps close only when explicit closure conditions pass with evidence refs and can reopen on regression.
- Dead running worker PIDs are normalized before dispatch gating, so stale registry entries do not block dispatch capacity.
- Dead PID recovery is evidence-first: if no new progress is ingested, OP queues immediate same-cycle same-slot redispatch and tracks retry metadata.
- `/op-resume --reset-exhausted-retries` clears continuation-limiting counters (gap/dead-pid/resume-fail/task-attempt/task-watchdog/global-watchdog) before resume.
- If `WORKER_REGISTRY.json` is unreadable, OP attempts auto-recovery; if recovery fails, it emits `worker_registry_recovery_failed_dispatch_allowed` and continues dispatch by policy.

Operator stop behavior:
- See `Operator Controls (Stop / Recovery Files)` above.
- `/op-build` applies stop to active worker PIDs (`SIGTERM` then `SIGKILL` fallback), writes `OPERATOR_STOP_STATE.json`, archives the marker, and exits with `stopped_operator`.
- `/op-resume` auto-reconciles stop-affected in-progress tasks (continue when worker/evidence is valid, requeue otherwise).

## Command Reference

Workflow commands:
- `/op-map-codebase` — map current codebase and generate planning context artifacts
- `/op-new-project` — initialize baseline project artifacts
- `/op-plan` — generate plan artifacts via strict LLM bundle + validation loop
- `/op-initialize` — map + new-project + plan chain
- `/op-build` — autonomous execution loop
- `/op-status` — deterministic status snapshot
- `/op-health` — strict readiness/integrity check
- `/op-resume` — resume build state safely

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
