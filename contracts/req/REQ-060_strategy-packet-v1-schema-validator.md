# REQ-060: Strategy Packet v1 Schema Validator

## Purpose
Define the contract and data-model surface for validating `strategy_packet.v1` payloads before handoff so schema failures and canonical ID violations return deterministic reason codes and actionable diagnostics.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-060):
  - Validate `strategy_packet.v1` payloads against `contracts/strategy_packet.v1.schema.json`.
  - Preserve deterministic machine-readable diagnostics for schema and canonical ID failures.
  - Preserve planner handoff coverage checks tied to embedded `recommendation_to_planner_mapping_artifact`.
- Out of scope (REQ-060): net-new packet sections, managers, orchestration flows, or non-validator gates outside the current packet contract.

## Interface surface
Builder:
- `build_req_060_strategy_packet_v1_schema_validator(payload) -> dict`

Validator:
- `validate_req_060_strategy_packet_v1_schema_validator(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
`strategy_artifacts_handoff.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "strategy_packet_v1_schema_validator",
  "now_utc": "2026-03-16T10:30:00Z",
  "strategy_packet_path": "op-tools/strategy/examples/strategy_packet.sample.v1.json",
  "schema_path": "contracts/strategy_packet.v1.schema.json"
}
```

Rules:
- `analysis_type` must be `strategy_packet_v1_schema_validator`.
- `now_utc` must be a non-empty UTC timestamp string; it is copied into `checked_at_utc` for deterministic outputs.
- Provide exactly one of:
  - `strategy_packet`
  - `strategy_packet_path`
- Provide at most one of:
  - `schema`
  - `schema_path`
- When `schema_path` is omitted, the validator loads `contracts/strategy_packet.v1.schema.json`.
- `strategy_packet` may be supplied inline as any JSON value; non-object roots return `packet_payload_not_object`.
- Canonical ID checks are enforced by the packet schema for:
  - `identity.project_id`
  - `identity.run_id`
  - `identity.event_id`
  - `identity.era_id`
  - `identity.plan_id`
  - `recommendations[].recommendation_id`
  - `recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings[].mapping_id`
  - `recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings[].planner_task_intent_handle`

## Output contract
REQ-060 output payload contains:
- `ok`
- `checked_at_utc`
- `verdict`
- `planner_consumability`
- `reason_codes`
- `diagnostic_count`
- `summary`
- `diagnostics`

Output behavior:
- `ok = true` means the packet passed schema validation and planner handoff coverage checks.
- `ok = false` means the packet is blocked from handoff.
- `verdict` is `pass` or `fail`.
- `planner_consumability` is `planner_ready` or `planner_blocked`.
- `reason_codes[]` is the sorted unique set of `diagnostics[].reason_code`.
- `diagnostic_count` must equal `len(diagnostics)`.

Each `diagnostics[]` row includes:
- `severity`
- `reason_code`
- `field_path`
- `message`

Deterministic reason-code families:
- Schema validation:
  - `schema_additional_property`
  - `schema_const_mismatch`
  - `schema_enum_violation`
  - `schema_min_items_violation`
  - `schema_min_length_violation`
  - `schema_pattern_mismatch`
  - `schema_required_field_missing`
  - `schema_type_mismatch`
- Packet root:
  - `packet_payload_not_object`
- Embedded REQ-054 coverage checks:
  - `req_054_contract_violation`
  - `mapping_references_unknown_packet_recommendation`
  - `packet_recommendation_missing_mapping`
  - `mapping_artifact_recommendation_ids_mismatch`

Handoff behavior:
- Schema failures surface exact `field_path` values such as `identity.project_id` and preserve the validator message for operator action.
- `recommendations[].recommendation_id` must remain fully covered by `recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings[]`.
- Mapping rows must not reference recommendation IDs absent from `recommendations[]`.

## Sample structure
Deterministic fixture:
- `examples/fixtures/strategy-packet-v1-schema-validator.json`

Deterministic sample artifact:
- `strategy/current/samples/REQ-060_strategy-packet-v1-schema-validator.sample.json`

The structure in `strategy/current/samples/REQ-060_strategy-packet-v1-schema-validator.sample.json`
is the canonical contract shape for REQ-060.
