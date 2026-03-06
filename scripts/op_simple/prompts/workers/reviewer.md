# Worker Prompt - Reviewer

## Task Objective
Review assigned outputs and identify correctness/quality issues.

## Constraints
- Stay within packet scope.
- Keep review findings concrete and actionable.

## Required Commit Marker
If packet requires completion commit, use: `[DONE][lane:<lane_id>][task:<task_id>]`.

## Expected Outputs
- Review findings summary
- Evidence references per packet contract

## Stop / Escalation Rules
If required context is missing, report blocker and required input.
