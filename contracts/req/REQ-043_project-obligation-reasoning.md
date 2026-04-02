# REQ-043 Project Obligation Reasoning

Status: Implemented  
Requirement ID: `REQ-043`  
Owner Surface: `scripts/strategy_llm_pipeline.py`

## Goal

Reason about what the current project should expose to or consume from other apps.
Each emitted obligation must carry concrete interface/contract expectations and an explicit ownership boundary.

This contract is intentionally scoped to REQ-043 only.

## Input Contract

`build_req_043_project_obligation_reasoning(...)` expects:

```json
{
  "target_project_root": "absolute path",
  "earth_root": "absolute path",
  "output_root": "absolute path",
  "revision_identity": "string",
  "strategy_goal": "string",
  "target_project_profile": {
    "project_id": "string",
    "owner_team": "string"
  },
  "call_id": "string",
  "checked_at_utc": "RFC3339 UTC timestamp",
  "target_project_evidence_refs": ["string"],
  "earth_sweep_evidence_refs": ["string"],
  "cross_project_context": [
    {
      "project_id": "string",
      "project_root": "absolute path",
      "owner_team": "string",
      "evidence_refs": ["string"],
      "context_note": "string"
    }
  ],
  "project_obligation_candidates": [
    {
      "obligation_id": "obl.slug",
      "direction": "expose|consume",
      "summary": "string",
      "counterparty_project_id": "string",
      "interface_id": "string",
      "contract_expectations": {
        "summary": "string",
        "version": "string",
        "transport": "event|file|http|json|queue",
        "required_fields": ["string"]
      },
      "ownership_boundary": {
        "current_project_role": "producer|consumer",
        "counterparty_role": "producer|consumer",
        "boundary_rule": "string"
      },
      "rationale": "string",
      "requires_earth_evidence": true,
      "evidence_refs": ["string"],
      "next_step": "string"
    }
  ]
}
```

Notes:

- `project_obligation_candidates` must contain at least one row.
- `direction=expose` requires `ownership_boundary.current_project_role=producer` and `counterparty_role=consumer`.
- `direction=consume` requires `ownership_boundary.current_project_role=consumer` and `counterparty_role=producer`.
- `counterparty_project_id` must differ from `target_project_profile.project_id`.
- Cross-project obligations are emitted only when counterparty context is present and Earth-sweep evidence is cited; otherwise the candidate is normalized into `open_risks`.

## Output Contract

`build_req_043_project_obligation_reasoning(...)` returns:

```json
{
  "schema_version": "req-043.project-obligation-reasoning.v1",
  "requirement_id": "REQ-043",
  "analysis_type": "project_obligation_reasoning",
  "call_id": "string",
  "checked_at_utc": "RFC3339 UTC timestamp",
  "processing_behavior": {
    "strategy": "project-obligation-reasoning",
    "reasoning_mode": "deterministic-contract-surface-mapping",
    "bounded_context": true,
    "context_inputs": {
      "target_project": {
        "project_root": "absolute path",
        "project_id": "string",
        "owner_team": "string",
        "evidence_refs": ["string"]
      },
      "earth_sweep": {
        "earth_root": "absolute path",
        "evidence_refs": ["string"]
      },
      "cross_project_context": [],
      "project_obligation_candidates": []
    },
    "context_usage": {
      "bounded_context_used": true,
      "earth_sweep_context_used": true,
      "cross_project_context_used": true,
      "counterparty_projects_considered": ["string"],
      "obligation_ids_considered": ["obl.slug"],
      "interface_ids_emitted": ["string"],
      "expose_obligation_ids_emitted": ["obl.slug"],
      "consume_obligation_ids_emitted": ["obl.slug"],
      "open_risk_ids_emitted": ["risk-obl.slug"],
      "evidence_refs_used": ["string"]
    },
    "recommendation": {
      "decision": "proceed|proceed-with-open-risks|collect-earth-evidence|resolve-strategy-gaps|insufficient-context",
      "rationale": "string",
      "confidence": "high|medium|low",
      "evidence_refs": ["string"],
      "project_obligations": [
        {
          "obligation_id": "obl.slug",
          "direction": "expose|consume",
          "summary": "string",
          "counterparty_project_id": "string",
          "interface_id": "string",
          "contract_expectations": {
            "summary": "string",
            "version": "string",
            "transport": "event|file|http|json|queue",
            "required_fields": ["string"]
          },
          "ownership_boundary": {
            "current_project_role": "producer|consumer",
            "current_project_owner": "string",
            "counterparty_role": "producer|consumer",
            "counterparty_owner": "string",
            "boundary_rule": "string"
          },
          "rationale": "string",
          "next_step": "string",
          "evidence_refs": ["string"]
        }
      ],
      "open_risks": [
        {
          "risk_id": "risk-obl.slug",
          "reason_code": "missing_cross_project_context|missing_earth_sweep_evidence_refs|uncited_strategic_claim",
          "summary": "string",
          "required_evidence_refs": ["string"]
        }
      ]
    }
  },
  "call_metadata": {
    "reproducibility": "deterministic-input-fingerprint",
    "canonical_input": {},
    "canonical_input_sha256": "hex",
    "reproducible_call_id": "string",
    "canonical_processing_input": {},
    "processing_input_sha256": "hex",
    "processing_call_id": "string",
    "llm_call_trace_schema_version": "req-043.llm-call-trace-row.v1",
    "llm_call_trace_path": "strategy/current/llm_call_trace.jsonl",
    "llm_call_trace_sha256": "hex",
    "llm_call_trace_rows": []
  }
}
```

## Sample Artifact

The concrete REQ-043 sample structure is at:

- `strategy/current/samples/REQ-043_project-obligation-reasoning.sample.json`

Source fixture used for deterministic testability:

- `examples/fixtures/project-obligation-reasoning.json`
