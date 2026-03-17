# REQ-052: strategy_packet.v1 Generator

## Purpose
Define the contract and data-model surface for generating a planner/runtime-ready `strategy_packet.v1` JSON artifact from validated final strategy synthesis output plus packet-specific enrichment.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-052):
  - Build deterministic `strategy_packet.v1` JSON output for planner/runtime consumption.
  - Emit canonical IDs in `packet.identity`.
  - Emit only the contract-required `strategy-packet.v1` top-level sections.
- Out of scope (REQ-052): net-new packet sections, managers, orchestration gates, or behavior outside the bounded packet generator surface.

## Interface surface
Builder:
- `build_req_052_strategy_packet_v1_generator(payload) -> dict`

Validator:
- `validate_req_052_strategy_packet_v1_generator(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

Reference contract:
- Human contract: `op-tools/strategy/contracts/STRATEGY_PACKET_V1.md`
- Machine schema: `op-tools/strategy/contracts/strategy_packet.v1.schema.json`

## Input contract
`strategy_artifacts_handoff.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "strategy_packet_v1_generator",
  "now_utc": "2026-03-16T10:05:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "identity": {
    "run_id": "run.20260316t100500z-task185",
    "event_id": "event.20260316t100500z-strategy-packet",
    "era_id": "era.2026q1-canary-stabilization",
    "plan_id": "plan.optimus-prime-gsd-fusion-canary"
  },
  "strategy": {
    "revision_id": "strategy-2026-03-15T08:00:00Z",
    "summary": "Human-facing strategy summary",
    "link_map_ref": "strategy/current/ECOSYSTEM_LINK_MAP.json"
  },
  "recommendation_profiles": [
    {
      "recommendation_id": "rec.harden-telemetry-freshness",
      "expected_impact": "Human-facing expected impact",
      "risk_level": "medium"
    }
  ],
  "constraints": {
    "hard": [],
    "soft": []
  },
  "kpi_targets": [
    {
      "metric": "telemetry_freshness_lag_minutes",
      "direction": "decrease",
      "target": "Return freshness lag to single-digit minutes."
    }
  ],
  "source": {
    "repo": "Optimus-Prime-GSD-Fusion",
    "tool": "scripts/strategy_artifacts_handoff.py"
  },
  "final_strategy_synthesis": {
    "final_recommendations": [],
    "deferred_recommendations": [],
    "open_risks": [],
    "strategy_packet_inputs": []
  }
}
```

Rules:
- `analysis_type` must be `strategy_packet_v1_generator`.
- `target_project.project_id` must be non-empty.
- `target_project.project_root` must normalize to an absolute path.
- `identity.run_id` must match `run.<lowercase-hyphenated-id>`.
- `identity.event_id` must match `event.<lowercase-hyphenated-id>`.
- `identity.era_id` and `identity.plan_id` are optional, but when present they must match `era.<lowercase-hyphenated-id>` and `plan.<lowercase-hyphenated-id>`.
- `strategy.revision_id` and `strategy.summary` must be non-empty.
- `strategy.link_map_ref` is optional; when present it must be a non-empty string.
- `recommendation_profiles[]` must provide exactly one row for every `final_strategy_synthesis.final_recommendations[].recommendation_id`.
- Each `recommendation_profiles[]` row must include:
  - `recommendation_id`
  - `expected_impact`
  - `risk_level`
- `risk_level` must be `low`, `medium`, `high`, or `critical`.
- `constraints` must include `hard[]` and `soft[]` string lists.
- Each `kpi_targets[]` row must include:
  - `metric`
  - `direction`
  - optional `target`
- `direction` must be `increase`, `decrease`, or `maintain`.
- `source` must include non-empty `repo` and `tool`.
- `final_strategy_synthesis.final_recommendations[]` must be a non-empty list and supplies the emitted packet recommendations.

## Output contract
REQ-052 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- synthesis target: `target_project`
- packet artifact surface: `strategy_packet_v1`
- planner/runtime audit context: `strategy_packet_context`
- bounded counts: `totals`

`strategy_packet_v1` contains:
- `artifact_path` (`strategy_packet.v1.json`)
- `packet`

`strategy_packet_v1.packet` contains the required `strategy-packet.v1` top-level sections only:
- `schema_version`
- `identity`
- `strategy`
- `recommendations`
- `constraints`
- `kpi_targets`
- `source`

`identity` includes:
- `project_id`
- `run_id`
- `event_id`
- optional `era_id`
- optional `plan_id`

Generation behavior:
- `identity.project_id` is derived canonically from `target_project.project_id` as `prj.<target-project-slug>`.
- `recommendations[]` are emitted from `final_strategy_synthesis.final_recommendations[]` in deterministic synthesis order.
- `priority`, `summary`, and `rationale` come from `final_strategy_synthesis.final_recommendations[]`.
- `expected_impact` and `risk_level` come from `recommendation_profiles[]`.
- No additional packet sections may be emitted beyond the required `strategy-packet.v1` top-level surface.

`strategy_packet_context` contains deterministic planner/runtime audit fields outside the packet:
- `recommendation_readiness`
- `cross_project_context_usage`
- `open_risks`

`recommendation_readiness[]` includes:
- `recommendation_id`
- `strategy_packet_input_id`
- `packet_kind`
- `peer_project_id`
- `lane`
- `evidence_refs`
- `earth_sweep_evidence_refs`
- `recommendation_field_completeness`

Generation guardrails:
- Every `final_strategy_synthesis.final_recommendations[].strategy_packet_input_id` must resolve to `final_strategy_synthesis.strategy_packet_inputs[]`.
- Cross-project recommendations must carry at least one direct Earth-sweep evidence ref in `evidence_refs`; otherwise generation fails instead of inventing a cross-project packet obligation.
- Unresolved ideas remain visible through `strategy_packet_context.open_risks` and must not be promoted into packet recommendations.

`totals` includes:
- `recommendations`
- `hard_constraints`
- `soft_constraints`
- `kpi_targets`

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/strategy-packet-v1-generator.json`
- Contract tests: `tests/contracts/test_strategy-packet-v1-generator.py`
- Output sample: `strategy/current/samples/REQ-052_strategy-packet-v1-generator.sample.json`

The structure in `strategy/current/samples/REQ-052_strategy-packet-v1-generator.sample.json`
is the canonical contract shape for REQ-052 and documents:
- `strategy_packet_v1.packet.identity`
- `strategy_packet_v1.packet.strategy`
- `strategy_packet_v1.packet.recommendations`
- `strategy_packet_v1.packet.constraints`
- `strategy_packet_v1.packet.kpi_targets`
- `strategy_packet_v1.packet.source`
- `strategy_packet_context.recommendation_readiness`
- `strategy_packet_context.cross_project_context_usage`
- `strategy_packet_context.open_risks`
- `totals`
