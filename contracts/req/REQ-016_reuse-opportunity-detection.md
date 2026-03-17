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
- `earth_sweep_source_artifacts` (array, optional)
- `required_context_documents` (array, optional)

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

Each `earth_sweep_source_artifacts[]` row must include:
- `artifact_ref` (string, required)
- `status` (`fresh` or `stale`, optional, defaults to `fresh`)
- `evidence_refs` (array of strings, optional)

Each `required_context_documents[]` row must include:
- `doc_kind` (`mission`, `scope`, or `peer-project`, required)
- `doc_ref` (string, required)
- `status` (`present` or `missing`, optional, defaults to `present`)
- `project_id` (string, required for `peer-project`, otherwise omitted)
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
- `open_risks`: deterministic stale/missing-context blocker rows with `reason_code` and `required_evidence_refs`
- `evidence_refs`: sorted unique evidence refs from reuse recommendations and open-risk diagnostics
- `decision`: `reuse_before_reimplement`, `partial_reuse_recommended`, `partial_reuse_recommended_with_open_risks`, `blocked_context_gaps`, or `no_reuse_opportunity_detected`
- `summary`: deterministic count summary including open risks

Behavior guarantees:
- A recommendation is emitted only when capability IDs match and required interfaces are satisfied.
- Reuse candidates from the active project are rejected.
- Recommendation rows always include `adoption_path` and `compatibility_constraints`.
- Stale Earth-sweep artifacts and missing mission/scope or peer-project docs emit deterministic `reason_code` values with actionable evidence refs.
- `scripts/strategy_context_sweep.py::serialize_reuse_opportunity_context_bundle` canonicalizes input context into `json-canonical-v1` for replay-stable serialization.

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
  "open_risks": [],
  "evidence_refs": [],
  "decision": "partial_reuse_recommended",
  "summary": ""
}
```
