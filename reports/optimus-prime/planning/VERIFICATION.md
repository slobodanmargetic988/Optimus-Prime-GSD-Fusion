# VERIFICATION

Plan ID: `plan-20260310T232916Z-strategy-tool-v1`

## Required Verify Commands
- `python3 -m pytest`
- `python3 -m pytest tests/e2e/test_strategy_regression_smoke.py -q`
- `python3 -m strategy.cli run --project-root fixtures/sample_project --earth-root fixtures/sample_earth --output-root tmp/strategy-smoke --revision-seed strategy-smoke-seed`

## Phase Exit Rules
- phase-1: every red TDD task must fail for expected reason codes before implementation starts.
- phase-2: implementation tasks across all three lanes must turn green and materialize current strategy outputs plus planner exports.
- phase-3: hardening/review tasks must pass verification, UAT scenarios must be covered, and open gaps must remain at zero.

## Evidence Expectations
- Every task writes progress into `reports/optimus-prime/planning/evidence/<task_id>/TASK_EVIDENCE.json`.
- Missing linked references must be recorded as explicit assumptions in narrative outputs.
- Final runnable smoke must regenerate strategy/current and history artifacts from canonical sample inputs.

## Regression Safety
- Preserve the repo's existing planning baseline signals while adding strategy-specific outputs.
- Protect exact downstream planning-gate wording and strategy recommendation IDs from drift.
