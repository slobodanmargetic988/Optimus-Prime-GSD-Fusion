# Research Plan Wave 3 Task Quality Lock (2026-03-13)

## Goal
Run a strict quality pass over the Wave 2 non-ceremonial packet without changing architecture direction, requirement set, or phase ordering.

## Scope of This Pass
- Reviewed all 222 tasks for ambiguity and manager-invention risk.
- Added requirement-anchored scope lock lines to every task.
- Preserved phase/lane structure, requirement IDs, and dependency DAG.

## Concrete Changes Applied
- `PLAN_PACKETS.json` updated:
  - every task now has 4 `must_haves` lines (up from 3),
  - added one `Scope lock for REQ-*` line per task,
  - scope lock text binds each task to that requirement's acceptance anchors and anti-hallucination boundaries.
- No tasks added or removed in Wave 3.
- No requirement IDs changed.
- No dependency edges changed.

## Why This Improves Autonomous Build
- Reduces unmanaged invention:
  - each task now states both what to do and what not to do.
- Tightens requirement traceability:
  - manager decisions can map directly to acceptance criteria.
- Improves failure-path quality:
  - hardening and validator tasks now explicitly forbid masking invalid/degraded outputs.

## Validation Results
- requirements: 60
- tasks: 222
- stage distribution unchanged:
  - contract/data-model: 60
  - reasoning/processing: 60
  - hardening: 60
  - multi-call trace: 20
  - validator/gate: 15
  - operational acceptance: 7
- ambiguity phrases (`where relevant`, `if applicable`, `as needed`, `as appropriate`): 0
- TDD-first tokens (`tdd`, `expect_fail`, `tdd_red`): 0
- tasks missing scope lock: 0
- tasks missing verify commands: 0
- dependency DAG issues: none

## Non-Changes (Intentional)
- No return to deterministic-only research generation.
- No reintroduction of uniform ceremonial validator/acceptance tasks.
- No schema-contract redesign in this pass.
