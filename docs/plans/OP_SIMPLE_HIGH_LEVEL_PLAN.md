# OP Simple High-Level Plan

This is our plan.

1. Keep `/op-initialize` as the first step, with the same initialize flow as today (including `/op-plan` inside it).
2. The build loop starts as a plain `while` loop.
3. Each loop iteration first checks for existence of a termination file; if present, stop loop.
4. First step inside each cycle is `cycle-manager`.
5. `cycle-manager` is a foreground LLM call (blocking; wait for completion before continuing).
6. `cycle-manager` responsibilities for now:
   - Ensure worker registry exists (create if missing).
   - If worker registry exists, determine which actions should be taken next in the cycle.

Rule for this document:
- Append-only updates from now on (do not delete/replace prior plan text; only add).

## Next Version: Cycle Redefinition Notes (Draft)

- Keep cycle counter in code; increment per cycle without LLM.

- Keep `profile-manager`, but redesign:
  - Take snapshots for all profiles each cycle.
  - Run LLM assignment to set `next-task-profile` per workstation.
  - Keep `current-task-profile` in worker registry to prevent profile changes mid-task.

- Remove `gap-consumption-manager`.
- Remove `branch-merge-manager`.

- Move `workstation-manager` to initialize phase (before cycle loop):
  - Prepare workstations once during initialize.
  - Workers keep their own workstations clean/sanitized afterward.
  - Candidate: move workstation init into a script.

- Remove current cycle steps:
  - #7 operator-stop handling in-cycle
  - #8 controller tick
  - #9 directive extraction/application
  - #11 second gap-consumption reconcile

- Keep `production-line-manager` (current #10) but redesign as structured LLM call:
  - Ensure tasks can run in parallel according to lanes.
  - Prepare worker packets.
  - Decide worker selection and dispatch timing.
  - Maintain a `production-line register` consumed by work-dispatcher.
  - Add schema validation tooling for this register.

- Keep watchdog but simplify (replacing current #12 behavior):
  - Monitor a specific branch.
  - Emit exit signal if no new commits appear for N cycles.
  - Initial N = 10 cycles (tunable).

- Remove current #13 terminal-reason evaluation path.

## Next Version: Additional Step Mapping Notes (Draft 2)

- #14 removed.

- #15 kept in principle:
  - Keep the behavior that avoids terminal exit on rate gates when reset is soon enough.
  - Final position/order in new cycle may change.

- #16 removed.
- #17 removed.

- #18 redesigned as `work-dispatcher`:
  - Dispatch packets to all workers that are ready to receive work.
  - Packets are prepared by production-line-manager.
  - Eligible workers are defined by worker registry.
  - Dispatcher sends background LLM tasks.
  - After each send, dispatcher updates registries with:
    - worker pid
    - thread id
  - Purpose: allow multiple liveness/completion verification paths in lane/production management.

- #19 removed.
- #20 removed.

- #21 moved/simplified into lane/production management logic:
  - Worker packets require workers to finish with a commit containing a DONE marker in commit message.
  - This becomes the primary completion signal.

- #22 removed.
- #23 removed (covered by #21 completion-marker model).

- #24 moved into production-line-manager:
  - Profile manager runs first and provides rate-limit/profile assignment info.
  - Production-line-manager decides which workers should receive work based on remaining rate limits.

- #25 removed (covered by redesigned #18 dispatcher).
- #26 removed completely.
- #27 removed.

- #28 removed as standalone step:
  - Production-line-manager now updates plan packets.
  - Plan packets become the single source of truth for task state (`done`, `in_progress`, `blocked`, etc.).

- #29 removed as standalone step:
  - Watchdog exists in one place only (exact placement TBD).

- #30 removed.
- #31 removed.

- #32 kept:
  - Keep cycle summary output.
  - Production-line-manager writes summary payload used for printing.

## Lane-Based Delivery Model (Draft 3)

- Keep TDD style from old OP, but remove per-task `dev -> test -> review` stage machine.
- New unit of orchestration is lane-level flow with task-level execution inside each lane.

Lane flow:
1. Lane contains up to 8 tasks.
2. Developer phase:
   - Execute tasks sequentially when dependencies are linear.
   - Execute tasks in parallel when dependency graph allows.
3. Lane-wide test phase:
   - Test whole lane and write findings.
4. Fix phase for test findings:
   - Developer cycle to fix all lane test findings.
5. Lane-wide review phase:
   - Review whole lane and write findings.
6. Fix phase for review findings:
   - Developer cycle to fix all lane review findings.
7. Deep lane review/regression check:
   - Re-check lane for regressions introduced by fixes.
   - Fix regressions if detected.

Parallel worker mix per cycle is lane-manager/production-line-manager decided by AI, for example:
- `5 dev + 1 tester`
- `3 dev + 1 tester + 1 reviewer`

Selection is based on:
- available runnable tasks
- dependency/parallelization constraints
- active workers still running from prior cycle
- available profile/rate budget

Decision output must be schema-constrained plan for next cycle.

Pre-LLM check must ensure manager input includes:
- which workers are still active on previous packets
- which workers are complete/idle

Completion signal model:
- Worker packets must require a commit message DONE marker.
- DONE marker is primary completion signal for lane progress accounting.

Delivery target model:
- This autonomous builder targets roughly 80% completion in this first cycle system.
- Planned next stage: second cycle focused on testers (MSP/browser-testing skills) to drive to roughly 95%.
- Final 95% -> 100% is user-driven with explicit minor-change prompts and is out of scope for auto-builder.
