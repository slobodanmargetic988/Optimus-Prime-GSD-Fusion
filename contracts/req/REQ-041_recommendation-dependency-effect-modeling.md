# REQ-041 Recommendation Dependency-Effect Modeling

Status: Implemented  
Requirement ID: `REQ-041`

## Scope anchors

This requirement surface is limited to:

- Modeling dependency side effects for each recommendation across affected projects.
- Recording likely blockers for each affected-project dependency effect.
- Recording mitigation hooks for each affected-project dependency effect.

Out of scope:

- Net-new packet sections, managers, orchestration gates, or unrelated strategy behaviors.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_041_recommendation_dependency_effect_modeling(...) -> dict`

Validator:

- `validate_req_041_recommendation_dependency_effect_modeling(payload) -> list[str]`

CLI:

- `python3 scripts/strategy_llm_pipeline.py --input-json <path|->`
- Dispatch to REQ-041 occurs when input includes `requirement_id: "REQ-041"` or `surface: "recommendation_dependency_effect_modeling"`.

## Input contract

The builder expects:

- `recommendations[]` (required, non-empty)
- Optional environment metadata:
  - `target_project_root`
  - `earth_root`
  - `output_root`
  - `revision_identity`
  - `modeled_at`

Each `recommendations[]` row must include:

- `recommendation_id`
- `summary`
- `evidence_refs[]` (at least one reference)
- `affected_project_effects[]` (required, non-empty)

Optional row field:

- `rationale`

Each `affected_project_effects[]` row must include:

- `project_id`
- `effect_type`
- `dependency_effect_summary`
- `likely_blockers[]` (required, non-empty)
- `mitigation_hooks[]` (required, non-empty)
- `evidence_refs[]` (at least one reference)

Each `likely_blockers[]` row must include:

- `blocker_id`
- `summary`
- `severity` (`critical|high|medium|low`)
- `evidence_refs[]`

Each `mitigation_hooks[]` row must include:

- `hook_id`
- `summary`
- `hook_type`
- `evidence_refs[]`

Behavior guarantees:

- Recommendation models normalize into deterministic `recommendation_id` order.
- Affected-project rows normalize into deterministic `project_id` order.
- Likely blockers normalize into deterministic `blocker_id` order.
- Mitigation hooks normalize into deterministic `hook_id` order.
- Every normalized model reports `affected_project_count`, `blocker_count`, `mitigation_hook_count`, and `highest_blocker_severity`.

## Output contract

Top-level required keys:

- `requirement_id` (must be `REQ-041`)
- `surface` (must be `recommendation_dependency_effect_modeling`)
- `schema_version` (must be `req-041.recommendation-dependency-effect-modeling.v1`)
- `recommendation_dependency_effect_modeling_entrypoint`
- `processing_behavior`
- `call_metadata`
- `modeled_at`
- `dependency_effect_models[]`
- `evidence_refs[]`
- `summary`

`dependency_effect_models[]` row keys:

- `recommendation_id`
- `summary`
- `rationale`
- `affected_project_count`
- `affected_project_ids[]`
- `blocker_count`
- `mitigation_hook_count`
- `highest_blocker_severity`
- `affected_project_effects[]`
- `evidence_refs[]`

`affected_project_effects[]` row keys:

- `project_id`
- `effect_type`
- `dependency_effect_summary`
- `blocker_count`
- `mitigation_hook_count`
- `highest_blocker_severity`
- `likely_blockers[]`
- `mitigation_hooks[]`
- `evidence_refs[]`

`summary` keys:

- `recommendation_count`
- `affected_project_count`
- `likely_blocker_count`
- `mitigation_hook_count`
- `highest_blocker_severity`

## Executable artifacts

- Fixture input: `examples/fixtures/recommendation-dependency-effect-modeling.json`
- Contract test: `tests/contracts/test_recommendation-dependency-effect-modeling.py`
- Canonical sample output: `strategy/current/samples/REQ-041_recommendation-dependency-effect-modeling.sample.json`

## Sample structure

The canonical sample output is stored at:

`strategy/current/samples/REQ-041_recommendation-dependency-effect-modeling.sample.json`

Its top-level shape is:

```json
{
  "requirement_id": "REQ-041",
  "surface": "recommendation_dependency_effect_modeling",
  "schema_version": "req-041.recommendation-dependency-effect-modeling.v1",
  "recommendation_dependency_effect_modeling_entrypoint": {},
  "processing_behavior": {},
  "call_metadata": {},
  "modeled_at": "2026-03-16T12:45:00Z",
  "dependency_effect_models": [],
  "evidence_refs": [],
  "summary": {}
}
```
