# REQ-070: End-to-End Autonomous Strategy Run And Acceptance Packet

## Purpose
Define the contract and data-model surface for a deterministic acceptance packet proving that a strategy run emitted the required current, history, and validator artifacts, and that the resulting output is planner-consumable and ecosystem-aware under Earth-sweep context.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-070):
  - Emit deterministic current, history, and validator artifact rows for one autonomous strategy run.
  - Carry planner consumability proof with recommendation mapping completeness.
  - Carry Earth-sweep ecosystem awareness proof with explicit peer project coverage.
  - Carry open risks needed to preserve acceptance honesty when peer-side proof is still pending.
  - Keep output bounded to this requirement's contract surface.
- Out of scope (REQ-070): net-new managers, orchestration gates, prompt changes, or autonomous processing behavior outside acceptance-packet handoff.

## Interface surface
Builder:
- `build_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(payload) -> dict`

Validator:
- `validate_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-070 expects:

```json
{
  "analysis_type": "end_to_end_autonomous_strategy_run_acceptance_packet",
  "now_utc": "2026-03-17T10:45:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "run_identity": {
    "project_id": "optimus-prime-gsd-fusion",
    "run_id": "run.2026-03-17T10-45-00Z.req070",
    "event_id": "evt.req070.acceptance",
    "strategy_revision_id": "strategy-rev-2026-03-17",
    "plan_id": "plan.req070.phase1"
  },
  "current_artifacts": [
    {
      "artifact_id": "current.strategy-packet",
      "path": "strategy/current/strategy_packet.json",
      "status": "present",
      "evidence_refs": [
        "strategy/current/strategy_packet.json#L1"
      ]
    }
  ],
  "history_artifacts": [
    {
      "artifact_id": "history.strategy-run",
      "path": "strategy/history/2026-03-17/strategy_run.json",
      "status": "present",
      "evidence_refs": [
        "strategy/history/2026-03-17/strategy_run.json#L1"
      ]
    }
  ],
  "validator_artifacts": [
    {
      "artifact_id": "validator.contract-report",
      "path": "strategy/current/validators/contract-report.json",
      "status": "pass",
      "evidence_refs": [
        "strategy/current/validators/contract-report.json#L1"
      ]
    }
  ],
  "planner_consumability": {
    "ready_for_planner": true,
    "recommendation_mapping_complete": true,
    "consumability_verdict": "planner-consumable",
    "recommendation_ids": [
      "rec.req070.current-history-validator"
    ],
    "recommendation_mapping_refs": [
      "strategy/current/strategy_packet.json#recommendations"
    ],
    "evidence_refs": [
      "strategy/current/strategy_packet.json#recommendations"
    ]
  },
  "ecosystem_awareness": {
    "ecosystem_aware": true,
    "context_project_ids": [
      "earth-analytics-hub",
      "earth-core-runtime",
      "optimus-prime-gsd-fusion"
    ],
    "peer_project_ids": [
      "earth-analytics-hub",
      "earth-core-runtime"
    ],
    "earth_sweep_evidence_refs": [
      "reports/earth/sweeps/earth-core-runtime/summary-2026-03-17.json"
    ]
  },
  "open_risks": [
    {
      "risk_id": "risk.peer-acceptance-pending",
      "summary": "Peer-side acceptance proof is not yet emitted for one downstream consumer.",
      "reason_code": "peer_acceptance_pending",
      "required_evidence_refs": [
        "reports/earth/sweeps/earth-analytics-hub/request-2026-03-17.json"
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `end_to_end_autonomous_strategy_run_acceptance_packet` when provided.
- `target_project.project_root` must be an absolute path.
- `run_identity` must include non-empty `project_id`, `run_id`, `event_id`, `strategy_revision_id`, and `plan_id`.
- `current_artifacts[]`, `history_artifacts[]`, and `validator_artifacts[]` must each contain at least one row.
- Every artifact row must include `artifact_id`, `path`, lowercase `status`, and non-empty sorted unique `evidence_refs[]`.
- `planner_consumability.ready_for_planner` and `planner_consumability.recommendation_mapping_complete` must both be `true`.
- `planner_consumability.recommendation_ids[]`, `recommendation_mapping_refs[]`, and `evidence_refs[]` must be non-empty sorted unique string lists.
- `ecosystem_awareness.ecosystem_aware` must be `true`.
- `ecosystem_awareness.context_project_ids[]` must include `target_project.project_id`.
- `ecosystem_awareness.peer_project_ids[]` must be external Earth apps only and must be a subset of `context_project_ids[]`.
- `ecosystem_awareness.earth_sweep_evidence_refs[]` must be a non-empty sorted unique string list.
- `open_risks[]` may be empty, but each row must include `risk_id`, `summary`, `reason_code`, and non-empty `required_evidence_refs[]`.

## Output contract
REQ-070 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchors: `target_project`, `run_identity`
- artifact payload: `end_to_end_strategy_run_acceptance_packet`
- bounded counts: `totals`

`end_to_end_strategy_run_acceptance_packet` contains:
- `current_artifacts[]`
- `history_artifacts[]`
- `validator_artifacts[]`
- `planner_consumability`
- `ecosystem_awareness`
- `open_risks[]`

`planner_consumability` contains:
- `ready_for_planner`
- `recommendation_mapping_complete`
- `consumability_verdict`
- `recommendation_ids[]`
- `recommendation_mapping_refs[]`
- `evidence_refs[]`

`ecosystem_awareness` contains:
- `ecosystem_aware`
- `context_project_ids[]`
- `peer_project_ids[]`
- `earth_sweep_evidence_refs[]`

`totals` includes:
- `current_artifacts`
- `history_artifacts`
- `validator_artifacts`
- `planner_recommendations`
- `peer_projects_considered`
- `open_risks`
- `evidence_refs`

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/end-to-end-autonomous-strategy-run-and-acceptance-packet.json`
- Contract tests: `tests/contracts/test_end-to-end-autonomous-strategy-run-and-acceptance-packet.py`
- Output sample: `strategy/current/samples/REQ-070_end-to-end-autonomous-strategy-run-and-acceptance-packet.sample.json`

The structure in `strategy/current/samples/REQ-070_end-to-end-autonomous-strategy-run-and-acceptance-packet.sample.json`
is the canonical contract shape for REQ-070 and documents:
- `end_to_end_strategy_run_acceptance_packet.current_artifacts`
- `end_to_end_strategy_run_acceptance_packet.history_artifacts`
- `end_to_end_strategy_run_acceptance_packet.validator_artifacts`
- `end_to_end_strategy_run_acceptance_packet.planner_consumability`
- `end_to_end_strategy_run_acceptance_packet.ecosystem_awareness`
- `end_to_end_strategy_run_acceptance_packet.open_risks`
- `totals`
