# Scope: Strategy Tool

## Mandatory planning contract
- Strategy outputs are pre-planner inputs and must be present before high-quality planning runs.
- For implementation projects generated from strategy, downstream planning must decompose into at least 400 tasks before build start.

## Core scope
- Accept target project root and optional Earth ecosystem root.
- Ingest mission/scope plus existing planning/runtime artifacts.
- Generate versioned strategy baseline, deltas, and forward recommendations.
- Produce explicit ecosystem-link map: current links, missing links, and proposed improvements.
- Identify opportunities to improve existing projects where ecosystem benefit is measurable.

## Artifact contract
- `strategy/current/STRATEGY.md`
- `strategy/current/STRATEGY.json`
- `strategy/current/ECOSYSTEM_LINK_MAP.json`
- `strategy/current/STRATEGY_CHANGELOG.md`
- `strategy/history/<revision-id>/...`

## Quality requirements
- Every strategic recommendation must include rationale, expected impact, and risk.
- Every recommendation should include candidate integration points and likely dependency effects.
- Strategy output must distinguish hard constraints, soft preferences, and speculative ideas.

## Integration scope
- Planner v2+ should ingest strategy artifacts as first-class input.
- Strategy must provide machine-readable recommendation IDs so planner can map tasks back to strategic intent.
- Strategy revisions should be diffable across time for governance and audit.

## Non-goals
- Directly executing implementation tasks.
- Replacing mission/scope ownership from the project owner.
- Forcing roadmap changes without explicit acceptance.
