# Optimus Prime GSD Fusion

Standalone experimental project for Optimus V2 fusion work.

Current implemented lane:
- Lane A / Phase 1: `optimus-cycle-controller` deterministic cycle loop core with terminal stop authorization guard.
- Lane B (core): generic runtime coordination + blocker intelligence (`runtime-coordinator`, runtime-aware packets/snapshots).
- Lane B add-on: historical thread/token audit (`THREAD_HISTORY.log` + `thread-token-audit` skill).
- Lane B command surface: deterministic `/op-*` planning + autonomous build flow (`/op-map-codebase`, `/op-new-project`, `/op-plan`, `/op-initialize`, `/op-build`).

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

Repo-local CLI wrapper:

```bash
./scripts/op/opctl.sh /op-initialize --mission \"Build MyBoard\" --scope \"Board workflows\" --json-pretty
./scripts/op/opctl.sh /op-build --json-pretty
```

`/op-build` behavior (new-only model):

- single-flight lock: `reports/optimus-prime/planning/BUILD_LOOP.lock`
- default cadence: `sleep_minutes=5` (unless overridden)
- canonical task state: `reports/optimus-prime/planning/TASK_EXECUTION_STATE.json`
- strict done completion requires all task/evidence/verify/UAT gates plus `--verify-final-state` authorization
- hard rate-gate policy: wait/resume when reset is within 2 hours, otherwise stop and require manual rerun
