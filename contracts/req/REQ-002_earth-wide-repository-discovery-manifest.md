# REQ-002 Earth-wide Repository Discovery Manifest

## Purpose

Define the contract and data-model surface for strategy-level Earth repository discovery.

This contract anchors:
- Earth subproject discovery
- canonical project IDs
- mission/scope source references
- explicit exclusion policy for archived and non-owner paths
- broad-sweep strategy inputs for cross-project reasoning
- evidence-linked recommendation output fields
- explicit open-risk capture for unresolved cross-project ideas
- rerun-stable manifest ordering and fingerprinting

## Interface Surface

- Implementation module: `scripts/strategy_context_sweep.py`
- Primary builder: `build_earth_repository_discovery_manifest(earth_root, owner_username=None, emit=None)`
- Contract validator: `validate_earth_repository_discovery_manifest(payload)`

## Manifest Contract (v1)

- `schema_version`: fixed string `req-002.earth-wide-repository-discovery-manifest.v1`
- `policy`: explicit include/exclude policy
- `earth_root`: resolved Earth root path
- `broad_sweep_inputs`: deterministic Earth-sweep context inputs
- `projects`: discovered project entries sorted by `project_id`
- `excluded_paths`: excluded candidate paths and explicit `reason_code`
- `evidence_refs`: stable, de-duplicated evidence refs gathered from sweep outputs
- `cross_project_context`: per-project context rows sourced from Earth-wide sweep evidence
- `recommendation`: complete recommendation model with decision/rationale/actions and evidence-backed obligations
- `open_risks`: unresolved ideas recorded explicitly when evidence is incomplete
- `stats`: deterministic counts
- `discovery_fingerprint`: SHA-256 of canonical `projects` payload

### `policy`

- `include_rule`: `direct_child_repository_roots_only`
- `owner_rule.owner_username`: owner username used by policy
- `owner_rule.required_path_prefix`: expected owner Earth prefix
- `exclude_rules`: explicit rules
  - `exclude_non_directory`
  - `exclude_hidden_path`
  - `exclude_archived_path`
  - `exclude_non_owner_path`
  - `exclude_non_repository_path`

### `projects[]`

- `project_id`: canonical ID (`prj.<slug>`)
- `project_name`: repository directory name
- `repo_relpath`: Earth-root-relative repository path
- `repo_root`: resolved repository root path
- `source_refs.mission`: `mission.md` or `null`
- `source_refs.scope`: `scope.md` or `null`

### `broad_sweep_inputs`

- `earth_root`: resolved Earth root path
- `owner_username`: owner username used by policy
- `owner_prefix`: resolved owner Earth prefix
- `include_rule`: `direct_child_repository_roots_only`
- `direct_child_count`: integer direct-child scan count
- `discovered_project_ids`: sorted list of discovered `project_id` values
- `source_ref_coverage`: mission/scope coverage counters
- `excluded_reason_counts`: deterministic counts for each explicit exclude rule

### `cross_project_context[]`

- one row per discovered project, sorted by `project_id`
- `context_status`: `complete` or `partial`
- `mission_ref` / `scope_ref`: repo-relative refs or `null`
- `evidence_refs`: non-empty refs grounded in Earth-sweep outputs

### `recommendation`

- `decision`: deterministic strategy decision string
- `rationale`: human-readable rationale grounded in sweep evidence
- `context_project_ids`: sorted discovered project IDs
- `evidence_refs`: non-empty recommendation evidence refs
- `action_items`: non-empty recommended actions
- `proposed_cross_project_obligations`: obligations are allowed only when backed by non-empty `evidence_refs`

### `open_risks[]`

- unresolved cross-project ideas must be recorded here when evidence is partial
- each risk includes `risk_id`, `summary`, and non-empty `evidence_refs`

## Stability Requirements

- Manifest must be stable across reruns for unchanged Earth root contents.
- `projects` must be sorted by `project_id`.
- `project_id` values must be unique.
- `evidence_refs` must be sorted, unique, and deterministic.
- `cross_project_context` must include exactly one row per discovered project.
- Cross-project obligations must not be emitted without Earth-sweep evidence refs.
- Unresolved cross-project ideas must be represented under `open_risks` (not silently implemented).
- `discovery_fingerprint` must be deterministic for stable input.

## Sample Artifacts

- Executable fixture:
  - `examples/fixtures/earth-wide-repository-discovery-manifest.json`
- Strategy sample:
  - `strategy/current/samples/REQ-002_earth-wide-repository-discovery-manifest.sample.json`

The sample structure in `strategy/current/samples/REQ-002_earth-wide-repository-discovery-manifest.sample.json`
is the reference shape for this requirement.
