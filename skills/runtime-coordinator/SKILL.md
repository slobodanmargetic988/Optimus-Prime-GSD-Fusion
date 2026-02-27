---
name: runtime-coordinator
description: Resolve runtime strategy, manage shared/isolated runtime leases, and aggregate blocker events into recurring adaptation candidates.
metadata:
  short-description: Runtime strategy + lease + blocker intelligence
---

# Runtime Coordinator

## Overview

Use this skill to keep runtime handling generic across projects and centralize blocker intelligence.

Core actions:
- `bootstrap` — initialize runtime health/action/repair artifacts.
- `start` — execute profile start command.
- `health` — evaluate pipeline + profile health gate.
- `stop` — execute profile stop command.
- `repair` — run self-heal once, then delegate repair task when still unhealthy.
- `resolve` — choose runtime strategy and return dispatch payload.
- `release_lease` — release shared-runtime tester lease.
- `upsert_runtime` — update runtime instance status.
- `log_blocker` — append one structured blocker event.
- `refresh_blocker_index` — aggregate `BLOCKERS.jsonl` into `BLOCKER_INDEX.json` + adaptation report.

## Script

`/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/runtime-coordinator/scripts/runtime_coordinator.py`

## Input Contract

```json
{
  "repo_root": "string",
  "action": "bootstrap|start|health|stop|repair|resolve|release_lease|upsert_runtime|refresh_blocker_index",
  "task_identifier": "MYO-123",
  "worker_slot": "test-1",
  "worker_role": "tester",
  "task_kind": "ui_flow",
  "requires_browser": true,
  "mutating_flow": false,
  "runtime_strategy_override": "shared_runtime",
  "test_train_mode": "off|final-stage|forced-shared-env",
  "test_train_pipeline_path": "reports/optimus-prime/config/TEST_TRAIN_PIPELINE.json",
  "runtime_profile_id": "default-web",
  "external_base_url": "http://127.0.0.1:4173",
  "runtime_id": "rt-shared-default-web",
  "lease_id": "uuid",
  "requested_status": "healthy",
  "blocker_stage": "runtime|build|test|review|orchestration|...",
  "blocker_code": "runtime_start_failed",
  "blocker_category": "runtime|infra|env|test-train|dependency|code|test|review|orchestration|external|unknown",
  "blocker_summary": "Human readable summary",
  "blocker_signature": "Stable signature for fingerprinting",
  "blocker_retryable": true,
  "blocker_evidence_paths": ["reports/optimus-prime/logs/..."],
  "blocker_index_min_count": 2,
  "blocker_index_max_entries": 20
}
```

Optional path overrides:
- `runtime_profiles_path`
- `runtime_registry_path`
- `runtime_leases_path`
- `blockers_path`
- `blocker_index_path`
- `blocker_adaptation_report_path`

Defaults map to `reports/optimus-prime/*` inside `repo_root`.

## Key Outputs

### resolve
- `runtime_strategy`
- `dispatch_payload.runtime_profile_id`
- `dispatch_payload.runtime_id`
- `dispatch_payload.base_url`
- `dispatch_payload.lease_id`
- `dispatch_payload.tester_must_not_start_runtime`

### refresh_blocker_index
- `rows_processed`
- `rows_malformed`
- `entries`
- `recurring_entries`
- output file paths for index/report

## Policy Notes

- Browser flow testing should prefer shared orchestrator-managed runtime.
- Mutating shared flows are lease-controlled (`serialized|account_pool|isolated`).
- Blocking runtime outcomes are appended to `BLOCKERS.jsonl`.
- Recurring blockers are converted into adaptation candidates.

See `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/runtime-coordinator/references/contracts.md`.
