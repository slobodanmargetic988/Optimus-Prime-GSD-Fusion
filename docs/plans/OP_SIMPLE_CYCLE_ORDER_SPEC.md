# OP Simple Cycle Order Spec (Final for T009)

## Scope
This document freezes the agreed in-cycle order for OP Simple runtime (post-initialize).

Out of scope:
- prompt text details
- full schema definitions
- implementation code

## Preconditions
- `/op-initialize` has already run.
- Workstations are prepared once in initialize phase (not in-cycle).
- Runtime loop uses plain `while` structure.

## Authoritative Stop Signal
- Runtime stops when file exists at repo root:
  - `terminate_run.json`
- Stop condition is file presence only.
- Runtime does not depend on file content for stopping.

## In-Cycle Order
1. Increment cycle counter (pure code).
2. Check `terminate_run.json` at repo root; if present, stop loop.
3. Run `cycle-manager` (foreground LLM, blocking):
   - ensure worker registry exists (create if missing)
   - no lane planning decisions at this step
4. Run `profile-manager` (hybrid: code + LLM):
   - snapshot all profiles/rate state
   - assign `next-task-profile` per workstation
   - preserve `current-task-profile` for in-progress tasks
5. Run `BOSS` manager (LLM + schema validation tooling):
   - lane-aware scheduling and parallelism decisions
   - worker/task routing decisions
   - packet preparation for dispatcher
   - plan-packet updates as source of truth
   - cycle summary payload generation
6. Run rate-gate wait/continue gate (profile-manager-owned wait loop):
   - always auto-wait when rate-gated
   - emit heartbeat every 5 minutes while waiting
   - re-run profile snapshot and profile re-scan every 15 minutes while waiting
7. Run `work-dispatcher` (pure code):
   - dispatch prepared packets to eligible ready workers as background tasks
   - write dispatch tracking for each send (`pid`, `thread_id`)
8. Run simplified watchdog (pure code):
   - monitor configured branch for commit activity
   - emit stop signal when no new commits for threshold cycles (default 10)
9. Print cycle summary from BOSS payload (pure code).

## Explicitly Removed From Old Loop
- gap-consumption-manager
- branch-merge-manager
- in-cycle workstation-manager
- controller tick/directive chain
- second gap reconcile pass
- old standalone step chain for dead-pid/offset/fingerprint orchestration (absorbed/simplified elsewhere)

## Notes
- Final prompt/schema details are tracked separately in backlog tasks.
- `BOSS` is the authority manager name for lane planning/coordination.
- `BOSS` is the only manager that authors termination decisions.
