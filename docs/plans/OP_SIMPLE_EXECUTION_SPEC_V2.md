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

## Parallelism and Canary
- Default max parallel workers remains 8 (configurable).
- First vertical target: `cycle-manager -> profile-manager -> BOSS -> dispatcher` with real dispatch and DONE marker observed.
- Canary success criteria: 5 consecutive successful cycles with no manual intervention.

## Watchdog and Summary Contracts
- Watchdog monitored branch source:
  - `.op-simple/current/initialize_state.json`
- Watchdog idle counter reset rule:
  - reset to zero on any new commit detected on monitored branch
- Minimum cycle summary payload:
  - `cycle_number`
  - `manager_statuses`
  - `task_counts` (`pending`, `in_progress`, `done`, `blocked`)
  - `dispatch_counts`
  - `notes`

## Initialize Workstation Artifact
- `workstation_prep` is written by initialize code once per run before cycle start.

## Phase 2 Placeholder
- Additional worker prompt types planned later (post-canary):
  - `integration_tester`
  - `plan-reviewer`
