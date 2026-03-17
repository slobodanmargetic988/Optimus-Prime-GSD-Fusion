# REQ-035: Evidence Citation Discipline In Reasoning Calls

## Purpose
Define the contract and data-model surface that enforces evidence citation discipline across reasoning call outputs before recommendations are promoted.

## Scope anchors
- Surface in scope: `scripts/strategy_llm_pipeline.py`.
- In scope (REQ-035):
  - Every strategic claim in reasoning call outputs must reference evidence IDs from the context provenance ledger.
  - Claims with missing or invalid citations are flagged.
  - Flagged claims are excluded from the final recommendation set.
- Out of scope (REQ-035): net-new packet sections, managers, or orchestration gates outside this citation-discipline contract surface.

## Interface surface
Builder:
- `build_req_035_evidence_citation_discipline_in_reasoning_calls(payload) -> dict`

Validator:
- `validate_req_035_evidence_citation_discipline_in_reasoning_calls(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_llm_pipeline.py --input-json <path|->`

## Input contract
`strategy_llm_pipeline.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "evidence_citation_discipline_in_reasoning_calls",
  "now_utc": "2026-03-16T12:00:00Z",
  "context_provenance_ledger": {
    "ledger_requirement_id": "REQ-021",
    "ledger_scope": "strategy_context_sweep.processing_behavior",
    "evidence_ids": ["claim-<id>"]
  },
  "reasoning_calls": [
    {
      "call_id": "call-2",
      "strategic_claims": [
        {
          "strategic_claim_id": "sc.<id>",
          "summary": "Human-facing strategic claim",
          "evidence_ids": ["claim-<id>"],
          "recommendation": {
            "recommendation_id": "rec.<id>",
            "summary": "Recommendation summary",
            "rationale": "Why this recommendation follows",
            "confidence_tag": "high"
          }
        }
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `evidence_citation_discipline_in_reasoning_calls`.
- `context_provenance_ledger.ledger_requirement_id` must be `REQ-021`.
- `context_provenance_ledger.evidence_ids[]` must be non-empty REQ-021 claim IDs (`claim-<id>`).
- `reasoning_calls[]` and each `strategic_claims[]` list are required and non-empty.
- `recommendation.recommendation_id` must be globally unique across all strategic claims.
- Strict builder mode rejects unexpected keys to keep scope bounded to REQ-035 anchors.

## Output contract
REQ-035 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- normalized inputs: `context_provenance_ledger`, `reasoning_calls`
- citation enforcement result: `evidence_citation_discipline`
- bounded totals: `totals`

`evidence_citation_discipline` contains:
- `strategic_claim_citation_status[]`: citation status per strategic claim (`cited|flagged`)
- `flagged_claims[]`: claims excluded from promotion with explicit reason codes
- `final_recommendations[]`: recommendations derived only from cited claims

Flag semantics:
- `uncited_strategic_claim`: claim has no evidence IDs.
- `evidence_id_not_in_context_provenance_ledger`: claim evidence includes IDs not present in `context_provenance_ledger.evidence_ids`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/evidence-citation-discipline-in-reasoning-calls.json`
- Contract tests: `tests/contracts/test_evidence-citation-discipline-in-reasoning-calls.py`
- Output sample: `strategy/current/samples/REQ-035_evidence-citation-discipline-in-reasoning-calls.sample.json`

The structure in `strategy/current/samples/REQ-035_evidence-citation-discipline-in-reasoning-calls.sample.json`
is the canonical contract shape for REQ-035.
