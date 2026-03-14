# REQ-007 Ground Graph Snapshot Ingestion

## Requirement intent
- Strategy ingests Ground graph artifacts as canonical cross-project linkage context.
- Ingestion preserves project-era-plan-phase-run lineage anchors so planning decisions can be ecosystem-aware.
- Scope is limited to ingestion fields and behavior for these lineage anchors.
- Processing must not invent cross-project obligations without Earth-sweep evidence refs.
- Candidate ideas missing Earth-sweep evidence stay visible as explicit open risks.

## Input contract
`scripts/strategy_context_sweep.py::ingest_ground_graph_snapshot` accepts one Ground snapshot object with:
- `schema_version` (string, required)
- `captured_at` (string, required)
- `graph_id` (string, required)
- `lineage_links` (non-empty array, required)

Each `lineage_links[]` row must include:
- `project_id` (string, required)
- `era_id` (string, required)
- `plan_id` (string, required)
- `phase_id` (string, required)
- `run_id` (string, required)
- `linked_project_id` (string, required)
- `relationship` (string, required)

## Output contract
The ingestion output is a canonical REQ-007 surface with:
- `requirement_id`: `REQ-007`
- `surface`: `ground_graph_snapshot_ingestion`
- `schema_version`: `req-007.ground-graph-snapshot-ingestion.v1`
- `ingested_at`: ingestion timestamp
- `source_artifact`: source metadata (`path`, `schema_version`, `captured_at`, `graph_id`, `checksum_sha256`)
- `lineage_anchors`: normalized and deduplicated lineage rows, each with:
  - `anchor_id` (`project_id::era_id::plan_id::phase_id::run_id::linked_project_id::relationship`)
  - all lineage fields from the input row
- `lineage_index`: unique sorted IDs across anchors:
  - `project_ids`
  - `era_ids`
  - `plan_ids`
  - `phase_ids`
  - `run_ids`
  - `linked_project_ids`

## Broad-sweep processing contract
`scripts/strategy_context_sweep.py::process_ground_graph_snapshot` accepts:
- the same Ground snapshot input used for ingestion
- `broad_sweep_context` object with:
  - `active_project_id` (string, required)
  - `earth_sweep_evidence_refs` (array of strings, optional, deduplicated/sorted)
  - one candidate-action array key from:
    - `cross_project_action_candidates`
    - `candidate_actions`
    - `recommendation_candidates`

Each candidate row must include:
- `linked_project_id` (string, required)
- `action` (string, required)
- `evidence_refs` (array of strings, optional)

Processing returns canonical ingestion fields plus deterministic reasoning fields:
- `cross_project_context`:
  - `active_project_id`
  - `linked_projects`
  - `linked_project_context` rows with anchor counts, relationship types, and anchor IDs
  - `active_project_anchor_count`
  - `total_anchor_count`
- `evidence_refs`:
  - `earth_sweep`
  - `recommendation`
- `recommendation`:
  - `decision`
  - `summary`
  - `supported_actions`
  - `deferred_actions`
  - `open_risks`
  - `evidence_refs`

Behavior guarantees:
- Supported cross-project actions are limited to linked projects present in Ground lineage anchors.
- Supported actions require Earth-sweep evidence refs.
- Missing-evidence or out-of-graph candidates remain explicit `open_risks`.

## Executable artifacts
- Fixture input: `examples/fixtures/ground-graph-snapshot-ingestion.json`
- Broad-sweep context fixture: `examples/fixtures/ground-graph-snapshot-broad-context.json`
- Contract test: `tests/contracts/test_ground-graph-snapshot-ingestion.py`
- Integration test: `tests/integration/test_ground-graph-snapshot-ingestion.py`
- Canonical sample output: `strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json`
- Canonical processing sample output: `strategy/current/samples/REQ-007_ground-graph-snapshot-processing.sample.json`

## Sample structure
The canonical sample output is stored at:

`strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json`

Its top-level shape is:

```json
{
  "requirement_id": "REQ-007",
  "surface": "ground_graph_snapshot_ingestion",
  "schema_version": "req-007.ground-graph-snapshot-ingestion.v1",
  "ingested_at": "2026-03-14T21:50:00Z",
  "source_artifact": {},
  "lineage_anchors": [],
  "lineage_index": {}
}
```
