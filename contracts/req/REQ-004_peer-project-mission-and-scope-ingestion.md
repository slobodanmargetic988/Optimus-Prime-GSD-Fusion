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
  ]
}
```

Notes:

- Only `mission` and `scope` documents are ingested for REQ-004 signal extraction.
- Non-mission/scope document types are ignored.

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
    "recommendation_count": 0
  }
}
```

## Provenance Rule

Every item in `cross_project_recommendations` must include a non-empty `source_provenance` array, preserving the originating peer mission/scope source.

## Sample Artifact

The concrete REQ-004 sample structure is at:

- `strategy/current/samples/REQ-004_peer-project-mission-and-scope-ingestion.sample.json`

Source fixture used for deterministic testability:

- `examples/fixtures/peer-project-mission-and-scope-ingestion.json`
