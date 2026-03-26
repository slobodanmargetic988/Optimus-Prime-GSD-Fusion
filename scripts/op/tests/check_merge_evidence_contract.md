# Merge Evidence Checker Contract

`scripts/op/planner/check_merge_evidence.py` validates lane merge evidence from:

- `reports/optimus-prime/planning/DONE_TASKS_REGISTRY.json`
- each task's referenced `MERGE_VALIDATION.json`

Default required tasks are:

- `TASK-003`
- `TASK-006`
- `TASK-009`

Pass criteria per task:

- task has a `merged_tasks[]` row in `DONE_TASKS_REGISTRY.json`
- `branch` matches `RAB-BASE` (or `--expected-branch`)
- `verification_passed=true`
- `verification_ref` exists and points to readable `MERGE_VALIDATION.json`
- `MERGE_VALIDATION.ok=true`
- `MERGE_VALIDATION.merge_proof_passed=true`

Failure behavior:

- deterministic timestamped terminal output (`PASS`/`FAIL` lines)
- non-zero exit code on any blocking issue

Future lane merge tasks can be checked by adding `--task-id` arguments.
