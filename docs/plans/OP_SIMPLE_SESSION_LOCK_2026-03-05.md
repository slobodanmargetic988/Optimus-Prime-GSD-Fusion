# OP Simple Session Lock (2026-03-05)

This file records decisions finalized in-session so no context is lost.

## Runtime Control
- Build loop is plain `while`.
- Stop signal is repo-root file presence:
  - `terminate_run.json`
- Stop logic ignores file contents (presence only).

## Manager Authority
- Authority manager name: `BOSS`.
- `cycle-manager` scope is minimal bootstrap only:
  - ensure worker registry exists.
- `BOSS` is the only manager allowed to author termination decisions (writes stop file).
- `BOSS` reads watchdog outputs and decides continuation/termination strategy.

## Rate-Gate Policy (Locked)
- Auto-wait on rate gates only when the soonest reset is within 3 hours.
- If all discovered profiles are hard-gated and the soonest reset is beyond 3 hours, or missing, stop cleanly with `all_rate_gates_blocking`.
- During wait:
  - heartbeat log every 5 minutes.
  - profile snapshot every 15 minutes.
  - profile re-scan every 15 minutes.
- Wait-loop ownership: `profile-manager`.

## Lane/TDD Execution Model (Locked)
- Keep TDD style, remove per-task `dev -> test -> review` machine.
- Lane lifecycle:
  1. Dev execution (sequential/parallel by dependency DAG).
  2. Lane-wide testing.
  3. Dev fix cycle for test findings.
  4. Lane-wide review.
  5. Dev fix cycle for review findings.
  6. Deep review/regression pass.
  7. Fix regressions if found.
- Lane cap: up to 8 tasks.

## Scheduling and Worker Policy (Locked)
- Scheduling policy: topological + capacity-aware.
- Recompute cadence: every cycle.
- Default max parallel workers: 8 (configurable).
- Role mix baseline: dev-heavy while dev work exists.
- Tester priority: when a lane finishes dev tasks, next cycle prioritizes tester assignment for that lane.
- Lane affinity rule: soft preference only.
  - Prefer same-lane continuity.
  - Override preference to keep workers busy when same-lane tasks are blocked.

## Commit Marker Contract (Locked)
- DONE signal is a structured token in commit subject.
- Workers may emit structured non-DONE completion tokens when blocked/incomplete.
- BOSS prompt will handle non-DONE outcomes with next-cycle repair/recovery packet planning.
- Worker packets must explicitly require commit-at-end behavior.

## Worker Registry Schema Outcome (Locked)
- `allowed_roles` removed (all workers can take any role).
- Added fields:
  - `worktree`
  - `branch`
- Final approved worker registry fields:
  - `worker_id`
  - `workstation_id`
  - `status`
  - `worktree`
  - `branch`
  - `current_lane_id`
  - `current_task_id`
  - `current_task_profile`
  - `next_task_profile`
  - `active_packet_id`
  - `dispatch_pid`
  - `dispatch_thread_id`
  - `last_commit_marker`
  - `last_update_at`

## Canary / MVP Boundaries
- MVP success target: canary pilot-ready.
- Canary project shape:
  - CRUD web app
  - Vue frontend
  - FastAPI backend
  - no auth
- Canary testing stack:
  - Pytest
  - Vitest
  - Playwright
- Canary task cap: hard cap 20 tasks.
- Canary execution model:
  1. fast run with fixed/mock plan artifacts
  2. full canary run with planner enabled
- External canary repo:
  - deferred setup item
  - placeholder: `CANARY_REPO_TBD`
  - intended repo name: `tetris` (private GitHub repo to be created later)

## Delivery Targeting
- Stage A auto-builder target: ~80% project completion.
- Stage B planned tester-heavy cycle target: ~95%.
- Final mile 95% -> 100% is user-driven explicit minor prompt work (out of scope for auto-builder).

## Tracking Decisions
- Backlog remains source of task status.
- Tracker pause rules (locked):
  - pause every 5 completed tasks
  - immediate pause on `BLOCKED_HUMAN`
- Blocker taxonomy (locked):
  - `schema`, `prompt`, `policy`, `runtime`
