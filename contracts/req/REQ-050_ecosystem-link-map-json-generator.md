# REQ-050: ECOSYSTEM_LINK_MAP.json Generator

## Purpose
Define the contract and data-model surface for generating a machine-readable `ECOSYSTEM_LINK_MAP.json` artifact that exposes current ecosystem links, missing links, and proposed links for integration planning.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-050):
  - Build deterministic `ECOSYSTEM_LINK_MAP.json` output from validated final strategy synthesis anchors.
  - Emit bounded link buckets for `current_links`, `missing_links`, and `proposed_links`.
  - Include confidence and obligation metadata for each link so downstream planning can distinguish backed, blocked, and proposed integration work.
- Out of scope (REQ-050): net-new packet sections, managers, orchestration gates, or behaviors outside ecosystem link-map generation.

## Interface surface
Builder:
- `build_req_050_ecosystem_link_map_json_generator(payload) -> dict`

Validator:
- `validate_req_050_ecosystem_link_map_json_generator(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
`strategy_artifacts_handoff.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "ecosystem_link_map_json_generator",
  "now_utc": "2026-03-16T09:30:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "final_strategy_synthesis": {
    "final_recommendations": [],
    "deferred_recommendations": [],
    "open_risks": [],
    "strategy_packet_inputs": [],
    "cross_project_context_usage": {
      "cross_project_context_provided": true,
      "cross_project_context_used": true,
      "projects_considered": [],
      "earth_sweep_evidence_refs_considered": [],
      "cross_project_obligation_count": 0,
      "unresolved_idea_count": 0,
      "recommendation_ids_with_context": []
    }
  }
}
```

Rules:
- `analysis_type` must be `ecosystem_link_map_json_generator`.
- `target_project.project_id` must be non-empty.
- `target_project.project_root` must normalize to an absolute path.
- `final_strategy_synthesis` must include:
  - `final_recommendations[]`
  - `deferred_recommendations[]`
  - `open_risks[]`
  - `strategy_packet_inputs[]`
- `final_strategy_synthesis.cross_project_context_usage` is optional input, but when present it is strict and limited to:
  - `cross_project_context_provided`
  - `cross_project_context_used`
  - `projects_considered[]`
  - `earth_sweep_evidence_refs_considered[]`
  - `cross_project_obligation_count`
  - `unresolved_idea_count`
  - `recommendation_ids_with_context[]`
- `strategy_packet_inputs[]` provide current cross-project links when `packet_kind = cross-project`.
- `open_risks[]` with peer `project_id` distinct from the target project provide missing ecosystem links.
- `deferred_recommendations[]` with `cross-project` in `packet_kind_candidates[]` provide proposed ecosystem links; these rows must include `peer_project_candidates[]`.

## Output contract
REQ-050 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- synthesis target: `target_project`
- ecosystem artifact surface: `ecosystem_link_map`
- bounded counts: `totals`

`ecosystem_link_map` contains:
- `artifact_path` (`ECOSYSTEM_LINK_MAP.json`)
- `planning_context`
- `current_links[]`
- `missing_links[]`
- `proposed_links[]`
- `summary`

`planning_context` includes:
- `cross_project_context_provided`
- `cross_project_context_used`
- `projects_considered[]`
- `earth_sweep_evidence_refs_considered[]`
- `cross_project_obligation_count`
- `unresolved_idea_count`
- `recommendation_ids_with_context[]`

Each link row in `current_links[]`, `missing_links[]`, and `proposed_links[]` includes:
- `link_id`
- `status`
- `source_project_id`
- `peer_project_id`
- `lane`
- `confidence`
- `recommendation_ids[]`
- `packet_input_ids[]`
- `open_risk_ids[]`
- `evidence_refs[]`
- `required_evidence_refs[]`
- `obligation_metadata`

`obligation_metadata` includes:
- `status`
- `source_field`
- `reason_codes[]`
- `evidence_refs[]`
- `required_evidence_refs[]`

`summary` includes:
- `linked_project_ids[]`
- `current_link_count`
- `missing_link_count`
- `proposed_link_count`
- `total_link_count`
- `active_obligation_count`
- `blocked_obligation_count`
- `proposed_obligation_count`

`totals` includes:
- `current_links`
- `missing_links`
- `proposed_links`
- `linked_projects`
- `obligation_rows`
- `context_project_count`

Generation behavior:
- `current_links[]` are derived from `final_strategy_synthesis.strategy_packet_inputs[]` rows where `packet_kind = cross-project`.
- `missing_links[]` are derived from cross-project `open_risks[]`.
- `proposed_links[]` are derived from `deferred_recommendations[]` rows that still carry cross-project routing candidates.
- Current links emit `confidence = high` with `obligation_metadata.status = active`.
- Missing links emit `confidence = low` with `obligation_metadata.status = blocked`.
- Proposed links emit `confidence = medium` or `low` with `obligation_metadata.status = proposed`.
- Link buckets are sorted deterministically by `peer_project_id`, `lane`, then `link_id`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/ecosystem-link-map-json-generator.json`
- Contract tests: `tests/contracts/test_ecosystem-link-map-json-generator.py`
- Output sample: `strategy/current/samples/REQ-050_ecosystem-link-map-json-generator.sample.json`

The structure in `strategy/current/samples/REQ-050_ecosystem-link-map-json-generator.sample.json`
is the canonical contract shape for REQ-050 and documents:
- `ecosystem_link_map.current_links`
- `ecosystem_link_map.missing_links`
- `ecosystem_link_map.proposed_links`
- `ecosystem_link_map.planning_context`
- `ecosystem_link_map.summary`
- `obligation_metadata`
- `totals`
