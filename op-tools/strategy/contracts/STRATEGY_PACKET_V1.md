# Strategy Packet v1 Contract

Status: Draft v1 (Phase 2 Packet 1)  
Date: 2026-03-12  
Owner: `op-tools/strategy`

## Purpose

Define a deterministic strategy output contract that planners and runtime orchestration can consume without local semantic forks.

## Top-Level Fields

- `schema_version`: fixed `strategy-packet.v1`
- `identity`: canonical ID object with required cross-project IDs
- `strategy`: versioned strategic baseline metadata
- `recommendations`: prioritized recommendation objects
- `recommendation_mapping`: deterministic per-recommendation refs for `op-plan` and `op-initialize`
- `constraints`: explicit hard/soft constraints for planning and dispatch
- `kpi_targets`: expected measurable outcomes
- `source`: generator context
- `gate_policy`: machine-readable thresholds for REQ-059 build gating
- `strategy_quality_report`: consumability artifact covering citation coverage, contradiction status, confidence distribution, and gate verdicts

## Required Canonical IDs

Minimum required:

- `identity.project_id`
- `identity.run_id`
- `identity.event_id`

Optional but recommended:

- `identity.era_id`
- `identity.plan_id`

## Recommendation Contract

Each recommendation entry must include:

- `recommendation_id`
- `priority` (`high` | `medium` | `low`)
- `summary`
- `rationale`
- `expected_impact`
- `risk_level` (`low` | `medium` | `high` | `critical`)

## Recommendation Mapping Contract

Each mapping entry must include:

- `recommendation_id`
- `op_plan_ref`
- `op_initialize_ref`

## Validation

- Machine schema: `contracts/strategy_packet.v1.schema.json`
- Deterministic sample: `examples/strategy_packet.sample.v1.json`
- Consumability validator: `python3 scripts/strategy_packet_validate.py --input strategy/current/strategy_packet.v1.json --schema contracts/strategy_packet.v1.schema.json`
