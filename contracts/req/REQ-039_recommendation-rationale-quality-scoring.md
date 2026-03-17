# REQ-039: Recommendation Rationale Quality Scoring

## Purpose
Define the contract and data-model surface for scoring recommendation rationale quality so low-substance recommendations are rejected before packet emission.

## Scope anchors
- Surface in scope: `scripts/strategy_llm_pipeline.py`.
- In scope (REQ-039):
  - Score recommendation rationale quality against a deterministic threshold policy.
  - Enforce a minimum evidence-ref count per recommendation.
  - Enforce explicit tradeoff articulation before a recommendation is emission-ready.
  - Reject low-substance recommendations before packet emission.
- Out of scope (REQ-039): net-new packet sections, managers, orchestration gates, or recommendation fields outside this scoring surface.

## Interface surface
Builder:
- `build_req_039_recommendation_rationale_quality_scoring(payload) -> dict`

Validator:
- `validate_req_039_recommendation_rationale_quality_scoring(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_llm_pipeline.py --input-json <path|->`

## Input contract
`strategy_llm_pipeline.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "recommendation_rationale_quality_scoring",
  "now_utc": "2026-03-16T12:00:00Z",
  "quality_policy": {
    "minimum_evidence_ref_count": 2,
    "minimum_tradeoff_count": 1,
    "passing_score": 4
  },
  "recommendations": [
    {
      "recommendation_id": "rec.example",
      "summary": "Human-facing recommendation summary",
      "rationale": "Why this recommendation is justified now.",
      "evidence_refs": [
        "reports/optimus-prime/planning/evidence/TASK-135/TASK_EVIDENCE.json"
      ],
      "tradeoffs": [
        "What this recommendation postpones or constrains."
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `recommendation_rationale_quality_scoring`.
- `quality_policy.minimum_evidence_ref_count` must be a positive integer.
- `quality_policy.minimum_tradeoff_count` must be a positive integer.
- `quality_policy.passing_score` must be an integer between `1` and `4`.
- `recommendations[]` rows are strict; unexpected keys are rejected.
- `recommendations[].rationale` must be non-empty, but acceptance still requires the configured evidence and tradeoff thresholds.
- `recommendations[].evidence_refs[]` and `recommendations[].tradeoffs[]` are normalized to sorted unique non-empty strings.
- The builder is strict: unexpected keys are rejected to keep scope bounded to REQ-039 anchors.

## Output contract
REQ-039 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- threshold policy: `quality_policy`
- normalized inputs: `recommendations[]`
- scoring surface: `recommendation_rationale_quality_scoring`
- bounded totals: `totals`

`recommendation_rationale_quality_scoring` contains:
- `scored_recommendations[]`: one scored row per normalized recommendation
- `accepted_recommendations[]`: emission-ready recommendations only
- `rejected_recommendations[]`: low-substance recommendations blocked before packet emission

Each scored row includes:
- `recommendation_id`, `summary`, `rationale`
- `evidence_refs[]`
- `tradeoffs[]`
- `quality_score` (deterministic `0..4`)
- `quality_status` (`accepted|rejected`)
- `score_breakdown`
  - `evidence_ref_count`
  - `evidence_requirement_met`
  - `tradeoff_count`
  - `tradeoff_requirement_met`
- `rejection_reason_codes[]`

Rejection semantics:
- `insufficient_evidence_refs`: recommendation did not meet `quality_policy.minimum_evidence_ref_count`
- `missing_explicit_tradeoffs`: recommendation did not meet `quality_policy.minimum_tradeoff_count`
- Recommendations are only emission-ready when both requirement checks pass and `quality_score >= quality_policy.passing_score`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/recommendation-rationale-quality-scoring.json`
- Contract tests: `tests/contracts/test_recommendation-rationale-quality-scoring.py`
- Output sample: `strategy/current/samples/REQ-039_recommendation-rationale-quality-scoring.sample.json`

The structure in `strategy/current/samples/REQ-039_recommendation-rationale-quality-scoring.sample.json`
is the canonical contract shape for REQ-039.
