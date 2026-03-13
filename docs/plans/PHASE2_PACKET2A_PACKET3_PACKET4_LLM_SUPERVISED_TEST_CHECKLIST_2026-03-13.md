# Phase 2 LLM Supervised Test Checklist (Deferred)

Date: 2026-03-13
Scope: Packet 2A + Packet 3 + Packet 4 runtime hardening validation
Execution mode: supervised LLM/canary batch (not executed in this implementation pass)

## Preconditions

1. Confirm non-LLM regression tests are green for `scripts/op/tests/test_op_simple_build.py`.
2. Confirm runtime artifacts are clean under `.op-simple/current/` before each supervised run.
3. Confirm target canary scope is `Tetris` only for this cycle.

## Packet 2A supervised checks

1. Run one `Tetris` canary where watchdog is healthy and verify:
- `cycle_mode` stays `normal` unless near-stale threshold is crossed.
- `mergeability_report.json` updates every cycle.
- `terminal_capsule.json` is emitted on unhappy-path cycles.
2. Induce BOSS timeout once and verify:
- timeout cycle is fail-closed (no dispatch in timeout cycle).
- timeout cycle writes `cycle_summary.json`, `cycle_manager_decision.json`, and `terminal_capsule.json`.
3. Induce second consecutive BOSS timeout and verify:
- `timeout_adaptation_state.consecutive_boss_timeouts >= 2`.
- `timeout_adaptation_state.adaptation_active=true`.
- if multiple eligible profiles exist, `rotation_required=true` and next BOSS call rotates alias.

## Packet 3 supervised checks

1. Scenario `watchdog_resume`:
- start from watchdog exit signal and resume mode.
- verify `restart_determinism_state.scenario == watchdog_resume`.
- verify idempotent continuation remains stable across repeated resume invocations.
2. Scenario `process_kill_resume`:
- simulate stale lock PID and resume.
- verify scenario classified as `process_kill_resume`.
- verify continuation log records deterministic checkpoint fingerprint updates.
3. Scenario `checkpoint_replay`:
- resume without watchdog signal and without stale process lock.
- verify scenario classified as `checkpoint_replay`.
- verify repeated resume with unchanged artifacts marks `idempotent_continuation=true`.

## Packet 4 supervised checks

1. Validate writer scaffolds by generating packet4 bundle intentionally in supervised mode.
2. Confirm naming contract compliance:
- `packet4_gate_evidence_bundle_<YYYY-MM-DD>.json`
- `packet4_gate_evidence_bundle_<YYYY-MM-DD>.md`
3. Attach KPI references and verify close/hold recommendation can be produced from real canary evidence.

## Watchdog terminal wrapup checks

1. Force watchdog terminal stop and verify wrapup manager executes.
2. Confirm wrapup context includes `mergeability_snapshot` fields:
- `run_base_sha`
- `unmerged_commit_count`
- `merge_blockers`
- `lane_status`

## Evidence capture

1. Capture before/after KPI artifacts for `Tetris` in the Earth report root.
2. Capture a delta artifact using naming contract v1.
3. Record open blockers with owner and due date for any hold recommendation.
