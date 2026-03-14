# REQ-004 Peer Project Mission And Scope Ingestion

Status: Implemented  
Requirement ID: `REQ-004`  
Owner Surface: `scripts/strategy_context_sweep.py`

## Goal

Ingest peer project mission/scope documents and produce a machine-readable model of:

- interaction obligations
- reuse opportunities
- cross-project recommendations with source provenance on every inferred recommendation

This contract is intentionally scoped to REQ-004 only.

## Input Contract

`ingest_peer_project_mission_and_scope(payload)` expects:

```json
{
  "current_project": {
    "project_id": "string"
  },
  "peer_projects": [
    {
      "project_id": "string",
      "documents": [
        {
          "document_type": "mission|scope|other",
          "source_path": "string",
          "content": "string"
        }
      ]
    }
  ],
  "earth_sweep_context": {
    "evidence_refs": [
      {
        "peer_project_id": "string",
        "source_path": "string",
        "line_number": 1,
        "evidence_ref": "string"
      }
    ]
  }
}
```

Notes:

- Only `mission` and `scope` documents are ingested for REQ-004 signal extraction.
- Non-mission/scope document types are ignored.
- Cross-project recommendations are emitted only when matching Earth-sweep evidence refs exist.
- Missing Earth-sweep coverage is represented in `open_risks` instead of silently inventing obligations/reuse actions.

## Output Contract

`ingest_peer_project_mission_and_scope(...)` returns:

```json
{
  "schema_version": "REQ-004-peer-project-mission-and-scope-ingestion.v1",
  "generated_at": "RFC3339 UTC timestamp",
  "current_project_id": "string",
  "peer_project_models": [
    {
      "peer_project_id": "string",
      "ingested_documents": [
        {
          "document_type": "mission|scope",
          "source_path": "string",
          "source_sha256": "hex",
          "line_count": 0
        }
      ],
      "interaction_obligations": [
        {
          "obligation_id": "string",
          "statement": "string",
          "source_provenance": [
            {
              "document_type": "mission|scope",
              "source_path": "string",
              "source_sha256": "hex",
              "line_number": 0,
              "excerpt": "string"
            }
          ]
        }
      ],
      "reuse_opportunities": [
        {
          "opportunity_id": "string",
          "statement": "string",
          "source_provenance": [
            {
              "document_type": "mission|scope",
              "source_path": "string",
              "source_sha256": "hex",
              "line_number": 0,
              "excerpt": "string"
            }
          ]
        }
      ]
    }
  ],
  "cross_project_recommendations": [
    {
      "recommendation_id": "string",
      "recommendation_type": "interaction_obligation|reuse_opportunity",
      "source_project_id": "string",
      "target_project_id": "string",
      "summary": "string",
      "rationale": "string",
      "source_provenance": [
        {
          "document_type": "mission|scope",
          "source_path": "string",
          "source_sha256": "hex",
          "line_number": 0,
          "excerpt": "string"
        }
      ],
      "evidence_refs": ["string"],
      "cross_project_context": {
        "context_type": "earth_sweep",
        "match_keys": ["peer_project_id:source_path:line_number"],
        "evidence_ref_count": 0
      }
    }
  ],
  "open_risks": [
    {
      "risk_id": "string",
      "risk_type": "missing_earth_sweep_evidence",
      "recommendation_type": "interaction_obligation|reuse_opportunity",
      "source_project_id": "string",
      "target_project_id": "string",
      "summary": "string",
      "required_context_match_keys": ["peer_project_id:source_path:line_number"],
      "source_provenance": [
        {
          "document_type": "mission|scope",
          "source_path": "string",
          "source_sha256": "hex",
          "line_number": 0,
          "excerpt": "string"
        }
      ]
    }
  ],
  "summary": {
    "peer_projects_evaluated": 0,
    "peer_projects_with_signals": 0,
    "interaction_obligation_count": 0,
    "reuse_opportunity_count": 0,
    "recommendation_count": 0,
    "open_risk_count": 0,
    "earth_sweep_context_entry_count": 0,
    "earth_sweep_evidence_refs_used_count": 0
  }
}
```

## Provenance Rule

Every item in `cross_project_recommendations` must include a non-empty `source_provenance` array, preserving the originating peer mission/scope source.

Every emitted recommendation must include non-empty `evidence_refs` tied to Earth-sweep context matching its source provenance.

## Sample Artifact

The concrete REQ-004 sample structure is at:

- `strategy/current/samples/REQ-004_peer-project-mission-and-scope-ingestion.sample.json`

Source fixture used for deterministic testability:

- `examples/fixtures/peer-project-mission-and-scope-ingestion.json`
