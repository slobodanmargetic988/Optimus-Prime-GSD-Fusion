---
name: optimus-cycle-controller
description: Run a deterministic long-lived Optimus cycle loop until one terminal condition is proven (project_done, insurmountable_blocker, or all_rate_gates_blocking). Emits heartbeat and machine-readable events each cycle.
metadata:
  short-description: Deterministic cycle-mode controller for Optimus V2
---

# Optimus Cycle Controller

## Overview

Use this skill to keep Optimus Prime in cycle mode with deterministic loop control.

The controller owns:
- snapshot pull
- rate-gate evaluation
- cycle action evaluation
- sleep interval execution
- terminal condition checks

It emits machine-readable cycle outputs so Optimus can monitor and act.
It also supports a stop-authorization verification mode so Optimus cannot end early.

## Script

`/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/scripts/optimus_cycle_controller.py`

## Terminal Conditions

The controller exits only when one condition is proven:
1. `project_done` (`PROJECT_DONE.json` valid)
2. `insurmountable_blocker` (`INSURMOUNTABLE_BLOCKER.json` valid)
3. `all_rate_gates_blocking` (computed true; controller writes `ALL_RATE_GATES_BLOCKING.json`)

## Input Contract (`--input-json`)

Required:
- `repo_root`

Optional:
- `sleep_minutes` (default `5`)
- `profile_aliases` (default `["codex"]`)
- `rate_gate_5h_percent` (default `15`)
- `rate_gate_weekly_percent` (default `10`)
- `soft_rate_gate_5h_percent` (default `40`)
- `soft_rate_gate_weekly_percent` (default `25`)
- `soft_rate_gated_max_running_workers` (default `3`)
- `control_flags_dir`
- `events_path`
- `heartbeat_path`
- `final_state_path`
- `lock_path`
- `worker_registry_path`
- `cycle_log_path`
- `handoff_log_path`
- `rate_registry_path`
- `rate_status_log_path`
- `allow_autonomous_ops` (default `false`)
- `max_cycles` (test-only non-terminal exit guard)
- `dry_run` (default `false`)
- `emit_stdout` (default `true`)

See detailed schemas in:
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/references/contracts.md`

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/scripts/optimus_cycle_controller.py --input-json - --json-pretty
{
  "repo_root": "/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion",
  "sleep_minutes": 5,
  "profile_aliases": ["codex", "codex-second"],
  "dry_run": true,
  "max_cycles": 2
}
JSON
```

### Verify terminal stop authorization

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/scripts/optimus_cycle_controller.py \
  --verify-final-state /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/controller/FINAL_STATE.json \
  --json-pretty
```

## Runtime Outputs

- `reports/optimus-prime/controller/HEARTBEAT.json`
- `reports/optimus-prime/controller/EVENTS.jsonl`
- `reports/optimus-prime/controller/FINAL_STATE.json` (terminal only)
- `reports/optimus-prime/controller/lock.pid`

Control/evidence files:
- `reports/optimus-prime/control/PROJECT_DONE.json`
- `reports/optimus-prime/control/INSURMOUNTABLE_BLOCKER.json`
- `reports/optimus-prime/control/ALL_RATE_GATES_BLOCKING.json`

## Notes

- Lock file prevents concurrent controller loops.
- Malformed evidence files are rejected and logged as warnings.
- Controller can emit `sync_linear_phase` directives when latest handoff state implies a deterministic phase/status transition.
- Controller can emit runtime/blocker directives (`runtime_strategy_resolve`, `refresh_blocker_index`) when tester activity or blocked signals require intervention.
- Controller can emit test-train directives (`close_test_wave`, `evaluate_promotion_gate`, `promote_test_next_to_test`, `deploy_test_branch`, `start_new_test_wave`) when `TEST_TRAIN_STATE.json` indicates shared-wave promotion flow.
- Optimus should treat absence of valid `FINAL_STATE.json` + valid evidence payload as **not allowed to stop**.
