# REQ-017 Overlap and Conflict Detection

## Requirement intent
- Strategy detects overlapping initiatives across related projects (shared domains + overlapping time window).
- Strategy detects conflicting roadmap direction signals across related projects (same topic + differing stances).
- Each detected conflict includes recommended `resolution_options` with explicit risk tradeoffs.
- Scope is limited to these anchors; no net-new packet sections, managers, or orchestration gates are introduced.

## Interface surface
Implementation file:
- `scripts/strategy_context_sweep.py`

Builder:
- `build_req_017_overlap_and_conflict_detection(...) -> dict`

Validator:
- `validate_req_017_overlap_and_conflict_detection(payload) -> list[str]`

Deterministic bundle serializer (for `source.context_bundle_sha256`):
- `serialize_req_017_overlap_and_conflict_bundle(payload) -> str`

## Input contract
The builder accepts:
- `target_project` (object, required)
  - `project_id` (string, required)
  - `project_name` (string, optional)
- `initiatives[]` (array, optional)
  - `project_id` (string, required)
  - `initiative_id` (string, required, unique per `project_id`)
  - `title` (string, required)
  - `summary` (string, optional)
  - `domains[]` (array of strings, optional)
  - `start_date` (string `YYYY-MM-DD`, optional)
  - `end_date` (string `YYYY-MM-DD`, optional)
  - `evidence_refs[]` (array of strings, optional)
- `direction_signals[]` (array, optional)
  - `project_id` (string, required)
  - `signal_id` (string, optional; defaulted deterministically)
  - `topic` (string, required)
  - `stance` (string, required)
  - `statement` (string, required)
  - `confidence` (number between 0 and 1, optional; defaults to `0.5`)
  - `evidence_refs[]` (array of strings, optional)
- `research_event_id` (string, optional; copied into per-row provenance)
- `normalized_at_utc` (string, optional ISO-8601 timestamp; recorded under `source.normalized_at_utc`)

Overlap detection rule (bounded to this requirement):
- An `overlaps[]` row is emitted only when two initiatives from different projects share at least one `domains[]` value and their `start_date`/`end_date` windows overlap.

Conflict detection rule (bounded to this requirement):
- A `conflicts[]` row is emitted only when at least two `direction_signals[]` share the same `topic` while having different `stance` values across projects.

## Output contract
Top-level required keys:
- `schema_version` (must be `req-017.overlap-and-conflict-detection.v1`)
- `requirement_id` (must be `REQ-017`)
- `target_project`
- `projects_considered` (sorted unique project IDs)
- `overlaps`
- `conflicts`
- `evidence_refs` (sorted unique evidence refs across overlaps + conflicts)
- `decision` (`conflicts_detected`, `overlaps_detected`, or `no_overlaps_or_conflicts_detected`)
- `summary`
- `source`

Each `overlaps[]` row includes:
- `overlap_id`
- `shared_domains[]`
- `overlap_window.start_date`
- `overlap_window.end_date`
- `initiatives.left` and `initiatives.right` (initiative reference objects)
- `overlap_summary`
- `evidence_refs[]`
- `provenance.source_fields[]`
- `provenance.research_event_id`

Each `conflicts[]` row includes:
- `conflict_id`
- `topic`
- `stance_variants[]` (one row per stance, including per-project `signals[]`)
- `conflict_summary`
- `resolution_options[]` (each option includes `risk_level` and `tradeoffs[]`)
- `evidence_refs[]`
- `provenance.source_fields[]`
- `provenance.research_event_id`

`source` includes:
- `normalized_at_utc`
- `tool`
- `tool_version`
- `context_bundle_sha256`

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
  "schema_version": "req-017.overlap-and-conflict-detection.v1",
  "requirement_id": "REQ-017",
  "target_project": {},
  "projects_considered": [],
  "overlaps": [],
  "conflicts": [],
  "evidence_refs": [],
  "decision": "no_overlaps_or_conflicts_detected",
  "summary": {},
  "source": {}
}
```

