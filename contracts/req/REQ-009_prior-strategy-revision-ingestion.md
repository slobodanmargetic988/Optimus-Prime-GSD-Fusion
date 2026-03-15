# REQ-009 Prior Strategy Revision Ingestion

Status: Implemented  
Requirement ID: `REQ-009`

## Scope anchors

This contract is limited to:

- Ingesting prior strategy revisions before new recommendation composition.
- Ingesting changelog history before new recommendation composition.
- Producing explicit continuity and drift analysis from ingested revision/changelog data.
- Reproducible call metadata derived from canonical ingestion input.

## Entrypoint surface

Implementation file: `scripts/strategy_context_sweep.py`

Builder function:

- `build_req_009_prior_strategy_revision_ingestion(...) -> dict`

Validator function:

- `validate_req_009_prior_strategy_revision_ingestion(payload) -> list[str]`

## Payload contract

Top-level required keys:

- `schema_version` (must equal `req-009.prior-strategy-revision-ingestion.v1`)
- `requirement_id` (must equal `REQ-009`)
- `prior_strategy_revision_ingestion` (object)
- `call_metadata` (object)

`prior_strategy_revision_ingestion` required keys:

- `current_revision_identity` (non-empty string)
- `prior_strategy_revisions` (normalized list that preserves source order)
- `changelog_history` (normalized list)
- `analysis` (deterministic continuity + drift output)

`analysis` required keys:

- `continuity`
- `drift`
- `composition_context`

`continuity.latest_prior_revision_id` semantics:

- Derived from the final element of `prior_strategy_revisions` after normalization.
- No lexicographic reordering is applied to revision identities, so `rev-10` remains later than `rev-9` when source order encodes chronology.

`call_metadata` required keys:

- `reproducibility` (must equal `deterministic-input-fingerprint`)
- `canonical_input_sha256` (sha256 over canonical ingestion input)
- `reproducible_call_id` (must equal `req009-` + first 16 chars of digest)
- `canonical_input` (normalized ingestion anchors)

## Sample structure

Sample artifact path:

- `strategy/current/samples/REQ-009_prior-strategy-revision-ingestion.sample.json`

Sample fixture path:

- `examples/fixtures/prior-strategy-revision-ingestion.json`

Sample JSON shape:

```json
{
  "schema_version": "req-009.prior-strategy-revision-ingestion.v1",
  "requirement_id": "REQ-009",
  "prior_strategy_revision_ingestion": {
    "current_revision_identity": "rev-req009-current",
    "prior_strategy_revisions": [
      {
        "revision_identity": "rev-req009-r1",
        "summary": "Previous strategy recommendation baseline.",
        "recommended_action_ids": ["action-a", "action-b"],
        "evidence_refs": ["reports/strategy/revisions/rev-req009-r1.json"]
      }
    ],
    "changelog_history": [
      {
        "change_id": "chg-001",
        "revision_identity": "rev-req009-r1",
        "action_id": "action-a",
        "change_type": "updated",
        "change_summary": "Adjusted action intent after review.",
        "changed_at": "2026-03-14T10:00:00Z",
        "evidence_refs": ["CHANGELOG.md#req-009"]
      }
    ],
    "analysis": {
      "continuity": {
        "latest_prior_revision_id": "rev-req009-r1",
        "ingested_revision_ids": ["rev-req009-r1"],
        "continuing_action_ids": [],
        "retired_action_ids": []
      },
      "drift": {
        "new_action_ids": ["action-a", "action-b"],
        "drift_action_ids": ["action-a", "action-b"],
        "changelog_change_ids": ["chg-001"],
        "changelog_action_ids": ["action-a"],
        "changelog_added_action_ids": [],
        "changelog_updated_action_ids": ["action-a"],
        "changelog_removed_action_ids": [],
        "changelog_only_action_ids": []
      },
      "composition_context": {
        "prior_revision_count": 1,
        "changelog_entry_count": 1,
        "recommendation_anchor_action_ids": ["action-a", "action-b"]
      }
    }
  },
  "call_metadata": {
    "reproducibility": "deterministic-input-fingerprint",
    "canonical_input_sha256": "sha256hex",
    "reproducible_call_id": "req009-0123456789abcdef",
    "canonical_input": {
      "current_revision_identity": "rev-req009-current",
      "prior_strategy_revisions": [
        {
          "revision_identity": "rev-req009-r1",
          "summary": "Previous strategy recommendation baseline.",
          "recommended_action_ids": ["action-a", "action-b"],
          "evidence_refs": ["reports/strategy/revisions/rev-req009-r1.json"]
        }
      ],
      "changelog_history": [
        {
          "change_id": "chg-001",
          "revision_identity": "rev-req009-r1",
          "action_id": "action-a",
          "change_type": "updated",
          "change_summary": "Adjusted action intent after review.",
          "changed_at": "2026-03-14T10:00:00Z",
          "evidence_refs": ["CHANGELOG.md#req-009"]
        }
      ]
    }
  }
}
```
