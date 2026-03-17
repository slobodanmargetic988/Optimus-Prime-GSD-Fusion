# REQ-058: Ecosystem Obligation Artifact

## Purpose
Define the contract and data-model surface for emitting project interaction obligations across other Earth apps, with explicit produce/consume responsibilities and dependency prerequisites.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-058):
  - Emit deterministic ecosystem obligations linked to peer Earth apps.
  - Distinguish obligation responsibility as `produce` or `consume`.
  - Require dependency prerequisites for each obligation.
  - Keep output bounded to this requirement's contract surface.
- Out of scope (REQ-058): net-new packet sections, managers, orchestration gates, or strategy behaviors outside ecosystem obligation artifact handoff.

## Interface surface
Builder:
- `build_req_058_ecosystem_obligation_artifact(payload) -> dict`

Validator:
- `validate_req_058_ecosystem_obligation_artifact(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-058 expects:

```json
{
  "analysis_type": "ecosystem_obligation_artifact",
  "now_utc": "2026-03-16T11:30:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "ecosystem_obligations": [
    {
      "obligation_id": "obl.consume-runtime-heartbeats",
      "peer_project_id": "earth-core-runtime",
      "responsibility": "consume",
      "artifact": "runtime_lease_heartbeat_events",
      "obligation_summary": "Consume runtime lease heartbeat events to detect stale worker behavior in strategy decisions.",
      "dependency_prerequisites": [
        "dep.runtime-heartbeat-contract",
        "dep.state-artifact-cadence"
      ],
      "evidence_refs": [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `ecosystem_obligation_artifact` when provided.
- `target_project.project_root` must be an absolute path.
- `ecosystem_obligations[]` must contain at least one row.
- `obligation_id` values must be unique.
- `peer_project_id` must reference an external Earth app (must not equal `target_project.project_id`).
- `responsibility` must be one of `produce`, `consume`.
- `dependency_prerequisites[]` must be a non-empty sorted unique string list.
- `evidence_refs[]` must be a non-empty sorted unique string list.

## Output contract
REQ-058 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- artifact payload: `ecosystem_obligation_artifact`
- bounded counts: `totals`

`ecosystem_obligation_artifact` contains:
- `ecosystem_obligations[]`

Each `ecosystem_obligations[]` row includes:
- `obligation_id`
- `peer_project_id`
- `responsibility`
- `artifact`
- `obligation_summary`
- `dependency_prerequisites[]`
- `evidence_refs[]`

`totals` includes:
- `ecosystem_obligations`
- `produce_responsibilities`
- `consume_responsibilities`
- `unique_dependency_prerequisites`

Obligation behavior:
- Every obligation must target another Earth app via `peer_project_id`.
- Every obligation must declare whether the project is producing or consuming.
- Every obligation must include dependency prerequisites.
- Totals must match emitted obligation rows and unique prerequisite coverage.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/ecosystem-obligation-artifact.json`
- Contract tests: `tests/contracts/test_ecosystem-obligation-artifact.py`
- Output sample: `strategy/current/samples/REQ-058_ecosystem-obligation-artifact.sample.json`

The structure in `strategy/current/samples/REQ-058_ecosystem-obligation-artifact.sample.json`
is the canonical contract shape for REQ-058 and documents:
- `ecosystem_obligation_artifact.ecosystem_obligations`
- `ecosystem_obligation_artifact.ecosystem_obligations[].responsibility`
- `ecosystem_obligation_artifact.ecosystem_obligations[].dependency_prerequisites`
- `totals`
