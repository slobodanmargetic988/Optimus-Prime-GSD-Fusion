# Scope: Active Cloner

## Core scope
- Run as independent active service with periodic scan cycles.
- Inspect all available plans, tasks, prompt histories, commit histories, and codebases.
- Build similarity graphs between:
  - prompt/task text clusters
  - produced code clusters
  - commit lineage and implementation outcomes
- Identify candidate reusable patterns and rank by expected reuse value.
- Convert selected candidates into configurable code tiles.
- Place/replace tiles in suitable code locations when policy checks pass.

## Tile definition and quality gates
- A tile must represent meaningful logical value, not trivial fragments.
- Minimum tile threshold must be enforced (structure + behavior + contract).
- Every tile must include:
  - parameter/argument schema
  - integration contract
  - test contract
  - compatibility notes
  - upgrade strategy
- Each tile carries lifetime maintenance obligation ("lifetime warranty") through tracked placements and versioning.

## Placement and integrity scope
- Maintain placement registry for all tile insertions.
- Store placement hashes and compatibility metadata.
- Support integrity checks to detect drift/corruption/manual divergence.
- Support safe in-place tile upgrades and rollback on failed validation.

## Data and search scope
- Index task groups, prompt clusters, commit clusters, and tile metadata in Elasticsearch.
- Keep searchable mapping from prompt families to candidate/satisfied tiles.
- Record confidence and evidence for each clustering and tile synthesis decision.

## Autonomy and escalation model
- Routine clustering and low-risk tile recommendations can use cost-optimized models.
- Tile synthesis and replacement actions require stronger policy checks.
- High-risk replacements escalate to stronger model or operator gate.
- All decisions must emit explicit reasoned terminal output and durable artifacts.

## Integration scope
- Planner should be able to consume tile catalog as reusable building blocks.
- BOSS/dispatch can reference tile-compatible tasks during packet design.
- Active Merger can validate tile placement commits through dedicated policy hooks.

## Non-goals
- Replacing all handcrafted code with tiles.
- Auto-rewriting high-risk code paths without validation gates.
- Treating one-off logic as reusable tile candidates.
