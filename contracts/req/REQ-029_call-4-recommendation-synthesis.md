# REQ-029: Call-4 Recommendation Synthesis

Status: Implemented  
Requirement ID: `REQ-029`

## Scope anchors

This requirement is limited to the Call-4 synthesis surface that:

- ingests candidate recommendations from earlier call outputs,
- synthesizes deterministic structured recommendation drafts, and
- enforces the Call-4 recommendation ID schema plus required `rationale`, `impact`, and `risk` fields.

Out of scope:

- new packet sections outside recommendation synthesis,
- new managers or gates,
- net-new orchestration behavior, and
- recommendation fields unrelated to the required Call-4 draft anchors.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_029_call_4_recommendation_synthesis(...) -> dict`

Validator:

- `validate_req_029_call_4_recommendation_synthesis(payload) -> list[str]`

CLI:

```bash
python3 scripts/strategy_llm_pipeline.py \
  --input-json examples/fixtures/call-4-recommendation-synthesis.json \
  --output-json strategy/current/samples/REQ-029_call-4-recommendation-synthesis.sample.json \
  --json-pretty
```

Documented sample structure:

- `strategy/current/samples/REQ-029_call-4-recommendation-synthesis.sample.json`

## Input contract

Accepted builder input shape:

```json
{
  "analysis_type": "call_4_recommendation_synthesis",
  "call_id": "call-4",
  "checked_at_utc": "2026-03-16T10:45:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion"
  },
  "earlier_call_outputs": [
    {
      "call_id": "call-1",
      "output_ref": "REQ-026::call::call-1::output::situational_analysis",
      "summary": "Call-1 established the bounded assessment and surfaced unknown-resolution work.",
      "candidate_recommendations": [
        {
          "candidate_id": "unknown-resolution",
          "summary": "Carry explicit unknown resolution into the next planning pass before execution scope widens.",
          "rationale": "Call-1 marked unresolved planning and runtime unknowns that later calls depend on.",
          "impact": "Keeps downstream execution choices grounded in refreshed planning and verification evidence.",
          "risk": "Skipping the unknown handoff can freeze later calls around stale branch-head assumptions.",
          "evidence_refs": [
            "reports/optimus-prime/planning/TASK_EXECUTION_STATE.json",
            "reports/optimus-prime/planning/VERIFICATION.md"
          ]
        }
      ]
    }
  ]
}
```

Rules:

- `analysis_type` must be `call_4_recommendation_synthesis`.
- `call_id` must be `call-4`.
- `target_project.project_id` is required.
- `earlier_call_outputs[]` must be a non-empty array of earlier call material.
- `earlier_call_outputs[].call_id` must be one of `call-1`, `call-2`, or `call-3`, and each source call may appear only once.
- `earlier_call_outputs[].output_ref` and `summary` are required.
- `earlier_call_outputs[].candidate_recommendations[]` must be non-empty.
- Each candidate row must include:
  - `candidate_id` using the slug schema `[a-z0-9]+(-[a-z0-9]+)*`
  - `summary`
  - `rationale`
  - `impact`
  - `risk`
  - non-empty `evidence_refs[]`
- Candidate rows may optionally include:
  - `recommendation_scope` = `local|cross-project` with default `local`
  - `project_id` required when `recommendation_scope` is `cross-project`
  - `requires_earth_evidence` with default `true` for `cross-project` rows and `false` otherwise
- Cross-project candidates without Earth-sweep evidence refs are not emitted as drafts; they are recorded in `open_risks[]` with `reason_code = missing_earth_sweep_evidence_refs`.

## Output contract

Top-level required keys:

- `ok`
- `tool`
- `tool_version`
- `schema_version`
- `requirement_id`
- `analysis_type`
- `call_id`
- `checked_at_utc`
- `recommendation_synthesis`
- `processing_behavior`
- `source`

`recommendation_synthesis` required sections:

- `target_project.project_id`
- `source_calls[]`
- `recommendation_drafts[]`
- `open_risks[]`
- `summary`
  - `source_call_count`
  - `candidate_recommendation_count`
  - `draft_count`
  - `open_risk_count`

`recommendation_drafts[]` row shape:

```json
{
  "recommendation_id": "rec-call-4-call-2-verification-refresh",
  "source_call_id": "call-2",
  "source_output_ref": "REQ-027::call::call-2::output::constraint_refinement",
  "source_candidate_id": "verification-refresh",
  "summary": "Refresh verification evidence on the working branch before promoting any follow-up packet.",
  "rationale": "Call-2 narrowed the main branch-head question to current verification freshness.",
  "impact": "Prevents recommendation drafts from citing stale runtime outcomes.",
  "risk": "Recommendation promotion may drift from the actual branch state if verification is not rerun.",
  "evidence_refs": [
    "reports/optimus-prime/planning/STATE.json",
    "reports/optimus-prime/planning/VERIFICATION.md"
  ]
}
```

Normalization rules:

- `recommendation_id` is synthesized deterministically as `rec-call-4-{source_call_id}-{candidate_id}`.
- `recommendation_id` values must be unique.
- Every emitted draft must retain the required `rationale`, `impact`, and `risk` fields.
- Cross-project candidates requiring Earth evidence must include at least one `reports/earth/...` ref in `evidence_refs[]` or be emitted as open risks instead of drafts.
- `summary.source_call_count` must equal `len(source_calls)`.
- `summary.candidate_recommendation_count` must equal `len(recommendation_drafts) + len(open_risks)`.
- `summary.draft_count` must equal `len(recommendation_drafts)`.
- `summary.open_risk_count` must equal `len(open_risks)`.

`processing_behavior` required sections:

- `strategy` = `call-4-recommendation-synthesis`
- `reasoning_mode` = `deterministic-recommendation-synthesis`
- `strict_evidence_discipline` = `true`
- `context_inputs.earlier_call_outputs[]`
- `context_usage`
  - `cross_project_context_used`
  - `cross_project_project_ids_used`
  - `earth_sweep_evidence_refs_used`
  - `target_project_evidence_refs_used`
  - `evidence_refs_used`
  - `recommendation_ids_emitted`
  - `open_risk_ids_emitted`
- `synthesis_rules`
  - `recommendation_id_schema` = `rec-call-4-{source_call_id}-{candidate_id}`
  - `required_draft_fields`
  - `allowed_source_call_ids`

`source` required fields:

- `earlier_call_output_count`
- `candidate_recommendation_count`
- `draft_count`
- `open_risk_count`
- `evidence_ref_count`
