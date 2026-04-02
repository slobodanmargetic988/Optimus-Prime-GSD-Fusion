# REQ-062: Recommendation ID Uniqueness Validator

## Purpose
Define the contract and data-model surface for validating recommendation ID uniqueness per revision and ID stability across revisions with deterministic diff-oriented diagnostics.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-062):
  - Validate recommendation ID uniqueness within each revision snapshot.
  - Validate recommendation ID stability for shared recommendation keys across revisions.
  - Emit diff-oriented diagnostics for ID drift and ID collision cases.
- Out of scope (REQ-062): net-new packet sections, managers, orchestration gates, or strategy behaviors outside recommendation ID uniqueness/stability validation.

## Interface surface
Builder:
- `build_req_062_recommendation_id_uniqueness_validator(payload) -> dict`

Validator:
- `validate_req_062_recommendation_id_uniqueness_validator(payload) -> list[str]`

## Input contract
REQ-062 expects:

```json
{
  "analysis_type": "recommendation_id_uniqueness_validator",
  "now_utc": "2026-03-16T10:30:00Z",
  "previous_revision": {
    "revision_id": "strategy-rev-041",
    "recommendations": [
      {
        "recommendation_key": "telemetry-freshness",
        "recommendation_id": "rec.harden-telemetry-freshness"
      }
    ]
  },
  "current_revision": {
    "revision_id": "strategy-rev-042",
    "recommendations": [
      {
        "recommendation_key": "telemetry-freshness",
        "recommendation_id": "rec.harden-telemetry-freshness-v2"
      }
    ]
  }
}
```

Rules:
- `analysis_type` must be `recommendation_id_uniqueness_validator` when provided.
- `previous_revision` and `current_revision` are required.
- Each revision requires `revision_id` and `recommendations[]`.
- Each `recommendations[]` row requires:
  - `recommendation_key` (non-empty string)
  - `recommendation_id` (non-empty string)

## Output contract
REQ-062 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- revision anchor: `revision_pair`, `revision_snapshots`
- diff diagnostics: `diagnostics`
- bounded counts: `totals`
- decision booleans: `verdict`

`revision_snapshots` contains:
- `revision_snapshots.previous.revision_id`
- `revision_snapshots.previous.recommendation_ids`
- `revision_snapshots.current.revision_id`
- `revision_snapshots.current.recommendation_ids`

`diagnostics` contains:
- `diagnostics.id_collisions[]` with:
  - `diagnostic_id`
  - `revision_id`
  - `recommendation_id`
  - `occurrence_count`
  - `recommendation_keys[]`
- `diagnostics.id_drift[]` with:
  - `diagnostic_id`
  - `recommendation_key`
  - `previous_recommendation_ids[]`
  - `current_recommendation_ids[]`
- `diagnostics.added_ids[]`
- `diagnostics.removed_ids[]`

`totals` contains:
- `previous_recommendation_rows`
- `current_recommendation_rows`
- `previous_unique_recommendation_ids`
- `current_unique_recommendation_ids`
- `added_ids`
- `removed_ids`
- `id_collisions`
- `id_drift`

`verdict` contains:
- `is_unique_within_revision`
- `ids_stable_across_revisions`
- `passed`

Behavior anchors:
- ID collisions are emitted when a recommendation ID appears multiple times within a single revision.
- ID drift is emitted when a shared recommendation key maps to different recommendation IDs across revisions.
- `verdict.passed` is true only when both uniqueness and stability checks pass.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/recommendation-id-uniqueness-validator.json`
- Contract tests: `tests/contracts/test_recommendation-id-uniqueness-validator.py`
- Output sample: `strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json`

The structure in `strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json`
is the canonical contract shape for REQ-062 and documents:
- `revision_snapshots.previous.recommendation_ids`
- `revision_snapshots.current.recommendation_ids`
- `diagnostics.id_collisions`
- `diagnostics.id_drift`
- `diagnostics.added_ids`
- `diagnostics.removed_ids`
- `totals`
- `verdict`
