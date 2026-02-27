# Optimus Prime GSD Fusion

Standalone experimental project for Optimus V2 fusion work.

Current implemented lane:
- Lane A / Phase 1: `optimus-cycle-controller` deterministic cycle loop core with terminal stop authorization guard.
- Lane B (core): generic runtime coordination + blocker intelligence (`runtime-coordinator`, runtime-aware packets/snapshots).
- Lane B add-on: historical thread/token audit (`THREAD_HISTORY.log` + `thread-token-audit` skill).
- Lane B command surface: deterministic `/op-*` planning + autonomous build flow (`/op-map-codebase`, `/op-new-project`, `/op-plan`, `/op-initialize`, `/op-build`, `/op-health`, `/op-status`, `/op-resume`) in provisional hardening.

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
