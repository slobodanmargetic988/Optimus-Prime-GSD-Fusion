# Active Cloner Architecture v1

## 1) Runtime model
- Component type: standalone `active-*` service.
- Loop cadence: configurable (default 30-120 seconds by workload).
- Main stages per cycle:
  1. source ingestion
  2. similarity graph update
  3. tile candidate ranking
  4. tile synthesis/evolution
  5. placement decision and execution
  6. integrity + telemetry update

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

## 6) Placement engine
- For each approved tile:
  - detect compatible insertion locations
  - evaluate replacement safety
  - perform bounded transformation
  - run targeted verification
- Persist placement record with hash and commit reference.

## 7) Warranty and lifecycle
- "Lifetime warranty" means tracked ownership:
  - all placements are known
  - tile updates can locate and migrate all placements
  - failed upgrades are rollbackable
- Warranty health is measured via integrity checks and drift detection.

## 8) Safety model
- Tiered decision model:
  - low-risk cluster updates: low-cost model
  - synthesis and placement: stronger model + policy gate
  - risky/high-impact replacements: operator approval path
- Never auto-place tiles on critical/high-risk code paths without policy confirmation.

## 9) Terminal observability
- All key actions emit timestamped terminal events:
  - discovery counts
  - candidate promotion decisions
  - synthesis results
  - placement outcomes
  - integrity check findings
- Artifacts remain machine-readable for downstream consumption.
