# REQ-038 Recommendation Priority Calibration

Status: Implemented  
Requirement ID: `REQ-038`

## Scope anchors

This requirement surface is limited to:

- Calibrating recommendation priority from three signals: ecosystem impact, feasibility, and urgency.
- Producing deterministic priority ranking from weighted signal scores.
- Emitting transparent per-signal scoring contributors for recommendation auditability.

Out of scope:

- Net-new packet sections, managers, orchestration gates, or unrelated strategy behaviors.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_038_recommendation_priority_calibration(...) -> dict`

Validator:

- `validate_req_038_recommendation_priority_calibration(payload) -> list[str]`

CLI:

- `python3 scripts/strategy_llm_pipeline.py --input-json <path|->`

## Input contract

The builder expects:

- `recommendations[]` (required, non-empty)
- Optional environment metadata:
  - `target_project_root`
  - `earth_root`
  - `output_root`
  - `revision_identity`
  - `calibrated_at`
- Optional `priority_weights` object with required keys:
  - `ecosystem_impact`
  - `feasibility`
  - `urgency`

Each `recommendations[]` row must include:

- `recommendation_id`
- `summary`
- `ecosystem_impact_score` (`0..10`)
- `feasibility_score` (`0..10`)
- `urgency_score` (`0..10`)
- `evidence_refs[]` (at least one reference)

Optional row field:

- `rationale`

Behavior guarantees:

- Signal weights are normalized to sum to `1.0`.
- `priority_score` is the weighted sum of the three signal scores.
- Priority sorting is deterministic: `priority_score desc`, `ecosystem_impact_score desc`, `urgency_score desc`, `feasibility_score desc`, `recommendation_id asc`.
- Every calibrated row includes `scoring_contributors` with per-signal `weight`, `score`, and `weighted_contribution` for transparent auditability.

## Output contract

Top-level required keys:

- `requirement_id` (must be `REQ-038`)
- `surface` (must be `recommendation_priority_calibration`)
- `schema_version` (must be `req-038.recommendation-priority-calibration.v1`)
- `recommendation_priority_calibration_entrypoint`
- `processing_behavior`
- `call_metadata`
- `calibrated_at`
- `priority_weights`
- `priority_calibrations[]`
- `evidence_refs[]`
- `summary`

`priority_calibrations[]` row keys:

- `rank`
- `recommendation_id`
- `summary`
- `rationale`
- `ecosystem_impact_score`
- `feasibility_score`
- `urgency_score`
- `priority_score`
- `priority_band`
- `scoring_contributors`
- `evidence_refs[]`

`scoring_contributors` keys:

- `ecosystem_impact`
- `feasibility`
- `urgency`

Each contributor object includes:

- `weight`
- `score`
- `weighted_contribution`

## Executable artifacts

- Fixture input: `examples/fixtures/recommendation-priority-calibration.json`
- Contract test: `tests/contracts/test_recommendation-priority-calibration.py`
- Canonical sample output: `strategy/current/samples/REQ-038_recommendation-priority-calibration.sample.json`

## Sample structure

The canonical sample output is stored at:

`strategy/current/samples/REQ-038_recommendation-priority-calibration.sample.json`

Its top-level shape is:

```json
{
  "requirement_id": "REQ-038",
  "surface": "recommendation_priority_calibration",
  "schema_version": "req-038.recommendation-priority-calibration.v1",
  "recommendation_priority_calibration_entrypoint": {},
  "processing_behavior": {},
  "call_metadata": {},
  "calibrated_at": "2026-03-16T12:30:00Z",
  "priority_weights": {},
  "priority_calibrations": [],
  "evidence_refs": [],
  "summary": {}
}
```
