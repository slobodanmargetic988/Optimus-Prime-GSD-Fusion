# REQ-051: STRATEGY_CHANGELOG.md Generator

## Purpose
Define the contract and data-model surface for generating a human-readable `STRATEGY_CHANGELOG.md` artifact that summarizes revision deltas and strategic direction changes while linking each changed recommendation to supporting evidence.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-051):
  - Build deterministic `STRATEGY_CHANGELOG.md` output from validated revision-delta anchors.
  - Summarize direction changes across `mission_scope`, `runtime_data`, and `ecosystem_signals`.
  - Link changed recommendation entries directly to current final/deferred recommendation anchors and supporting evidence refs.
- Out of scope (REQ-051): net-new packet sections, managers, orchestration gates, or behavior outside strategy changelog generation.

## Interface surface
Builder:
- `build_req_051_strategy_changelog_md_generator(payload) -> dict`

Validator:
- `validate_req_051_strategy_changelog_md_generator(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
`strategy_artifacts_handoff.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "strategy_changelog_md_generator",
  "now_utc": "2026-03-16T09:45:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "revision_pair": {
    "previous_revision_id": "strategy-2026-03-14T08:00:00Z",
    "current_revision_id": "strategy-2026-03-15T08:00:00Z"
  },
  "change_detection": {
    "mission_scope": {
      "changed": true,
      "change_count": 1,
      "changes": []
    },
    "runtime_data": {
      "changed": true,
      "change_count": 1,
      "changes": []
    },
    "ecosystem_signals": {
      "changed": true,
      "change_count": 1,
      "changes": []
    }
  },
  "change_summary": {
    "total_change_count": 3,
    "changed_sections": [
      "ecosystem_signals",
      "mission_scope",
      "runtime_data"
    ],
    "change_ids": []
  },
  "recommendation_deltas": [],
  "evidence_refs": [],
  "final_strategy_synthesis": {
    "final_recommendations": [],
    "deferred_recommendations": [],
    "open_risks": [],
    "strategy_packet_inputs": []
  }
}
```

Rules:
- `analysis_type` must be `strategy_changelog_md_generator`.
- `target_project.project_id` must be non-empty.
- `target_project.project_root` must normalize to an absolute path.
- `revision_pair.previous_revision_id` and `revision_pair.current_revision_id` must be non-empty and different.
- `change_detection` is strict and limited to:
  - `mission_scope`
  - `runtime_data`
  - `ecosystem_signals`
- Each `change_detection.<section>.changes[]` row must include:
  - `change_id`
  - `section_key`
  - `path`
  - `change_type`
  - `previous_value`
  - `current_value`
- `change_summary` must exactly match derived `change_detection` counts and `change_id` coverage.
- `recommendation_deltas[]` rows must include:
  - `recommendation_id`
  - `summary`
  - `anchors[]`
  - `change_ids[]`
  - `delta_type`
  - `evidence_refs[]`
- `recommendation_deltas[]` must cover every `change_summary.change_ids[]` value.
- Every `recommendation_deltas[].recommendation_id` must resolve to a recommendation in `final_strategy_synthesis.final_recommendations[]` or `final_strategy_synthesis.deferred_recommendations[]`.
- `evidence_refs[]` must be a sorted unique superset of every `recommendation_deltas[].evidence_refs[]`.

## Output contract
REQ-051 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- synthesis target: `target_project`
- revision delta anchors: `revision_pair`, `change_summary`
- changelog artifact surface: `strategy_changelog_md`
- bounded counts: `totals`

`strategy_changelog_md` contains:
- `artifact_path` (`STRATEGY_CHANGELOG.md`)
- `markdown`
- `content_sha256`
- `line_count`
- `sections[]`
- `direction_changes[]`
- `entries[]`
- `alignment`

Each `direction_changes[]` row includes:
- `direction_id`
- `section_key`
- `title`
- `change_ids[]`
- `change_count`
- `recommendation_ids[]`
- `recommendation_refs[]`
- `evidence_refs[]`

Each `entries[]` row includes:
- `entry_id`
- `recommendation_id`
- `recommendation_ref`
- `summary`
- `delta_type`
- `anchors[]`
- `change_ids[]`
- `evidence_refs[]`

`alignment` includes:
- `direction_ids[]`
- `entry_ids[]`
- `recommendation_ids[]`
- `recommendation_refs[]`
- `change_ids[]`
- `evidence_refs[]`

`totals` includes:
- `direction_changes`
- `changed_recommendations`
- `change_count`
- `evidence_refs`
- `markdown_sections`
- `markdown_lines`

Generation behavior:
- `direction_changes[]` are derived from changed `mission_scope`, `runtime_data`, and `ecosystem_signals` sections.
- Each changelog entry resolves to a direct recommendation ref:
  - `final_strategy_synthesis.final_recommendations#<recommendation_id>`
  - or `final_strategy_synthesis.deferred_recommendations#<recommendation_id>`
- Changelog markdown is emitted in deterministic section order.
- `content_sha256` and `line_count` are derived directly from `strategy_changelog_md.markdown`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/strategy-changelog-md-generator.json`
- Contract tests: `tests/contracts/test_strategy-changelog-md-generator.py`
- Output sample: `strategy/current/samples/REQ-051_strategy-changelog-md-generator.sample.json`

The structure in `strategy/current/samples/REQ-051_strategy-changelog-md-generator.sample.json`
is the canonical contract shape for REQ-051 and documents:
- `revision_pair`
- `change_summary`
- `strategy_changelog_md.markdown`
- `strategy_changelog_md.direction_changes`
- `strategy_changelog_md.entries`
- `strategy_changelog_md.alignment`
- `totals`
