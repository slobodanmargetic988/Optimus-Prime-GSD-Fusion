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

### F-20260302-PLAN-EVIDENCE-001
Status: open

Finding:
1. Fresh canary run entered cycle loop, but all tasks were already `blocked` at cycle 1.
2. Planner-generated `TASK_EVIDENCE.json` stubs for every task contain `summary.result=blocked` with `reason_codes=[awaiting_execution]`.
3. Production-line sync treated those stubs as real blocked outcomes and opened 3 gaps per task (`task_blocked`, `verify_missing`, `uat_missing`), resulting in:
4. `WORK_DISPATCH_PLAN.assignments=[]`
5. `active_workers=0`
6. repeated `dispatch_plan_no_assignments`
7. increasing no-progress watchdog counter.

Observed in:
1. Canary #4 (2026-03-02)

Evidence:
1. `reports/optimus-prime/planning/evidence/TASK-00*/TASK_EVIDENCE.json`
2. `reports/optimus-prime/planning/TASK_EXECUTION_STATE.json`
3. `reports/optimus-prime/planning/WORK_DISPATCH_PLAN.json`
4. `reports/optimus-prime/planning/RUN_PROGRESS_LEDGER.jsonl`
5. `reports/optimus-prime/planning/BUILD_STATE.json`
6. `reports/optimus-prime/WORKER_REGISTRY.json`

Impact:
1. Full dispatch starvation from cycle 1 with no worker execution or workstation creation.

### F-20260302-STATUS-UX-001
Status: open

Finding:
1. During active run with live lock/pid, `op-status` still reports command `status=completed` and `next_action=/op-resume`.
2. `op-report` correctly shows `build=running`, but this split still causes operator confusion in stalled runs.

Observed in:
1. Canary #4 (2026-03-02)

Evidence:
1. `opctl /op-status --repo-root /Users/slobodan/Projects/MyBoard --json-pretty`
2. `opctl /op-report --repo-root /Users/slobodan/Projects/MyBoard --json-pretty`

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
4. Canary #4 (2026-03-02): planner evidence stubs marked all tasks blocked on cycle 1, causing immediate dispatch starvation.
