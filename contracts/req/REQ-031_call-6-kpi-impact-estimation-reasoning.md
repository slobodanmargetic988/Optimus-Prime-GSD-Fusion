# REQ-031: Call-6 KPI Impact Estimation Reasoning

Status: Implemented  
Requirement ID: `REQ-031`

## Scope anchors

This requirement is limited to the Call-6 estimation surface that:

- ingests bounded recommendation-adoption inputs,
- ingests KPI definitions plus evidence-backed impact assumptions,
- estimates KPI movement expected from adoption, and
- requires explicit `confidence` and `caveats` fields on every estimate to avoid false precision.

Out of scope:

- net-new packet sections outside Call-6 KPI estimation,
- new managers or gates,
- exact forecast precision without evidence-backed assumptions, and
- orchestration behavior unrelated to the Call-6 contract surface.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_031_call_6_kpi_impact_estimation_reasoning(...) -> dict`

Validator:

- `validate_req_031_call_6_kpi_impact_estimation_reasoning(payload) -> list[str]`

CLI:

```bash
python3 scripts/strategy_llm_pipeline.py \
  --input-json examples/fixtures/call-6-kpi-impact-estimation-reasoning.json \
  --output-json strategy/current/samples/REQ-031_call-6-kpi-impact-estimation-reasoning.sample.json \
  --json-pretty
