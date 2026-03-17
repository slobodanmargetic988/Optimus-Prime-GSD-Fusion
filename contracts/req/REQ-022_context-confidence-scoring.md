# REQ-022 Context Confidence Scoring

Status: Implemented  
Requirement ID: `REQ-022`

## Scope anchors

This contract is limited to:

- Scoring broad-sweep context inputs for confidence based on:
  - source quality (context type + explicit freshness status)
  - recency (derived from evidence ref date patterns when available)
- Explicitly marking low-confidence context so downstream planning does not overfit weak inputs.
- Recording unresolved ideas as open risks instead of silently committing cross-project obligations without Earth-sweep evidence refs.

## Entrypoint surface

Implementation file: `scripts/strategy_context_sweep.py`

Builder function:

- `build_req_022_context_confidence_scoring(...) -> dict`

Validator function:

- `validate_req_022_context_confidence_scoring(payload) -> list[str]`

## Payload contract

Top-level required keys:

- `schema_version` (must equal `req-022.context-confidence-scoring.v1`)
- `requirement_id` (must equal `REQ-022`)
- `context_confidence_scoring_entrypoint` (object)
- `processing_behavior` (object)
- `call_metadata` (object)

`context_confidence_scoring_entrypoint` required keys:

- `runtime_mode` (must equal `llm-first`)
- `execution_mode` (must equal `long-thinking`)
- `target_project_root` (absolute path)
- `earth_root` (absolute path)
- `output_root` (absolute path)
- `revision_identity` (non-empty string)

`processing_behavior` required keys:

- `strategy` (must equal `context-confidence-scoring-broad-sweep`)
- `reasoning_mode` (must equal `long-thinking`)
- `heuristic_summarization_only` (must be `false`)
- `context_inputs` (broad-sweep context inputs)
- `context_usage` (deterministic evidence refs usage summary)
- `context_confidence` (confidence report with per-element scores)
- `recommendation` (standard recommendation surface with open risks)

## Samples and fixtures

Sample artifact path:

- `strategy/current/samples/REQ-022_context-confidence-scoring.sample.json`

Fixture path:

- `examples/fixtures/context-confidence-scoring.json`

