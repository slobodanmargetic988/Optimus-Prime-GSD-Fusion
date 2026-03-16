# REQ-028 Call-3 Gap And Opportunity Reasoning

Status: Implemented  
Requirement ID: `REQ-028`

## Scope anchors

This contract is limited to:

- Reasoning in Call-3 about strategic gaps that are not visible from the target project's local mission alone.
- Tying every promoted opportunity to an ecosystem-level benefit and explicit dependency effects.
- Preserving deterministic grouping from ecosystem-visible gaps to linked opportunities.

No net-new packet sections, managers, or orchestration gates are introduced by this contract.

## Entrypoint surface

Implementation file: `scripts/strategy_llm_pipeline.py`

Builder function:

- `build_req_028_call_3_gap_and_opportunity_reasoning(...) -> dict`

Validator function:

- `validate_req_028_call_3_gap_and_opportunity_reasoning(payload) -> list[str]`

## Payload contract

Top-level required keys:

- `schema_version` (must equal `req-028.call-3-gap-and-opportunity-reasoning.v1`)
- `requirement_id` (must equal `REQ-028`)
- `call_3_gap_and_opportunity_reasoning_entrypoint` (object)
- `processing_behavior` (object)
- `call_metadata` (object)

`call_3_gap_and_opportunity_reasoning_entrypoint` required keys:

- `runtime_mode` (must equal `llm-first`)
- `execution_mode` (must equal `long-thinking`)
- `target_project_root` (absolute path)
- `earth_root` (absolute path)
- `output_root` (absolute path)
- `revision_identity` (non-empty string)
- `strategy_goal` (non-empty string)
- `call_sequence` (must equal `3`)

`processing_behavior` required keys:

- `strategy` (must equal `call-3-gap-and-opportunity-reasoning`)
- `reasoning_mode` (must equal `long-thinking`)
- `strict_evidence_discipline` (must be `true`)
- `heuristic_summarization_only` (must be `false`)
- `context_inputs`
- `context_usage`
- `call_3_reasoning`
- `summary`

`context_inputs.target_project` required keys:

- `project_root` (must match `target_project_root`)
- `mission_summary`
- `evidence_refs`

`context_inputs.earth_sweep` required keys:

- `earth_root` (must match `earth_root`)
- `evidence_refs` (must be non-empty)

`context_inputs.gap_candidates[]` required keys:

- `gap_id`
- `summary`
- `visibility_rationale`
- `local_mission_blind_spot`
- `evidence_refs` (must include Earth-sweep evidence)

`context_inputs.opportunity_candidates[]` required keys:

- `opportunity_id`
- `gap_id` (must reference a declared `gap_id`)
- `summary`
- `ecosystem_level_benefit`
- `dependency_effects[]`
- `evidence_refs` (must include Earth-sweep evidence)

Each `dependency_effects[]` row must include:

- `project_id`
- `effect_summary`
- `impact`

`context_usage` required keys:

- `target_project_context_used`
- `earth_sweep_context_used`
- `gap_ids_considered`
- `opportunity_ids_considered`
- `evidence_refs_used`

`call_3_reasoning` required keys:

- `call_sequence` (must equal `3`)
- `reasoning_focus` (must equal `strategic-gaps-and-opportunities-beyond-local-mission`)
- `gap_reasoning`
- `gap_count`
- `opportunity_count`

Each `gap_reasoning[]` row must include:

- `gap_id`
- `summary`
- `visibility_rationale`
- `local_mission_blind_spot`
- `evidence_refs`
- `opportunities`

Each `opportunities[]` row must include:

- `opportunity_id`
- `summary`
- `ecosystem_level_benefit`
- `dependency_effects` (`dependency_effects[]`)
- `evidence_refs`

`call_metadata` required keys:

- `reproducibility`
- `canonical_input_sha256`
- `reproducible_call_id`
- `canonical_input`
- `processing_input_sha256`
- `processing_call_id`
- `canonical_processing_input`

## Samples and fixtures

Sample artifact path:

- `strategy/current/samples/REQ-028_call-3-gap-and-opportunity-reasoning.sample.json`

Fixture path:

- `examples/fixtures/call-3-gap-and-opportunity-reasoning.json`

## Sample structure

The canonical sample output is stored at:

`strategy/current/samples/REQ-028_call-3-gap-and-opportunity-reasoning.sample.json`

Its top-level shape is:

```json
{
  "schema_version": "req-028.call-3-gap-and-opportunity-reasoning.v1",
  "requirement_id": "REQ-028",
  "call_3_gap_and_opportunity_reasoning_entrypoint": {},
  "processing_behavior": {
    "context_inputs": {
      "gap_candidates": [],
      "opportunity_candidates": []
    },
    "context_usage": {
      "gap_ids_considered": [],
      "opportunity_ids_considered": [],
      "evidence_refs_used": []
    },
    "call_3_reasoning": {
      "gap_reasoning": [
        {
          "gap_id": "",
          "opportunities": [
            {
              "opportunity_id": "",
              "ecosystem_level_benefit": "",
              "dependency_effects": []
            }
          ]
        }
      ]
    }
  },
  "call_metadata": {
    "canonical_input_sha256": "",
    "processing_input_sha256": ""
  }
}
```
