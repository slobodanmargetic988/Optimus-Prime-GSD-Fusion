# Lane B Canary Findings Log

Updated: 2026-03-02

## Purpose
Track real canary-run findings with clear status:
1. Active findings that still need patches.
2. Resolved findings archived to avoid re-triaging already-fixed issues.

## Active Findings (Needs Patch)

### F-20260302-RESUME-001
Status: open

Finding:
1. `/op-resume` can resume loop execution from a blocked state, but in the specific case of a task blocked by exhausted workstation retries it does not autonomously unfreeze/requeue that task.
2. Resulting behavior is likely continued no-progress cycles (`dispatch_plan_no_assignments`) until watchdog triggers, unless manual task/gap reset or fresh initialize/build is done.

Observed in:
1. Canary #3 (2026-03-02)

Evidence:
1. `reports/optimus-prime/planning/TASK_EXECUTION_STATE.json`
2. `reports/optimus-prime/planning/WORK_DISPATCH_PLAN.json`
3. `reports/optimus-prime/planning/RUN_PROGRESS_LEDGER.jsonl`
4. `reports/optimus-prime/planning/NO_PROGRESS_WATCHDOG_STATE.json`

Follow-up decision needed:
1. Define whether resume should include deterministic unfreeze/retry policy for specific exhausted manager-gap categories.

## UX Follow-ups (Still Open)
1. Keep improving console visibility for long-running loops:
2. Ensure watchdog state/proximity is always obvious from interactive output without extra artifact digging.

## Resolved Findings Archive

### R-20260301-WS-CONTRACT-001
Status: resolved

Observed:
1. Canary #1 and Canary #2 (2026-03-01)

What was wrong:
1. Workstation-manager action validation mismatch (`task_id`/`lane_id` normalization and `prereq_policy` prompt/validator mismatch) caused repeated retry loops at cycle `0`.

Resolution summary:
1. Runtime action validation and prompt contracts were aligned.
2. Cycle moved past pre-dispatch stall behavior after patch set.

### R-20260302-WS-SKILL-NAMING-001
Status: resolved (patched + reinstalled)

Observed:
1. Canary #3 (2026-03-02)

What was wrong:
1. Installed `prepare_workstation.py` enforced legacy names (`workstation-1..10`) while manager/runtime required slot-specific names (`workstation-dev/test/review-*`).

Resolution summary:
1. `workstation-preparation` now accepts both legacy and manager slot naming patterns.
2. Added tests for accepted/rejected worktree naming.
3. Verified updated skill is included in bundle and installed under `~/.optimus-prime/install/current/skills/workstation-preparation/scripts/prepare_workstation.py`.

## Historical Canary Summary
1. Canary #1 (2026-03-01): early workstation-manager contract stall, stopped by operator.
2. Canary #2 (2026-03-01): same blocker confirmed with `.env` restored, stopped by operator.
3. Canary #3 (2026-03-02): cycle progressed, workstation script naming mismatch blocked `TASK-001`, then no-assignment/no-progress loop.
