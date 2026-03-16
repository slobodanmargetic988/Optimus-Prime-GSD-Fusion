# REQ-068: Op-Plan Strategy Ingestion Hook

## Purpose
Define the contract and data-model surface for ingesting canonical strategy artifacts into `/op-plan` as first-class planner input while retaining recommendation traceability and avoiding a semantic fork from the source strategy artifacts.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-068):
  - Ingest canonical REQ-046 final strategy synthesis output as planner-facing `strategy_packet_inputs`.
  - Retain recommendation traceability by carrying call lineage, KPI linkage, and recommendation ID validator diagnostics into the ingestion surface.
  - Keep op-plan ingestion bounded to canonical strategy artifact consumption without inventing new planner packet sections or gates.
- Out of scope (REQ-068): net-new packet sections, managers, orchestration gates, or planner behaviors outside canonical strategy artifact ingestion.

## Interface surface
Builder:
- `build_req_068_op_plan_strategy_ingestion_hook(payload) -> dict`

Validator:
- `validate_req_068_op_plan_strategy_ingestion_hook(payload) -> list[str]`

## Input contract
REQ-068 expects:

```json
{
  "analysis_type": "op_plan_strategy_ingestion_hook",
  "now_utc": "2026-03-16T11:10:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "final_strategy_artifact": {
    "artifact_ref": "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json",
    "payload": {
      "requirement_id": "REQ-046",
      "analysis_type": "final_strategy_synthesis_composer"
    }
  },
  "kpi_target_artifact": {
    "artifact_ref": "strategy/current/samples/REQ-056_kpi-target-artifact.sample.json",
    "payload": {
      "requirement_id": "REQ-056",
      "analysis_type": "kpi_target_artifact"
    }
  },
  "recommendation_id_validator": {
    "artifact_ref": "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json",
    "payload": {
      "requirement_id": "REQ-062",
      "analysis_type": "recommendation_id_uniqueness_validator"
    }
  }
}
```

Rules:
- `analysis_type` must be `op_plan_strategy_ingestion_hook` when provided.
- `target_project.project_root` must normalize to an absolute path.
- `final_strategy_artifact`, `kpi_target_artifact`, and `recommendation_id_validator` are required.
- Each artifact envelope is strict and limited to:
  - `artifact_ref`
  - `payload`
- `final_strategy_artifact.payload` must validate as canonical REQ-046 output.
- `kpi_target_artifact.payload` must validate as canonical REQ-056 output.
- `recommendation_id_validator.payload` must validate as canonical REQ-062 output.
- `final_strategy_artifact.payload.target_project` and `kpi_target_artifact.payload.target_project` must match top-level `target_project`.

## Output contract
REQ-068 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- ingestion target: `target_project`
- planner ingestion surface: `op_plan_strategy_ingestion`
- bounded counts: `totals`

`op_plan_strategy_ingestion` contains:
- `canonical_strategy_artifacts`
- `planner_inputs`
- `planning_alerts`

`canonical_strategy_artifacts` contains:
- `final_strategy_artifact_ref`
- `final_recommendations_ref`
- `strategy_packet_inputs_ref`
- `kpi_target_artifact_ref`
- `kpi_targets_ref`
- `recommendation_id_validator_ref`
- `recommendation_id_validator_verdict_ref`

`planner_inputs` contains:
- `strategy_packet_inputs[]`
- `recommendation_traceability_index[]`

Each `recommendation_traceability_index[]` row includes:
- `recommendation_id`
- `strategy_packet_input_id`
- `packet_kind`
- `peer_project_id`
- `lane`
- `sequence_hint`
- `priority`
- `summary`
- `rationale`
- `evidence_refs[]`
- `traceability_refs[]`
- `call_trace_lineage[]`
- `contributing_call_ids[]`
- `contributing_requirement_ids[]`
- `supporting_call_count`
- `linked_kpi_target_ids[]`
- `linked_kpi_target_refs[]`
- `id_validation_status`
- `validator_diagnostic_refs[]`

`planning_alerts` contains:
- `deferred_recommendations[]`
- `open_risks[]`
- `id_collisions[]`
- `id_drift[]`
- `validator_verdict`

`totals` contains:
- `strategy_packet_inputs`
- `planner_ready_recommendations`
- `linked_kpi_targets`
- `deferred_recommendations`
- `open_risks`
- `id_collisions`
- `id_drift`

Behavior anchors:
- `planner_inputs.strategy_packet_inputs[]` are consumed directly from canonical REQ-046 strategy packet inputs.
- `recommendation_traceability_index[]` preserves recommendation lineage by combining final recommendation evidence, call-trace lineage, KPI target linkage, and REQ-062 diagnostic refs.
- `id_validation_status` is `collision`, `drifted`, or `stable` based on the canonical REQ-062 diagnostics relevant to the recommendation.
- `planning_alerts` carries deferred recommendations, open risks, and recommendation ID diagnostics forward without redefining planner packet semantics.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/op-plan-strategy-ingestion-hook.json`
- Contract tests: `tests/contracts/test_op-plan-strategy-ingestion-hook.py`
- Output sample: `strategy/current/samples/REQ-068_op-plan-strategy-ingestion-hook.sample.json`

The fixture stores canonical artifact refs used by the contract test to load the full REQ-046, REQ-056, and REQ-062 payload envelopes.

The structure in `strategy/current/samples/REQ-068_op-plan-strategy-ingestion-hook.sample.json`
is the canonical contract shape for REQ-068 and documents:
- `op_plan_strategy_ingestion.canonical_strategy_artifacts`
- `op_plan_strategy_ingestion.planner_inputs.strategy_packet_inputs`
- `op_plan_strategy_ingestion.planner_inputs.recommendation_traceability_index`
- `op_plan_strategy_ingestion.planning_alerts`
- `op_plan_strategy_ingestion.planning_alerts.validator_verdict`
- `totals`
