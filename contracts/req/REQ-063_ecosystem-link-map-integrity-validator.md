# REQ-063: Ecosystem Link-Map Integrity Validator

## Purpose
Define the contract and data-model surface for validating ecosystem link-map schema integrity and referential consistency against discovered projects, with source-level diagnostics for broken or orphaned links.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-063):
  - Validate deterministic link-map rows against a bounded schema.
  - Validate `source_project_id` and `target_project_id` against discovered projects.
  - Flag orphaned links when a link endpoint does not resolve to a discovered project.
  - Flag broken links when the link row is self-referential.
  - Emit source-level diagnostics with `field_path` and `source_ref`.
- Out of scope (REQ-063): new packet sections, new managers, new orchestration gates, or non-link-map strategy behaviors.

## Interface surface
Builder:
- `build_req_063_ecosystem_link_map_integrity_validator(payload) -> dict`

Validator:
- `validate_req_063_ecosystem_link_map_integrity_validator(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-063 expects:

```json
{
  "analysis_type": "ecosystem_link_map_integrity_validator",
  "now_utc": "2026-03-16T12:30:00Z",
  "target_project": {
    "project_id": "prj.optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "link_map_ref": "strategy/current/ECOSYSTEM_LINK_MAP.json",
  "discovered_projects": [
    {
      "project_id": "prj.optimus-prime-gsd-fusion",
      "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
    }
  ],
  "links": [
    {
      "link_id": "link.runtime-core.depends-on",
      "source_project_id": "prj.optimus-prime-gsd-fusion",
      "target_project_id": "prj.runtime-core",
      "link_type": "depends_on",
      "declared_in": "strategy/current/ECOSYSTEM_LINK_MAP.json#links[0]",
      "source_refs": [
        "strategy/current/strategy_packet.v1.json#strategy.link_map_ref"
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `ecosystem_link_map_integrity_validator` when provided.
- `target_project.project_root` must be an absolute path.
- `link_map_ref` must be a non-empty string.
- `discovered_projects[]` must contain at least one row with unique `project_id` values and absolute `project_root` values.
- `links[]` must contain at least one row with unique `link_id` values.
- Every `links[]` row must include `link_id`, `source_project_id`, `target_project_id`, `link_type`, `declared_in`, and non-empty sorted unique `source_refs[]`.

## Output contract
REQ-063 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- artifact payload: `ecosystem_link_map_integrity_validator`
- bounded counts: `totals`

`ecosystem_link_map_integrity_validator` contains:
- `link_map_ref`
- `discovered_projects[]`
- `links[]`
- `diagnostics[]`
- `summary`

Each `discovered_projects[]` row includes:
- `project_id`
- `project_root`

Each `links[]` row includes:
- `link_id`
- `source_project_id`
- `target_project_id`
- `link_type`
- `declared_in`
- `source_refs[]`
- `integrity_status`

`integrity_status` rules:
- `valid`: both link endpoints resolve to discovered projects and the row is not self-referential.
- `orphaned`: at least one link endpoint does not resolve to a discovered project.
- `broken`: the row is self-referential.

Each `diagnostics[]` row includes:
- `diagnostic_id`
- `severity`
- `category`
- `code`
- `message`
- `link_id`
- `field_path`
- `source_ref`
- `project_ids[]`

`summary` includes:
- `integrity_status`
- `valid_link_ids[]`
- `orphaned_link_ids[]`
- `broken_link_ids[]`
- `diagnostic_codes[]`
- `missing_project_ids[]`

`totals` includes:
- `discovered_projects`
- `links`
- `valid_links`
- `orphaned_links`
- `broken_links`
- `diagnostics`

Behavior:
- Broken or orphaned links must be retained in `links[]` with the derived `integrity_status`.
- Every flagged condition must emit a source-level diagnostic row with `field_path` and `source_ref`.
- `summary.valid_link_ids`, `summary.orphaned_link_ids`, and `summary.broken_link_ids` must match the derived link statuses.
- `summary.missing_project_ids` must reflect unresolved project IDs referenced by diagnostics.
- `totals` counts must match the discovered project count, link count, status counts, and diagnostic count.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/ecosystem-link-map-integrity-validator.json`
- Contract tests: `tests/contracts/test_ecosystem-link-map-integrity-validator.py`
- Output sample: `strategy/current/samples/REQ-063_ecosystem-link-map-integrity-validator.sample.json`

The structure in `strategy/current/samples/REQ-063_ecosystem-link-map-integrity-validator.sample.json`
is the canonical contract shape for REQ-063 and documents:
- `ecosystem_link_map_integrity_validator.link_map_ref`
- `ecosystem_link_map_integrity_validator.discovered_projects`
- `ecosystem_link_map_integrity_validator.links`
- `ecosystem_link_map_integrity_validator.links[].integrity_status`
- `ecosystem_link_map_integrity_validator.diagnostics`
- `ecosystem_link_map_integrity_validator.diagnostics[].field_path`
- `ecosystem_link_map_integrity_validator.diagnostics[].source_ref`
- `ecosystem_link_map_integrity_validator.summary`
- `totals`
