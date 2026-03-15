# REQ-016 Reuse Opportunity Detection

## Requirement intent
- Strategy detects existing functionality in other apps before reimplementing capability in the active project.
- Reuse recommendations must include explicit adoption path steps.
- Reuse recommendations must include compatibility constraints needed for safe adoption.
- Scope is limited to reuse detection and recommendation fields for these anchors.

## Input contract
`scripts/strategy_context_sweep.py::detect_reuse_opportunities` accepts one object with:
- `active_project_id` (string, required)
- `required_capabilities` (non-empty array, required)
- `existing_functionality` (non-empty array, required)

Each `required_capabilities[]` row must include:
- `capability_id` (string, required)
- `intent` (string, required)
- `required_interfaces` (array of strings, optional)

Each `existing_functionality[]` row must include:
- `source_project_id` (string, required, must differ from `active_project_id`)
- `capability_id` (string, required)
- `functionality` (string, required)
- `adoption_path` (non-empty array of strings, required)
- `compatibility_constraints` (non-empty array of strings, required)
- `provided_interfaces` (array of strings, optional)
- `evidence_refs` (array of strings, optional)

## Output contract
The detection output is a canonical REQ-016 surface with:
- `requirement_id`: `REQ-016`
- `surface`: `reuse_opportunity_detection`
- `schema_version`: `req-016.reuse-opportunity-detection.v1`
- `evaluated_at`: evaluation timestamp
- `active_project_id`: active project ID
- `reuse_index`: deterministic indexes for required capabilities and source projects
- `reuse_recommendations`: compatible reuse recommendations by capability
- `no_reuse_detected`: required capabilities with no compatible external functionality
- `evidence_refs`: sorted unique evidence refs from reuse recommendations
- `decision`: `reuse_before_reimplement`, `partial_reuse_recommended`, or `no_reuse_opportunity_detected`
- `summary`: deterministic count summary

Behavior guarantees:
- A recommendation is emitted only when capability IDs match and required interfaces are satisfied.
- Reuse candidates from the active project are rejected.
- Recommendation rows always include `adoption_path` and `compatibility_constraints`.

## Executable artifacts
- Fixture input: `examples/fixtures/reuse-opportunity-detection.json`
- Contract test: `tests/contracts/test_reuse-opportunity-detection.py`
- Canonical sample output: `strategy/current/samples/REQ-016_reuse-opportunity-detection.sample.json`

## Sample structure
The canonical sample output is stored at:

`strategy/current/samples/REQ-016_reuse-opportunity-detection.sample.json`

Its top-level shape is:

```json
{
  "requirement_id": "REQ-016",
  "surface": "reuse_opportunity_detection",
  "schema_version": "req-016.reuse-opportunity-detection.v1",
  "evaluated_at": "2026-03-15T01:30:00Z",
  "active_project_id": "optimus-prime-gsd-fusion",
  "reuse_index": {},
  "reuse_recommendations": [],
  "no_reuse_detected": [],
  "evidence_refs": [],
  "decision": "partial_reuse_recommended",
  "summary": ""
}
```
