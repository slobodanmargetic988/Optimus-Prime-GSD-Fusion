# OP Tools Incubator

This folder contains OP-native tool projects that OP can run directly and evolve internally.

## Naming convention
- Prefix `active-` means a standalone long-lived thread/service with bounded autonomy.
- `active-*` tools are optimized for frequent, surgical operations and can use lower-cost models for small problems.

## Initial tool set
- `strategy`: ecosystem-aware strategy expansion before planning.
- `research`: mission/strategy-aligned evidence and resource synthesis before planning.
- `active-merger`: independent merge monitor and commit decision service.
- `active-debugger`: independent small-fix and runtime triage service.
- `active-cloner`: reusable code-tile mining, adaptation, and placement service.

## Pipeline intent
1. Strategy generates ecosystem-fit guidance artifacts.
2. Research expands strategy and mission with implementation evidence.
3. Planner consumes mission + scope + strategy/research artifacts.
