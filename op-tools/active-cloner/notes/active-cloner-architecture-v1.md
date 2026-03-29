# Active Cloner Architecture v1

## 1) Runtime model
- Component type: standalone `active-*` service.
- Loop cadence: configurable (default 30-120 seconds by workload).
- Main stages per cycle:
  1. source ingestion
  2. similarity graph update
  3. tile candidate ranking
  4. tile synthesis/evolution
  5. variant translation and catalog update
  6. placement decision and execution
  7. integrity + telemetry update

## 2) Source ingestion
- Inputs:
  - plan artifacts (`PLAN_PACKETS`, `TASK_EXECUTION_STATE`, evidence bundles)
  - prompt/task histories
  - commit histories and diffs
  - code snapshots
  - prior tile registry and placement logs
- Extract unified records:
  - prompt family signal
  - task intent tags
  - code pattern fingerprints
  - commit outcome metadata

## 3) Similarity and clustering
- Build dual similarity system:
  - text/intention similarity (prompts, tasks, user stories)
  - code/structure similarity (AST/fingerprint/diff signatures)
- Generate task groups with cross-links:
  - many prompts -> many commits -> shared solution families
- Persist searchable groups in Elasticsearch.

## 4) Elasticsearch index model (v1)
- `task_groups`:
  - group_id, labels, prompt_cluster_ids, code_cluster_ids, support_count
- `tile_candidates`:
  - candidate_id, group_id, priority_score, expected_reuse, risk_score
- `code_tiles`:
  - tile_id, version, contract, params, tests, status
- `tile_variants`:
  - tile_id, variant_id, framework_family, source_path, translation_source_variant, status
- `tile_placements`:
  - placement_id, tile_id, project, repo_path, commit_sha, hash, status
- `tile_integrity_events`:
  - tile_id, placement_id, event_type, findings, resolved

## 5) Tile synthesis contract
- Tile is generated only when candidate passes minimum threshold:
  - sufficient usage/support count
  - non-trivial logical unit
  - stable behavioral contract
  - testability and integration clarity
- Tile package includes:
  - source template/module
  - parameter schema
  - compatibility matrix
  - tests and verification recipe
  - migration notes
  - one or more framework variants
  - translation trace between variants

## 6) Variant translation and catalog
- Cloner should maintain a catalog that is useful before full autonomous placement exists.
- Each tile can have one or more stack variants under the same behavioral contract.
- Translation should be explicit:
  - source variant
  - target variant
  - translation notes
  - drift status
- Manual extraction is acceptable in v1 as long as the tile is normalized into the shared catalog structure.

## 7) Placement engine
- For each approved tile:
  - detect compatible insertion locations
  - resolve the host stack and choose the best matching tile variant
  - evaluate replacement safety
  - perform bounded transformation
  - run targeted verification
- Persist placement record with hash and commit reference.

## 8) Warranty and lifecycle
- "Lifetime warranty" means tracked ownership:
  - all placements are known
  - tile updates can locate and migrate all placements
  - failed upgrades are rollbackable
- Warranty health is measured via integrity checks and drift detection.

## 9) Safety model
- Tiered decision model:
  - low-risk cluster updates: low-cost model
  - synthesis, translation, and placement: stronger model + policy gate
  - risky/high-impact replacements: operator approval path
- Never auto-place tiles on critical/high-risk code paths without policy confirmation.

## 10) Terminal observability
- All key actions emit timestamped terminal events:
  - discovery counts
  - candidate promotion decisions
  - synthesis results
  - translation results
  - catalog updates
  - placement outcomes
  - integrity check findings
- Artifacts remain machine-readable for downstream consumption.
