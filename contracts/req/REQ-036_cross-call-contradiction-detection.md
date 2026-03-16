# REQ-036 Cross-Call Contradiction Detection

Status: Implemented  
Requirement ID: `REQ-036`  
Owner surface: `scripts/strategy_llm_pipeline.py`

## Purpose

Strategy must detect contradictions across call outputs before final synthesis.

REQ-036 requires contradiction handling to be explicit:

1. Contradictions are detected from per-claim support vs contradict stances across calls.
2. Each contradiction is either explicitly resolved or marked as an unresolved risk.
3. Final-synthesis readiness is gated by unresolved contradiction count in deterministic output fields.

## Input Contract

Builder:

- `build_req_036_cross_call_contradiction_detection(...) -> dict`

Required anchors:

- `target_project_root`
- `earth_root`
- `output_root`
- `revision_identity`
- `call_outputs[]`

Optional anchors:

- `contradiction_resolutions[]`

`call_outputs[]` rows must include:

- `call_id`
- `call_requirement_id`
- `emitted_claims[]`

`emitted_claims[]` rows must include:

- `claim_id`
- `claim_text`
- `stance` (`support` or `contradict`)
- `evidence_refs[]`

`contradiction_resolutions[]` rows must include:

- `claim_id`
- `resolution_status` (`resolved` or `unresolved`)
- `resolution_summary`
- `resolved_by_call_id` (required when status is `resolved`)
- `evidence_refs[]`

## Output Contract

Top-level required keys:

- `schema_version` (must be `req-036.cross-call-contradiction-detection.v1`)
- `requirement_id` (must be `REQ-036`)
- `cross_call_contradiction_detection`
- `processing_behavior`
- `contradiction_report`
- `context_bundle`
- `call_metadata`

`processing_behavior` required keys:

- `strategy`
- `reasoning_mode`
- `heuristic_summarization_only`
- `contradiction_handling_policy`
- `context_inputs`
- `context_usage`
- `recommendation`

`contradiction_report` required keys:

- `detection_strategy`
- `contradiction_count`
- `resolved_contradictions`
- `unresolved_contradictions`
- `contradictions`
- `open_risks`
- `evidence_refs`

Each row in `contradiction_report.contradictions[]` preserves:

- `claim_id`
- `summary`
- `contradictory_calls[]`
- `resolution_status`
- `resolution`
- `unresolved_risk`
- `required_evidence_refs`

## Contradiction Handling Policy

`processing_behavior.contradiction_handling_policy` is fixed to:

- `explicit-resolution-or-unresolved-risk`

Policy semantics:

- If contradiction has explicit `resolved` entry, `resolution_status` is `resolved` and `unresolved_risk` is `null`.
- Otherwise contradiction remains `unresolved` and must emit `unresolved_risk` with reason code `cross_call_contradiction`.

## Sample Structure

Deterministic fixture:

- `examples/fixtures/cross-call-contradiction-detection.json`

Deterministic sample artifact:

- `strategy/current/samples/REQ-036_cross-call-contradiction-detection.sample.json`
