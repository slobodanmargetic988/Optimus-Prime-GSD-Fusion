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
3. `cycle-manager` (foreground LLM, blocking).
4. `profile-manager` (code snapshot + LLM assignment).
5. `BOSS` manager (structured LLM + schema validation tools).
6. Rate-gate wait/continue gate (profile-manager-owned wait loop).
7. `work-dispatcher` (pure code dispatch engine).
8. `watchdog-manager` (pure code, commit-based inactivity check).
9. Pure code: print cycle summary from BOSS summary payload.

## Old OP-Build Mapping (to New Managers)
- `cycle-manager`:
  - New manager; absorbs early cycle orchestration intent.
  - Related old behavior context: controller/directive path (#8, #9), but redesigned.
- `profile-manager`:
  - Keeps old profile-manager role (#2), plus old dispatch-capacity intent from #24.
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

### 1) cycle-manager
- Type: LLM-based manager (foreground, blocking call).
- Job:
  - Ensure worker registry exists; create it if missing.
  - Do not own lane planning/routing decisions.
- Must ensure:
  - Worker registry availability before downstream managers run.
  - Deterministic output artifact/schema for downstream consumers.
  - No cycle continuation without successful decision output.

### 2) profile-manager
- Type: Hybrid manager (pure code snapshot + LLM assignment).
- Job:
  - Snapshot all profile rate-limit state each cycle.
  - Assign `next-task-profile` for each workstation.
  - Respect `current-task-profile` lock so profile does not change mid-task.
- Must ensure:
  - Every eligible workstation has a valid `next-task-profile`.
  - Active workers keep `current-task-profile` stable until task completion.
  - Assignment output is written in registry fields consumed by production-line-manager.

### 3) BOSS manager
- Type: LLM-based manager (structured output, schema-validated by tools).
- Job:
  - Decide parallelism by lanes.
  - Decide worker-to-task routing and whether dispatch should happen now.
  - Prepare worker packets for dispatcher.
  - Maintain production-line register.
  - Update plan packets as single source of truth for task states.
  - Produce cycle summary payload for printing.
- Must ensure:
  - Packets are complete and valid before dispatch.
  - Worker eligibility/rate constraints are respected (using profile-manager output).
  - Plan packets remain authoritative for `pending/in_progress/done/blocked`.
  - Register conforms to schema on every write.

### 4) work-dispatcher
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

### 5) watchdog-manager
- Type: Pure code manager.
- Job:
  - Monitor configured branch for commit activity.
  - Emit exit signal if no new commits appear for N cycles.
- Must ensure:
  - Default threshold starts at 10 cycles (tunable).
  - Single watchdog location/authority in runtime.
  - Clear machine-readable exit signal artifact.

### 6) rate-gate wait/continue gate
- Type: Pure code gate (not LLM manager).
- Job:
  - Always auto-wait while rate-gated.
- Must ensure:
  - heartbeat every 5 minutes while waiting.
  - profile snapshot + profile re-scan every 15 minutes while waiting.
  - wait-loop is owned by profile-manager logic.

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

- `profile-manager` feeds rate-aware capacity into lane scheduling:
  - profile snapshots + `next-task-profile` assignment each cycle
  - `current-task-profile` lock prevents mid-task profile reassignment

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
