# REQ-057: Blocker Handling Policy Artifact

## Purpose
Define the contract and data-model surface for emitting machine-consumable blocker handling policy rows with explicit escalation triggers, owner hints, and fallback paths.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-057):
  - Emit deterministic blocker handling policy rows.
  - Require explicit `escalation_trigger` fields for escalation routing.
  - Require explicit `owner_hints` and `fallback_paths` fields so planner/runtime can consume policy data without narrative parsing.
- Out of scope (REQ-057): net-new packet sections, managers, orchestration gates, or policy behaviors outside blocker handling artifact handoff.

## Interface surface
Builder:
- `build_req_057_blocker_handling_policy_artifact(payload) -> dict`

Validator:
- `validate_req_057_blocker_handling_policy_artifact(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-057 expects:

```json
{
  "analysis_type": "blocker_handling_policy_artifact",
  "now_utc": "2026-03-16T11:10:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "blocker_policies": [
    {
      "policy_id": "policy.cross-project-rate-limit",
      "blocker_code": "all_rate_gates_blocking",
      "escalation_trigger": {
        "trigger_type": "attempts_exhausted",
        "threshold": 3,
        "window": "cycles"
      },
      "owner_hints": [
        "boss-manager",
        "runtime-coordinator"
      ],
      "fallback_paths": [
        "pause-and-retry-window",
        "reroute-to-lower-rate-profile"
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `blocker_handling_policy_artifact` when provided.
- `target_project.project_root` must be an absolute path.
- `blocker_policies[]` must contain at least one row.
- `policy_id` values must be unique.
- `blocker_code` must be non-empty.
- `escalation_trigger.trigger_type` must be one of `attempts_exhausted`, `dependency_timeout`, `guardrail_violation`.
- `escalation_trigger.threshold` must be a positive integer.
- `escalation_trigger.window` must be one of `attempts`, `cycles`, `minutes`.
- `owner_hints[]` must be a non-empty sorted unique string list.
- `fallback_paths[]` must be a non-empty sorted unique string list.

## Output contract
REQ-057 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- artifact payload: `blocker_handling_policy_artifact`
- bounded counts: `totals`

`blocker_handling_policy_artifact` contains:
- `policies[]`

Each `policies[]` row includes:
- `policy_id`
- `blocker_code`
- `escalation_trigger.trigger_type`
- `escalation_trigger.threshold`
- `escalation_trigger.window`
- `owner_hints[]`
- `fallback_paths[]`

`totals` includes:
- `policies`
- `unique_blocker_codes`
- `unique_owner_hints`
- `unique_fallback_paths`

Policy behavior:
- Every emitted policy row must include explicit escalation trigger fields.
- Every emitted policy row must include owner hints and fallback paths.
- `totals` counts must match unique IDs/paths referenced in `blocker_handling_policy_artifact.policies[]`.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/blocker-handling-policy-artifact.json`
- Contract tests: `tests/contracts/test_blocker-handling-policy-artifact.py`
- Output sample: `strategy/current/samples/REQ-057_blocker-handling-policy-artifact.sample.json`

The structure in `strategy/current/samples/REQ-057_blocker-handling-policy-artifact.sample.json`
is the canonical contract shape for REQ-057 and documents:
- `blocker_handling_policy_artifact.policies`
- `blocker_handling_policy_artifact.policies[].escalation_trigger.trigger_type`
- `blocker_handling_policy_artifact.policies[].escalation_trigger.threshold`
- `blocker_handling_policy_artifact.policies[].escalation_trigger.window`
- `blocker_handling_policy_artifact.policies[].owner_hints`
- `blocker_handling_policy_artifact.policies[].fallback_paths`
- `totals`
