# Optimus Prime GSD Fusion

Standalone experimental project for Optimus V2 fusion work.

Current implemented lane:
- Lane A / Phase 1: `optimus-cycle-controller` deterministic cycle loop core with terminal stop authorization guard.
- Lane B (core): generic runtime coordination + blocker intelligence (`runtime-coordinator`, runtime-aware packets/snapshots).
- Lane B add-on: historical thread/token audit (`THREAD_HISTORY.log` + `thread-token-audit` skill).
- Lane B command surface: deterministic `/op-*` planning + autonomous build flow (`/op-map-codebase`, `/op-new-project`, `/op-plan`, `/op-initialize`, `/op-build`, `/op-health`, `/op-status`, `/op-resume`) in provisional hardening.
- Lane C (in progress): private-first installable product flow (release fetch/auth + install/update/uninstall/doctor + product CLI wrapper + release/smoke workflows).

See:
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_A_PHASE1_PLAN.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_A_IMPLEMENTATION_STATUS.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_A_WORKSTATION_HYDRATION_ADDENDUM.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_B_GENERIC_RUNTIME_AND_BLOCKER_INTELLIGENCE_PLAN.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_B_IMPLEMENTATION_STATUS.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/SKILL.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/runtime-coordinator/SKILL.md`

## Shared Runtime Pipeline Commands

The shared test-train runtime lifecycle is repo-local and script-driven:

- deploy: `scripts/deploy-test.sh`
- heal: `scripts/runtime-heal.sh`
- start: `scripts/runtime/start.sh`
- health: `scripts/runtime/health.sh`
- stop: `scripts/runtime/stop.sh`

Pipeline policy and health/repair gating config:

- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/config/TEST_TRAIN_PIPELINE.json`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/config/RUNTIME_PROFILES.json`

Operator entrypoints:

- `make tt-bootstrap`
- `make tt-start`
- `make tt-health`
- `make tt-deploy`
- `make tt-stop`
- `make tt-flow`
- `make tt-gate-drills`

Deterministic local lifecycle sequence:

```bash
make tt-bootstrap
make tt-start
make tt-health
make tt-deploy
make tt-health
make tt-stop
```

## OP Command Surface

Chat/skill aliases and CLI use the same canonical commands:

- `/op-map-codebase`
- `/op-new-project`
- `/op-plan`
- `/op-initialize`
- `/op-build`
- `/op-health`
- `/op-status`
- `/op-resume`

Repo-local CLI wrapper:

```bash
./scripts/op/opctl.sh /op-initialize --mission \"Build MyBoard\" --scope \"Board workflows\" --json-pretty
./scripts/op/opctl.sh /op-build --json-pretty
./scripts/op/opctl.sh /op-status --json-pretty
./scripts/op/opctl.sh /op-health --json-pretty
```

`/op-build` behavior (new-only model):

- single-flight lock: `reports/optimus-prime/planning/BUILD_LOOP.lock`
- default cadence: `sleep_minutes=5` (unless overridden)
- canonical task state: `reports/optimus-prime/planning/TASK_EXECUTION_STATE.json`
- canonical task evidence: `reports/optimus-prime/planning/evidence/<task_id>/TASK_EVIDENCE.json`
- multi-phase planning: `PLAN_PACKETS.json` includes `phases[]` with strict phase barrier progression
- autonomous gap closure: `GAPS.json` + `GAP_CLOSURE_PLAN_PACKETS.json` are generated/consumed during build
- gap closure convergence: no recursive closure-task gap generation; retries are bounded (max 5) then escalated/suppressed
- sticky explicit closure: open gaps are not auto-closed by recomputation drift; closure requires explicit `GAPFIX-*` review-done evidence
- gap artifact resilience: `/op-build` auto-heals malformed `GAPS.json` or `GAP_CLOSURE_PLAN_PACKETS.json` with deterministic backup + recovery metadata
- strict-first dispatch gating: `dispatch_filter`/hard-gated cycles skip dispatch before any packet launch
- adapter mode source: runtime/test-train directives derive `test_train_mode` from `TEST_TRAIN_STATE.json` (fallback `off`)
- truncation-safe handoff ingestion: stale `handoff_log_offset` is reset with deterministic warning/event
- directive failure handling: remediation is queued and feature dispatch is skipped for that cycle
- dispatch cap enforcement: `dispatch_window.max_running_workers` is a hard cap
- strict done completion requires all phase/task/evidence/verify/UAT gates, zero open gaps, plus `--verify-final-state` authorization
- hard rate-gate policy: wait/resume when reset is within 2 hours, otherwise stop and require manual rerun
- malformed rate registry handling: if `PROFILE_RATE_REGISTRY.json` is invalid during `all_rate_gates_blocking`, build continues with warning `rate_registry_invalid_ignored`
- strict health parity: `/op-health` is build-readiness strict and fails when `/op-build` preflight would block
- health gap-artifact parity: malformed `GAPS.json` or `GAP_CLOSURE_PLAN_PACKETS.json` blocks `/op-health` with `gap_artifact_integrity_blocked`
- status resilience: `/op-status` degrades to deterministic blocked snapshot (no crash) with `status_artifact_invalid` and `status_snapshot_degraded`
- resume resilience: `/op-resume` auto-backs up malformed `BUILD_STATE.json` to `BUILD_STATE.corrupt.<timestamp>.json`, resets state, and continues with warning `resume_state_corrupt_reset`

## Lane B Quality Gate

Deterministic reliability-first release gate:

- command: `python3 -m scripts.quality.lane_b_quality_gate --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion`
- runbook wrapper: `scripts/quality/run_lane_b_quality.sh`
- required risk tests manifest: `scripts/quality/lane_b_required_tests.json`
- quality artifact: `reports/optimus-prime/planning/LANE_B_QUALITY_GATE.json`

Gate contract:

- hard-blocks when any required risk-test is failing/missing
- hard-blocks when full matrix fails
- records module coverage snapshot for core Lane B modules
- returns `status=passed|blocked` with deterministic `next_action`

## Lane C Installable Product (Private-First)

Lane C command/tooling:

- release bundle builder: `python3 -m scripts.release.build_lane_c_bundle`
- release readiness validator: `python3 -m scripts.release.validate_release_readiness`
- install command: `python3 scripts/install/op_install.py`
- update command: `python3 scripts/install/op_update.py`
- uninstall command: `python3 scripts/install/op_uninstall.py`
- doctor command: `python3 scripts/install/op_doctor.py`
- product wrapper: `python3 scripts/op/opctl_product.py`

Installer/update source modes:

- local bundle: `--bundle-dir`
- private GitHub release: `--repo-owner --repo-name --channel [--version]`

Private release auth resolution:

1. `gh auth token`
2. `GH_TOKEN`
3. `GITHUB_TOKEN`

Product CLI behavior:

- `opctl /op-*` delegates to the existing Lane B workflow contract unchanged.
- `opctl doctor` returns deterministic readiness report with manifest + checksum integrity checks.
- `opctl update` performs manual explicit update with checksum enforcement.
- `opctl uninstall` removes only managed install paths.
- `opctl version` returns `version/build/commit`.

Config/profile model:

- deterministic precedence: CLI args -> project config (`<repo>/.optimus-prime/config.json`) -> global config (`$XDG_CONFIG_HOME/optimus-prime/config.json` or `~/.optimus-prime/config/config.json`) -> defaults
- profiles: `quality`, `balanced`, `budget`
- config validation returns field-level fix guidance via deterministic `config_error` details

Deterministic install/update error codes:

- `auth_error`
- `release_not_found`
- `asset_missing`
- `download_error`
- `checksum_mismatch`
- `doctor_blocked`

Primary docs:

- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/install/QUICKSTART.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/install/UPGRADE.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/install/TROUBLESHOOTING.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/release/LANE_C_RELEASE_CHECKLIST.md`
