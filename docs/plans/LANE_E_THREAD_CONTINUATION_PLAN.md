# Lane E Thread Continuation Plan (Core Idea)

## Summary
Lane E introduces thread continuation for worker dispatch so related tasks can reuse an existing Codex session instead of always spawning a fresh one.

Primary outcome:
1. Lower token burn and context loss on related tasks.
2. Keep deterministic safety and recovery behavior from Lane B.
3. Let `/op-build` choose continue-vs-new dispatch mode automatically.
4. Add automatic profile recognition so `/op-build` uses all available Codex profiles by default.

## Why This Lane
Current dispatch behavior creates a new Codex run for each dispatched task/stage.
That is reliable, but inefficient for related work streams where continuing the same worker thread would preserve context and reduce repeated prompt overhead.

## Scope (Initial)
1. Add dispatch-level continuation mode in `thread-dispatch` flow.
2. Add affinity policy in `/op-build` to decide when continuation is preferred.
3. Persist session/thread lineage per task family and slot.
4. Add deterministic fallback to fresh dispatch when continuation is unsafe/unavailable.
5. Add automatic profile recognition in `/op-initialize` and persist detected profile set for `/op-build`.

## Non-Goals (Initial)
1. No backward-compat shims for legacy dispatch formats.
2. No cross-repo/global orchestration migration.
3. No relaxation of safety gates (runtime gates, stop/reconcile, strict done).

## Core Design Idea
1. Introduce a per-slot/per-task-family session affinity key.
2. On dispatch, `/op-build` evaluates:
   - same task lineage or clearly related follow-up work,
   - prior worker session health,
   - no conflicting active ownership.
3. If continuation conditions pass:
   - dispatch in "continue thread" mode with next prompt payload.
4. If conditions fail:
   - dispatch as a new worker run (existing behavior).

## Required Behavior
1. Continuation must be explicit in artifacts/logs (never implicit/hidden).
2. Failed continuation attempt must degrade safely to new-dispatch path.
3. Stop/resume reconciliation must remain authoritative over in-progress state.
4. Operator stop must halt both continued and newly spawned workers equivalently.
5. `/op-initialize` must detect available profiles once and seed build state with `profile_aliases[]` for rate-gate decisions.

## `/op-build` Integration Expectations
1. `/op-build` remains the owner of dispatch decisions.
2. Controller continues to emit directives only; no controller-owned dispatching.
3. Dispatch adapter receives a deterministic mode field:
   - `dispatch_mode=continue_thread|new_thread`.
4. Build state records the decision rationale each cycle.
5. `/op-build` consumes initialized profile aliases instead of hardcoding a single profile.

## Suggested Artifacts (Planned)
1. `reports/optimus-prime/planning/THREAD_AFFINITY_STATE.json`
2. `reports/optimus-prime/planning/THREAD_CONTINUATION_LOG.jsonl`
3. `reports/optimus-prime/planning/PROFILE_SELECTION.json` (detected aliases + selected aliases + detection timestamp)

## Acceptance Direction (Phase 1)
1. Related task chains can continue prior session when healthy.
2. Unrelated tasks still spawn fresh workers.
3. No increase in deadlock/orphan-worker incidents.
4. Deterministic recovery on missing/invalid continuation metadata.
5. Existing strict gates and final-state verification remain unchanged.
6. Fresh `/op-initialize` detects available profiles and `/op-build` uses the detected set without manual profile flags.

## Dependencies
1. `dispatch-worker-packet` contract extension for continuation metadata.
2. `thread-dispatch` capability to target existing session/thread.
3. `/op-build` policy wiring + tests for continue-vs-new decisions.
4. Codex profile detector wiring (`codex-rate-snapshot`-based discovery) integrated into `/op-initialize`.

## Next Planning Step
Convert this core idea into a decision-complete implementation batch with:
1. exact contracts,
2. migration-free new-only schemas,
3. test matrix for continuation safety, stop/reconcile parity, and fallback behavior.
