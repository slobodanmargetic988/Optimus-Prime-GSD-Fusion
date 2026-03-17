# REQ-027: Call-2 Ecosystem Linkage Reasoning

## Purpose
Define the contract and data-model surface for Call-2 reasoning about ecosystem links and interaction obligations between the target project and peer projects.

## Scope Anchors
- Surface in scope: `scripts/strategy_llm_pipeline.py`.
- Linkage reasoning in scope:
  - Distinguish **existing links**, **missing links**, and **proposed links**.
  - Each link row includes a `confidence_tag` (`high|medium|low`).
  - Each link row may include bounded `interaction_obligations[]` between target and peer projects.
- Out of scope (REQ-027): net-new packet sections, managers, or orchestration gates outside of this linkage/obligation surface.

## Input Contract
`strategy_llm_pipeline.py` accepts `--input-json <path|->` with this JSON object shape:

```json
{
  "analysis_type": "call_2_ecosystem_linkage_reasoning",
  "now_utc": "2026-03-16T12:00:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "peer_projects": [
    {
      "project_id": "tetris",
      "project_root": "/Users/slobodan/projects/Earth/Tetris"
    }
  ],
  "existing_links": [
    {
      "peer_project_id": "tetris",
      "link_kind": "contract-consumer",
      "direction": "target_to_peer",
      "summary": "Target consumes peer contract fixtures and samples as cross-project evidence anchors.",
      "evidence_refs": ["contracts/req/REQ-002_earth-wide-repository-discovery-manifest.md"],
      "confidence_tag": "high",
      "interaction_obligations": [
        {
          "obligated_party": "target",
          "obligation_kind": "keep-fixtures-compatible",
          "summary": "Keep fixture references stable or update expectations with evidence.",
          "evidence_refs": ["tests/contracts/test_change-detection-since-previous-strategy-revision.py"]
        }
      ]
    }
  ],
  "missing_links": [],
  "proposed_links": []
}
```

Rules:
- `now_utc` must be a non-empty string; it becomes `checked_at_utc` in the output for deterministic verification.
- `target_project` and each `peer_projects[]` row must provide:
  - `project_id`: non-empty string
  - `project_root`: absolute path (normalizes via `Path(...).resolve()` in the builder)
- Links are bucketed in exactly three arrays: `existing_links`, `missing_links`, `proposed_links`.
- Each link row requires: `peer_project_id`, `link_kind`, `direction`, `summary`, `evidence_refs`, `confidence_tag`, `interaction_obligations`.
- `direction` must be one of: `target_to_peer`, `peer_to_target`, `bidirectional`.
- `confidence_tag` must be one of: `high`, `medium`, `low`.
- Each obligation row requires: `obligated_party`, `obligation_kind`, `summary`, `evidence_refs`.
- The builder is strict: unexpected keys are rejected to keep scope bounded to REQ-027 anchors.

## Output Contract
REQ-027 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- identity anchors: `target_project`, `peer_projects`
- linkage buckets: `linkage_reasoning.existing_links[]`, `linkage_reasoning.missing_links[]`, `linkage_reasoning.proposed_links[]`
- bounded totals: `totals`

Each output link row contains:
- `link_id`: deterministic `lnk.<id>` derived from target/peer/kind/direction/bucket
- `peer_project_id`, `link_kind`, `direction`, `summary`
- `evidence_refs`: sorted, de-duplicated string list
- `confidence_tag`: `high|medium|low`
- `interaction_obligations[]`: each includes deterministic `obligation_id` (`obl.<id>`) and evidence refs

## Deterministic Fixtures and Samples
- Input fixture: `examples/fixtures/call-2-ecosystem-linkage-reasoning.json`
- Contract tests: `tests/contracts/test_call-2-ecosystem-linkage-reasoning.py`
- Output sample: `strategy/current/samples/REQ-027_call-2-ecosystem-linkage-reasoning.sample.json`

Documented sample structure (`REQ-027_call-2-ecosystem-linkage-reasoning.sample.json`) includes:
- `linkage_reasoning` with existing/missing/proposed link buckets,
- `confidence_tag` per link row,
- `interaction_obligations[]` per link row,
- deterministic stable ids (`link_id`, `obligation_id`),
- `totals` for measurable contract verification.

