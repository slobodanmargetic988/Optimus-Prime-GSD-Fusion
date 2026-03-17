# REQ-017 Overlap and Conflict Detection

## Requirement intent
- Strategy detects overlapping initiatives across the active project and related projects.
- Strategy detects conflicting roadmap directions for overlaps that share capability scope and execution window.
- Conflict output includes recommended resolution options with explicit risk tradeoffs.
- Scope is limited to overlap/conflict detection fields tied to these anchors.

## Input contract
`scripts/strategy_context_sweep.py::detect_overlap_and_conflicts` accepts one object with:
- `active_project_id` (string, required)
- `related_project_ids` (non-empty array of strings, required)
- `initiatives` (non-empty array, required)

Each `initiatives[]` row must include:
- `initiative_id` (string, required)
- `project_id` (string, required, must be `active_project_id` or one of `related_project_ids`)
- `roadmap_direction` (string, required)
- `direction_signal` (string, optional, defaults to `advance`, allowed: `advance`, `hold`, `sunset`)
- `capability_tags` (non-empty array of strings, required)
- `timeline` (object, required)
  - `start_week` (non-negative integer, required)
  - `end_week` (non-negative integer, required, must be `>= start_week`)
- `evidence_refs` (array of strings, optional)

Optional broad-sweep context:
- `broad_sweep_context.earth_sweep_evidence_refs` (array of strings, optional)
- `broad_sweep_context.earth_sweep_source_artifacts[]` (array, optional)
  - `artifact_ref` (string, required)
  - `status` (string, optional; `fresh` or `stale`, defaults to `fresh`)
  - `evidence_refs` (array of strings, optional)
- `broad_sweep_context.project_context[]` (array, optional)
  - `project_id` (string, required, must be one of `related_project_ids`)
  - `context_note` (string, optional)
  - `evidence_refs` (array of strings, optional)
- `broad_sweep_context.required_context_documents[]` (array, optional)
  - `doc_kind` (string, required; one of `mission`, `scope`, `peer-project`)
  - `doc_ref` (string, required)
  - `status` (string, optional; `present` or `missing`, defaults to `present`)
  - `project_id` (string, required for `peer-project`; must be one of `related_project_ids`)
  - `evidence_refs` (array of strings, optional)
- `broad_sweep_context.unresolved_direction_ideas[]` (array, optional)
  - `idea_id` (string, optional; deterministic id derived when omitted)
  - `project_id` (string, required, must be one of `related_project_ids`)
  - `summary` (string, required)
  - `related_conflict_ids` (array of strings, optional)
  - `evidence_refs` (array of strings, optional)

## Output contract
The detection output is a canonical REQ-017 surface with:
- `requirement_id`: `REQ-017`
- `surface`: `overlap_and_conflict_detection`
- `schema_version`: `req-017.overlap-and-conflict-detection.v1`
- `evaluated_at`: evaluation timestamp
- `active_project_id`: active project ID
- `related_project_ids`: normalized related project IDs
- `overlap_index`: deterministic initiative/capability index
- `overlapping_initiatives`: overlaps across related projects on shared capability tags and overlapping timeline windows
- `conflicting_directions`: overlap rows with incompatible `direction_signal` values
- `cross_project_context`: normalized broad-sweep context usage
- `evidence_refs`: deterministic evidence partitions for overlap detection, Earth sweep, recommendation support, and out-of-scope refs
- `recommendation`: evidence-backed conflict resolution recommendations, cross-project obligations, and open risks
- `decision`: `conflicts_detected`, `overlap_detected_no_direction_conflict`, or `no_overlap_or_conflict_detected`
- `summary`: deterministic count summary

Conflict row guarantees:
- Every `conflicting_directions[]` row includes `risk_level` and `resolution_options`.
- Every `resolution_options[]` row includes `option_id`, `summary`, and `risk_tradeoff`.
- Every overlap/conflict row includes `earth_sweep_evidence_refs` and `out_of_scope_evidence_refs`.

Recommendation guardrails:
- `recommendation.conflict_resolution_recommendations[]` rows include `recommendation_id`, `summary`, `risk_level`, `resolution_options`, and Earth-sweep-backed `evidence_refs`.
- `recommendation.cross_project_obligations[]` must only be emitted when `evidence_refs` intersect `broad_sweep_context.earth_sweep_evidence_refs`.
- Unresolved ideas from broad-sweep context must be emitted under `recommendation.open_risks[]`; they are never silently promoted into obligations.

## Executable artifacts
- Fixture input: `examples/fixtures/overlap-and-conflict-detection.json`
- Contract test: `tests/contracts/test_overlap-and-conflict-detection.py`
- Integration test: `tests/integration/test_overlap-and-conflict-detection.py`
- Hardening test: `tests/hardening/test_overlap-and-conflict-detection_hardening.py`
- Canonical sample output: `strategy/current/samples/REQ-017_overlap-and-conflict-detection.sample.json`

## Sample structure
The canonical sample output is stored at:

`strategy/current/samples/REQ-017_overlap-and-conflict-detection.sample.json`

Its top-level shape is:

```json
{
  "requirement_id": "REQ-017",
  "surface": "overlap_and_conflict_detection",
  "schema_version": "req-017.overlap-and-conflict-detection.v1",
  "evaluated_at": "2026-03-15T03:10:00Z",
  "active_project_id": "optimus-prime-gsd-fusion",
  "related_project_ids": [],
  "overlap_index": {},
  "overlapping_initiatives": [],
  "conflicting_directions": [],
  "cross_project_context": {},
  "evidence_refs": {},
  "recommendation": {},
  "decision": "conflicts_detected",
  "summary": ""
}
```
