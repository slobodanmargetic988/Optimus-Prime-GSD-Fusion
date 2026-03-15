# REQ-010 Change Detection Since Previous Strategy Revision

## Purpose

Define the contract and data-model surface for deterministic strategy-change detection between two strategy revisions.

This contract anchors:
- mission scope changes
- runtime data changes
- ecosystem signal changes
- machine-readable recommendation deltas that directly reference emitted `change_id` values

## Interface Surface

- Implementation module: `scripts/strategy_context_sweep.py`
- Primary builder:
  - `build_change_detection_since_previous_strategy_revision(previous_revision, current_revision)`
- Contract validator:
  - `validate_change_detection_since_previous_strategy_revision(payload)`

## Contract (v1)

- `schema_version`: fixed string `req-010.change-detection-since-previous-strategy-revision.v1`
- `revision_pair`: previous/current revision identifiers
- `change_detection`: sectioned change model for
  - `mission_scope`
  - `runtime_data`
  - `ecosystem_signals`
- `change_summary`: deterministic aggregate summary (`total_change_count`, changed sections, sorted `change_ids`)
- `recommendation_deltas`: machine-readable recommendation adjustments with direct `change_ids` references
- `evidence_refs`: sorted unique evidence references grounding the revision pair

### `change_detection.<section>`

Each section (`mission_scope`, `runtime_data`, `ecosystem_signals`) contains:
- `changed`: boolean
- `change_count`: integer
- `changes[]`: sorted by `change_id`

Each `changes[]` item contains:
- `change_id`: deterministic ID `chg.<section>.<hex16>`
- `section_key`: must equal section name
- `path`: JSON pointer path
- `change_type`: `added` | `removed` | `updated`
- `previous_value`: value before change (or `null` when added)
- `current_value`: value after change (or `null` when removed)

### `recommendation_deltas[]`

- `recommendation_id`: stable recommendation identifier
- `summary`: human-facing recommendation delta summary
- `anchors`: ordered subset of `mission_scope`, `runtime_data`, `ecosystem_signals`
- `change_ids`: sorted non-empty list of referenced change IDs
- `delta_type`: `new` | `updated` | `retained` | `derived`

`recommendation_deltas` must reference every detected `change_id` so recommendation deltas remain directly traceable to strategy changes.
When explicit recommendation anchors cover only a subset of changed sections, the builder must append a deterministic `derived`
delta that backfills the missing `change_id` references.

## Stability Requirements

- Change detection output must be deterministic for identical inputs.
- `change_ids` must be stable and globally unique per payload.
- Every detected change must be referenced by at least one recommendation delta.
- `evidence_refs` must be sorted and unique.

## Sample Artifacts

- Executable fixture:
  - `examples/fixtures/change-detection-since-previous-strategy-revision.json`
- Strategy sample:
  - `strategy/current/samples/REQ-010_change-detection-since-previous-strategy-revision.sample.json`

The sample structure in `strategy/current/samples/REQ-010_change-detection-since-previous-strategy-revision.sample.json`
is the reference shape for this requirement.
