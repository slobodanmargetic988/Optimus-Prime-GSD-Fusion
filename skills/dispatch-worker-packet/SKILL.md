---
name: dispatch-worker-packet
description: Prepare worker packet, dispatch worker via thread-dispatch, and update local orchestration state files in one deterministic operation.
metadata:
  short-description: Packet + dispatch + state sync
---

# Dispatch Worker Packet

## Overview

Use this skill to replace manual multi-step dispatch flow:
1. create packet in `reports/optimus-prime/prompts`
2. run `thread-dispatch`
3. update `WORKER_REGISTRY.json`
4. append `HANDOFF_LOG.jsonl`
5. update `BRANCH_LINEAGE.json`
6. append `THREAD_HISTORY.log`
7. optional cycle note append

## Script

`/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/dispatch-worker-packet/scripts/dispatch_worker_packet.py`

## Input Contract

```json
{
  "slot": "dev-1|dev-2|dev-3|test-1|test-2|review-1",
  "role": "developer|tester|reviewer|flex-tester",
  "task_identifier": "MYO-###",
  "repo_root": "string",
  "worktree_root": "string",
  "branch_name": "codex/<slot>/<issue>",
  "start_from_branch": "string",
  "start_from_commit": "sha",
  "acceptance_criteria": ["string"],
  "packet_version": 1,
  "codex_profile_alias": "codex|codex-second|...",
  "mcp_mode": "disable-all|enable-only",
  "mcp_allowlist": ["context7", "playwright", "chrome_devtools"],
  "sandbox_mode": "workspace-write|danger-full-access",
  "sandbox_add_dirs": ["string"],
  "runtime_strategy": "none|external_url|shared_runtime|isolated_runtime",
  "runtime_base_url": "https://shared-test.example.com",
  "tester_must_not_start_runtime": true,
  "test_train_mode": "off|final-stage|forced-shared-env",
  "wave_id": "wave-0007",
  "deployed_test_commit": "abc1234",
  "test_lane_account": "acct-02",
  "op_build_mode": false,
  "plan_id": "plan-20260227T010101Z",
  "requirement_ids": ["REQ-001"],
  "task_acceptance_refs": ["AC-001"],
  "dev_ready_evidence_ref": "reports/optimus-prime/planning/DEV_READY_EVIDENCE.json",
  "dry_run": false
}
```

Optional:
- `cycle_note` (append note to `CYCLE_LOG.jsonl`)

## Enforcement

- Slot/role compatibility is validated before dispatch.
- Worker MCP allowlist cannot include `linear` or `linear_sse`.
- `enable-only` requires a non-empty allowlist.
- Branch must match slot prefix `codex/<slot>/...`.
- `start_from_commit` must be a 7-40 hex SHA.
- In `test_train_mode` (`final-stage` / `forced-shared-env`), tester packets must set:
  - `tester_must_not_start_runtime=true`
  - `runtime_strategy=external_url|shared_runtime`
  - non-empty `runtime_base_url`
- In `op_build_mode=true`, packets must set:
  - non-empty `plan_id`
  - non-empty `requirement_ids[]`
  - non-empty `task_acceptance_refs[]`
  - non-empty `dev_ready_evidence_ref`
- Legacy compatibility paths are intentionally out of scope for this repo; use the OP-build packet contract as the only supported model.

## Packet Requirements Included

Generated packet includes:
- start anchors (`start_from_branch`, `start_from_commit`)
- fallback suffix policy (`-dev`, `-test`)
- required worker fallback reporting fields:
  - `intended_branch`
  - `fallback_branch`
  - `fallback_reason`

## Usage

### Dry run

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/dispatch-worker-packet/scripts/dispatch_worker_packet.py --input-json - --json-pretty
{
  "slot": "dev-1",
  "role": "developer",
  "task_identifier": "MYO-156",
  "repo_root": "/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion",
  "worktree_root": "/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion",
  "branch_name": "codex/dev-1/MYO-156",
  "start_from_branch": "main",
  "start_from_commit": "abc1234",
  "acceptance_criteria": ["Implement tool and tests"],
  "packet_version": 1,
  "codex_profile_alias": "codex",
  "mcp_mode": "disable-all",
  "mcp_allowlist": [],
  "sandbox_mode": "danger-full-access",
  "sandbox_add_dirs": [],
  "dry_run": true
}
JSON
```

## Failure Behavior

- Packet creation failure -> dispatch not attempted.
- Dispatch failure -> registry remains non-running.
- Registry update failure after dispatch -> critical error with remediation block (`pid`, `task_identifier`, `slot`, manual steps).
