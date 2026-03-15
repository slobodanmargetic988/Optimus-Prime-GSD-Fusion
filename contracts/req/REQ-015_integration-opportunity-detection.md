# REQ-015 Integration Opportunity Detection

Status: Implemented  
Requirement ID: `REQ-015`

## Scope anchors

This requirement surface is limited to:

- Detecting concrete integration opportunities between the target project and other Earth projects.
- Recording expected interaction contract details for each opportunity.
- Recording dependency side-effect notes for each opportunity.
- Recording unresolved or under-evidenced cross-project ideas as `open_risks` instead of emitting synthetic opportunities.

No net-new packet sections, managers, or orchestration gates are introduced by this contract.

## Interface surface

Implementation file:

- `scripts/strategy_context_sweep.py`

Builder:

- `build_req_015_integration_opportunity_detection(...) -> dict`

Validator:

- `validate_req_015_integration_opportunity_detection(payload) -> list[str]`

## Input contract

The builder expects these anchors:

- `target_project` object with required field:
  - `project_id`
- One or both candidate sources:
  - `integration_candidates[]` rows with required fields:
    - `peer_project_id`
    - `opportunity_summary`
    - `expected_interaction_contract` object:
      - `interaction_type`
      - `producer_component`
      - `consumer_component`
      - `interface`
      - `data_contract`
    - `dependency_side_effect_notes[]` (at least one note)
    - `evidence_refs[]` (at least one evidence row with `artifact_id`, `kind`, `uri`)
  - `broad_sweep_context.cross_project_obligations[]` rows with required fields for opportunity promotion:
    - `target_project_id`
    - `summary`
    - `recommendation_ids[]`
    - `expected_interaction_contract`
    - `dependency_side_effect_notes[]`
    - `earth_sweep_evidence_refs[]`
- Optional support anchors:
  - `recommendations[]` with per-recommendation fields:
    - `recommendation_id`
    - `summary`
    - `rationale`
    - `expected_impact`
    - `risk_level`
  - `evidence_refs[]` Earth-sweep evidence catalog used to resolve artifact IDs referenced in broad-sweep context
  - `research_event_id` for provenance stitching
- `normalized_at_utc` (optional ISO-8601 timestamp)

## Output contract

Top-level required keys:

- `schema_version` (must be `req-015.integration-opportunity-detection.v1`)
- `requirement_id` (must be `REQ-015`)
- `target_project`
- `integration_opportunities`
- `open_risks`
- `source`

`integration_opportunities[]` required keys:

- `integration_opportunity_id`
- `target_project_id`
- `peer_project_id`
- `opportunity_summary`
- `recommendation_id`
- `linked_recommendation_ids[]`
- `recommendation_fields`
  - `summary`
  - `rationale`
  - `expected_impact`
  - `risk_level`
- `expected_interaction_contract`
- `dependency_side_effect_notes[]`
- `evidence_refs[]`
- `provenance.source_fields[]`

`open_risks[]` required keys:

- `open_risk_id`
- `reason_code`
- `risk_level`
- `risk_statement`
- `recommendation_ids[]`
- `evidence_refs[]`
- `provenance.source_fields[]`

`source` required keys:

- `normalized_at_utc`
- `tool`
- `tool_version`
- `context_bundle_sha256`

## Sample structure

Deterministic fixture:

- `examples/fixtures/integration-opportunity-detection.json`

Deterministic sample artifact:

- `strategy/current/samples/REQ-015_integration-opportunity-detection.sample.json`

The structure in `strategy/current/samples/REQ-015_integration-opportunity-detection.sample.json`
is the canonical contract shape for REQ-015.
