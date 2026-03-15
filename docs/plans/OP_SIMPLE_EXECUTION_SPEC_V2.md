# OP Simple Execution Spec V2

## Status
- This is the active planning baseline as of 2026-03-06.
- `docs/plans/OP_SIMPLE_TASK_BACKLOG.md` is frozen as V1 historical context.

## Locked Direction
- Branch safety: do all work on `codex/simple-op` only.
- Product direction: replace old build runtime behavior on this branch; no backward compatibility target.
- Command target: `/op-simple-build`.
- Initialize boundary: keep `/op-initialize` mostly intact and adapt only where needed.
- Initialize order (locked): profile detection/state update -> rate snapshot seed -> planner.
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
- `wrapup_manager_report.json`
- `watchdog_state.json`
- `watchdog_exit_signal.json`

## In-Cycle Order (V2)
1. Increment cycle counter (code).
2. Check termination file (code).
3. Run `BOSS` foreground LLM (renamed from production-line-manager).
4. Run rate-gate wait stage (pure code, snapshot refresh via skill).
5. Run `work-dispatcher` in fire-and-forget mode.
6. Run `watchdog` (pure code).
7. Print summary.
8. Fixed sleep: 5 minutes.

## Post-Loop Finalization
- When terminal reason is `project_done`, runtime executes one terminal foreground LLM manager call:
  - `wrapup-manager`
- `wrapup-manager` responsibilities:
  - merge/finalize intended completed work into run-base
  - finalize app lifecycle ledger (`app_lifecycle.json`)
  - write `.op-simple/current/wrapup_manager_report.json`
- Gate policy:
  - soft gate (warnings on failure), terminal reason remains `project_done`

## Stop Priority
1. Manual terminate file.
2. `project_done`.
3. `insurmountable_blocker`.
4. Watchdog idle-stop.

## LLM/Artifact Policy
- OP code does not hard-validate or lint LLM-generated manager artifacts in-cycle.
- LLM prompts should include links to artifact validator/helper scripts.
- Deterministic generation + immediate deterministic validation is allowed for deterministic artifacts only.
- `dispatch_registry` is maintained by deterministic dispatcher code as event/history log.
- Dispatcher writes deterministic launch receipts to `dispatch_launch_log.jsonl` and continues.
- Dispatcher does not write deterministic failure-state artifacts for reassignment; BOSS handles recovery.
- OP code does not generate deterministic DONE evidence handoff artifacts; BOSS gathers evidence via prompt/tooling.
- `cycle-manager` and `profile-manager` calls are currently skipped in runtime; BOSS absorbs cycle preflight intent.
- `profile_assignment` artifact is removed in V2.

## Profile Selection Policy (Runtime)
- Multi-profile source policy:
  - when multiple `.codex*` profiles are detected, default `.codex` is excluded from selectable pool.
  - when only one profile exists, default `.codex` remains valid.
- BOSS profile selection (pure code):
  - source: `.op-simple/current/profile_snapshot.json`
  - choose profile with highest weekly remaining percentage that is not 5h hard-gated
  - runtime applies chosen profile by setting `CODEX_HOME` on BOSS `codex exec`
  - fallback on missing/malformed snapshot: use default runtime profile behavior
- Planner profile selection (pure code):
  - source: `PROFILE_SELECTION.json` + `PROFILE_RATE_REGISTRY.json`
  - same selection rule: highest weekly remaining, excluding 5h hard-gated
  - exclude `codex` when multiple selected aliases exist
  - runtime applies chosen profile by setting `CODEX_HOME` for planner `codex exec`
  - fallback on missing/malformed artifacts: use default runtime profile behavior

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

## Timeout Handling (Locked)
- Active foreground LLM timeout:
  - `BOSS`: 12 minutes
