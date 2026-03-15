# REQ-021 Evidence Provenance Ledger For Context

Status: Implemented  
Requirement ID: `REQ-021`  
Owner surface: `scripts/strategy_context_sweep.py`

## Purpose

Strategy context sweep must maintain a deterministic provenance ledger that maps every key context claim to concrete source artifacts and evidence references.

This requirement hardens replay and failure-path diagnostics by:

1. Preserving a claim-to-source-artifact ledger for audit.
2. Emitting explicit reason codes and evidence refs when stale Earth-sweep artifacts or missing docs are detected.
3. Serializing a replay-stable context bundle for repeated runs.

## Input Contract

Builder:

- `build_req_021_evidence_provenance_ledger_for_context(...) -> dict`

Required anchors:

- `target_project_root`
- `earth_root`
- `output_root`
- `revision_identity`

Optional context anchors:

- `target_project_evidence_refs[]`
- `earth_sweep_evidence_refs[]`
- `cross_project_context[]`
- `earth_sweep_source_artifacts[]`
- `required_context_documents[]`
- `context_claims[]`

Every `context_claims[]` row must include:

- `claim_id`
- `claim_text`
- `source_artifact_refs[]`

## Output Contract

Top-level required keys:

- `schema_version` (must be `req-021.evidence-provenance-ledger-for-context.v1`)
- `requirement_id` (must be `REQ-021`)
- `evidence_provenance_ledger_for_context`
- `processing_behavior`
- `provenance_ledger`
- `context_bundle`
- `call_metadata`

`provenance_ledger` required keys:

- `ledger_strategy`
- `claim_count`
- `claims`
- `source_artifact_catalog`
- `claim_ids`
- `evidence_refs`

`context_bundle` required keys:

- `schema_version`
- `canonical_json`
- `sha256`

## Hardening Semantics

REQ-021 keeps explicit deterministic reason-code behavior for:

- stale Earth-sweep source artifacts (`stale_earth_sweep_source_artifact`)
- missing mission docs (`missing_mission_doc`)
- missing scope docs (`missing_scope_doc`)
- missing peer-project docs (`missing_peer_project_doc`)

Each unhappy-path row must preserve deterministic evidence refs for replay diagnostics.

## Sample Structure

Deterministic fixture:

- `examples/fixtures/evidence-provenance-ledger-for-context.json`

Deterministic sample artifact:

- `strategy/current/samples/REQ-021_evidence-provenance-ledger-for-context.sample.json`
