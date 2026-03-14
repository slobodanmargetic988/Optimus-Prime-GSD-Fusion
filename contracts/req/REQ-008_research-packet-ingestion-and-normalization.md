# REQ-008 Research Packet Ingestion And Normalization

Status: Implemented  
Requirement ID: `REQ-008`

## Scope anchors

This requirement surface is limited to:

- Ingesting a research packet payload into strategy context processing.
- Normalizing deterministic strategy context arrays:
  - `assumptions`
  - `unknowns`
  - `risk_evidence`
  - `cross_project_context`
  - `open_risks`
- Preserving research provenance and linking it into recommendation rationale references.
- Cross-project obligations require Earth-sweep evidence refs; missing evidence is normalized into `open_risks` instead of implied obligations.

No net-new packet sections, managers, or orchestration gates are introduced by this contract.

## Interface surface

Implementation file:

- `scripts/strategy_context_sweep.py`

Builder:

- `build_req_008_research_packet_ingestion_and_normalization(...) -> dict`

Validator:

- `validate_req_008_research_packet_ingestion_and_normalization(payload) -> list[str]`

CLI:

```bash
python3 scripts/strategy_context_sweep.py \
  --input-json examples/fixtures/research-packet-ingestion-and-normalization.json \
  --output-json strategy/current/samples/REQ-008_research-packet-ingestion-and-normalization.sample.json \
  --json-pretty
```

## Input contract

The builder expects these anchors:

- `research_packet`: object containing research packet identity/topics/open questions/evidence refs.
- `recommendation_ids` or `recommendations`: recommendation IDs and/or recommendation metadata rows.
- `recommendations` rows include `recommendation_id`, `summary`, `rationale`, `expected_impact`, `risk_level`.
- `recommendation_topic_map` (optional): map from recommendation ID to contributing `topic_id` list.
- `broad_sweep_context` (optional): explicit broad-sweep input for cross-project obligations and unresolved ideas. If omitted, context aliases under `research_packet.context` are consumed.
- `normalized_at_utc` (optional): ISO-8601 timestamp for deterministic output metadata.

## Output contract

Top-level required keys:

- `schema_version` (must be `req-008.research-packet-ingestion-and-normalization.v1`)
- `requirement_id` (must be `REQ-008`)
- `research_packet_identity`
- `strategy_context`
- `recommendation_rationale_provenance`
- `source`

`strategy_context` required arrays:

- `assumptions[]`
  - `assumption_id`
  - `topic_id`
  - `statement`
  - `provenance.research_event_id`
  - `provenance.source_field`
- `unknowns[]`
  - `unknown_id`
  - `question`
  - `provenance.research_event_id`
  - `provenance.source_field`
- `risk_evidence[]`
  - `risk_evidence_id`
  - `topic_id`
  - `risk_level`
  - `risk_statement`
  - `evidence_refs[]` (`artifact_id`, `kind`, `uri`, optional `notes`)
  - `provenance.research_event_id`
  - `provenance.source_fields[]`
- `cross_project_context[]`
  - `cross_project_context_id`
  - `target_project_id`
  - `summary`
  - `evidence_refs[]` (`artifact_id`, `kind`, `uri`, optional `notes`)
  - `provenance.research_event_id`
  - `provenance.source_fields[]`
- `open_risks[]`
  - `open_risk_id`
  - `risk_level`
  - `risk_statement`
  - `target_project_id` (optional)
  - `evidence_refs[]` (`artifact_id`, `kind`, `uri`, optional `notes`)
  - `provenance.research_event_id`
  - `provenance.source_fields[]`

`recommendation_rationale_provenance[]` required keys:

- `recommendation_id`
- `rationale_field` (fixed `rationale`)
- `linked_assumption_ids[]`
- `linked_unknown_ids[]`
- `linked_risk_evidence_ids[]`
- `linked_cross_project_context_ids[]`
- `linked_open_risk_ids[]`
- `recommendation_fields.summary`
- `recommendation_fields.rationale`
- `recommendation_fields.expected_impact`
- `recommendation_fields.risk_level`
- `research_provenance.research_packet_event_id`
- `research_provenance.source_schema_version`
- `research_provenance.linked_topic_ids[]`
- `research_provenance.context_mission_refs[]`
- `research_provenance.context_scope_refs[]`
- `research_provenance.context_strategy_ref` (optional)
- `provenance_refs[]` (mirrors research evidence refs)

## Sample structure

Deterministic fixture:

- `examples/fixtures/research-packet-ingestion-and-normalization.json`

Deterministic sample artifact:

- `strategy/current/samples/REQ-008_research-packet-ingestion-and-normalization.sample.json`

The structure in `strategy/current/samples/REQ-008_research-packet-ingestion-and-normalization.sample.json`
is the canonical contract shape for REQ-008.
