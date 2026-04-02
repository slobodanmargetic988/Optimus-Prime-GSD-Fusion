# REQ-040 Recommendation Feasibility Scoring

Status: Implemented  
Requirement ID: `REQ-040`  
Owner surface: `scripts/strategy_llm_pipeline.py`

## Purpose

Strategy must score recommendation feasibility from three anchors only:

1. Resource constraints.
2. Dependency readiness.
3. Current repo maturity.

REQ-040 then uses those feasibility scores to produce deterministic sequencing guidance and risk policy output.

## Input Contract

Builder:

- `build_req_040_recommendation_feasibility_scoring(...) -> dict`

Required anchors:

- `target_project_root`
- `earth_root`
- `output_root`
- `revision_identity`
- `resource_constraints`
- `dependency_readiness[]`
- `repo_maturity`
- `candidate_recommendations[]`

`resource_constraints` required keys:

- `available_parallel_slots`
- `available_daily_tokens`
- `max_recommendation_cost_tier` (`low|medium|high`)
- `constrained_resources[]`
- `evidence_refs[]`

`dependency_readiness[]` required keys:

- `dependency_id`
- `readiness_status` (`ready|partial|blocked`)
- `blocker_count`
- `evidence_refs[]`

`repo_maturity` required keys:

- `maturity_level` (`bootstrap|developing|stable`)
- `test_pass_rate`
- `open_defect_count`
- `evidence_refs[]`

`candidate_recommendations[]` required keys:

- `recommendation_id`
- `summary`
- `required_dependency_ids[]`
- `required_cost_tier` (`low|medium|high`)
- `evidence_refs[]`

## Output Contract

Top-level required keys:

- `schema_version` (must be `req-040.recommendation-feasibility-scoring.v1`)
- `requirement_id` (must be `REQ-040`)
- `recommendation_feasibility_scoring`
- `processing_behavior`
- `feasibility_assessment`
- `sequencing_policy`
- `risk_policy`
- `context_bundle`
- `call_metadata`

`feasibility_assessment` required keys:

- `overall_feasibility_score`
- `score_breakdown`
- `recommendations[]`
- `evidence_refs[]`

Each row in `feasibility_assessment.recommendations[]` includes:

- `recommendation_id`
- `summary`
- `required_dependency_ids[]`
- `required_cost_tier`
- `feasibility_score`
- `feasibility_label`
- `sequencing_bucket`
- `risk_policy`
- `reason_codes[]`
- `evidence_refs[]`

`sequencing_policy` required keys:

- `ordered_recommendation_ids[]`
- `reason_codes[]`

`risk_policy` required keys:

- `global_policy`
- `open_risks[]`
- `evidence_refs[]`

## Feasibility Scoring Semantics

REQ-040 weighting is deterministic and fixed:

- Resource constraints weight: `0.40`
- Dependency readiness weight: `0.35`
- Repo maturity weight: `0.25`

Score output controls the recommendation row fields `sequencing_bucket` and `risk_policy`, and therefore controls top-level `sequencing_policy` ordering plus `risk_policy.open_risks` emission.

## Sample Structure

Deterministic fixture:

- `examples/fixtures/recommendation-feasibility-scoring.json`

Deterministic sample artifact:

- `strategy/current/samples/REQ-040_recommendation-feasibility-scoring.sample.json`
