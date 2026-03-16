# REQ-065 Planner Consumability Validator

## Purpose
`REQ-065` defines a deterministic validator artifact that confirms strategy outputs are directly consumable by `op-plan` and `op-initialize` without manual transforms.

The implementation surface is in `scripts/strategy_artifacts_handoff.py`:
- `build_planner_consumability_validator(payload: dict[str, Any]) -> dict[str, Any]`
- `write_planner_consumability_validator(payload: dict[str, Any], output_path: str | Path | None = None) -> dict[str, Any]`

## Input Contract
The validator consumes a JSON object with these contract anchors:

1. Required files
- `required_files: list[str]`
- `available_files: list[str]`
- Pass condition: every required file is present in available files.

2. Required keys
- `required_keys: list[str]` using dotted / indexed paths (for example `recommendations[0].recommendation_id`).
- `strategy_output: object` (fallback: `strategy_packet`).
- Pass condition: each required key path resolves and the resolved value is non-empty.

3. Recommendation mapping completeness
- `strategy_output.recommendations` (fallbacks supported).
- `recommendation_mapping` entries keyed or listed by `recommendation_id`.
- Required mapping fields per recommendation:
  - `op_plan_ref`
  - `op_initialize_ref`
- Pass condition: every recommendation has one mapping entry and both required mapping fields are populated.

Fixture input used for executable contract checks:
- `examples/fixtures/planner-consumability-validator.json`

## Output Contract
The validator returns:
- `artifact_type: "planner_consumability_validator"`
- `requirement_id: "REQ-065"`
- `validator_version: "1.0"`
- `planner_targets: ["op-plan", "op-initialize"]`
- `checks.required_files`
- `checks.required_keys`
- `checks.recommendation_mapping`
- `gate_verdict`

`gate_verdict.verdict` is `"pass"` only when all three anchored checks pass.

## Sample Artifact Structure
The canonical sample artifact is:
- `strategy/current/samples/REQ-065_planner-consumability-validator.sample.json`

Its structure is:

```json
{
  "artifact_type": "planner_consumability_validator",
  "checks": {
    "recommendation_mapping": {
      "incomplete_mappings": [],
      "mapped_recommendation_ids": ["rec.dispatch-quality-first"],
      "missing_mapping_ids": [],
      "pass": true,
      "recommendation_ids": ["rec.dispatch-quality-first"],
      "recommendations_missing_id": [],
      "required_mapping_fields": ["op_plan_ref", "op_initialize_ref"]
    },
    "required_files": {
      "available_files": [
        "contracts/req/REQ-065_planner-consumability-validator.md",
        "strategy/current/samples/REQ-065_planner-consumability-validator.sample.json",
        "strategy/current/strategy_packet.v1.json"
      ],
      "missing_required_files": [],
      "pass": true,
      "required_files": [
        "strategy/current/samples/REQ-065_planner-consumability-validator.sample.json",
        "strategy/current/strategy_packet.v1.json"
      ]
    },
    "required_keys": {
      "empty_required_keys": [],
      "missing_required_keys": [],
      "pass": true,
      "required_keys": [
        "identity.project_id",
        "recommendation_mapping[0].op_initialize_ref",
        "recommendation_mapping[0].op_plan_ref",
        "recommendations[0].recommendation_id",
        "strategy.summary"
      ]
    }
  },
  "gate_verdict": {
    "blocking_reasons": [],
    "ready_for_planner_consumption": true,
    "verdict": "pass",
    "warning_reasons": []
  },
  "planner_targets": ["op-plan", "op-initialize"],
  "requirement_id": "REQ-065",
  "validator_version": "1.0"
}
```
