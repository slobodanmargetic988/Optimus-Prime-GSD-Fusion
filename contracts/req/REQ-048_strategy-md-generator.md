# REQ-048: STRATEGY.md Generator

## Purpose
Define the contract and data-model surface for generating a human-readable `STRATEGY.md` narrative from validated recommendation outputs while keeping the narrative aligned with machine-readable fields.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-048):
  - Build deterministic `STRATEGY.md` narrative output from validated recommendation outputs.
  - Keep narrative diff-friendly (stable ordering and stable sections).
  - Emit machine-readable alignment fields that map directly to narrative sections.
- Out of scope (REQ-048): net-new packet sections, managers, orchestration gates, or behavior outside STRATEGY narrative generation.

## Interface surface
Builder:
- `build_req_048_strategy_md_generator(payload) -> dict`

Validator:
- `validate_req_048_strategy_md_generator(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
`strategy_artifacts_handoff.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "strategy_md_generator",
  "now_utc": "2026-03-16T09:15:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "final_strategy_synthesis": {
    "final_recommendations": [],
    "deferred_recommendations": [],
    "open_risks": [],
    "strategy_packet_inputs": []
  },
  "multi_call_orchestration_trace": []
}
```

Rules:
- `analysis_type` must be `strategy_md_generator`.
- `target_project.project_id` must be non-empty.
- `target_project.project_root` must normalize to an absolute path.
- `final_strategy_synthesis` must include:
  - `final_recommendations[]`
  - `deferred_recommendations[]`
  - `open_risks[]`
  - `strategy_packet_inputs[]`
- `final_recommendations[]` rows must include recommendation identity, routing fields, evidence refs, lineage, contributing call/requirement ids, and `strategy_packet_input_id`.
- `multi_call_orchestration_trace[]` rows must include call/requirement identity, trace refs, input/output refs, and handoff summary.

## Output contract
REQ-048 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- synthesis target: `target_project`
- strategy artifact surface: `strategy_md`
- bounded counts: `totals`

`strategy_md` contains:
- `artifact_path` (`STRATEGY.md`)
- `markdown` (human-readable narrative)
- `content_sha256`
- `line_count`
- `sections[]`
- `alignment`

`sections[]` rows include:
- `section_id`
- `title`
- `machine_field`
- `entry_count`
- `anchor_ids[]`

`alignment` includes:
- `final_recommendation_ids[]`
- `deferred_recommendation_ids[]`
- `open_risk_ids[]`
- `strategy_packet_input_ids[]`
- `trace_ids[]`

`totals` includes:
- `final_recommendations`
- `deferred_recommendations`
- `open_risks`
- `strategy_packet_inputs`
- `multi_call_trace_rows`
- `markdown_sections`
- `markdown_lines`

Generation behavior:
- Narrative sections are emitted in deterministic order.
- Narrative references recommendation/trace ids from validated outputs.
- `strategy_md.alignment` maps narrative anchors to machine-readable field ids.
- `content_sha256` and `line_count` are derived directly from `strategy_md.markdown`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/strategy-md-generator.json`
- Contract tests: `tests/contracts/test_strategy-md-generator.py`
- Output sample: `strategy/current/samples/REQ-048_strategy-md-generator.sample.json`

The structure in `strategy/current/samples/REQ-048_strategy-md-generator.sample.json`
is the canonical contract shape for REQ-048 and documents:
- `strategy_md.markdown`
- `strategy_md.sections`
- `strategy_md.alignment`
- `totals`
