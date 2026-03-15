# REQ-021 Evidence Provenance Ledger for Context

Status: Implemented  
Requirement ID: `REQ-021`

## Scope anchors

This contract is limited to:

- Strategy context sweep outputs that contain evidence-backed context claims.
- A provenance ledger that maps each key context claim to concrete source artifacts (`source_artifact_refs`).
- Deterministic, reproducible call metadata derived from canonicalized invocation + context inputs.

This contract explicitly does **not** introduce new strategy packet sections, orchestration managers, or gates outside the ledger fields described below.

## Entrypoint surface

Implementation file: `scripts/strategy_context_sweep.py`

Builder function:

- `build_req_021_evidence_provenance_ledger_for_context(...) -> dict`

Validator function:

- `validate_req_021_evidence_provenance_ledger_for_context(payload) -> list[str]`

## Payload contract

Top-level required keys:

- `schema_version` (must equal `req-021.evidence-provenance-ledger-for-context.v1`)
- `requirement_id` (must equal `REQ-021`)
- `evidence_provenance_ledger_for_context` (object)
- `call_metadata` (object)

`evidence_provenance_ledger_for_context` required keys:

- `ledger_scope` (must equal `strategy_context_sweep.processing_behavior`)
- `claim_count` (integer; must equal `len(context_claims)`)
- `context_claims` (list)
- `artifact_refs_index` (sorted unique list; must equal union of claim sources)

Each `context_claims[]` entry required keys:

- `claim_id` (stable deterministic id; `claim-` + 12 hex chars)
- `claim_key` (string key identifying the context claim surface)
- `source_artifact_refs` (sorted unique list of artifact refs supporting the claim)

`call_metadata` required keys:

- `reproducibility` (must equal `deterministic-input-fingerprint`)
- `canonical_input_sha256` (sha256 over `canonical_input`)
- `reproducible_call_id` (must equal `req021-` + first 16 chars of digest)
- `canonical_input` (normalized invocation anchors + fixed mode fields)
- `processing_input_sha256` (sha256 over `canonical_processing_input`)
- `processing_call_id` (must equal `req021-processing-` + first 16 chars of digest)
- `canonical_processing_input` (normalized context inputs used to build evidence-backed claims)

## Sample structure

Sample artifact path:

- `strategy/current/samples/REQ-021_evidence-provenance-ledger-for-context.sample.json`

Sample fixture path:

- `examples/fixtures/evidence-provenance-ledger-for-context.json`

Sample JSON shape:

```json
{
  "schema_version": "req-021.evidence-provenance-ledger-for-context.v1",
  "requirement_id": "REQ-021",
  "evidence_provenance_ledger_for_context": {
    "ledger_scope": "strategy_context_sweep.processing_behavior",
    "claim_count": 3,
    "context_claims": [
      {
        "claim_id": "claim-0123456789ab",
        "claim_key": "processing_behavior.recommendation.decision",
        "source_artifact_refs": [
          "reports/earth/sweeps/2026-03-14/portfolio.json",
          "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json"
        ]
      }
    ],
    "artifact_refs_index": [
      "reports/earth/sweeps/2026-03-14/portfolio.json",
      "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json"
    ]
  },
  "call_metadata": {
    "reproducibility": "deterministic-input-fingerprint",
    "canonical_input_sha256": "sha256hex",
    "reproducible_call_id": "req021-0123456789abcdef",
    "canonical_input": {
      "earth_root": "/abs/path/to/Earth",
      "execution_mode": "long-thinking",
      "output_root": "/abs/path/to/output",
      "revision_identity": "git-or-runtime-revision-id",
      "runtime_mode": "llm-first",
      "target_project_root": "/abs/path/to/project"
    },
    "processing_input_sha256": "sha256hex",
    "processing_call_id": "req021-processing-0123456789abcdef",
    "canonical_processing_input": {
      "target_project_evidence_refs": [],
      "earth_sweep_evidence_refs": [],
      "cross_project_context": [],
      "candidate_recommendations": []
    }
  }
}
```