- `BOSS`: on timeout, sleep 3 minutes, skip remainder of cycle, restart cycle, and emit BOSS-timeout marker.
- `work-dispatcher`: fire-and-forget; do not block on per-send hang; continue with other sends.
- `watchdog` and `summary` are pure-code stages in current runtime (no LLM timeout contract).

## Lane/TDD Behavior
- Keep lane-based TDD mode.
- DONE marker contract in commit subject:
  - `[DONE][lane:<id>][task:<id>]`
- DONE detection owner: BOSS (LLM) from repo/artifact context.
- Worker liveness owner: BOSS (LLM).

## Manager I/O Contracts (Locked)
- `BOSS`:
  - produces atomically each cycle:
    - `production_line_register.json`
    - `worker_packets.json`
    - `plan_packets.json`
    - `task_execution_state.json`
    - `cycle_summary.json`
    - `worker_registry.json` updates
  - every required BOSS-authored artifact must carry top-level `cycle_number` equal to the current runtime cycle
  - if BOSS returns non-zero, the binary is missing, a required artifact is missing, or a required artifact has missing/stale `cycle_number`, runtime converts the cycle into deterministic `skip_cycle` and does not dispatch that cycle
- `wrapup-manager`:
  - invoked only after loop exit with `project_done`
  - must write `wrapup_manager_report.json` with current-cycle `cycle_number`
  - runtime treats wrapup failures as warnings (soft gate), not terminal-state rollback
- `work-dispatcher`:
  - writes deterministic launch receipts to `dispatch_launch_log.jsonl`
  - no deterministic reassignment/failure artifact for BOSS recovery
- `cycle_manager_decision.json`:
  - retained as canonical artifact/stub for compatibility and telemetry continuity
  - runtime writes deterministic `skip_cycle` decisions when BOSS fails safety checks
  - BOSS should refresh it each cycle for proceed/skip visibility
- `profile_snapshot.json`:
  - refreshed by pure code rate-gate stage via `minimal-rate-snapshot`
  - may also be updated by BOSS behavior, but code refresh remains authoritative for gating checks

## Artifact Field Locks (Current)
- `worker_registry` row minimum fields:
  - `worker_id`, `worktree`, `branch`, `status`
  - `current_task_profile`, `next_task_profile`
  - `current_task_id`, `current_packet_id`
  - `pid`, `thread_id`
  - `last_update`
- `worker_registry` time format:
  - `last_update` uses full UTC timestamp
- `worker_registry` `pid/thread_id` writer:
  - BOSS updates from dispatch receipts
- `dispatch_registry` role:
  - dispatch event/history log
  - `worker_registry` remains latest worker state
- `dispatch_registry` status enum:
  - `launched`, `launch_failed`, `unknown`
- `dispatch_registry` event row minimum fields:
  - `cycle_number`, `worker_id`, `packet_id`, `thread_id`, `pid`, `status`, `timestamp`, `message`
- `production_line_register` row minimum fields:
  - `worker_id`, `lane_id`, `task_id`, `packet_id`, `profile_alias`, `assignment_state`, `reason`
- `production_line_register` assignment state enum:
  - `assigned`, `unassigned`, `deferred`
- `worker_packet` minimum fields:
  - `packet_id`, `worker_id`, `lane_id`, `task_id`, `profile_alias`, `prompt`, `required_done_marker`
- `worker_packet` done-marker template:
  - `[DONE][lane:<lane_id>][task:<task_id>]`
- `plan_packets` status enum:
  - `pending`, `in_progress`, `done`, `blocked`
- `plan_packets` structure model:
  - keep old OP topology shape with `phases[]`, `requirements[]`, `tasks[]`
  - phases form an acyclic DAG via `depends_on_phase_ids`
  - `lane_id` format remains `<phase_id>/lane-[a-c]`
