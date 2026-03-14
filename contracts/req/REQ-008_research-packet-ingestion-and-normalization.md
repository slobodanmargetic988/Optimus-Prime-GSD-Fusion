# REQ-008 Research Packet Ingestion And Normalization

Status: Implemented  
Requirement ID: `REQ-008`

## Scope anchors

This requirement surface is limited to:

- Ingesting a research packet payload into strategy context processing.
- Normalizing exactly these context arrays:
  - `assumptions`
  - `unknowns`
  - `risk_evidence`
- Preserving research provenance and linking it into recommendation rationale references.

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
- `recommendation_ids`: non-empty array of recommendation IDs whose rationale fields must keep research provenance links.
- `recommendation_topic_map` (optional): map from recommendation ID to contributing `topic_id` list.
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

`recommendation_rationale_provenance[]` required keys:

- `recommendation_id`
- `rationale_field` (fixed `rationale`)
- `linked_assumption_ids[]`
- `linked_unknown_ids[]`
- `linked_risk_evidence_ids[]`
- `research_provenance.research_packet_event_id`
- `research_provenance.source_schema_version`
- `research_provenance.linked_topic_ids[]`
- `provenance_refs[]` (mirrors research evidence refs)

## Sample structure

Deterministic fixture:

- `examples/fixtures/research-packet-ingestion-and-normalization.json`

Deterministic sample artifact:

- `strategy/current/samples/REQ-008_research-packet-ingestion-and-normalization.sample.json`

The structure in `strategy/current/samples/REQ-008_research-packet-ingestion-and-normalization.sample.json`
is the canonical contract shape for REQ-008.
