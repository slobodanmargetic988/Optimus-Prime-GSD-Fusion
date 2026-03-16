# REQ-061: Recommendation Quality Validator

## Purpose
Define the contract and data-model surface for validating whether planner-facing recommendations are complete, substantive, and sufficiently cited before they are handed to the final planner packet.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-061):
  - Validate recommendation completeness against the required planner-facing fields.
  - Enforce a minimum rationale word-count floor to block low-substance recommendations.
  - Enforce a minimum evidence citation count before a recommendation is allowed through.
  - Emit accepted vs blocked recommendation assessments plus deterministic planner-readiness IDs.
- Out of scope (REQ-061): net-new packet sections, managers, orchestration systems, or gates outside this validator artifact.

## Interface surface
Builder:
- `build_req_061_recommendation_quality_validator(payload) -> dict`

Validator:
- `validate_req_061_recommendation_quality_validator(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-061 expects:

```json
{
  "analysis_type": "recommendation_quality_validator",
  "now_utc": "2026-03-16T10:20:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "quality_thresholds": {
    "min_rationale_word_count": 12,
    "min_evidence_citations": 2
  },
  "recommendations": [
    {
      "recommendation_id": "rec.contract-enforce-quality-floor",
      "summary": "Enforce recommendation quality checks before planner packet handoff.",
      "rationale": "The planner packet should only ship recommendations with enough substance to explain sequencing and cite the source artifacts that justify execution.",
      "packet_kind": "target-project",
      "lane": "execution",
      "priority": "high",
      "sequence_hint": 1,
      "evidence_refs": [
        "contracts/req/REQ-046_final-strategy-synthesis-composer.md",
        "reports/quality/req-039-rationale-quality-score.json"
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `recommendation_quality_validator` when provided.
- `target_project.project_root` must be an absolute path.
- `recommendations[]` must include at least one row.
- `recommendation_id` is always required and must be unique.
- Quality-completeness fields are anchored to:
  - `summary`
  - `rationale`
  - `packet_kind`
  - `lane`
  - `priority`
  - `sequence_hint`
  - `evidence_refs`
- Supported `packet_kind` values are strictly `target-project` and `cross-project`.
- Supported `priority` values are strictly `high`, `medium`, and `low`.
- `quality_thresholds.min_rationale_word_count` and `quality_thresholds.min_evidence_citations` must be positive integers.
- Missing completeness fields are blocked in output rather than promoted into planner-ready recommendations.

## Output contract
REQ-061 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- quality config: `quality_thresholds`
- validation result: `quality_validation`
- bounded counts: `totals`

`quality_thresholds` contains:
- `required_recommendation_fields[]`
- `min_rationale_word_count`
- `min_evidence_citations`

`quality_validation` contains:
- `accepted_recommendations[]`
- `blocked_recommendations[]`
- `planner_readiness`

Each recommendation assessment row includes:
- `recommendation_id`
- `summary`
- `packet_kind`
- `lane`
- `priority`
- `sequence_hint`
- `completeness_status`
- `missing_fields[]`
- `rationale_quality`
- `evidence_citations`
- `decision`
- `failure_reason_codes[]`

Assessment rules:
- `completeness_status = complete` only when every field in `required_recommendation_fields[]` is present with usable planner-facing content.
- `rationale_quality.status = low_substance` when the rationale word count is below `min_rationale_word_count`.
- `evidence_citations.status = below_minimum` when evidence citation count is below `min_evidence_citations`.
- `decision = accepted` only when the recommendation is complete, rationale quality meets minimum, and evidence citations meet minimum.
- `decision = blocked` when any of these fail.

`planner_readiness` contains:
- `decision`
- `allowed_recommendation_ids[]`
- `blocked_recommendation_ids[]`
- `blocking_reason_codes[]`

Planner-readiness behavior:
- `allow_planner_packet` means at least one recommendation cleared all quality checks.
- `block_planner_packet` means every recommendation was blocked.
- `allowed_recommendation_ids[]` must exactly match `accepted_recommendations[]`.
- `blocked_recommendation_ids[]` and `blocking_reason_codes[]` must exactly match blocked assessment output.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/recommendation-quality-validator.json`
- Contract tests: `tests/contracts/test_recommendation-quality-validator.py`
- Output sample: `strategy/current/samples/REQ-061_recommendation-quality-validator.sample.json`

The structure in `strategy/current/samples/REQ-061_recommendation-quality-validator.sample.json`
is the canonical contract shape for REQ-061 and documents:
- `quality_thresholds.required_recommendation_fields`
- `quality_validation.accepted_recommendations`
- `quality_validation.blocked_recommendations`
- `quality_validation.planner_readiness`
- `totals`
