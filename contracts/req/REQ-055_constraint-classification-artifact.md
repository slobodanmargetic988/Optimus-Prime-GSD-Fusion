# REQ-055: Constraint Classification Artifact

## Purpose
Define the contract and data-model surface for emitting explicit hard, soft, and speculative constraint artifacts so planner policy logic can disambiguate mandatory guardrails from optional guidance.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-055):
  - Normalize strategy constraints into explicit `hard_constraints`, `soft_constraints`, and `speculative_constraints`.
  - Emit planner-policy IDs for mandatory guardrails and optional guidance.
  - Keep classification output deterministic and bounded to this artifact.
- Out of scope (REQ-055): net-new packet sections, managers, orchestration gates, or policy systems outside this classification artifact.

## Interface surface
Builder:
- `build_req_055_constraint_classification_artifact(payload) -> dict`

Validator:
- `validate_req_055_constraint_classification_artifact(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-055 expects:

```json
{
  "analysis_type": "constraint_classification_artifact",
  "now_utc": "2026-03-16T09:05:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "constraints": [
    {
      "constraint_id": "guardrail-task-floor",
      "statement": "Before build starts, planner must output at least 400 tasks.",
      "classification": "hard",
      "rationale": "Why this constraint classification applies.",
      "evidence_refs": [
        "scope.md#mandatory-planning-gate"
      ],
      "source_refs": [
        "scope.md#mandatory-planning-gate"
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `constraint_classification_artifact` when provided.
- `target_project.project_root` must be an absolute path.
- `constraints[]` must contain at least one row.
- Supported classifications are strictly `hard`, `soft`, and `speculative`.
- `constraint_id` values must be unique across the input set.
- Every constraint row must include non-empty `source_refs[]` for traceability.

## Output contract
REQ-055 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- classified artifact: `constraint_classification`
- bounded counts: `totals`

`constraint_classification` contains:
- `hard_constraints[]`
- `soft_constraints[]`
- `speculative_constraints[]`
- `planner_policy`

Each constraint row includes:
- `constraint_id`
- `statement`
- `classification`
- `rationale`
- `evidence_refs[]`
- `source_refs[]`
- `policy_role`

`planner_policy` includes:
- `hard_constraint_ids[]`
- `soft_constraint_ids[]`
- `speculative_constraint_ids[]`
- `mandatory_guardrail_ids[]`
- `optional_guidance_ids[]`

Classification behavior:
- `hard` constraints emit with `policy_role = mandatory_guardrail` and populate `mandatory_guardrail_ids`.
- `soft` and `speculative` constraints emit with `policy_role = optional_guidance` and populate `optional_guidance_ids`.
- Planner-policy ID arrays must stay aligned with the concrete classified rows.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/constraint-classification-artifact.json`
- Contract tests: `tests/contracts/test_constraint-classification-artifact.py`
- Output sample: `strategy/current/samples/REQ-055_constraint-classification-artifact.sample.json`

The structure in `strategy/current/samples/REQ-055_constraint-classification-artifact.sample.json`
is the canonical contract shape for REQ-055 and documents:
- `constraint_classification.hard_constraints`
- `constraint_classification.soft_constraints`
- `constraint_classification.speculative_constraints`
- `constraint_classification.planner_policy`
- `totals`
