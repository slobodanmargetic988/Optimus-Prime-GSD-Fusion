# Scope: Research Tool

## Mandatory planning contract
- Research artifacts must be generated before planner runs that target major project scopes.
- For implementation projects generated from research-informed planning, decomposition must reach at least 400 tasks before build start.

## Core scope
- Consume mission, scope, and Strategy outputs.
- Build milestone-to-topic mapping and prioritize research depth by milestone criticality.
- Generate per-topic research documents with implementation-ready suggestions.
- Capture provenance for all external references and clearly label confidence.
- Highlight unresolved research gaps that require follow-up before build.

## Artifact contract
- `research/current/RESEARCH_INDEX.md`
- `research/current/MILESTONE_MAP.json`
- `research/current/topics/<topic-id>.md`
- `research/current/topics/<topic-id>.json`
- `research/current/OPEN_QUESTIONS.md`

## Quality requirements
- Each topic pack must include: context, options, tradeoffs, recommendation, and risks.
- Visual/media references must include source and usage notes.
- Technical suggestions should include concrete implementation pathways, not abstract commentary only.

## Integration scope
- Planner v2+ should ingest research index and selected topic packs as first-class context.
- Planner should be able to reference research topic IDs in generated task rationale.
- Research outputs must remain both human-readable and machine-readable.

## Non-goals
- Auto-executing implementation tasks.
- Generating or redistributing restricted copyrighted assets.
- Replacing architecture ownership decisions by project maintainers.
