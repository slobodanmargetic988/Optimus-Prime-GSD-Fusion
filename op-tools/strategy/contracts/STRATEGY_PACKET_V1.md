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
- `recommendation_to_planner_mapping_artifact`: REQ-054 mapping from recommendation IDs to planner task intent handles
- `constraints`: explicit hard/soft constraints for planning and dispatch
- `kpi_targets`: expected measurable outcomes
- `source`: generator context

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

## REQ-054 Planner Mapping Contract

The strategy packet must embed `recommendation_to_planner_mapping_artifact` so planner/runtime can gate intake deterministically.

The artifact must include:

- `recommendation_to_task_intent_mappings`
- `recommendation_ids`
- `planner_task_intent_handles`

Each mapping row must include:

- `mapping_id`
- `recommendation_id`
- `planner_task_intent_handle`
- `planner_task_intent_summary`
- `planner_lane`
- `sequence_hint`
- `traceability_refs`
- `downstream_audit_trail`

Planner consumability rule:

- every `recommendations[].recommendation_id` must be covered by at least one mapping row
- mapping rows must not reference recommendation IDs absent from `recommendations[]`

## Validation

- Machine schema: `contracts/strategy_packet.v1.schema.json`
- Deterministic sample: `examples/strategy_packet.sample.v1.json`
- Packet validator/gate: `python3 scripts/strategy_packet_validate.py --input strategy/current/strategy_packet.v1.json --schema contracts/strategy_packet.v1.schema.json`
