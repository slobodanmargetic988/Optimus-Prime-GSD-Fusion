# REQ-044: Recommendation Omission Detector

Status: Implemented  
Requirement ID: `REQ-044`

## Scope anchors

This requirement is limited to detecting recommendation-class omissions that are required by:

- target-project mission anchors, and
- ecosystem need anchors.

In scope behavior:

- detect missing recommendation classes against mission + ecosystem requirements,
- mark critical cross-project class omissions explicitly,
- detect local-only candidate plans when critical cross-project classes are required,
- prevent promotion by returning `resolve-strategy-gaps` when critical cross-project obligations are missing.

Out of scope:

- new managers,
- new orchestration gates,
- new packet sections outside this omission-detector contract surface.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_044_recommendation_omission_detector(...) -> dict`

Validator:

- `validate_req_044_recommendation_omission_detector(payload) -> list[str]`

CLI:

```bash
python3 scripts/strategy_llm_pipeline.py \
  --input-json examples/fixtures/recommendation-omission-detector.json \
  --output-json strategy/current/samples/REQ-044_recommendation-omission-detector.sample.json \
  --json-pretty
```

Note: The fixture file stores `input` and `expected_contract_anchors`; pass the `input` object to the CLI.

## Input contract

Builder input anchors:

- invocation anchors:
  - `target_project_root`
  - `earth_root`
  - `output_root`
  - `revision_identity`
  - `strategy_goal`
  - `call_id`
  - `checked_at_utc`
- evidence context:
  - `target_project_evidence_refs[]`
  - `earth_sweep_evidence_refs[]`
  - `cross_project_context[]`
- omission-detector anchors:
  - `mission_required_recommendation_classes[]`
  - `ecosystem_required_recommendation_classes[]`
  - `candidate_recommendations[]`

`mission_required_recommendation_classes[]` and `ecosystem_required_recommendation_classes[]` row shape:

- `class_id` matching `^class\.[a-z0-9]+(?:-[a-z0-9]+)*$`
- `summary`
- `required_scope` in `local | cross-project`
- `project_id` required when `required_scope` is `cross-project`
- `critical` boolean (defaults to `true` for cross-project rows when omitted)
- `evidence_refs[]` non-empty

`candidate_recommendations[]` row shape:

- `recommendation_id` matching `^rec\.[a-z0-9]+(?:-[a-z0-9]+)*$`
- `recommendation_class_id` matching `^class\.[a-z0-9]+(?:-[a-z0-9]+)*$`
- `summary`
- `rationale`
- `recommendation_scope` in `local | cross-project`
- `project_id` required when `recommendation_scope` is `cross-project`
- `requires_earth_evidence` boolean
- `evidence_refs[]` non-empty
- `next_step`

## Output contract

Top-level keys:

- `schema_version`: `req-044.recommendation-omission-detector.v1`
- `requirement_id`: `REQ-044`
- `analysis_type`: `recommendation_omission_detector`
- `call_id`
- `checked_at_utc`
- `processing_behavior`
- `call_metadata`

`processing_behavior` keys:

- `strategy`: `recommendation-omission-detector`
- `reasoning_mode`: `deterministic-coverage-guard`
- `strict_evidence_discipline`: `true`
- `context_inputs`
- `context_usage`
- `recommendation`

`processing_behavior.recommendation` keys:

- `decision`
- `rationale`
- `confidence`
- `evidence_refs[]`
- `recommended_actions[]`
- `cross_project_obligations[]`
- `omitted_recommendation_classes[]`
- `open_risks[]`

`omitted_recommendation_classes[]` row shape:

- `class_id`
- `anchor_sources[]` in `mission | ecosystem`
- `required_scope`
- `project_id`
- `critical`
- `summary`
- `reason_code`
- `required_evidence_refs[]`

Behavior guarantees:

- Omitted required classes are always emitted under `omitted_recommendation_classes[]`.
- Missing critical cross-project classes are surfaced in `context_usage.missing_critical_cross_project_class_ids[]`.
- Local-only plans are flagged in `context_usage.local_only_plan_detected`.
- When critical cross-project obligations remain missing, decision is `resolve-strategy-gaps`.

## Executable artifacts

- Fixture input + anchor expectations: `examples/fixtures/recommendation-omission-detector.json`
- Contract tests: `tests/contracts/test_recommendation-omission-detector.py`
- Canonical sample output: `strategy/current/samples/REQ-044_recommendation-omission-detector.sample.json`

## Sample structure

`strategy/current/samples/REQ-044_recommendation-omission-detector.sample.json` is documented to include:

- deterministic requirement metadata,
- normalized mission/ecosystem required class inputs,
- omission detector context usage metrics,
- recommendation output with omissions, obligations, and open risks,
- deterministic call metadata and one REQ-044 call-trace row.
