# REQ-037 Recommendation Deduplication and Merge

Status: Implemented  
Requirement ID: `REQ-037`

## Scope anchors

This requirement surface is limited to:

- Merging duplicate recommendation drafts into one deterministic recommendation row.
- Preserving per-source rationale entries and evidence links for every merged draft.
- Preserving stable `recommendation_id` anchors while preventing semantic duplication from spanning multiple stable IDs.

No net-new packet sections, managers, or orchestration gates are introduced by this contract.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_037_recommendation_deduplication_and_merge(...) -> dict`

Validator:

- `validate_req_037_recommendation_deduplication_and_merge(payload) -> list[str]`

## Input contract

The builder expects:

- `recommendation_drafts[]` (non-empty array, required)
- Optional broad-sweep context inputs:
  - `target_project_root`
  - `earth_root`
  - `output_root`
  - `revision_identity`
  - `target_project_evidence_refs[]`
  - `earth_sweep_evidence_refs[]`
  - `cross_project_context[]`

Each `recommendation_drafts[]` row must include:

- `draft_id`
- `recommendation_id`
- `summary`
- `rationale`
- `evidence_refs[]` (at least one evidence link)

Optional input field:

- `semantic_signature`
  - When omitted, the builder derives a normalized signature from `summary`.
- `action_scope`
- `requires_earth_evidence`
- `project_id`
- `next_step`

Behavior guarantees:

- Duplicate drafts merge only when they resolve to the same stable `recommendation_id` and the same semantic signature.
- A stable `recommendation_id` cannot span multiple semantic signatures.
- A semantic signature cannot span multiple stable `recommendation_id` values.
- Merged output preserves every source rationale row and the union of all source `evidence_refs`.

## Output contract

Top-level required keys:

- `requirement_id` (must be `REQ-037`)
- `surface` (must be `recommendation_deduplication_and_merge`)
- `schema_version` (must be `req-037.recommendation-deduplication-and-merge.v1`)
- `recommendation_deduplication_and_merge_entrypoint`
- `processing_behavior`
- `call_metadata`
- `merged_at`
- `deduplication_index`
- `merged_recommendations`
- `evidence_refs`
- `summary`

`deduplication_index` required keys:

- `input_draft_count`
- `merged_recommendation_count`
- `duplicate_group_count`
- `recommendation_ids[]`
- `semantic_signatures[]`

`merged_recommendations[]` required keys:

- `recommendation_id`
- `semantic_signature`
- `summary`
- `summary_variants[]`
- `merged_from_draft_ids[]`
- `source_rationales[]`
- `evidence_refs[]`
- `duplicate_count`

`source_rationales[]` required keys:

- `draft_id`
- `rationale`
- `evidence_refs[]`

`processing_behavior.recommendation` required keys:

- `decision`
- `rationale`
- `confidence`
- `evidence_refs[]`
- `merged_recommendations[]`
- `cross_project_obligations[]`
- `open_risks[]`

## Executable artifacts

- Fixture input: `examples/fixtures/recommendation-deduplication-and-merge.json`
- Contract test: `tests/contracts/test_recommendation-deduplication-and-merge.py`
- Canonical sample output: `strategy/current/samples/REQ-037_recommendation-deduplication-and-merge.sample.json`

## Sample structure

The canonical sample output is stored at:

`strategy/current/samples/REQ-037_recommendation-deduplication-and-merge.sample.json`

Its top-level shape is:

```json
{
  "requirement_id": "REQ-037",
  "surface": "recommendation_deduplication_and_merge",
  "schema_version": "req-037.recommendation-deduplication-and-merge.v1",
  "recommendation_deduplication_and_merge_entrypoint": {},
  "processing_behavior": {},
  "call_metadata": {},
  "merged_at": "2026-03-16T12:00:00Z",
  "deduplication_index": {},
  "merged_recommendations": [],
  "evidence_refs": [],
  "summary": ""
}
```
