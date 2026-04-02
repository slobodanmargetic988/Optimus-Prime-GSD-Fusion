# UAT

Plan ID: `plan-20260310T232916Z-strategy-tool-v1`

## Actors
- `ProjectMaintainer`
- `EarthSteward`
- `PlannerOrchestrator`

## Primary Flows
1. Project-scoped strategy run
   Success signal: `strategy/current/STRATEGY.md`, `STRATEGY.json`, `ECOSYSTEM_LINK_MAP.json`, and `STRATEGY_CHANGELOG.md` are regenerated alongside a history revision.
2. Earth-root stewardship run
   Success signal: drift, investment-balance, synergy, and strategic-debt analysis appears with measurable rationale and risks.
3. Planner handoff
   Success signal: recommendation IDs, dependency effects, and the exact 400-task mandatory planning gate are present for downstream planning.

## UAT Pass Conditions
- The local smoke scenario runs without manual steps beyond the documented CLI command.
- Narrative outputs preserve missing-reference assumptions instead of silently discarding them.
- Strategy history is diffable across consecutive runs and does not show random directional churn for unchanged inputs.

Autonomous tester-driven UAT is satisfied only when scenario evidence is present in canonical task evidence artifacts and all requirement scenarios have a corresponding green verification path.
