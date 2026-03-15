# REQ-012 Interface Contract Extraction

Status: Implemented  
Requirement ID: `REQ-012`  
Owner Surface: `scripts/strategy_context_sweep.py`

## Goal

Extract shared interface contracts from Earth contract sources that are relevant to the current target project.  
Each extracted obligation is explicitly marked as either `required` or `optional` to avoid over-constraining planning.

This contract is intentionally scoped to REQ-012 only.

## Input Contract

`extract_interface_contracts(payload)` expects:

```json
{
  "current_project": {
    "project_id": "string"
  },
  "earth_contract_sources": [
    {
      "source_id": "string",
      "source_path": "string",
      "applies_to_projects": ["*", "project-id"],
      "content": "string"
    }
  ]
}
```

Notes:

- `applies_to_projects` is optional. When omitted, it defaults to `["*"]`.
- A source is relevant when `applies_to_projects` contains `"*"` or the `current_project.project_id`.
- Interface IDs are resolved from `Interface: <interface_id>` declarations, interface tokens in statements (for example `name.v1`), or the current active declaration.
- Obligation level classification:
- `required`: statement contains `must|shall|required|needs to`
- `optional`: statement contains `should|may|optional|can|recommended`

## Output Contract

`extract_interface_contracts(...)` returns:

```json
{
  "schema_version": "REQ-012-interface-contract-extraction.v1",
  "generated_at": "RFC3339 UTC timestamp",
  "current_project_id": "string",
  "shared_interface_contracts": [
    {
      "interface_id": "string",
      "source_contract_ids": ["string"],
      "required_obligation_count": 0,
      "optional_obligation_count": 0,
      "obligations": [
        {
          "obligation_id": "string",
          "obligation_level": "required|optional",
          "statement": "string",
          "source_provenance": [
            {
              "source_id": "string",
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
  "summary": {
    "earth_contract_source_count": 0,
    "relevant_source_count": 0,
    "shared_interface_contract_count": 0,
    "required_obligation_count": 0,
    "optional_obligation_count": 0,
    "total_obligation_count": 0
  }
}
```

## Sample Artifact

The concrete REQ-012 sample structure is at:

- `strategy/current/samples/REQ-012_interface-contract-extraction.sample.json`

Source fixture used for deterministic testability:

- `examples/fixtures/interface-contract-extraction.json`
