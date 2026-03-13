# Research Plan Wave 2 Non-Ceremonial Rewrite (2026-03-13)

## Goal
Apply a second-pass task-shape rewrite consistent with prior Wave 2 pattern: remove ceremony, keep non-TDD execution-first flow, and retain only value-bearing stages.

## Changes Applied
- Preserved requirements at 60 (no scope shrink).
- Replaced uniform 4-stage-per-requirement packet with targeted stage expansion.
- New task count: 222 (down from 240).
- Stage distribution:
  - contract/data-model: 60
  - reasoning/processing: 60
  - hardening: 60
  - multi-call trace: 20
  - validator/gate: 15
  - operational acceptance: 7

## Why This Is Better For Autonomous Build
- Keeps baseline execution shape simple (contract -> reasoning -> hardening everywhere).
- Adds extra stages only where they matter (trace-heavy, planner-critical, UI-reference-critical requirements).
- Reduces low-value duplication in validator/acceptance tasks while preserving quality gates.

## Vision Alignment
- LLM-first research remains core.
- UI projects still receive per-screen visual reference URL + provenance outputs.
- Planner handoff stays machine-readable and validator-backed.
