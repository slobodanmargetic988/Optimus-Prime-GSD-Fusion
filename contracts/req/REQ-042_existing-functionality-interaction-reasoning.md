# REQ-042 Existing-Functionality Interaction Reasoning

## Requirement intent
- Strategy reasons about when to consume already-built functionality versus build new capability.
- Interaction reasoning includes explicit compatibility checks for each reviewed existing-functionality candidate.
- Interaction reasoning includes integration burden estimates that are compared against the build-new path.
- Scope is limited to these consume-vs-build decision anchors and does not introduce new packet sections, managers, or gates.

## Input contract
`scripts/strategy_llm_pipeline.py::build_req_042_existing_functionality_interaction_reasoning` accepts one object with:
- `target_project_root` (absolute path string, optional, defaults to `/workspace/projects/optimus-prime`)
- `earth_root` (absolute path string, optional, defaults to `/workspace/projects/Earth`)
- `active_project_id` (string, required)
- `capability_need` (object, required)
- `build_new_assessment` (object, required)
- `target_project_evidence_refs` (array of strings, optional)
- `earth_sweep_evidence_refs` (array of strings, optional)
- `cross_project_context` (array of objects, optional)
- `existing_functionality_candidates` (non-empty array, required)
- `evaluated_at` (string, optional, defaults to current UTC timestamp)

`capability_need` must include:
- `capability_id` (string, required)
- `intent` (string, required)
- `required_interfaces` (array of strings, optional)

`build_new_assessment` must include:
- `summary` (string, required)
- `estimated_burden` (`low`, `medium`, or `high`, required)
- `rationale` (string, required)
- `evidence_refs` (non-empty array of strings, required)

Each `existing_functionality_candidates[]` row must include:
- `candidate_id` (string, optional, defaults to `candidate-XX`)
- `source_project_id` (string, required)
- `capability_id` (string, required)
- `functionality_summary` (string, required)
- `provided_interfaces` (array of strings, optional)
- `compatibility_checks` (non-empty array of objects, required)
- `integration_burden` (object, required)
- `evidence_refs` (non-empty array of strings, required)

Each `compatibility_checks[]` row must include:
- `check_id` (string, required)
- `requirement` (string, required)
- `status` (`pass`, `fail`, or `unknown`, required)
- `detail` (string, required)

`integration_burden` must include:
- `estimate_level` (`low`, `medium`, or `high`, required)
- `drivers` (non-empty array of strings, required)
- `rationale` (string, required)

Each `cross_project_context[]` row must include:
- `project_id` (string, required)
- `project_root` (absolute path string, required)
- `evidence_refs` (array of strings, optional but required to promote cross-project obligations)
- `context_note` (string, required)

## Output contract
The builder emits a canonical REQ-042 surface with:
- `requirement_id`: `REQ-042`
- `surface`: `existing_functionality_interaction_reasoning`
- `schema_version`: `req-042.existing-functionality-interaction-reasoning.v1`
- `evaluated_at`: evaluation timestamp
- `active_project_id`: active project identifier
- `capability_need`: normalized requested capability details
- `build_new_assessment`: normalized build-new burden baseline
- `interaction_reasoning`: per-candidate interaction reasoning rows
- `selected_path`: final consume-vs-build decision
- `processing_behavior`: deterministic reasoning, recommendation, and broad-sweep context usage details
- `evidence_refs`: sorted unique evidence refs from the target project, Earth sweep, build-new assessment, reviewed candidates, and any recommendation-level obligations or open risks
- `summary`: deterministic count summary

Each `interaction_reasoning[]` row includes:
- `candidate_id`
- `source_project_id`
- `capability_id`
- `functionality_summary`
- `required_interfaces`
- `provided_interfaces`
- `missing_interfaces`
- `compatibility_state` (`compatible`, `needs_followup`, or `incompatible`)
- `compatibility_checks`
- `integration_burden`
- `candidate_decision` (`consume_existing_functionality`, `investigate_existing_functionality`, `reject_existing_functionality`, or `build_new_capability`)
- `decision_rationale`
- `evidence_refs`

`selected_path` includes:
- `decision` (`consume_existing_functionality`, `investigate_existing_functionality`, or `build_new_capability`)
- `selected_candidate_id` (string when consuming existing functionality, otherwise `null`)
- `rationale`

`processing_behavior` includes:
- `strategy`, `reasoning_mode`, `strict_evidence_discipline`, and `heuristic_summarization_only`
- `context_inputs` with:
  - `target_project`
  - `build_new_assessment`
  - `earth_sweep`
  - `cross_project_context`
  - `existing_functionality_candidates`
- `context_usage` with explicit `target_project_context_used`, `earth_sweep_context_used`, `cross_project_context_used`, `candidate_ids_considered`, `cross_project_projects_considered`, and evidence-ref usage rollups
- `existing_functionality_reasoning` with the deterministic `candidate_assessments` array and reviewed counts
- `recommendation` with:
  - `decision`
  - `rationale`
  - `confidence`
  - `evidence_refs`
  - `selected_path`
  - `reuse_candidates`
  - `cross_project_obligations`
  - `open_risks`
- `summary`

Behavior guarantees:
- Missing required interfaces make a candidate `incompatible`.
- Any failed compatibility check makes a candidate `incompatible`.
- Unknown compatibility checks yield `needs_followup` when no failure is present.
- A compatible candidate is recommended for consumption only when its `integration_burden.estimate_level` is not higher than `build_new_assessment.estimated_burden`.
- The final `selected_path` prefers the lowest-burden compatible candidate, otherwise falls back to follow-up or build-new reasoning.
- Cross-project obligations are emitted only when matching Earth-sweep evidence refs exist for the selected reuse candidate.
- If Earth-sweep evidence is missing for the preferred cross-project reuse path, the builder records an `open_risks[]` entry and downgrades the selected path to investigation instead of silently promoting the obligation.

## Executable artifacts
- Fixture input/output: `examples/fixtures/existing-functionality-interaction-reasoning.json`
- Contract test: `tests/contracts/test_existing-functionality-interaction-reasoning.py`
- Canonical sample output: `strategy/current/samples/REQ-042_existing-functionality-interaction-reasoning.sample.json`

## Sample structure
The canonical sample output is stored at:

`strategy/current/samples/REQ-042_existing-functionality-interaction-reasoning.sample.json`

Its top-level shape is:

```json
{
  "requirement_id": "REQ-042",
  "surface": "existing_functionality_interaction_reasoning",
  "schema_version": "req-042.existing-functionality-interaction-reasoning.v1",
  "evaluated_at": "2026-03-16T12:00:00Z",
  "active_project_id": "optimus-prime-gsd-fusion",
  "capability_need": {},
  "build_new_assessment": {},
  "interaction_reasoning": [],
  "selected_path": {},
  "processing_behavior": {},
  "evidence_refs": [],
  "summary": ""
}
```
