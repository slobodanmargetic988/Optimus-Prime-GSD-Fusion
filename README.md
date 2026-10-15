# Optimus Prime GSD Fusion

A free, local, plan-driven autonomous builder with a desktop interface and the `/op-*` command-line workflow. Configure your AI provider, set your task and worker limits, then plan, build and resume projects on your own computer.

[Website](https://optimus.weeyuga.com/) · [Desktop setup](desktop/README.md) · [Contribute](CONTRIBUTING.md) · [Sponsor the project](https://github.com/sponsors/slobodanmargetic988)

Optimus code is open source under [Apache 2.0](LICENSE). Third-party components retain their own licenses; see [the notices](THIRD_PARTY_NOTICES.md). The repository remains **private during testing** and will be made public only when the maintainer is ready. Access currently requires an invitation.

Optimus is free to use. Sponsorship is optional and helps support development. Bring your own provider account; provider subscriptions and API usage remain your responsibility.

## Testing status

**The CLI is confirmed usable. The desktop app is experimental, has not been
validated end to end in real projects, and may have bugs.** Automated checks and
installer builds have passed, but they do not establish real-world desktop
reliability. Volunteers are welcome to test it, report problems, and submit a
pull request (merge request) for any fixes they find necessary. Include the OS,
provider, reproduction steps, and relevant logs with credentials removed. See
[Contributing](CONTRIBUTING.md) and the [desktop guide](desktop/README.md).

## Branch policy

The shared GitHub and Gitea repositories retain two long-lived branches:

| Branch | Purpose |
| --- | --- |
| `main` | Current integrated CLI, desktop preview, documentation, and website. Use this branch for the latest source. |
| `langstack` | Retained development/reference lineage for the LangStack integration. Its current implementation is included in `main`; it is kept for comparison and continued integration work. |

Old `op-simple-canary-*`, worker/task, lane-baseline, and completed review
branches are disposable build/test history. They were removed during the
October 15, 2026 publication cleanup; a private recovery archive was retained
outside the published repository. They are not additional supported versions.
Keep future canary and worker branches local or in dedicated test repositories,
and remove short-lived review branches after integration. Sync the two retained
branches explicitly between remotes rather than mirroring every local ref.

This repository currently ships:
- Lane A core cycle control
- Lane B autonomous planning/build execution
- Lane C private-first install/update/release pipeline

Current distribution mode: **private GitHub Releases** (prerelease channel first).

## What You Get

- Desktop app for macOS, Linux and Windows (Windows engine execution uses WSL 2)
- New/existing projects, drag-and-drop inputs, provider settings and live progress
- Optional task ceilings from 1 to 400 and configurable parallel workers

- Deterministic 2-step flow: **plan first, then autonomous build**
- Strict gates for quality, runtime health, and completion evidence
- Install/update/uninstall/doctor commands for local or global usage
- Repo-local and machine-readable artifacts for traceability

## Desktop quick start

```sh
cd desktop
npm ci
npm start
```

Use Node.js 24. Python 3.11+, Git and the selected provider CLI must be installed. See the [desktop guide](desktop/README.md) for Windows/WSL setup, provider configuration and installer builds. The app’s **About** page links to this repository and GitHub Sponsors.

## Requirements

- macOS or Linux
- Python 3.11+
- `git`, `bash`
- A configured executor CLI on `PATH`: Codex, Claude Code, or Blackbox. OpenRouter uses a configured Codex provider profile.
- For Codex subscription mode, at least one authenticated Codex home, usually `~/.codex/auth.json`. Claude and explicit API profiles do not require a Codex subscription home.
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

OP is installed once, then pointed at another project with `--repo-root`.

For a first demo on a target project:

```bash
cd /absolute/path/to/target-project
opctl doctor --json-pretty
```

Strategy is optional but recommended. If `strategy/STRATEGY_MANIFEST.md` exists,
`/op-initialize` runs the strategy stage before planning and writes:

- `strategy/current/strategy_packet.md`
- `strategy/current/STRATEGY_SUMMARY.md`

Minimal strategy manifest:

```md
# Strategy Manifest

## Mission
Build or update this project according to the operator request.

## Scope
- Inspect README, source code, tests, and docs.
- Identify constraints, sequencing risks, and reusable context.
- Produce planner-facing guidance before implementation planning starts.

## Sources to inspect
- README.md
- docs/
- tests/
```

## 1) Planning Bootstrap

Run one command to prepare planning artifacts:

```bash
opctl /op-initialize \
  --repo-root /absolute/path/to/target-project \
  --mission "Build X" \
  --scope "Y" \
  --json-pretty
```

File-source mode is also supported:

```bash
opctl /op-initialize \
  --repo-root /absolute/path/to/target-project \
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
opctl /op-build --repo-root /absolute/path/to/target-project --json-pretty
```

`/op-build` now has start-policy routing built in:
- `--start-policy auto` (default): resumes when valid `.op-simple/current/initialize_state.json` + run-base branch state already exist, otherwise starts a fresh build.
- `--start-policy new`: always starts a fresh OP Simple run-base.
- `--start-policy resume`: requires valid OP Simple resume state and mirrors `/op-resume`.

In fresh mode, `/op-build` will run `/op-initialize` first when:
- mission/scope input is provided (`--mission`, `--scope`, `--mission-file`, `--scope-file`),
- `--override-old-plan` is set, or
- required planning baseline artifacts are missing.

Auto mode still forces a fresh run when you explicitly supply fresh-run intent:
- `--mission`
- `--mission-file`
- `--scope`
- `--scope-file`
- `--override-old-plan`
- `--run-base-source-branch`

Strategy routing flags:
- `--strategy-manifest "<markdown text>"` provides an inline manifest for the strategy stage.
- `--strategy-manifest-file strategy/custom.md` points to a manifest file in the target project.
- `--skip-strategy` bypasses strategy generation and lets planning continue without strategy artifacts.
- If no strategy manifest exists and no explicit strategy flag is passed, initialize skips strategy and records that reason.

Use file inputs directly on `/op-build`:

```bash
opctl /op-build \
  --repo-root /absolute/path/to/target-project \
  --mission-file /abs/path/to/mission.md \
  --scope-file /abs/path/to/scope.txt \
  --override-old-plan \
  --json-pretty
```

Execution continues with strict gates until:
- done with full evidence, or
- deterministic hard stop condition is reached.

Executor routing flags:
- `--executor-provider codex|openrouter|blackbox|claude` (default: `codex`)
- `--selected-aliases "alias1,alias2,..."` (Codex account/home alias pool for rate/dispatch profile selection)
- `--profile <codex_config_profile_name>` (optional Codex config profile inside selected `CODEX_HOME`; not a provider selector and not an alias selector)
- `--executor-model <model-id>` (optional)
- `--blackbox-lane free|api_key` (default: `free`)
- `--allow-worker-executor-override` (default off)

Desktop planning limits:
- `--max-plan-tasks N` optionally caps the generated plan at 1–400 tasks. It is a maximum, not a target; smaller plans retain the same coverage and quality checks.
- An explicit cap overrides older fixed minimum-task-count instructions for that run. Omitting it preserves existing CLI planning policy.
- The cap is saved with the plan and rechecked before build/resume. Oversized plans are rejected, never silently truncated.
- `--max-parallel-workers N` separately controls worker concurrency. `/op-initialize` still generates a plan without starting build execution.

Planning, bootstrap, and strategy honor the selected executor. API configurations use `--profile` with an appropriate `CODEX_HOME`; Claude uses its own local CLI authentication. See [Desktop Runtime Contract](docs/contracts/DESKTOP_RUNTIME_CONTRACT.md).

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
- `/op-simple-build`: `.op-simple/current/merge_queue.json` (active deterministic merge failures waiting for cadence-based merge-manager handling).
- `/op-simple-build`: `.op-simple/current/unmergable_merges.json` (merge-manager-consumed items that still could not be resolved).
- `/op-simple-build`: `.op-simple/current/merge_manager_report.json` (runtime-normalized merge-manager outcome report).
- `/op-simple-build`: `.op-simple/current/merge_journal.jsonl` (append-only merge attempt/disposition history).

Resume after stop:

```bash
opctl /op-resume --repo-root /absolute/path/to/project --json-pretty
```

`/op-resume` preflight requirement:
- `.op-simple/current/initialize_state.json` must exist.
- If missing, runtime returns `op_simple_resume_unavailable` and you must run `/op-build` first.
- Legacy `/op-resume` fallback to old non-`.op-simple` state is removed.
- `/op-build --start-policy resume` now uses the same OP Simple resume semantics.

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
- `/op-build` defaults to `--start-policy auto`, so it can resume existing valid OP Simple state instead of always starting over.
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
- [BEGINNER DEMO FOR NON-PROGRAMMERS](docs/install/BEGINNER_DEMO.md)
- [QUICKSTART](docs/install/QUICKSTART.md)
- [USING OP FOR PROJECTS](docs/install/USING_OP_FOR_PROJECTS.md)
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

## Community and support

Bug reports, documentation, examples and pull requests are welcome. See [Contributing](CONTRIBUTING.md), [Support](SUPPORT.md) and [Security](SECURITY.md). If Optimus helps you, consider [sponsoring development](https://github.com/sponsors/slobodanmargetic988). Sponsorship is voluntary and does not unlock features.
