# REQ-019 Execution-Resource Context Ingestion

Status: Implemented  
Requirement ID: `REQ-019`

## Scope anchors

This requirement surface is limited to:

- Ingesting execution-resource context (hardware, rate-limits, runtime budget, model inventory).
- Using resource context to produce deterministic sequencing policy suggestions.
- Using resource context to produce deterministic model-routing policy suggestions.
- Emitting open risks when candidate workloads exceed resource constraints.

No net-new packet sections, managers, or orchestration gates are introduced by this contract.

## Interface surface

Implementation file:

- `scripts/strategy_context_sweep.py`

Builder:

- `build_req_019_execution_resource_context_ingestion(...) -> dict`

Validator:

- `validate_req_019_execution_resource_context_ingestion(payload) -> list[str]`

## Input contract

Builder anchors:

- `target_project_root` (absolute path)
- `earth_root` (absolute path)
- `output_root` (absolute path)
- `revision_identity` (non-empty string)
- `execution_resource_context` (object)
- `execution_candidates` (optional list)

`execution_resource_context` required sections:

- `hardware_profile`
  - `cpu_cores` (> 0 integer)
  - `memory_gb` (> 0 integer)
  - `gpu_count` (>= 0 integer, default `0`)
  - `storage_tier` (`standard` | `high-throughput`, default `standard`)
  - `evidence_refs` (optional list of strings)
- `rate_limits`
  - `max_parallel_tasks` (> 0 integer)
  - `tokens_per_minute` (> 0 integer)
  - `requests_per_minute` (> 0 integer)
  - `daily_token_budget` (> 0 integer, optional; defaults to `0` when omitted)
  - `evidence_refs` (optional list of strings)
- `runtime_budget`
  - `max_execution_minutes` (> 0 integer)
  - `checkpoint_interval_minutes` (> 0 integer, default `15`)
  - `evidence_refs` (optional list of strings)
- `model_inventory` (non-empty list)
  - `model_id` (unique, non-empty string)
  - `routing_tier` (`fast` | `balanced` | `heavy`)
  - `max_output_tokens` (> 0 integer)
  - `requests_per_minute_cap` (> 0 integer, optional; defaults to `rate_limits.requests_per_minute`)
  - `evidence_refs` (optional list of strings)

`execution_candidates[]` fields:

- `action_id` (unique, non-empty string)
- `summary` (non-empty string)
- `priority` (`high` | `medium` | `low`, default `medium`)
- `complexity` (`high` | `medium` | `low`, default `medium`)
- `estimated_token_cost` (> 0 integer, default `1200`)
- `requires_gpu` (boolean, default `true` when complexity is `high`)
- `preferred_model_tier` (`fast` | `balanced` | `heavy`, optional)
- `evidence_refs` (optional list of strings)
- `next_step` (non-empty string, default generated)

## Output contract

Top-level required keys:

- `schema_version` (must be `req-019.execution-resource-context-ingestion.v1`)
- `requirement_id` (must be `REQ-019`)
- `execution_resource_context_ingestion`
- `processing_behavior`
- `call_metadata`

`execution_resource_context_ingestion` required keys:

- `runtime_mode` (must be `llm-first`)
- `execution_mode` (must be `long-thinking`)
- `target_project_root`
- `earth_root`
- `output_root`
- `revision_identity`
- `resource_context` (normalized resource context)

`processing_behavior.recommendation` required keys:

- `decision`
- `rationale`
- `confidence`
- `evidence_refs`
- `sequencing_policy_suggestions[]`
- `model_routing_policy_suggestions[]`
- `open_risks[]`

Resource influence guarantees:

- Sequencing order and `execution_batch` are derived from resource-constrained parallel slots.
- Model-routing suggestions are derived from candidate complexity/priority and available model tiers.
- Open risks are emitted when routing is unavailable or token budgets are exceeded.

## Sample structure

Deterministic fixture:

- `examples/fixtures/execution-resource-context-ingestion.json`

Deterministic sample artifact:

- `strategy/current/samples/REQ-019_execution-resource-context-ingestion.sample.json`

The structure in `strategy/current/samples/REQ-019_execution-resource-context-ingestion.sample.json`
is the canonical contract shape for REQ-019.
