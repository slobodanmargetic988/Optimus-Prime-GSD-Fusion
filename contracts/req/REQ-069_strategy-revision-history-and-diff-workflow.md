# REQ-069: Strategy Revision History and Diff Workflow

## Purpose
Define the contract and data-model surface for deterministic strategy revision history snapshots and diff workflow governance before planning execution.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-069):
  - Emit deterministic revision-history + diff-workflow payloads.
  - Preserve revision snapshot refs and diff artifact refs across reruns.
  - Provide planner readiness gating with deterministic fail-closed/fail-open behavior.
  - Keep failure-path reason codes and evidence refs stable for replay diagnostics.
- Out of scope (REQ-069): net-new orchestration managers, runtime switching policy, or non-deterministic review rules.

## Interface surface
Builder:
- `build_req_069_strategy_revision_history_and_diff_workflow(payload) -> dict`

Validator:
- `validate_req_069_strategy_revision_history_and_diff_workflow(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-069 expects:

```json
{
  "analysis_type": "strategy_revision_history_and_diff_workflow",
  "now_utc": "2026-03-17T08:15:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "workflow_config": {
    "strictness": "strict",
    "deterministic_failure_mode": "fail_closed"
  },
  "revision_history": {
    "current_revision_id": "strategy-rev-20260317-081500",
    "previous_revision_id": "strategy-rev-20260316-190000",
    "revision_snapshot_refs": [
      "strategy/current/STRATEGY.json"
    ],
    "diff_artifact_refs": [
      "strategy/current/DIFF_SUMMARY.json"
    ],
    "recommendation_ids": [
      "rec.harden-diff-governance"
    ],
    "constraint_ids": [
      "guardrail-deterministic-diff-order"
    ],
    "strategy_is_current": true,
    "semantic_drift_detected": false
  }
}
```

Rules:
- `analysis_type` must be `strategy_revision_history_and_diff_workflow` when provided.
- `target_project.project_root` must be an absolute path.
- `workflow_config.strictness` supports `strict` and `advisory`.
- `workflow_config.deterministic_failure_mode` supports `fail_closed` and `fail_open`.
- `revision_history.current_revision_id` is required.
- `revision_history.revision_snapshot_refs[]` and `revision_history.diff_artifact_refs[]` are deterministic context anchors.
- Missing context fields are derived deterministically from:
  - empty `revision_snapshot_refs[]`
  - empty `diff_artifact_refs[]`
  - `strategy_is_current = false`
  - `semantic_drift_detected = true`

## Output contract
REQ-069 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- workflow contract: `strategy_revision_history_and_diff_workflow`
- bounded counts: `totals`

`strategy_revision_history_and_diff_workflow` contains:
- `hook_stage`
- `strictness`
- `revision_history`
- `deterministic_failure`
- `planner_readiness`

`deterministic_failure` contains:
- `mode`
- `status`
- `reason_code`
- `planner_action`

`planner_readiness` contains:
- `hook_applied`
- `context_ready`
- `missing_context_fields[]`
- `decision`
- `gating_reason_codes[]`
- `next_command`

Decision behavior:
- If context is ready: `decision = allow_diff_review`, failure status is `not_triggered`, and `next_command = /op-plan`.
- If context is missing and mode is `fail_closed`: `decision = block_diff_review` with reason `strategy_revision_diff_context_missing`.
- If context is missing and mode is `fail_open`: `decision = allow_diff_review_with_warning` with reason `strategy_revision_diff_context_missing_soft`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/strategy-revision-history-and-diff-workflow.json`
- Contract tests: `tests/contracts/test_strategy-revision-history-and-diff-workflow.py`
- Output sample: `strategy/current/samples/REQ-069_strategy-revision-history-and-diff-workflow.sample.json`

The structure in `strategy/current/samples/REQ-069_strategy-revision-history-and-diff-workflow.sample.json`
is the canonical contract shape for REQ-069 and documents:
- `strategy_revision_history_and_diff_workflow.revision_history`
- `strategy_revision_history_and_diff_workflow.deterministic_failure`
- `strategy_revision_history_and_diff_workflow.planner_readiness`
- `totals`
