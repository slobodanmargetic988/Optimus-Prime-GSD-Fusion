# REQ-059: Strategy Quality Report Artifact

## Purpose
Define the contract and data-model surface for emitting a strategy quality report that summarizes citation coverage, contradiction status, and confidence distribution with machine-readable gate verdict fields for build automation.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-059):
  - Emit deterministic quality report summary fields for citation coverage.
  - Emit deterministic contradiction status summary fields.
  - Emit deterministic confidence distribution summary fields.
  - Emit machine-readable gate verdict fields consumed by build automation.
- Out of scope (REQ-059): net-new packet sections, managers, orchestration gates, or strategy behaviors outside strategy quality report artifact handoff.

## Interface surface
Builder:
- `build_req_059_strategy_quality_report_artifact(payload) -> dict`

Validator:
- `validate_req_059_strategy_quality_report_artifact(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-059 expects:

```json
{
  "analysis_type": "strategy_quality_report_artifact",
  "now_utc": "2026-03-16T11:00:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "citation_coverage": {
    "cited_claims": 18,
    "uncited_claims": 2
  },
  "contradiction_status": {
    "unresolved_contradiction_ids": []
  },
  "confidence_distribution": {
    "high": 6,
    "medium": 3,
    "low": 1
  },
  "gate_policy": {
    "min_citation_coverage_ratio": 0.85,
    "max_unresolved_contradictions": 0,
    "min_high_confidence_ratio": 0.5
  }
}
```

Rules:
- `analysis_type` must be `strategy_quality_report_artifact` when provided.
- `target_project.project_root` must be an absolute path.
- `citation_coverage.cited_claims` and `citation_coverage.uncited_claims` must be non-negative integers.
- Citation coverage must evaluate at least one claim (`cited_claims + uncited_claims >= 1`).
- `contradiction_status.unresolved_contradiction_ids` must be a sorted unique string list.
- Confidence buckets (`high`, `medium`, `low`) must be non-negative integers and sum to at least one scored item.
- Gate policy thresholds must be bounded: ratios in `[0, 1]`, unresolved contradiction cap as non-negative integer.

## Output contract
REQ-059 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- artifact payload: `strategy_quality_report_artifact`
- automation policy: `gate_policy`
- bounded counts: `totals`

`strategy_quality_report_artifact` contains:
- `citation_coverage`
- `contradiction_status`
- `confidence_distribution`
- `gate_verdicts`

`citation_coverage` includes:
- `cited_claims`
- `uncited_claims`
- `total_claims`
- `coverage_ratio`

`contradiction_status` includes:
- `has_unresolved_contradictions`
- `unresolved_contradiction_count`
- `unresolved_contradiction_ids[]`

`confidence_distribution` includes:
- `high`
- `medium`
- `low`
- `total`
- `high_ratio`
- `medium_ratio`
- `low_ratio`

`gate_verdicts` includes machine-readable build gate verdict fields:
- `citation_coverage_pass`
- `contradiction_pass`
- `confidence_distribution_pass`
- `overall_pass`
- `failed_gate_ids[]`

`totals` includes:
- `quality_gates`
- `failed_quality_gates`

Quality report behavior:
- `coverage_ratio` must equal `cited_claims / total_claims` rounded to 4 decimals.
- Contradiction status booleans/counts must match `unresolved_contradiction_ids[]`.
- Confidence ratios must match bucket counts over `total`, rounded to 4 decimals.
- Gate verdicts must be computed from report summaries and `gate_policy`.
- `totals.failed_quality_gates` must equal `len(gate_verdicts.failed_gate_ids)`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/strategy-quality-report-artifact.json`
- Contract tests: `tests/contracts/test_strategy-quality-report-artifact.py`
- Output sample: `strategy/current/samples/REQ-059_strategy-quality-report-artifact.sample.json`

The structure in `strategy/current/samples/REQ-059_strategy-quality-report-artifact.sample.json`
is the canonical contract shape for REQ-059 and documents:
- `strategy_quality_report_artifact.citation_coverage`
- `strategy_quality_report_artifact.contradiction_status`
- `strategy_quality_report_artifact.confidence_distribution`
- `strategy_quality_report_artifact.gate_verdicts`
- `strategy_quality_report_artifact.gate_verdicts.overall_pass`
- `strategy_quality_report_artifact.gate_verdicts.failed_gate_ids`
- `gate_policy`
- `totals`