```

Documented sample structure:

- `strategy/current/samples/REQ-031_call-6-kpi-impact-estimation-reasoning.sample.json`

## Input contract

Accepted builder input shape:

```json
{
  "analysis_type": "call_6_kpi_impact_estimation_reasoning",
  "call_id": "call-6",
  "checked_at_utc": "2026-03-16T14:30:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion"
  },
  "call_chain": [
    {
      "sequence": 1,
      "call_id": "call-1",
      "phase": "analysis",
      "output_ref": "REQ-026::call::call-1::output::situational_analysis"
    },
    {
      "sequence": 6,
      "call_id": "call-6",
      "phase": "estimation",
      "output_ref": "REQ-031::call::call-6::output::kpi_impact_estimation"
    }
  ],
  "target_project_evidence_refs": [
    "reports/optimus-prime/planning/evidence/TASK-103/TASK_EVIDENCE.json"
  ],
  "earth_sweep_evidence_refs": [
    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
  ],
  "recommendation_adoptions": [
    {
      "recommendation_id": "rec.local-replay-hardening",
      "summary": "Keep the local replay diagnostics deterministic.",
      "adoption_status": "planned",
      "adoption_window": "next-14-days",
      "evidence_refs": [
        "REQ-029::call::call-4::output::recommendation_synthesis"
      ]
    }
  ],
  "kpi_definitions": [
    {
      "kpi_id": "kpi.replay-failure-rate",
      "name": "Replay failure rate",
      "unit": "percent",
      "baseline_value": 18.0,
      "desired_direction": "decrease",
      "source_ref": "reports/optimus-prime/planning/VERIFICATION.md"
    }
  ],
  "impact_assumptions": [
    {
      "assumption_id": "assump.local-failure-rate",
      "recommendation_id": "rec.local-replay-hardening",
      "kpi_id": "kpi.replay-failure-rate",
      "statement": "Deterministic replay diagnostics should shrink repeated failure incidence before promotion.",
      "expected_movement_lower": -6.0,
      "expected_movement_upper": -3.0,
      "confidence": "medium",
      "caveats": [
        "Estimate depends on the recommendation landing without follow-on drift."
      ],
      "evidence_refs": [
        "reports/optimus-prime/planning/VERIFICATION.md",
        "REQ-029::call::call-4::output::recommendation_synthesis"
      ]
    }
  ]
}
```

Rules:

- `analysis_type` must be `call_6_kpi_impact_estimation_reasoning`.
- `call_id` must be `call-6`.
- `target_project.project_id` is required.
- `call_chain[]` must contain exactly six rows for `call-1` through `call-6`, in order.
- `target_project_evidence_refs[]` must be non-empty.
- `recommendation_adoptions[]` must be non-empty and each row must include:
  - `recommendation_id`
  - `summary`
  - `adoption_status` in `planned | conditional | pilot`
  - `adoption_window`
  - non-empty `evidence_refs[]`
- Cross-project recommendation rows may set `project_id`; when `requires_earth_evidence = true`, at least one Earth-scoped evidence ref must be present through either the row itself or `earth_sweep_evidence_refs[]`.
- `kpi_definitions[]` must be non-empty and each row must include:
  - `kpi_id`
  - `name`
  - `unit`
  - numeric `baseline_value`
  - `desired_direction` in `increase | decrease`
  - `source_ref`
- `impact_assumptions[]` must be non-empty and each row must include:
  - `assumption_id`
  - `recommendation_id` referencing `recommendation_adoptions[]`
  - `kpi_id` referencing `kpi_definitions[]`
  - `statement`
  - numeric `expected_movement_lower`
  - numeric `expected_movement_upper`
  - `confidence` in `high | medium | low`
  - non-empty `caveats[]`
  - non-empty `evidence_refs[]`
- `impact_assumptions[].evidence_refs[]` must stay inside the bounded evidence set supplied by target-project refs, Earth refs, call outputs, KPI sources, and recommendation refs.

## Output contract

Top-level required keys:

- `ok`
- `tool`
- `tool_version`
- `schema_version`
- `requirement_id`
- `analysis_type`
- `call_id`
- `checked_at_utc`
- `kpi_impact_estimation`
- `processing_behavior`
- `source`

`kpi_impact_estimation` required sections:

- `target_project.project_id`
- `recommendation_adoptions[]`
- `kpi_estimates[]`
- `summary`
  - `recommendation_count`
  - `kpi_count`
  - `estimate_count`
  - `low_confidence_estimate_count`
  - `caveat_count`

`kpi_estimates[]` row shape:

```json
{
  "estimate_id": "estimate::rec.local-replay-hardening::kpi.replay-failure-rate",
  "recommendation_id": "rec.local-replay-hardening",
  "recommendation_summary": "Keep the local replay diagnostics deterministic.",
  "kpi_id": "kpi.replay-failure-rate",
  "kpi_name": "Replay failure rate",
  "baseline_value": 18.0,
  "unit": "percent",
  "desired_direction": "decrease",
  "adoption_status": "planned",
  "adoption_window": "next-14-days",
  "expected_movement": {
    "lower_bound": -6.0,
    "upper_bound": -3.0,
    "unit": "percent",
    "direction": "decrease"
  },
  "estimated_post_adoption_range": {
    "lower_bound": 12.0,
    "upper_bound": 15.0,
    "unit": "percent"
  },
  "reasoning_summary": "Adopting 'Keep the local replay diagnostics deterministic.' is estimated to shift Replay failure rate by -6 to -3 percent over next-14-days under assumption assump.local-failure-rate.",
  "confidence": "medium",
  "caveats": [
    "Estimate depends on the recommendation landing without follow-on drift."
  ],
  "evidence_backed_assumptions": [
    {
      "assumption_id": "assump.local-failure-rate",
      "statement": "Deterministic replay diagnostics should shrink repeated failure incidence before promotion.",
      "evidence_refs": [
        "reports/optimus-prime/planning/VERIFICATION.md",
        "REQ-029::call::call-4::output::recommendation_synthesis"
      ]
    }
  ],
  "evidence_refs": [
    "REQ-029::call::call-4::output::recommendation_synthesis",
    "reports/optimus-prime/planning/VERIFICATION.md"
  ]
}
```

Normalization rules:

- `estimate_id` is synthesized deterministically as `estimate::{recommendation_id}::{kpi_id}`.
- Every estimate must include `confidence` and non-empty `caveats[]`.
- Every estimate must include bounded `expected_movement.lower_bound` and `expected_movement.upper_bound`.
- `estimated_post_adoption_range` must equal `baseline_value + expected_movement` at both bounds.
- `summary.recommendation_count` must equal `len(recommendation_adoptions)`.
- `summary.kpi_count` must equal the count of KPI definitions used for the output.
- `summary.estimate_count` must equal `len(kpi_estimates)`.
- `summary.low_confidence_estimate_count` must equal the number of estimates with `confidence = low`.
- `summary.caveat_count` must equal the total count of emitted caveat strings.

`processing_behavior` required sections:

- `strategy` = `call-6-kpi-impact-estimation`
- `reasoning_mode` = `deterministic-evidence-bounded-estimation`
- `strict_evidence_discipline` = `true`
- `context_inputs`
  - `call_chain[]`
  - `target_project_evidence_refs[]`
  - `earth_sweep_evidence_refs[]`
  - `recommendation_adoptions[]`
  - `kpi_definitions[]`
  - `impact_assumptions[]`
- `context_usage`
  - `source_call_ids_used`
  - `earth_sweep_context_used`
  - `earth_sweep_evidence_refs_used`
  - `recommendation_ids_considered`
  - `kpi_ids_considered`
  - `estimate_ids_emitted`
  - `low_confidence_estimate_ids`
  - `caveat_count`
  - `evidence_refs_used`
- `estimation_rules`
  - `confidence_scale`
  - `required_estimate_fields`
  - `caveats_required`
  - `bounded_range_required`
  - `assumption_evidence_required`

`call_metadata` required sections:

- `llm_call_trace_path` = `strategy/current/llm_call_trace.jsonl`
- `llm_call_trace_rows[]`
  - exactly 6 rows
  - one row each for `call-1` through `call-6`
  - every row must include `call_objective`, `input_refs[]`, `output_refs[]`, and `handoff_summary`

`source` required fields:

- `recommendation_adoption_count`
- `kpi_definition_count`
- `impact_assumption_count`
- `estimate_count`
- `evidence_ref_count`
- `earth_sweep_evidence_count`
