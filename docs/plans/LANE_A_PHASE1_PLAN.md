# Lane A — V2 First-Change Plan Document (Cycle Controller Core)

## Summary
This is the **first set of changes** for V2 in a **new standalone project** (separate from current Agents repo).  
Goal: prevent premature Optimus stop behavior by moving long-running conditional loop logic into a deterministic controller skill.

This plan intentionally excludes backward-compatibility, staged rollout, and deployment planning.

---

## Target Project + Document Location
- New project root:  
  `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion`
- Plan document path for this phase:  
  `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/docs/plans/LANE_A_PHASE1_PLAN.md`

---

## Scope (Lane A / Phase 1)
1. Add new skill: `optimus-cycle-controller`
2. Move cycle loop decisions from prompt logic into controller script:
   - snapshot pull
   - rate-gate evaluation
   - cycle action evaluation
   - sleep control
   - terminal condition checks
3. Enforce hard stop-prevention:
   - Optimus may stop only when controller emits terminal final state
4. Emit structured controller outputs for Optimus to monitor and act on

---

## Terminal Conditions (only 3)
Controller exits only when one is proven:
1. `project_done` — evidence file exists and is valid
2. `insurmountable_blocker` — evidence file exists and is valid
3. `all_rate_gates_blocking` — computed true and evidence file written

---

## Public Interfaces / Types

### 1) Controller input contract (`--input-json`)
- `repo_root`
- `sleep_minutes`
- `profile_aliases`
- gate thresholds (hard + soft)
- `control_flags_dir`
- `events_path`
- `heartbeat_path`
- `final_state_path`
- `allow_autonomous_ops`
- `max_cycles` (test mode)
- `dry_run`

### 2) Event stream contract (`EVENTS.jsonl`)
- `timestamp`
- `cycle_number`
- `event_type` (`snapshot|directive|sleep|warning|terminal`)
- `action_code`
- `payload`
- `requires_optimus_action`

### 3) Final state contract (`FINAL_STATE.json`)
- `terminal_reason`
- `evidence_file`
- `last_cycle_number`
- `profiles_state`
- `active_workers_summary`
- `pending_directives`
- `generated_at`

---

## Files to Build

### Skill
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/SKILL.md`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/scripts/optimus_cycle_controller.py`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/tests/test_optimus_cycle_controller.py`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/references/contracts.md`

### Runtime artifacts
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/controller/HEARTBEAT.json`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/controller/EVENTS.jsonl`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/controller/FINAL_STATE.json`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/controller/lock.pid`

### Terminal evidence flags
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/control/PROJECT_DONE.json`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/control/INSURMOUNTABLE_BLOCKER.json`
- `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/reports/optimus-prime/control/ALL_RATE_GATES_BLOCKING.json`

---

## Test Cases
1. Loop continues when no terminal evidence exists.
2. Stops on valid `PROJECT_DONE.json`.
3. Stops on valid `INSURMOUNTABLE_BLOCKER.json`.
4. Stops on all-rate-gated condition and writes rate evidence file.
5. Rejects malformed evidence files.
6. Lock file prevents concurrent controller runs.
7. Emits heartbeat each cycle.
8. Emits directives when Optimus action is required.
9. Optimus cannot end run without `FINAL_STATE.json` terminal payload.

---

## Acceptance Criteria
- Controller owns cycle timing + condition logic.
- Optimus cannot produce “done” summary unless controller terminal output exists.
- Terminal reason is always one of the 3 allowed reasons.
- Controller outputs are deterministic and machine-readable.

---

## Explicit Assumptions / Defaults
- New repo is standalone and does **not** require backward compatibility with current Agents repo.
- No deployment/rollout planning in this lane.
- Lane B (full GSD feature fusion) is planned next.
- Lane C (installable product packaging) is intentionally deferred.
