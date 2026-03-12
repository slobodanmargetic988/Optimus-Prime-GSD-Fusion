# OP Pre-Planner Stage: Strategy and Research

## Goal
Add a pre-planner stage before `/op-initialize` planning:
1. Strategy
2. Research
3. Planner
4. Active optimization services (for example `active-cloner`, `active-merger`, `active-debugger`) consume outputs continuously.

## Rationale
- Planner quality improves when it consumes structured strategic and research context.
- Ecosystem alignment should be explicit, versioned, and auditable.
- Cross-project synergy and strategic drift should be measured over time.

## Stage contracts

### Strategy stage
- Inputs:
  - mission/scope
  - project artifacts
  - Earth ecosystem context (when available)
- Outputs:
  - versioned strategy docs
  - ecosystem linkage analysis
  - strategic change suggestions for current and adjacent projects

### Research stage
- Inputs:
  - mission/scope
  - strategy outputs
- Outputs:
  - milestone-topic research packs
  - implementation suggestions
  - public resource references and provenance

### Planner stage (v2+ target)
- Inputs:
  - mission/scope
  - strategy outputs
  - research outputs
- Behavior:
  - absorb pre-planner artifacts as first-class context
  - produce higher-quality task decomposition and dependency graph

### Post-planner active services
- `active-cloner`:
  - mines reusable patterns across plan/task/prompt/commit/code history
  - synthesizes adaptable code tiles with placement/integrity tracking
- `active-merger`:
  - continuously evaluates and merges relevant commits
- `active-debugger`:
  - continuously resolves bounded small defects with evidence

## Active tool convention
- Prefix `active-` means a standalone service/thread with bounded autonomy.
- `active-*` tools are intended for frequent high-precision loops and can use cost-optimized models by default.
- Required for all `active-*` tools:
  - strict evidence trail
  - confidence-aware escalation
  - operator override path
