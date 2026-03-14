This nudge is broad by design. Run a full diagnostics sweep before deciding to skip repeatedly.

## Most common nudge reason
Usualy you get this nudge file because you failed to merge anything into the run-base branch for a long time. you need to merge all the done tasks that are possible to merge immediately. if you have already issued worker packets for merge jobs they have failed and you need to merge done tasks yourself. make this a #1 priority and do it immediately. merege all done tasks into run base. and create 3 new tasks to test, review and patch fix all the merged changes as a bundle. 

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

After applying this nudge, rename this file to `recovery_instructions_CONSUMED<counter>.md` if a consumed file already exists increment the counter so i can have seperate consumed file for each nudge you recived. Also append a summary of what you did to recover at the end of the file in the recovery summary section.

## Recovery summary
