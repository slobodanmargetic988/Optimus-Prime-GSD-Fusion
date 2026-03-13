# Strategy Plan Wave 3 Task Quality Lock (2026-03-13)

## Goal
Run a strict quality pass over the existing Wave 2 non-TDD packet without changing architecture direction, phase ordering, or requirement set.

## Scope of This Pass
- Reviewed all 260 tasks for ambiguity, ceremonial drift, and places where BOSS would need to invent behavior.
- Added requirement-anchored scope locks to every task so execution is bounded by acceptance criteria already defined in the requirement set.
- Preserved existing phase/lane layout and dependency graph.

## Concrete Changes Applied
- `PLAN_PACKETS.json` updated:
  - every task now has 4 `must_haves` lines (up from 3),
  - added one `Scope lock for REQ-*` line per task,
  - scope lock line includes requirement acceptance anchors and anti-hallucination boundary text.
- No new tasks added and no tasks removed in Wave 3.
- No requirement IDs changed.
- No dependency edges changed.

## Why This Helps Autonomous Build
- Reduces unmanaged invention:
  - each task now explicitly states what not to do, not only what to build.
- Binds implementation to requirement anchors:
  - managers can trace each decision back to acceptance criteria instead of inferring missing intent.
- Improves failure hygiene:
  - hardening tasks now explicitly forbid masking unhappy paths and require deterministic reason-code evidence.

## Validation Results
- requirements: 70
- tasks: 260
- stage distribution unchanged:
  - contract/data-model: 70
  - reasoning/processing: 70
  - hardening: 70
  - multi-call trace: 23
  - validator/gate: 17
  - operational acceptance: 10
- ambiguity phrases (`where relevant`, `if applicable`, `as needed`, `as appropriate`): 0
- TDD-first tokens (`tdd`, `expect_fail`, `tdd_red`): 0
- tasks missing scope lock: 0
- tasks missing verify commands: 0
- bad requirement references: 0
- dependency DAG issues: none

## Non-Changes (Intentional)
- No move back to deterministic-only strategy generation.
- No reintroduction of ceremonial-only acceptance tasks.
- No broad rewrite of validator or trace schema contracts in this pass.