- task fields policy:
  - `requirement_ids` field is mandatory but may be empty
  - keep old rich task shape, but drop per-task `verify_commands`
  - `task_kind` is mandatory on every task and determines whether runtime routes the task as implementation, lane test, lane review, deep review, fix, or merge work
  - `verification_contract` remains mandatory, but is now task-kind oriented (`mode`, `expected_failure_reason_codes`, `infra_failure_reason_codes`) rather than per-task dev/test/review expectation fields
- `task_execution_state` artifact policy:
  - separate from `plan_packets`
  - authoritative writer: BOSS
  - minimum top-level sections: `tasks`, `blockers`, `attempts`, `last_handoff_outcome`
- `task_execution_state` task status enum:
  - `pending`, `in_progress`, `done`, `blocked`
- `task_execution_state` attempts model:
  - stage-keyed counters (`dev`, `lane_test`, `test_fix`, `lane_review`, `review_fix`, `deep_review`, `deep_fix`)
- `task_execution_state` `last_handoff_outcome.status` enum:
  - `success`, `blocked`, `failed`, `unknown`
- `task_execution_state` blocker row minimum fields:
  - `blocker_code`, `message`, `first_seen_cycle`, `last_seen_cycle`, `active`
- `profile_snapshot` row minimum fields:
  - `alias`, `codex_home`
  - `window_5h_remaining_pct`, `window_week_remaining_pct`
  - `hard_gated`, `soft_gated`, `reset_at`
- `cycle_manager_decision` remains proceed-gate minimal:
  - no `next_action` field
- lane size policy:
  - no schema-level task cap; parallelism limits come from runtime config

## Parallelism and Canary
- Default max parallel workers remains 8 (configurable).
- parallelism limit source:
  - resolved global OP config stack (`scripts/install/config.py`)
  - key: `workflow.max_parallel_workers`
  - per-run override: `/op-simple-build --max-parallel-workers <n>`
- BOSS capacity lookup policy:
  - BOSS reads configured parallelism limits from configured artifact/config path via prompt guidance (no extra packet fields required)
- First vertical target: `BOSS -> rate-gate -> dispatcher` with real dispatch and DONE marker observed.
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
  - `dispatch_counts` (`attempted`, `launched`, `launch_failed`, `unknown`)
  - `notes`
- `watchdog_exit_signal.json` minimum fields:
  - `cycle_number`
  - `reason_code`
  - `message`
  - `monitored_branch`
  - `idle_cycles`
- `watchdog_state.json` minimum fields:
  - `cycle_number`, `monitored_branch`, `last_commit_sha`, `last_commit_seen_cycle`, `idle_cycles`, `threshold_cycles`

## App Lifecycle Ledger Contract
- Location:
  - `<repo-root>/app_lifecycle.json` (git-tracked in built app repo)
- Top-level:
  - `schema_version`, `updated_at`, `app_lifecycle[]`
- Era row minimum:
  - `era_id`, `status`, `started_at`, `completed_at`
  - `mission` (`text`, `source`)
  - `scope` (`text`, `source`)
  - `run_context`
  - `completion`
- Initialize behavior:
  - append new era with `status=in_progress`
  - persist mission/scope as full text plus source metadata
- Project-done behavior:
  - wrapup finalizes active era to `status=completed`
  - records final run-base branch + final commit sha

## Initialize Workstation Artifact
- `workstation_prep` is written by initialize code once per run before cycle start.
- `workstation_prep` row minimum fields:
  - `workstation_id`, `branch`, `worktree`, `prepared_at`, `status`, `preparation_notes`, `git_head_sha`

## Prompt Contract Minimums
- manager prompts must include:
  - role
  - inputs (artifact paths)
  - required outputs (files + schema contract)
  - failure handling
  - tool usage rules
- worker prompts must include:
  - task objective
  - constraints
  - required commit marker
  - expected artifact/evidence outputs
  - stop/escalation rules
- validator/helper script references use absolute install-location paths (not repo-relative paths)

## Phase 2 Placeholder
- Additional worker prompt types planned later (post-canary):
  - `integration_tester`
  - `plan-reviewer`
