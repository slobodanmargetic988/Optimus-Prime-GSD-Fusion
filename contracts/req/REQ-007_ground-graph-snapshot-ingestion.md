# REQ-007 Ground Graph Snapshot Ingestion

## Requirement intent
- Strategy ingests Ground graph artifacts as canonical cross-project linkage context.
- Ingestion preserves project-era-plan-phase-run lineage anchors so planning decisions can be ecosystem-aware.
- Scope is limited to ingestion fields and behavior for these lineage anchors.

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

## Executable artifacts
- Fixture input: `examples/fixtures/ground-graph-snapshot-ingestion.json`
- Contract test: `tests/contracts/test_ground-graph-snapshot-ingestion.py`
- Canonical sample output: `strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json`

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
