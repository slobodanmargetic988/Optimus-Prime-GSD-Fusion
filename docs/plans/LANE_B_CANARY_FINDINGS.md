# Lane B Canary Findings Log

Updated: 2026-03-01

## Purpose
Track real canary-run findings, probable causes, and UX follow-ups that should be patched after observation runs.

## Run: 2026-03-01 (Canary #1)
Status: stopped early by operator after clear failure signal.

### Primary observed failure
1. Build remained at cycle `0` while process stayed alive.
2. Workers stayed idle because runtime was stuck in workstation-manager retry loop.
3. Deterministic validation error repeated:
   - `task_id mismatch; lane_id mismatch; prereq_policy must be copy_env_files|symlink_deps`

### Artifact evidence
1. `reports/optimus-prime/workstation-manager/attempt-dev-1-10/WORKSTATION_VALIDATION.json`
2. `reports/optimus-prime/workstation-manager/attempt-dev-2-6/WORKSTATION_VALIDATION.json`
3. `reports/optimus-prime/workstation-manager/attempt-dev-2-6/WORKSTATION_ACTION.json`

### Root-cause notes (confirmed)
1. Workstation manager action validation failed before workstation script execution, so no workstation worktree could be created.
2. LLM did reference the bundled `prepare_workstation.py` path in `prepare_command`, but validation stopped execution earlier.
3. Two contract mismatches were observed:
   - empty-string normalization mismatch (`lane_id`/`task_id` written as `""`, compared against normalized `None`),
   - prompt/validator mismatch on `prereq_policy`:
     - prompt example asked for `copy_env_files|symlink_deps`,
     - validator accepts only `copy_env_files` or `symlink_deps`.
4. Because workstation manager runs before controller/dispatcher in the cycle, build remained at `cycle=0` while retries were in progress.

## Run: 2026-03-01 (Canary #2, `.env` restored)
Status: stopped by operator after confirming same workstation-manager stall behavior.

### Observed behavior
1. Build process remained alive with lock held.
2. `cycle` stayed `0`; workers remained idle.
3. `WORK_DISPATCH_PLAN.json` contained assignment(s), but dispatcher was never reached due workstation-manager retries.
4. `git worktree list` showed only the main worktree; no `workstation-*` worktree was created.

### Conclusion
1. Missing `.env` was not the first blocker for these runs.
2. First blocker remained workstation-manager action validation contract mismatch.

### Probable contributing cause to later test-stage failures
1. `.env` was intentionally missing for this canary setup.
2. This is a probable cause for verify/test failures once task execution reaches DB-dependent pytest commands.
3. For this specific early stop, the first hard blocker was workstation-manager action validation, before `.env` could be exercised by test execution.

## UX Follow-ups (Do Not Forget)
1. `/op-build` should print clear step progress for pre-loop stages (auto-init, planning, preflight, manager setup) so users do not assume it is stuck.
2. `/op-build` should print per-cycle summary lines in interactive mode (for example: cycle number, active tasks, dispatch decision, health color/state).
3. Nested long-running internal calls (auto `/op-initialize`, planner attempts, manager retries) should emit lightweight progress breadcrumbs to stdout.
4. Keep JSON response contract unchanged for non-TTY usage; these should remain interactive UX prints only.

## Next Canary Focus
1. Re-run with `.env` present to isolate workstation-manager/runtime behavior from environment-missing effects.
2. Confirm cycle advances beyond `0` and dispatch starts.
3. Verify worker activity and assignment observations progress each cycle.
