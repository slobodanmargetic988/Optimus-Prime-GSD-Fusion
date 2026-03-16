# REQ-046: Final Strategy Synthesis Composer

## Purpose
Define the contract and data-model surface for composing the final recommendation set from validated multi-call outputs into coherent strategy packet inputs while preserving call-trace lineage for every finalized recommendation.

## Scope anchors
- Surface in scope: `scripts/strategy_llm_pipeline.py`.
- In scope (REQ-046):
  - Compose final recommendations from validated multi-call recommendation outputs.
  - Group finalized recommendations into deterministic `strategy_packet_inputs`.
  - Preserve ordered call-trace lineage for each finalized recommendation.
  - Defer recommendations with conflicting packet routing instead of emitting ambiguous packet inputs.
- Out of scope (REQ-046): net-new packet sections, managers, orchestration gates, or recommendation behaviors outside final synthesis composition.

## Interface surface
Builder:
- `build_req_046_final_strategy_synthesis_composer(payload) -> dict`

Validator:
- `validate_req_046_final_strategy_synthesis_composer(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_llm_pipeline.py --input-json <path|->`

## Input contract
`strategy_llm_pipeline.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "final_strategy_synthesis_composer",
  "now_utc": "2026-03-16T08:45:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "validated_call_outputs": [
    {
      "requirement_id": "REQ-027",
      "call_id": "call-2",
      "call_status": "validated",
      "call_trace": {
        "trace_id": "trace-call-2-001",
        "trace_ref": "strategy/current/llm_call_trace.jsonl#call-2-001",
        "artifact_ref": "strategy/current/llm_call_trace_artifacts/req-027/call-2/trace-call-2-001.json",
        "checked_at_utc": "2026-03-16T08:10:00Z"
      },
      "recommendations": [
        {
          "recommendation_id": "rec.align-earth-runtime-canary",
          "summary": "Human-facing recommendation summary",
          "rationale": "Why this recommendation survives validated multi-call synthesis.",
          "packet_kind": "cross-project",
          "peer_project_id": "earth-core-runtime",
          "lane": "coordination",
          "sequence_hint": 2,
          "priority": "high",
          "evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
          ]
        }
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `final_strategy_synthesis_composer`.
- `target_project.project_id` must be non-empty.
- `target_project.project_root` must normalize to an absolute path.
- `validated_call_outputs[]` must be a non-empty list.
- Each `validated_call_outputs[]` row is strict and limited to:
  - `requirement_id`
  - `call_id`
  - `call_status`
  - `call_trace`
  - `recommendations`
- `call_status` must be `validated`.
- `call_trace` is required for every validated call and must include:
  - `trace_id`
  - `trace_ref`
  - `artifact_ref`
  - `checked_at_utc`
- `call_trace.trace_id` must be unique across the input set.
- Each `recommendations[]` row is strict and limited to:
  - `recommendation_id`
  - `summary`
  - `rationale`
  - `packet_kind`
  - `peer_project_id`
  - `lane`
  - `sequence_hint`
  - `priority`
  - `evidence_refs`
- `packet_kind` must be `target-project` or `cross-project`.
- `peer_project_id` is required for `cross-project` recommendations and must be empty for `target-project`.
- `sequence_hint` must be a positive integer.
- `priority` must be `high`, `medium`, or `low`.
- `evidence_refs[]` must normalize to a sorted unique non-empty list.
- Duplicate `recommendation_id` values inside a single validated call are rejected.

## Output contract
REQ-046 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- synthesis target: `target_project`
- final synthesis surface: `final_strategy_synthesis`
- bounded counts: `totals`

`final_strategy_synthesis` contains:
- `final_recommendations[]`
- `deferred_recommendations[]`
- `strategy_packet_inputs[]`

Each `final_recommendations[]` row includes:
- `recommendation_id`
- `summary`
- `rationale`
- `packet_kind`
- `peer_project_id`
- `lane`
- `sequence_hint`
- `priority`
- `evidence_refs[]`
- `call_trace_lineage[]`
- `contributing_call_ids[]`
- `contributing_requirement_ids[]`
- `supporting_call_count`
- `strategy_packet_input_id`

Each `call_trace_lineage[]` row includes:
- `call_id`
- `requirement_id`
- `trace_id`
- `trace_ref`
- `artifact_ref`
- `checked_at_utc`

Each `strategy_packet_inputs[]` row includes:
- `packet_input_id`
- `packet_kind`
- `target_project_id`
- `peer_project_id`
- `lane`
- `recommendation_ids[]`
- `recommendation_count`
- `earliest_sequence_hint`
- `evidence_refs[]`

Each `deferred_recommendations[]` row includes:
- `recommendation_id`
- `summary`
- `deferred_reason_code`
- `packet_kind_candidates[]`
- `peer_project_candidates[]`
- `evidence_refs[]`
- `call_trace_lineage[]`
- `contributing_call_ids[]`

Synthesis behavior:
- Recommendations are grouped by `recommendation_id` across validated calls.
- Finalized recommendations preserve every contributing `call_trace` row in sorted `call_trace_lineage[]`.
- `strategy_packet_inputs[]` are grouped by `packet_kind + peer_project_id + lane`.
- When packet routing conflicts across contributing calls, the recommendation is emitted in `deferred_recommendations[]` with `deferred_reason_code = conflicting_packet_routing`.
- Only finalized recommendations contribute to `strategy_packet_inputs[]`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/final-strategy-synthesis-composer.json`
- Contract tests: `tests/contracts/test_final-strategy-synthesis-composer.py`
- Output sample: `strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json`

The structure in `strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json`
is the canonical contract shape for REQ-046 and documents:
- `final_strategy_synthesis.final_recommendations`
- `final_strategy_synthesis.deferred_recommendations`
- `final_strategy_synthesis.strategy_packet_inputs`
- `final_strategy_synthesis.final_recommendations[].call_trace_lineage`
- `totals`
