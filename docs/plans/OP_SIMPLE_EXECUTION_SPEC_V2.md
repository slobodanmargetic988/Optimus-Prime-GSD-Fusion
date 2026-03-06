# OP Simple Execution Spec V2

## Status
- This is the active planning baseline as of 2026-03-06.
- `docs/plans/OP_SIMPLE_TASK_BACKLOG.md` is frozen as V1 historical context.

## Locked Direction
- Branch safety: do all work on `codex/simple-op` only.
- Product direction: replace old build runtime behavior on this branch; no backward compatibility target.
- Command target: `/op-simple-build`.
- Initialize boundary: keep `/op-initialize` mostly intact and adapt only where needed.
- Reference policy for old behavior: use `main` branch history, not in-branch legacy copies.

## Runtime Model (V2)
- Build loop is a plain `while` loop.
- Deterministic backbone owned by code:
  - cycle counter
  - run lock
  - manager call log (raw telemetry)
- Artifact root: `./.op-simple/`.
- Artifact layout:
  - `./.op-simple/current/` canonical files overwritten each cycle
  - `./.op-simple/history/cycle-<n>/` snapshots (enabled by default, unlimited retention)
- Prompt layout: `scripts/op_simple/prompts/` with manager and worker subfolders.
- Manager packets always include deterministic artifact path map.
- Manager read scope defaults:
  - read from `./.op-simple/current/` by default
  - read from `./.op-simple/history/` only when explicitly needed

## Canonical Manager Artifacts (`.op-simple/current/`)
- `cycle_manager_decision.json`
- `profile_snapshot.json`
- `production_line_register.json`
- `worker_packets.json`
- `plan_packets.json`
- `task_execution_state.json`
- `worker_registry.json`
- `dispatch_registry.json`
- `cycle_summary.json`
- `watchdog_state.json`
- `watchdog_exit_signal.json`

## In-Cycle Order (V2)
1. Increment cycle counter (code).
2. Check termination file (code).
3. Run `cycle-manager` foreground LLM.
4. Run `profile-manager` foreground LLM.
5. Run `BOSS` foreground LLM (renamed from production-line-manager).
6. Run rate-gate wait stage (profile-manager-owned behavior).
7. Run `work-dispatcher` in fire-and-forget mode.
8. Run `watchdog`.
9. Print summary.
10. Fixed sleep: 5 minutes.

## Stop Priority
1. Manual terminate file.
2. `project_done`.
3. `insurmountable_blocker`.
4. Watchdog idle-stop.

## LLM/Artifact Policy
- OP code does not hard-validate or lint LLM-generated manager artifacts in-cycle.
- LLM prompts should include links to artifact validator/helper scripts.
- Deterministic generation + immediate deterministic validation is allowed for deterministic artifacts only.
- `dispatch_registry` ownership is LLM manager side in this model.
- Dispatcher writes deterministic launch receipts to `dispatch_launch_log.jsonl` and continues.
- Dispatcher does not write deterministic failure-state artifacts for reassignment; BOSS handles recovery.
- OP code does not generate deterministic DONE evidence handoff artifacts; BOSS gathers evidence via prompt/tooling.
- `profile-manager` is snapshot-only in V2.
- `profile_assignment` artifact is removed in V2.

## BOSS Timeout Marker
- Marker file: `boss_evidence.json`.
- Purpose: only signal BOSS timeout from previous cycle.
- Created by OP code immediately when BOSS times out.
- Minimal fields:
  - `cycle_number`
  - `manager` = `BOSS`
  - `event` = `timeout`
  - `timestamp`
- BOSS is instructed to consume/delete marker via tool call.

## Manager Timeout Handling (Locked)
- Timeout budgets:
  - `cycle-manager`: 5 minutes
  - `profile-manager`: 7 minutes
  - `BOSS`: 12 minutes
  - `watchdog`: 2 minutes
  - `summary`: 2 minutes
- `cycle-manager`: on timeout, skip cycle body and start next cycle.
- `profile-manager`: on timeout, proceed with previous profile assignments.
- `BOSS`: on timeout, sleep 3 minutes, skip remainder of cycle, restart cycle, and emit BOSS-timeout marker.
- `work-dispatcher`: fire-and-forget; do not block on per-send hang; continue with other sends.
- `watchdog`: timeout means no stop signal this cycle.
- `summary`: skip summary and print timeout skip note.

