# REQ-019 Execution Resource Context Ingestion

Status: Implemented  
Requirement ID: `REQ-019`  
Owner surface: `scripts/strategy_context_sweep.py`

## Purpose

Strategy context sweep must ingest execution-resource constraints so recommendations stay executable under real hardware and rate-limit conditions.

This requirement deterministically maps resource context into:

1. Sequencing policy suggestions.
2. Model-routing policy suggestions.
3. Replay-stable context-bundle serialization for diagnostics.

Unhappy paths are never masked: stale source artifacts and missing mission/scope or peer-project docs emit explicit reason codes with evidence references.

## Input Contract

Builder:

- `build_req_019_execution_resource_context_ingestion(...) -> dict`

Required anchors:

- `target_project_root`
- `earth_root`
- `output_root`
- `revision_identity`

Optional context anchors:

- `target_project_evidence_refs[]`
- `earth_sweep_evidence_refs[]`
- `cross_project_context[]`
- `candidate_recommendations[]`
- `earth_sweep_source_artifacts[]`
- `required_context_documents[]`
- `execution_resource_context` object:
  - `hardware_profiles[]`
  - `rate_limit_windows[]`
  - `model_catalog[]`
  - `runtime_budget.max_parallel_actions`

## Output Contract

Top-level required keys:

- `schema_version` (must be `req-019.execution-resource-context-ingestion.v1`)
- `requirement_id` (must be `REQ-019`)
- `execution_resource_context_ingestion`
- `processing_behavior`
- `resource_policy`
- `context_bundle`
- `call_metadata`

`resource_policy` required keys:

- `sequencing_policy_suggestions`
- `model_routing_policy_suggestions`
- `resource_context_summary`

`context_bundle` required keys:

- `schema_version`
- `canonical_json`
- `sha256`

## Hardening Semantics

REQ-019 keeps explicit deterministic reason-code behavior for:

- stale Earth-sweep source artifacts (`stale_earth_sweep_source_artifact`)
- missing mission/scope docs (`missing_mission_doc`, `missing_scope_doc`)
- missing peer-project docs (`missing_peer_project_doc`)

Each row carries deterministic evidence refs for replay diagnostics.

## Sample Structure

Deterministic fixture:

- `examples/fixtures/execution-resource-context-ingestion.json`

Deterministic sample artifact:

- `strategy/current/samples/REQ-019_execution-resource-context-ingestion.sample.json`
