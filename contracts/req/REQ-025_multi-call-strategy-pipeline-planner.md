# REQ-025 Multi-Call Strategy Pipeline Planner

Status: Implemented  
Requirement ID: `REQ-025`

## Scope anchors

This contract is limited to:

- Planning a multi-call reasoning chain with explicit call purposes.
- Capturing per-call dependencies and expected outputs.
- Publishing a replay-stable per-call orchestration trace with call objectives, input refs, output refs, and handoff summaries.
- Supporting adjustable call depth for heavy-thinking runs.
- Enforcing strict evidence discipline for all planned calls.

## Entrypoint surface

Implementation file: `scripts/strategy_llm_pipeline.py`

Builder function:

- `build_req_025_multi_call_strategy_pipeline_planner(...) -> dict`

Validator function:

- `validate_req_025_multi_call_strategy_pipeline_planner(payload) -> list[str]`

## Payload contract

Top-level required keys:

- `schema_version` (must equal `req-025.multi-call-strategy-pipeline-planner.v1`)
- `requirement_id` (must equal `REQ-025`)
- `multi_call_strategy_pipeline_planner_entrypoint` (object)
- `processing_behavior` (object)
- `call_metadata` (object)

`call_metadata` required keys:

- `reproducibility`
- `canonical_input_sha256`
- `reproducible_call_id`
- `canonical_input`
- `processing_input_sha256`
- `processing_call_id`
- `canonical_processing_input`
- `llm_call_trace_schema_version` (must equal `req-025.llm-call-trace-row.v1`)
- `llm_call_trace_path` (must equal `strategy/current/llm_call_trace.jsonl`)
- `llm_call_trace_sha256`
- `llm_call_trace_rows` (array)

`multi_call_strategy_pipeline_planner_entrypoint` required keys:

- `runtime_mode` (must equal `llm-first`)
- `execution_mode` (must equal `long-thinking`)
- `target_project_root` (absolute path)
- `earth_root` (absolute path)
- `output_root` (absolute path)
- `revision_identity` (non-empty string)
- `strategy_goal` (non-empty string)
- `call_depth` (integer between 1 and 8)

`processing_behavior` required keys:

- `strategy` (must equal `multi-call-strategy-pipeline-planner`)
- `reasoning_mode` (must equal `long-thinking`)
- `strict_evidence_discipline` (must be `true`)
- `pipeline_plan` (object)
- `summary` (human-facing deterministic summary)

`pipeline_plan` required keys:

- `plan_id` (must derive from `call_metadata.processing_input_sha256`)
- `planner_mode` (must equal `multi-call-reasoning-chain`)
- `total_calls` (must equal `call_depth`)
- `required_evidence_refs` (non-empty array of evidence refs)
- `calls` (array of call objects)
- `dependency_edges` (array of call dependency links)
- `terminal_expected_output` (must match final call `expected_output`)

Each `calls[]` row must include:

- `call_id` (deterministic ID)
- `sequence` (1-based index)
- `purpose` (explicit call purpose)
- `depends_on` (array of prior `call_id` values)
- `expected_output` (explicit per-call output)
- `evidence_refs` (must match `required_evidence_refs`)

Each `llm_call_trace_rows[]` row must include:

- `call_id` (must match a planned call)
- `call_objective` (must mirror `calls[].purpose`)
- `depends_on` (must mirror planned dependencies)
- `expected_output` (must mirror `calls[].expected_output`)
- `input_refs` (required evidence refs plus upstream call output refs)
- `output_refs` (deterministic logical output refs for the call)
- `handoff_summary` (human-facing deterministic summary)

## Samples and fixtures

Sample artifact path:

- `strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json`

Fixture path:

- `examples/fixtures/multi-call-strategy-pipeline-planner.json`

## Sample structure

The canonical sample output is stored at:

`strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json`

Its top-level shape is:

```json
{
  "schema_version": "req-025.multi-call-strategy-pipeline-planner.v1",
  "requirement_id": "REQ-025",
  "multi_call_strategy_pipeline_planner_entrypoint": {},
  "processing_behavior": {
    "strategy": "multi-call-strategy-pipeline-planner",
    "reasoning_mode": "long-thinking",
    "strict_evidence_discipline": true,
    "pipeline_plan": {},
    "summary": ""
  },
  "call_metadata": {
    "llm_call_trace_path": "strategy/current/llm_call_trace.jsonl",
    "llm_call_trace_rows": [
      {
        "call_objective": "",
        "input_refs": [],
        "output_refs": [],
        "handoff_summary": ""
      }
    ]
  }
}
```