## Lane/TDD Behavior
- Keep lane-based TDD mode.
- DONE marker contract in commit subject:
  - `[DONE][lane:<id>][task:<id>]`
- DONE detection owner: BOSS (LLM) from repo/artifact context.
- Worker liveness owner: BOSS (LLM).

## Manager I/O Contracts (Locked)
- `cycle-manager`:
  - output: `cycle_manager_decision.json`
  - minimum fields: `cycle_number`, `decision` (`proceed|skip_cycle`), `reason_code`, `message`, `worker_registry_ready`
- `profile-manager`:
  - output: `profile_snapshot.json` only
- `BOSS`:
  - produces atomically each cycle:
    - `production_line_register.json`
    - `worker_packets.json`
    - `plan_packets.json`
    - `cycle_summary.json`
    - `worker_registry.json` updates
- `work-dispatcher`:
  - writes deterministic launch receipts to `dispatch_launch_log.jsonl`
  - no deterministic reassignment/failure artifact for BOSS recovery

## Artifact Field Locks (Current)
- `worker_registry` row minimum fields:
  - `worker_id`, `worktree`, `branch`, `status`
  - `current_task_profile`, `next_task_profile`
  - `current_task_id`, `current_packet_id`
  - `pid`, `thread_id`
  - `last_update`
- `worker_registry` `pid/thread_id` writer:
  - BOSS updates from dispatch receipts
- `dispatch_registry` role:
  - dispatch event/history log
  - `worker_registry` remains latest worker state
- `dispatch_registry` status enum:
  - `launched`, `launch_failed`, `unknown`
- `production_line_register` row minimum fields:
  - `worker_id`, `lane_id`, `task_id`, `packet_id`, `profile_alias`, `assignment_state`, `reason`
- `worker_packet` minimum fields:
  - `packet_id`, `worker_id`, `lane_id`, `task_id`, `profile_alias`, `prompt`, `required_done_marker`
- `plan_packets` status enum:
  - `pending`, `in_progress`, `done`, `blocked`
- `plan_packets` structure model:
  - keep old OP topology shape with `phases[]`, `requirements[]`, `tasks[]`
  - phases form an acyclic DAG via `depends_on_phase_ids`
  - `lane_id` format remains `<phase_id>/lane-[a-c]`
- task fields policy:
  - `requirement_ids` field is mandatory but may be empty
  - keep old rich task shape, but drop per-task `verify_commands`
  - `verification_contract` remains mandatory, adapted for lane-level test/review flow (not per-task dev->test->review loop)
- `task_execution_state` artifact policy:
  - separate from `plan_packets`
  - authoritative writer: BOSS
  - minimum sections: task rows, blockers, attempts, `last_handoff_outcome`

## Parallelism and Canary
- Default max parallel workers remains 8 (configurable).
- parallelism limit source:
  - resolved global OP config stack (`scripts/install/config.py`)
  - key: `workflow.max_parallel_workers`
  - per-run override: `/op-simple-build --max-parallel-workers <n>`
- BOSS capacity lookup policy:
  - BOSS reads configured parallelism limits from configured artifact/config path via prompt guidance (no extra packet fields required)
- First vertical target: `cycle-manager -> profile-manager -> BOSS -> dispatcher` with real dispatch and DONE marker observed.
- Canary success criteria: 5 consecutive successful cycles with no manual intervention.

## Watchdog and Summary Contracts
- Watchdog monitored branch source:
  - `.op-simple/current/initialize_state.json`
- Watchdog idle counter reset rule:
  - reset to zero on any new commit detected on monitored branch
- Minimum cycle summary payload:
  - `cycle_number`
  - `manager_statuses` as map `{status, note}` keyed by manager name
  - `task_counts` (`pending`, `in_progress`, `done`, `blocked`)
  - `dispatch_counts`
  - `notes`
- `watchdog_exit_signal.json` minimum fields:
  - `cycle_number`
  - `reason_code`
  - `message`
  - `monitored_branch`
  - `idle_cycles`

## Initialize Workstation Artifact
- `workstation_prep` is written by initialize code once per run before cycle start.

## Phase 2 Placeholder
- Additional worker prompt types planned later (post-canary):
  - `integration_tester`
  - `plan-reviewer`
