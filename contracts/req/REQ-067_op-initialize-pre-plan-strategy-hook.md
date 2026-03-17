# REQ-067: op-initialize Pre-Plan Strategy Hook

## Purpose
Define the contract and data-model surface for injecting current strategy context before `/op-plan` runs inside `/op-initialize`, with configurable strictness and deterministic failure handling.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-067):
  - Emit a deterministic pre-plan hook payload for `/op-initialize`.
  - Bind planner readiness to current strategy context presence.
  - Support strictness and deterministic failure mode configuration (`fail_closed` / `fail_open`).
  - Keep readiness decisions deterministic (`allow_planning`, `allow_planning_with_warning`, `block_planning`).
- Out of scope (REQ-067): net-new packet sections, managers, or orchestration gates beyond this pre-plan hook contract.

## Interface surface
Builder:
- `build_req_067_op_initialize_pre_plan_strategy_hook(payload) -> dict`

Validator:
- `validate_req_067_op_initialize_pre_plan_strategy_hook(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-067 expects:

```json
{
  "analysis_type": "op_initialize_pre_plan_strategy_hook",
  "now_utc": "2026-03-16T11:40:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "hook_config": {
    "strictness": "strict",
    "deterministic_failure_mode": "fail_closed"
  },
  "strategy_context": {
    "strategy_revision_id": "strategy-rev-20260316-113000",
    "strategy_artifact_refs": [
      "strategy/current/STRATEGY.json"
    ],
    "recommendation_ids": [
      "rec.pre-plan-sequence-alignment"
    ],
    "constraint_ids": [
      "guardrail-task-floor"
    ],
    "strategy_is_current": true
  }
}
```

Rules:
- `analysis_type` must be `op_initialize_pre_plan_strategy_hook` when provided.
- `target_project.project_root` must be an absolute path.
- `hook_config.strictness` supports `strict` and `advisory`.
- `hook_config.deterministic_failure_mode` supports `fail_closed` and `fail_open`.
- `strategy_context.strategy_revision_id` is required.
- `strategy_context.strategy_artifact_refs[]` carries planner-ingested strategy artifacts.
- Missing context fields are derived deterministically from:
  - empty `strategy_artifact_refs[]`
  - `strategy_is_current = false`

## Output contract
REQ-067 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- hook contract: `pre_plan_strategy_hook`
- bounded counts: `totals`

`pre_plan_strategy_hook` contains:
- `hook_stage`
- `strictness`
- `strategy_context`
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
- If context is ready: `decision = allow_planning`, failure status is `not_triggered`, and `next_command = /op-plan`.
- If context is missing and mode is `fail_closed`: `decision = block_planning` with reason `pre_plan_strategy_context_missing`.
- If context is missing and mode is `fail_open`: `decision = allow_planning_with_warning` with reason `pre_plan_strategy_context_missing_soft`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/op-initialize-pre-plan-strategy-hook.json`
- Contract tests: `tests/contracts/test_op-initialize-pre-plan-strategy-hook.py`
- Output sample: `strategy/current/samples/REQ-067_op-initialize-pre-plan-strategy-hook.sample.json`

The structure in `strategy/current/samples/REQ-067_op-initialize-pre-plan-strategy-hook.sample.json`
is the canonical contract shape for REQ-067 and documents:
- `pre_plan_strategy_hook.strategy_context`
- `pre_plan_strategy_hook.deterministic_failure`
- `pre_plan_strategy_hook.planner_readiness`
- `totals`
