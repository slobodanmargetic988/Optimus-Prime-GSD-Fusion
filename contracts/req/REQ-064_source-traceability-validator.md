# REQ-064: Source Traceability Validator

## Purpose
Define the contract and data-model surface for validating that emitted recommendations and claims stay traceable to concrete source evidence references.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-064):
  - Emit deterministic source traceability payload rows for source references, recommendations, and claims.
  - Enforce that every recommendation and every claim cites at least one evidence reference.
  - Fail validation on broken evidence references that do not resolve to declared source references.
  - Keep output bounded to this requirement's contract surface.
- Out of scope (REQ-064): net-new packet sections, managers, orchestration gates, or strategy behaviors outside source traceability validator handoff.

## Interface surface
Builder:
- `build_req_064_source_traceability_validator(payload) -> dict`

Validator:
- `validate_req_064_source_traceability_validator(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-064 expects:

```json
{
  "analysis_type": "source_traceability_validator",
  "now_utc": "2026-03-16T12:45:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "source_references": [
    {
      "evidence_ref": "src.mission-001",
      "source_path": "mission.md#L1",
      "source_excerpt": "Keep strategy outputs grounded in verifiable evidence from runtime and planning artifacts."
    }
  ],
  "recommendations": [
    {
      "recommendation_id": "rec.harden-source-citations",
      "summary": "Require citations before recommendation emission.",
      "evidence_refs": [
        "src.mission-001"
      ],
      "claims": [
        {
          "claim_id": "claim.citations-required",
          "statement": "Recommendation packets without citations cannot pass source traceability checks.",
          "evidence_refs": [
            "src.mission-001"
          ]
        }
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `source_traceability_validator` when provided.
- `target_project.project_root` must be an absolute path.
- `source_references[]` must contain at least one row with unique `evidence_ref`.
- `recommendations[]` must contain at least one row with unique `recommendation_id`.
- Every `recommendations[].evidence_refs[]` list must be non-empty sorted unique and only reference ids from `source_references[].evidence_ref`.
- Every `recommendations[].claims[]` list must be non-empty.
- Every `recommendations[].claims[].evidence_refs[]` list must be non-empty sorted unique and only reference ids from `source_references[].evidence_ref`.
- Uncited claims fail validation.
- Broken evidence references fail validation.

## Output contract
REQ-064 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- artifact payload: `source_traceability_validator`
- bounded counts: `totals`

`source_traceability_validator` contains:
- `source_references[]`
- `recommendations[]`

Each `source_references[]` row includes:
- `evidence_ref`
- `source_path`
- `source_excerpt`

Each `recommendations[]` row includes:
- `recommendation_id`
- `summary`
- `evidence_refs[]`
- `claims[]`

Each `claims[]` row includes:
- `claim_id`
- `statement`
- `evidence_refs[]`

`totals` includes:
- `source_references`
- `recommendations`
- `claims`
- `recommendation_evidence_links`
- `claim_evidence_links`

Traceability behavior:
- Recommendations must remain citation-backed by concrete source refs.
- Claims must remain citation-backed by concrete source refs.
- Reference ids not present in `source_references` are treated as broken and fail validation.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/source-traceability-validator.json`
- Contract tests: `tests/contracts/test_source-traceability-validator.py`
- Output sample: `strategy/current/samples/REQ-064_source-traceability-validator.sample.json`

The structure in `strategy/current/samples/REQ-064_source-traceability-validator.sample.json`
is the canonical contract shape for REQ-064 and documents:
- `source_traceability_validator.source_references`
- `source_traceability_validator.recommendations`
- `source_traceability_validator.recommendations[].evidence_refs`
- `source_traceability_validator.recommendations[].claims`
- `source_traceability_validator.recommendations[].claims[].evidence_refs`
- `totals`
