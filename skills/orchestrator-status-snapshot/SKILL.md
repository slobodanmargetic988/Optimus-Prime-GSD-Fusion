---
name: orchestrator-status-snapshot
description: Build a deterministic single-call orchestration state snapshot from Optimus report files (workers, cycle, handoff, rate gates, runtime leases, and blocker intelligence).
metadata:
  short-description: Single-call orchestration status fan-in
---

# Orchestrator Status Snapshot

## Overview

Use this skill to replace manual fan-in status checks across:
- `reports/optimus-prime/WORKER_REGISTRY.json`
- `reports/optimus-prime/CYCLE_LOG.jsonl`
- `reports/optimus-prime/HANDOFF_LOG.jsonl`
- `reports/optimus-prime/PROFILE_RATE_REGISTRY.json`
- `reports/optimus-prime/RATE_STATUS_LOG.jsonl`
- optional runtime/blocker sources:
  - `reports/optimus-prime/RUNTIME_REGISTRY.json`
  - `reports/optimus-prime/TEST_RUNTIME_LEASES.json`
  - `reports/optimus-prime/BLOCKERS.jsonl`
  - `reports/optimus-prime/BLOCKER_INDEX.json`

The script is read-only and emits deterministic JSON.

## Script

`/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/skills/orchestrator-status-snapshot/scripts/orchestrator_status_snapshot.py`

## Input Contract

```json
{
  "repo_root": "string",
  "include_history": false,
  "max_history_items": 5,
  "include_process_check": true,
  "output_mode": "json|json+text"
}
```

Notes:
- `repo_root` is required.
- `output_mode=json+text` adds deterministic `text_summary` in JSON.
- Worker output includes required `session_id` field.

## Usage

### CLI flags

```bash
python3 /Users/slobodan/projects/Optimus-Prime-GSD-Fusion/skills/orchestrator-status-snapshot/scripts/orchestrator_status_snapshot.py \
  --repo-root /Users/slobodan/projects/Optimus-Prime-GSD-Fusion \
  --output-mode json+text \
  --include-history \
  --max-history-items 5 \
  --json-pretty
```

### JSON contract via file/stdin

```bash
cat <<'JSON' | python3 /Users/slobodan/projects/Optimus-Prime-GSD-Fusion/skills/orchestrator-status-snapshot/scripts/orchestrator_status_snapshot.py \
  --input-json - --json-pretty
{
  "repo_root": "/Users/slobodan/projects/Optimus-Prime-GSD-Fusion",
  "include_history": false,
  "max_history_items": 5,
  "include_process_check": true,
  "output_mode": "json+text"
}
JSON
```

## Output Contract

Top-level fields:
- `ok`
- `schema_version` (`1.0`)
- `tool` (`orchestrator-status-snapshot`)
- `tool_version`
- `generated_at` (UTC ISO8601)
- `cycle`
- `workers` (fixed ordering: `dev-1`, `dev-2`, `dev-3`, `test-1`, `test-2`, `review-1`)
- `counts`
- `rate`
- `high_priority_blockers`
- `runtime`
- `blockers`
- `warnings`
- `errors`
- `parse_warning_count`
- `text_summary` (when `output_mode=json+text`)

Worker object fields:
- `slot`, `role`, `state`
- `active_task`, `branch`
- `dispatch_pid`, `session_id`, `pid_alive`
- `last_result`, `last_result_at`
- `blocker_summary`, `next_expected_action`

## Failure Behavior

- Missing required source file -> `errors[]` item with `code=missing_file` and full path.
- Malformed JSONL line -> `parse_warning_count` increments and warning is logged.
- All required sources unavailable -> `ok=false` with actionable remediation.
