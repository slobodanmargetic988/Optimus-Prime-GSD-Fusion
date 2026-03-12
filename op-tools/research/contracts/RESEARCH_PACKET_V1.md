# Research Packet v1 Contract

Status: Draft v1 (Phase 2 Packet 1)  
Date: 2026-03-12  
Owner: `op-tools/research`

## Purpose

Define a deterministic machine-readable research output contract that can be consumed by Strategy and OP planning/runtime flows.

## Top-Level Fields

- `schema_version`: fixed `research-packet.v1`
- `identity`: canonical ID object with required cross-project IDs
- `context`: project mission/scope/strategy linkage metadata
- `topics`: research topic pack summaries
- `open_questions`: unresolved questions requiring follow-up
- `evidence_refs`: source artifacts proving research claims
- `source`: generator context

## Required Canonical IDs

Minimum required:

- `identity.project_id`
- `identity.run_id`
- `identity.event_id`

Optional but recommended:

- `identity.era_id`
- `identity.plan_id`

## Topic Contract

Each topic entry must include:

- `topic_id`
- `title`
- `recommendation_summary`
- `tradeoffs` (non-empty array)
- `risk_level` (`low` | `medium` | `high` | `critical`)

## Evidence Ref Contract

Each evidence reference must include:

- `artifact_id`
- `kind`
- `uri`

Optional:

- `notes`

## Validation

- Machine schema: `contracts/research_packet.v1.schema.json`
- Deterministic sample: `examples/research_packet.sample.v1.json`
