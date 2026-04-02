# REQ-013: Capability Catalog Extraction

## Purpose
Define the contract and data-model surface for extracting a deterministic capability catalog from strategy context sweep inputs so planners can see what each project already provides, what is missing, and avoid recommending already-completed work.

## Scope Anchors
- Surface in scope: `scripts/strategy_context_sweep.py`.
- Contract fixture in scope: `examples/fixtures/capability-catalog-extraction.json`.
- Contract tests in scope: `tests/contracts/test_capability-catalog-extraction.py`.
- Out of scope: adding packet managers, new execution gates, or non-REQ-013 packet sections.

## Input Contract
`strategy_context_sweep.py` accepts optional REQ-013 fields in the existing `--input-json` payload:

```json
{
  "required_capability_ids": [
    "planning-artifact-sweep",
    "capability-catalog-extraction"
  ],
  "projects": [
    {
      "project_id": "earth-north",
      "provided_capabilities": [
        {
          "capability_id": "planning-artifact-sweep",
          "source_version": "1.1.0",
          "source_ref": "scripts/strategy_context_sweep.py"
        }
      ]
    }
  ]
}
```

Rules:
- `required_capability_ids` is optional; when provided it must be a list of non-empty strings (deduplicated and sorted deterministically).
- `projects[].provided_capabilities` is optional; when provided it must be a list of objects.
- Each capability object must include:
  - `capability_id` (non-empty string)
  - `source_version` (non-empty string)
- `source_ref` is optional and preserved when present.

## Output Contract
The script adds a top-level `capability_catalog` section:

```json
{
  "capability_catalog": {
    "required_capability_ids": ["capability-catalog-extraction"],
    "projects": [
      {
        "project_id": "earth-north",
        "provided_capabilities": [
          {
            "capability_id": "capability-catalog-extraction",
            "source_version": "1.0.0",
            "source_ref": "contracts/req/REQ-013_capability-catalog-extraction.md"
          }
        ],
        "provided_capability_ids": ["capability-catalog-extraction"],
        "missing_capability_ids": []
      }
    ],
    "catalog_entries": [
      {
        "capability_id": "capability-catalog-extraction",
        "availability": "provided",
        "providers": [
          {
            "project_id": "earth-north",
            "source_version": "1.0.0",
            "source_ref": "contracts/req/REQ-013_capability-catalog-extraction.md"
          }
        ],
        "source_versions": ["1.0.0"],
        "project_ids_missing": [],
        "provider_count": 1,
        "projects_missing_count": 0
      }
    ],
    "already_completed_capability_ids": ["capability-catalog-extraction"],
    "missing_capability_ids": [],
    "recommended_capability_ids": [],
    "summary": {
      "projects": 1,
      "required_capabilities": 1,
      "already_completed_capabilities": 1,
      "missing_capabilities": 0
    }
  }
}
```

Behavior:
- `projects[]` explicitly shows what each project provides and which required capabilities are missing.
- `catalog_entries[]` includes provider-level `source_version` metadata for each capability.
- `recommended_capability_ids` only contains capabilities with zero providers, preventing recommendations for already-completed capabilities.

## Deterministic Fixtures and Samples
- Input fixture: `examples/fixtures/capability-catalog-extraction.json`
- Output sample: `strategy/current/samples/REQ-013_capability-catalog-extraction.sample.json`

`strategy/current/samples/REQ-013_capability-catalog-extraction.sample.json` is the reference structure for REQ-013 output shape and includes the `capability_catalog` section produced by the script.
