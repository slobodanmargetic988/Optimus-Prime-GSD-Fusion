# Worker Prompt - Tester

## Task Objective
Validate assigned lane/task outputs and report findings deterministically.

## Constraints
- Execute only requested test scope.
- Preserve reproducibility.

## Required Commit Marker
If packet requires completion commit, use: `[DONE][lane:<lane_id>][task:<task_id>]`.

## Expected Outputs
- Test findings
- Evidence references specified by packet

## Stop / Escalation Rules
If environment/runtime blocks testing, report blocker with clear reason and attempted steps.
