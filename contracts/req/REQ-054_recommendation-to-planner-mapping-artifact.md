# REQ-054: Recommendation-to-Planner Mapping Artifact

## Purpose
Define the contract and data-model surface for emitting a deterministic mapping artifact from strategy recommendation IDs to planner task intent handles so planner traceability and downstream audit trails remain citation-ready.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-054):
  - Emit mapping rows from `recommendation_id` to `planner_task_intent_handle`.
  - Preserve recommendation-to-planner traceability refs per emitted mapping row.
  - Emit deterministic downstream audit-trail metadata for each mapping row.
- Out of scope (REQ-054): net-new packet sections, managers, orchestration gates, or requirement behavior outside recommendation-to-planner mapping.

## Interface surface
Builder:
- `build_req_054_recommendation_to_planner_mapping_artifact(payload) -> dict`

Validator:
- `validate_req_054_recommendation_to_planner_mapping_artifact(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
`strategy_artifacts_handoff.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "recommendation_to_planner_mapping_artifact",
  "now_utc": "2026-03-16T09:05:00Z",
  "recommendation_mappings": [
    {
      "recommendation_id": "rec.harden-telemetry-freshness",
      "planner_task_intent_handle": "intent.telemetry-freshness-hardening",
      "planner_task_intent_summary": "Human-facing planner intent summary",
      "planner_lane": "execution",
      "sequence_hint": 1,
      "call_trace_refs": [
        "strategy/current/llm_call_trace.jsonl#call-5-001"
      ],
      "evidence_refs": [
        "reports/runtime/telemetry/freshness-gap-2026-03-15.json"
      ],
      "planner_packet_refs": [
        "reports/optimus-prime/planning/PLAN_PACKETS.json#execution.telemetry-freshness"
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `recommendation_to_planner_mapping_artifact`.
- `recommendation_mappings[]` must be a non-empty list.
- Each `recommendation_mappings[]` row is strict and limited to:
  - `recommendation_id`
  - `planner_task_intent_handle`
  - `planner_task_intent_summary`
  - `planner_lane`
  - `sequence_hint`
  - `call_trace_refs`
  - `evidence_refs`
  - `planner_packet_refs`
- `recommendation_id`, `planner_task_intent_handle`, `planner_task_intent_summary`, and `planner_lane` must be non-empty strings.
- `sequence_hint` must be a positive integer.
- `call_trace_refs[]` and `evidence_refs[]` must each normalize to sorted, unique, non-empty lists.
- `planner_packet_refs[]` is optional and normalizes to a sorted, unique list.
- Duplicate (`recommendation_id`, `planner_task_intent_handle`) pairs are rejected.

## Output contract
REQ-054 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- mapping artifact surface: `recommendation_to_planner_mapping_artifact`
- bounded counts: `totals`

`recommendation_to_planner_mapping_artifact` contains:
- `recommendation_to_task_intent_mappings[]`
- `recommendation_ids[]`
- `planner_task_intent_handles[]`

Each `recommendation_to_task_intent_mappings[]` row includes:
- `mapping_id`
- `recommendation_id`
- `planner_task_intent_handle`
- `planner_task_intent_summary`
- `planner_lane`
- `sequence_hint`
- `traceability_refs[]`
- `downstream_audit_trail`

`downstream_audit_trail` includes:
- `source_call_trace_refs[]`
- `source_evidence_refs[]`
- `source_packet_refs[]`
- `emitted_at_utc`
- `emitted_by_requirement_id`

`totals` includes:
- `input_rows`
- `mapping_rows`
- `unique_recommendation_ids`
- `unique_planner_task_intent_handles`
- `traceability_refs`

Behavior anchors:
- Mapping rows are sorted by `sequence_hint`, then `planner_task_intent_handle`, then `recommendation_id`.
- `traceability_refs[]` is the sorted unique union of `source_call_trace_refs[]`, `source_evidence_refs[]`, and `source_packet_refs[]`.
- `mapping_id` is deterministic per (`recommendation_id`, `planner_task_intent_handle`, `planner_lane`, `sequence_hint`).
- `recommendation_ids[]` and `planner_task_intent_handles[]` must match unique values present in emitted mapping rows.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/recommendation-to-planner-mapping-artifact.json`
- Contract tests: `tests/contracts/test_recommendation-to-planner-mapping-artifact.py`
- Output sample: `strategy/current/samples/REQ-054_recommendation-to-planner-mapping-artifact.sample.json`

The structure in `strategy/current/samples/REQ-054_recommendation-to-planner-mapping-artifact.sample.json`
is the canonical contract shape for REQ-054 and documents:
- `recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings`
- `recommendation_to_planner_mapping_artifact.recommendation_ids`
- `recommendation_to_planner_mapping_artifact.planner_task_intent_handles`
- `recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings[].downstream_audit_trail`
- `totals`
