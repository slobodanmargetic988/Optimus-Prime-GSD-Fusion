# REQ-011 Cross-Project Dependency Extraction

## Purpose

Define the contract and data-model surface for deterministic extraction of cross-project dependency edges from contracts, traces, and declared integration points.

This requirement anchors:
- extraction of cross-project dependency edges only
- confidence grading for each extracted edge
- explicit evidence refs per edge so weak links are not promoted to hard facts

## Interface Surface

- Implementation module: `scripts/strategy_context_sweep.py`
- Primary builder:
  - `build_req_011_cross_project_dependency_extraction(...)`
- Contract validator:
  - `validate_req_011_cross_project_dependency_extraction(payload)`

## Input Contract

The builder accepts:

- `target_project_id`: non-empty string
- `contract_signals[]`, `trace_signals[]`, `integration_point_signals[]`: optional lists of signal rows

Each signal row requires:
- `consumer_project_id`: non-empty string
- `provider_project_id`: non-empty string
- `dependency_ref`: non-empty string
- `summary`: non-empty string
- `evidence_refs[]`: non-empty, sorted-unique list of string evidence refs after normalization

Optional per-row:
- `signal_strength`: `strong` | `moderate` | `weak`

Default `signal_strength` by source:
- contract signals: `strong`
- integration point signals: `moderate`
- trace signals: `weak`

## Output Contract (v1)

- `schema_version`: fixed string `req-011.cross-project-dependency-extraction.v1`
- `requirement_id`: fixed string `REQ-011`
- `cross_project_dependency_extraction`:
  - `target_project_id`
  - `source_signals` (normalized signal inputs)
  - `dependency_edges[]`
  - `open_risks[]`
  - `summary`
  - `evidence_refs[]`
- `call_metadata`: deterministic canonical input/process fingerprints

### `dependency_edges[]`

Each edge contains:
- `dependency_edge_id`: deterministic edge ID from `consumer_project_id` and `provider_project_id`
- `consumer_project_id`
- `provider_project_id`
- `relationship`: fixed `depends_on`
- `summary`
- `source_kinds[]`: sorted set from `contract|trace|integration_point`
- `supporting_signal_count`
- `dependency_refs[]`
- `confidence`: `high|medium|low`
- `hard_dependency`: `true` only when confidence is `high`
- `evidence_refs[]`

Low-confidence edges must not be treated as hard dependencies.

### Confidence and hard-fact policy

- `high`: strong contract-backed signal support
- `medium`: partial or mixed support
- `low`: weak support only

Only `high` confidence edges are emitted with `hard_dependency=true`.
This ensures weak links are preserved as evidence-bearing hypotheses, not hard facts.

### `open_risks[]`

Soft edges (`medium`/`low`) are surfaced as risks with:
- `reason_code`: `medium_confidence_dependency_edge` or `low_confidence_dependency_edge`
- `confidence`
- `evidence_refs[]`

## Stability Requirements

- Extraction is deterministic for identical normalized inputs.
- Edge IDs are stable for the same consumer/provider pair.
- Edge and risk evidence refs are sorted and unique.
- Normalized signal rows and tied edge-support rows must use `evidence_refs[]` as a canonical tie-breaker when other ordering fields match.
- `call_metadata.canonical_input` must include the normalized `target_project_id` plus the normalized `contract_signals`, `trace_signals`, and `integration_point_signals`.
- `call_metadata` canonical hashes and IDs are reproducible and must change when materially different normalized dependency signal sets are supplied.

## Sample Artifacts

- Executable fixture:
  - `examples/fixtures/cross-project-dependency-extraction.json`
- Strategy sample:
  - `strategy/current/samples/REQ-011_cross-project-dependency-extraction.sample.json`

The structure in `strategy/current/samples/REQ-011_cross-project-dependency-extraction.sample.json` is the reference shape for this requirement's output payload.
