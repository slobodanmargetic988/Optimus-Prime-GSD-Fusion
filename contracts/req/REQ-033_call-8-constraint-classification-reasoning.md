# REQ-033 Call-8 Constraint Classification Reasoning

Status: Implemented  
Requirement ID: `REQ-033`

## Scope anchors

This contract is limited to:

- Classifying Call-8 strategy outputs into explicit `hard_constraints`, `soft_preferences`, and `speculative_ideas`.
- Preserving planner-safe separation between obligation, guidance, and speculation so downstream planning does not conflate them.
- Emitting deterministic evidence refs, source output refs, and trace metadata for replay-stable planner ingestion.

No net-new packet sections, managers, or orchestration gates are introduced by this contract.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_033_call_8_constraint_classification_reasoning(...) -> dict`

Validator:

- `validate_req_033_call_8_constraint_classification_reasoning(payload) -> list[str]`

## Input contract

The builder expects:

- `strategy_goal` (required)
- `evidence_refs[]` (required)
- `constraint_candidates[]` (required)
- Optional context inputs:
  - `target_project_root`
  - `earth_root`
  - `output_root`
  - `revision_identity`
  - `target_project_evidence_refs[]`
  - `earth_sweep_evidence_refs[]`
  - `cross_project_context[]`

Each `constraint_candidates[]` row must include:

- `candidate_id`
- `summary`
- `classification` (`hard-constraint`, `soft-preference`, or `speculative-idea`)
- `classification_rationale`
- `planner_implication`
- `source_output_refs[]`
- `evidence_refs[]`

Behavior guarantees:

- Classification is explicit and emitted under separate planner-consumable arrays for `hard_constraints`, `soft_preferences`, and `speculative_ideas`.
- The same source output ref cannot be cleanly promoted into multiple classification buckets without surfacing an `open_risks[]` collision.
- Evidence refs and source output refs remain attached to every classified row so planner can preserve provenance.

## Output contract

Top-level required keys:

- `schema_version` (must be `req-033.call-8-constraint-classification-reasoning.v1`)
- `requirement_id` (must be `REQ-033`)
- `call_8_constraint_classification_reasoning_entrypoint`
- `processing_behavior`
- `call_metadata`

`call_8_constraint_classification_reasoning_entrypoint` required keys:

- `runtime_mode`
- `execution_mode`
- `target_project_root`
- `earth_root`
- `output_root`
- `revision_identity`
- `strategy_goal`
- `call_sequence` (must be `8`)

`processing_behavior` required keys:

- `strategy`
- `reasoning_mode`
- `strict_evidence_discipline`
- `heuristic_summarization_only`
- `context_inputs`
- `context_usage`
- `call_8_reasoning`
- `recommendation`
- `summary`

`context_inputs` required sections:

- `target_project`
- `earth_sweep`
- `cross_project_context[]` under key `cross_project_context`
- `constraint_candidates[]` under key `constraint_candidates`

`context_usage` required keys:

- `target_project_context_used`
- `earth_sweep_context_used`
- `cross_project_context_used`
- `candidate_ids_considered`
- `classifications_present`
- `cross_project_projects_considered`
- `cross_project_refs_used`
- `evidence_refs_used`

`call_8_reasoning` required keys:

- `call_sequence`
- `reasoning_focus`
- `classification_reasoning`
- `hard_constraint_count`
- `soft_preference_count`
- `speculative_idea_count`

Each `classification_reasoning[]` row must include:

- `candidate_id`
- `summary`
- `classification`
- `classification_rationale`
- `planner_implication`
- `source_output_refs[]`
- `evidence_refs[]`

`recommendation` required keys:

- `decision`
- `rationale`
- `confidence`
- `evidence_refs[]`
- `planner_contract`
- `open_risks` (`open_risks[]`)

`planner_contract` required keys:

- `classification_is_explicit`
- `hard_constraints` (`hard_constraints[]`)
- `soft_preferences` (`soft_preferences[]`)
- `speculative_ideas` (`speculative_ideas[]`)

Each classified row under `hard_constraints[]`, `soft_preferences[]`, and `speculative_ideas[]` carries:

- `candidate_id`
- `summary`
- `planner_implication`
- `classification_rationale`
- `source_output_refs[]`
- `evidence_refs[]`

`call_metadata` required keys:

- `reproducibility`
- `canonical_input_sha256`
- `reproducible_call_id`
- `canonical_input`
- `processing_input_sha256`
- `processing_call_id`
- `canonical_processing_input`
- `llm_call_trace_schema_version`
- `llm_call_trace_path`
- `llm_call_trace_sha256`
- `llm_call_trace_rows[]` under key `llm_call_trace_rows`

Each `llm_call_trace_rows[]` row must include the keys:

- `call_objective`
- `input_refs`
- `output_refs`
- `handoff_summary`

Trace guarantees:

- `output_refs[]` must keep the primary Call-8 reasoning output plus explicit replay-stable bucket outputs for `call_8_hard_constraints`, `call_8_soft_preferences`, `call_8_speculative_ideas`, and `call_8_planner_contract`.
- `handoff_summary` must state that the call separated hard constraints, soft preferences, and speculative ideas before planner reuse.

## Executable artifacts

- Fixture input: `examples/fixtures/call-8-constraint-classification-reasoning.json`
- Contract test: `tests/contracts/test_call-8-constraint-classification-reasoning.py`
- Canonical sample output: `strategy/current/samples/REQ-033_call-8-constraint-classification-reasoning.sample.json`
- Replay-stable trace artifact path: `strategy/current/llm_call_trace.jsonl`

## Sample structure

The canonical sample output is stored at:

`strategy/current/samples/REQ-033_call-8-constraint-classification-reasoning.sample.json`

Its top-level shape is:

```json
{
  "schema_version": "req-033.call-8-constraint-classification-reasoning.v1",
  "requirement_id": "REQ-033",
  "call_8_constraint_classification_reasoning_entrypoint": {},
  "processing_behavior": {
    "context_inputs": {},
    "context_usage": {},
    "call_8_reasoning": {
      "classification_reasoning": []
    },
    "recommendation": {
      "planner_contract": {
        "hard_constraints": [],
        "soft_preferences": [],
        "speculative_ideas": []
      },
      "open_risks": []
    }
  },
  "call_metadata": {
    "canonical_input_sha256": "",
    "processing_input_sha256": "",
    "llm_call_trace_path": "strategy/current/llm_call_trace.jsonl",
    "llm_call_trace_rows": []
  }
}
```
