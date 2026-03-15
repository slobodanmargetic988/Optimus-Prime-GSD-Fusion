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
- `evidence_refs`: sorted unique evidence refs across overlaps
- `decision`: `conflicts_detected`, `overlap_detected_no_direction_conflict`, or `no_overlap_or_conflict_detected`
- `summary`: deterministic count summary

Conflict row guarantees:
- Every `conflicting_directions[]` row includes `risk_level` and `resolution_options`.
- Every `resolution_options[]` row includes `option_id`, `summary`, and `risk_tradeoff`.

## Executable artifacts
- Fixture input: `examples/fixtures/overlap-and-conflict-detection.json`
- Contract test: `tests/contracts/test_overlap-and-conflict-detection.py`
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
  "evidence_refs": [],
  "decision": "conflicts_detected",
  "summary": ""
}
```
