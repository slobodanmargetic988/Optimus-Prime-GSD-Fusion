This nudge is broad by design. Run a full diagnostics sweep before deciding to skip repeatedly.

## Broad diagnostics checklist (not limited to one failure mode)
1. Inspect repeated cycle-gate skip reasons in `.op-simple/current/cycle_manager_decision.json` and recent `.op-simple/history/cycle-*/cycle_manager_decision.json`.
2. Reconcile all in-progress workers with `pid=null` by scanning canonical and non-obvious evidence locations.
3. Ingest reviewer outcomes from:
   - `<worker_worktree>/reports/handoffs/<task_identifier>.handoff.json`
   - `<worker_worktree>/.codex-dispatch/dispatch-*.log`
4. Normalize decision aliases during ingestion when needed (`reviewer_decision` -> `decision`) and update canonical artifacts.
5. Verify `task_execution_state.json`, `worker_registry.json`, and `production_line_register.json` are aligned after reconciliation.
6. Validate worker packet/worktree integrity (`worker_packets.json` entries map to valid worker rows and existing worktrees).
7. Validate profile gating posture (`profile_snapshot.json`) so dispatch is not starved by hard/soft gate mistakes.
8. Check for dispatch launch failures/timeouts in `.op-simple/current/dispatch_launch_log.jsonl`.
9. If evidence is still missing, create explicit remediation tasks instead of repeating passive skips.

After applying this nudge, rename this file to `recovery_instructions_CONSUMED.md`.
