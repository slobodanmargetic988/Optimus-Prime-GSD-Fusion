# REQ-032 Call-7 Blocker And Risk Policy Reasoning

Status: Implemented  
Requirement ID: `REQ-032`

## Scope anchors

This requirement surface is limited to:

- Reasoning over Call-7 blocker candidates with deterministic escalation triggers and fallback sequencing paths.
- Mapping each blocker to bounded risk policy decisions without inventing new packet sections, managers, or orchestration gates.
- Preserving replay-stable evidence refs, call metadata, and trace rows for Call-7 blocker promotion.

No net-new packet sections, managers, or orchestration gates are introduced by this contract.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_032_call_7_blocker_and_risk_policy_reasoning(...) -> dict`

Validator:

- `validate_req_032_call_7_blocker_and_risk_policy_reasoning(payload) -> list[str]`

## Input contract

The builder expects:

- `strategy_goal` (required)
- `evidence_refs[]` (required)
- `blocker_candidates[]` (required)
- `risk_policy_candidates[]` (required)
- Optional context inputs:
  - `target_project_root`
  - `earth_root`
  - `output_root`
  - `revision_identity`
  - `target_project_evidence_refs[]`
  - `earth_sweep_evidence_refs[]`
  - `cross_project_context[]`
  - `strategic_claims[]`

Each `blocker_candidates[]` row must include:

- `blocker_id`
- `summary`
- `severity`
- `affected_project_ids[]`
- `evidence_refs[]`
- `escalation_triggers[]`
- `fallback_paths[]`

Each `escalation_triggers[]` row must include:

- `trigger_id`
- `project_id`
- `summary`
- `fire_when`
- `urgency`
- `evidence_refs[]`

Each `fallback_paths[]` row must include:

- `fallback_id`
- `sequence`
- `summary`
- `activates_when`
- `next_step`
- `evidence_refs[]`

Each `risk_policy_candidates[]` row must include:

- `policy_id`
- `blocker_id`
- `policy_decision`
- `rationale`
- `preferred_fallback_ids[]`
- `escalation_trigger_ids[]`
- `evidence_refs[]`

Behavior guarantees:

- Every promoted blocker policy remains tied to one declared `blocker_id`.
- `preferred_fallback_ids[]` and `escalation_trigger_ids[]` must resolve to the referenced blocker's declared fallback paths and escalation triggers.
- Call-7 output always includes escalation trigger rows and fallback sequencing paths when policy decisions require them.
- Strategic claims are optional, but when supplied they must remain citation-complete and contradiction-free before REQ-032 can promote a clean decision.

## Output contract

Top-level required keys:

- `schema_version` (must be `req-032.call-7-blocker-and-risk-policy-reasoning.v1`)
- `requirement_id` (must be `REQ-032`)
- `call_7_blocker_and_risk_policy_reasoning_entrypoint`
- `processing_behavior`
- `call_metadata`

`call_7_blocker_and_risk_policy_reasoning_entrypoint` required keys:

- `runtime_mode`
- `execution_mode`
- `target_project_root`
- `earth_root`
- `output_root`
- `revision_identity`
- `strategy_goal`
- `call_sequence` (must be `7`)

`processing_behavior` required keys:

- `strategy`
- `reasoning_mode`
- `strict_evidence_discipline`
- `heuristic_summarization_only`
- `context_inputs`
- `context_usage`
- `call_7_reasoning`
- `recommendation`
- `summary`

`context_inputs` required sections:

- `target_project`
- `earth_sweep`
- `cross_project_context[]` under key `cross_project_context`
- `blocker_candidates[]` under key `blocker_candidates`
- `risk_policy_candidates[]` under key `risk_policy_candidates`
- `strategic_claims[]` under key `strategic_claims`

`context_usage` required keys:

- `target_project_context_used`
- `earth_sweep_context_used`
- `cross_project_context_used`
- `blocker_ids_considered`
- `policy_ids_considered`
- `fallback_ids_considered`
- `cross_project_projects_considered`
- `escalation_project_ids`
- `cross_project_refs_used`
- `evidence_refs_used`

`call_7_reasoning` required keys:

- `call_sequence`
- `reasoning_focus`
- `blocker_reasoning`
- `blocker_count`
- `policy_count`
- `escalation_trigger_count`
- `fallback_path_count`

Each `blocker_reasoning[]` row must include:

- `blocker_id`
- `summary`
- `severity`
- `affected_project_ids[]`
- `linked_context_projects[]`
- `evidence_refs[]`
- `escalation_triggers[]`
- `fallback_paths[]`
- `applicable_policies[]`

`blocker_reasoning[]` carries the nested keys `escalation_triggers`, `fallback_paths`, and `applicable_policies`.

`recommendation` required keys:

- `decision`
- `rationale`
- `confidence`
- `evidence_refs[]`
- `escalation_triggers[]` under key `escalation_triggers`
- `fallback_sequence[]` under key `fallback_sequence`
- `open_risks[]` under key `open_risks`

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

## Executable artifacts

- Fixture input: `examples/fixtures/call-7-blocker-and-risk-policy-reasoning.json`
- Contract test: `tests/contracts/test_call-7-blocker-and-risk-policy-reasoning.py`
- Canonical sample output: `strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json`
- Replay-stable trace artifact path: `strategy/current/llm_call_trace.jsonl`

## Sample structure

The canonical sample output is stored at:

`strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json`

Its top-level shape is:

```json
{
  "schema_version": "req-032.call-7-blocker-and-risk-policy-reasoning.v1",
  "requirement_id": "REQ-032",
  "call_7_blocker_and_risk_policy_reasoning_entrypoint": {},
  "processing_behavior": {
    "context_inputs": {
      "blocker_candidates": [],
      "risk_policy_candidates": []
    },
    "context_usage": {
      "blocker_ids_considered": [],
      "policy_ids_considered": [],
      "fallback_ids_considered": [],
      "escalation_project_ids": [],
      "evidence_refs_used": []
    },
    "call_7_reasoning": {
      "blocker_reasoning": [
        {
          "blocker_id": "",
          "escalation_triggers": [],
          "fallback_paths": [],
          "applicable_policies": []
        }
      ]
    },
    "recommendation": {
      "escalation_triggers": [],
      "fallback_sequence": [],
      "open_risks": []
    }
  },
  "call_metadata": {}
}
```
