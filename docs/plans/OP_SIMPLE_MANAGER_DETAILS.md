# OP Simple Manager Details

## Purpose
Define the new OP Simple managers based on current decisions, map them to old OP-build points, and describe manager responsibilities and guarantees.

## High-Level Flow

### Before cycle loop
1. Run `/op-initialize` (same flow as current app, including `/op-plan`).
2. Prepare workstations once during initialize (moved from old in-cycle workstation-manager).
3. Start build loop as plain `while` loop.

### Inside each cycle (suggested order)
1. Pure code: increment cycle counter.
2. Pure code: termination-file check; stop loop if file exists.
3. `BOSS` manager (structured LLM + schema validation tools).
4. Rate-gate wait/continue gate (pure code snapshot + wait loop).
5. `work-dispatcher` (pure code dispatch engine).
6. `watchdog-manager` (pure code, commit-based inactivity check).
7. Pure code: print cycle summary from BOSS summary payload.

## Old OP-Build Mapping (to New Managers)
- `cycle-manager`:
  - Runtime call is currently skipped.
  - Intent is absorbed by BOSS preflight behavior.
- `profile-manager`:
  - Runtime call is currently skipped.
  - Snapshot/rate gating is handled by pure code wait stage; planning intent is absorbed by BOSS.
- `production-line-manager`:
  - Keeps and expands old production-line-manager (#10).
  - Absorbs state-source responsibilities previously spread across #21, #24, #28.
- `work-dispatcher`:
  - Redesign of old dispatch step (#18 / #25).
- `watchdog-manager`:
  - Simplified replacement of old watchdog-related behavior (#12 / #29).
- Rate-gate wait/continue gate:
  - Keeps old #15 behavior (do not hard-stop if reset window is acceptable).
- Workstation preparation:
  - Old in-cycle workstation-manager moved to initialize phase (old #6 moved pre-cycle).

## Manager Details

### 1) BOSS manager
- Type: LLM-based manager (structured output, schema-validated by tools).
- Job:
  - Execute cycle preflight intent that replaced standalone cycle/profile manager calls.
  - Decide parallelism by lanes.
  - Decide worker-to-task routing and whether dispatch should happen now.
  - Prepare worker packets for dispatcher.
  - Maintain production-line register.
  - Update plan packets as single source of truth for task states.
  - Produce cycle summary payload for printing.
- Must ensure:
  - Packets are complete and valid before dispatch.
  - Worker eligibility/rate constraints are respected (using current snapshot artifacts).
  - Plan packets remain authoritative for `pending/in_progress/done/blocked`.
  - Register conforms to schema on every write.
  - Use runtime-selected profile context when available (highest weekly budget, not 5h gated).

### 2) work-dispatcher
- Type: Pure code manager.
- Job:
  - Send prepared packets to all ready workers as background LLM tasks.
  - Update registries per dispatch with process/thread tracking.
- Must ensure:
  - Only eligible workers from worker registry are dispatched.
  - For each dispatch, persist:
    - `pid`
    - `thread_id`
  - Dispatch records are sufficient for later liveness/completion checks.

### 3) watchdog-manager
- Type: Pure code manager.
- Job:
  - Monitor configured branch for commit activity.
  - Emit exit signal if no new commits appear for N cycles.
- Must ensure:
  - Default threshold starts at 20 cycles (tunable).
  - Single watchdog location/authority in runtime.
  - Clear machine-readable exit signal artifact.

### 4) rate-gate wait/continue gate
- Type: Pure code gate (not LLM manager).
- Job:
  - Refresh `profile_snapshot.json` via `minimal-rate-snapshot`.
  - Always auto-wait while rate-gated.
- Must ensure:
  - heartbeat every 5 minutes while waiting.
  - profile snapshot + profile re-scan every 15 minutes while waiting.
  - wait-loop stays deterministic and independent from LLM manager calls.

## Current Explicit Removals
- Removed from new cycle: old #7, #8, #9, #11, #13, #14, #16, #17, #19, #20, #22, #23, #26, #27, #29 (as standalone), #30, #31.
- Removed managers: gap-consumption-manager, branch-merge-manager.

## Lane-Oriented TDD Mode (Applied to Managers)

### Lane execution policy
- Keep TDD mindset from old OP.
- Remove per-task stage machine (`dev -> test -> review` per task).
- Orchestrate by lane lifecycle:
1. Up to 8 tasks per lane.
2. Developer execution (sequential for linear dependencies, parallel where graph allows).
3. Whole-lane testing pass.
4. Whole-lane test-fix dev pass.
5. Whole-lane review pass.
6. Whole-lane review-fix dev pass.
7. Deep review/regression pass and fix-if-needed.

### Manager implications

- `production-line-manager` becomes lane scheduler:
  - manager authority name is `BOSS`
  - decides runnable task set from dependency graph
  - decides worker role mix each cycle (default max parallel workers = 8, configurable)
  - emits schema-valid next-cycle execution plan
  - prepares packets accordingly
  - updates plan packets as single source of truth
  - prefers lane affinity when possible but prioritizes keeping workers busy when same-lane tasks are blocked

- profile/rate input is now produced by code snapshot stage and consumed by BOSS for lane scheduling:
  - profile snapshots refreshed each cycle during rate-gate stage
  - `current-task-profile` lock remains in worker registry semantics

- `work-dispatcher` sends all packets for ready workers and records runtime tracking:
  - `pid` + `thread_id` persisted after each dispatch
  - dispatch uses production-line register and worker registry eligibility

- Completion accounting is simplified:
  - worker packets require commit message DONE marker
  - DONE marker is primary completion signal for manager state transitions

### Pre-LLM input gate (required)
- Before lane/production LLM decisions, pure code must provide:
  - active workers still running prior packets
  - workers complete/idle and eligible
  - dependency-ready task set
  - profile/rate availability snapshot

### Delivery staging targets
- Stage A (this system): autonomous lane cycle targets ~80% project completion.
- Stage B (planned follow-up): tester-heavy cycle using MSP/browser-testing skills to push to ~95%.
- Final mile (95% -> 100%): user-provided explicit minor-change prompts; outside auto-builder scope.
