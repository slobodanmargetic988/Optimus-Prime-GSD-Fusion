# REQ-056: KPI Target Artifact

## Purpose
Define the contract and data-model surface for emitting KPI targets with explicit expected direction, baseline reference, and confidence level while preserving target lineage to originating recommendations and assumptions.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-056):
  - Emit deterministic KPI targets with `expected_direction`, `baseline_reference`, and `confidence_level`.
  - Link every KPI target to originating recommendations and assumptions.
  - Keep KPI artifact output bounded to this requirement's contract surface.
- Out of scope (REQ-056): net-new packet sections, managers, orchestration gates, or strategy behaviors outside KPI target artifact handoff.

## Interface surface
Builder:
- `build_req_056_kpi_target_artifact(payload) -> dict`

Validator:
- `validate_req_056_kpi_target_artifact(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-056 expects:

```json
{
  "analysis_type": "kpi_target_artifact",
  "now_utc": "2026-03-16T09:20:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "kpi_targets": [
    {
      "target_id": "kpi.telemetry-freshness-slo",
      "metric_name": "telemetry_freshness_slo_breach_rate",
      "expected_direction": "decrease",
      "baseline_reference": "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json#open_risks",
      "confidence_level": "high",
      "originating_recommendation_ids": [
        "rec.harden-telemetry-freshness"
      ],
      "assumption_ids": [
        "assumption.telemetry-path-stable"
      ],
      "rationale": "Human-facing KPI rationale.",
      "evidence_refs": [
        "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json#final_recommendations"
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `kpi_target_artifact` when provided.
- `target_project.project_root` must be an absolute path.
- `kpi_targets[]` must contain at least one row.
- `target_id` values must be unique.
- `expected_direction` must be one of `increase`, `decrease`, `maintain`.
- `confidence_level` must be one of `high`, `medium`, `low`.
- `baseline_reference` must be non-empty for every KPI target.
- `originating_recommendation_ids[]` must be a non-empty sorted unique string list.
- `assumption_ids[]` must be a non-empty sorted unique string list.
- `evidence_refs[]` must be a non-empty sorted unique string list.

## Output contract
REQ-056 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- artifact payload: `kpi_target_artifact`
- bounded counts: `totals`

`kpi_target_artifact` contains:
- `kpi_targets[]`

Each `kpi_targets[]` row includes:
- `target_id`
- `metric_name`
- `expected_direction`
- `baseline_reference`
- `confidence_level`
- `originating_recommendation_ids[]`
- `assumption_ids[]`
- `rationale`
- `evidence_refs[]`

`totals` includes:
- `kpi_targets`
- `unique_recommendations_linked`
- `unique_assumptions_linked`

KPI target behavior:
- Every emitted KPI target must include direction, baseline, and confidence anchors.
- Every emitted KPI target must link to at least one originating recommendation and at least one assumption.
- `totals.unique_recommendations_linked` and `totals.unique_assumptions_linked` must match unique IDs referenced in `kpi_target_artifact.kpi_targets[]`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/kpi-target-artifact.json`
- Contract tests: `tests/contracts/test_kpi-target-artifact.py`
- Output sample: `strategy/current/samples/REQ-056_kpi-target-artifact.sample.json`

The structure in `strategy/current/samples/REQ-056_kpi-target-artifact.sample.json`
is the canonical contract shape for REQ-056 and documents:
- `kpi_target_artifact.kpi_targets`
- `kpi_target_artifact.kpi_targets[].expected_direction`
- `kpi_target_artifact.kpi_targets[].baseline_reference`
- `kpi_target_artifact.kpi_targets[].confidence_level`
- `kpi_target_artifact.kpi_targets[].originating_recommendation_ids`
- `kpi_target_artifact.kpi_targets[].assumption_ids`
- `totals`
