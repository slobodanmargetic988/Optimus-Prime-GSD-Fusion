# REQ-045 Alternative Strategic Scenario Generator

Status: Implemented  
Requirement ID: `REQ-045`

## Scope anchors

This contract is limited to:

- Generating alternative strategic scenarios only when uncertainty or conflict is high.
- Requiring each scenario branch to expose comparative tradeoffs.
- Requiring each scenario branch to expose explicit trigger conditions for choosing that branch.
- Keeping the surface bounded to the scenario generator contract only; no new managers, gates, or packet sections are introduced here.

## Entrypoint surface

Implementation file: `scripts/strategy_llm_pipeline.py`

Builder function:

- `build_req_045_alternative_strategic_scenario_generator(...) -> dict`

Validator function:

- `validate_req_045_alternative_strategic_scenario_generator(payload) -> list[str]`

CLI surface:

- `python3 scripts/strategy_llm_pipeline.py --input-json <path> --output-json <path> --json-pretty`

## Input surface (builder)

Invocation anchors:

- `target_project_root` (absolute path)
- `earth_root` (absolute path)
- `output_root` (absolute path)
- `revision_identity` (non-empty string)
- `strategy_goal` (non-empty string)

Trigger inputs:

- `generated_at_utc` (required ISO-8601 UTC timestamp string)
- `uncertainty_score` (required number in `0.0..1.0`)
- `conflict_score` (required number in `0.0..1.0`)
- `uncertainty_signals` (optional list of strings)
- `conflict_signals` (optional list of strings)

Evidence inputs:

- `target_project_evidence_refs` (optional list of strings)
- `earth_sweep_evidence_refs` (optional list of strings)

Scenario inputs:

- `scenario_candidates` (required list with at least 2 objects)
  - `branch_key` (required lower-case slug)
  - `label` (required non-empty string)
  - `summary` (required non-empty string)
  - `comparative_tradeoffs` (required non-empty list)
    - `dimension` (required non-empty string)
    - `position` (required; one of: `advantaged`, `balanced`, `constrained`)
    - `summary` (required non-empty string)
  - `trigger_conditions` (required non-empty list)
    - `condition_id` (required slug matching `cond.<name>`)
    - `signal` (required non-empty string)
    - `operator` (required; one of: `gte`, `lte`, `eq`, `present`)
    - `value` (required for `gte|lte|eq`, must be `null` for `present`)
    - `summary` (required non-empty string)
  - `evidence_refs` (required non-empty list of strings)

## Trigger behavior

- Alternative generation is considered required when either:
  - `uncertainty_score >= 0.7`
  - `conflict_score >= 0.7`
- The payload records this result in:
  - `alternative_strategic_scenario_generator.scenario_trigger.triggered`
  - `alternative_strategic_scenario_generator.comparative_summary.requires_alternative_generation`
  - `processing_behavior.recommendation.decision`

## Payload contract

Top-level required keys:

- `schema_version` (must equal `req-045.alternative-strategic-scenario-generator.v1`)
- `requirement_id` (must equal `REQ-045`)
- `analysis_type` (must equal `alternative_strategic_scenario_generator`)
- `alternative_strategic_scenario_generator` (object)
- `processing_behavior` (object)
- `call_metadata` (object)

`alternative_strategic_scenario_generator` required keys:

- Invocation anchors (`runtime_mode`, `execution_mode`, roots, `revision_identity`, `strategy_goal`)
- `generated_at_utc`
- `scenario_trigger`
- `evidence_refs`
- `scenarios`
- `comparative_summary`

`alternative_strategic_scenario_generator.scenarios[]` required keys:

- `scenario_id` (must equal `scenario.<branch_key>`)
- `branch_key`
- `label`
- `summary`
- `comparative_tradeoffs`
- `trigger_conditions`
- `evidence_refs`

`processing_behavior.recommendation` required keys:

- `decision` (one of: `generate-alternatives`, `single-path-sufficient`)
- `rationale`
- `confidence` (one of: `high`, `medium`, `low`)
- `preferred_branch`
- `fallback_branch`
- `evidence_refs`

`call_metadata` must preserve deterministic digests for:

- `canonical_input`
- `canonical_processing_input`
- `canonical_input_sha256`
- `processing_input_sha256`
- Reproducible call IDs derived from those digests

## Sample structure

Sample artifact path:

- `strategy/current/samples/REQ-045_alternative-strategic-scenario-generator.sample.json`

Fixture path (builder + expected payload):

- `examples/fixtures/alternative-strategic-scenario-generator.json`
