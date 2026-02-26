---
name: linear-handoff-sync
description: Perform atomic Linear issue status update + deduplicated handoff comment + local sync log append in one deterministic operation.
metadata:
  short-description: Atomic Linear handoff sync
---

# Linear Handoff Sync

## Overview

Use this skill to replace manual multi-step handoff sync:
1. resolve issue
2. resolve/mapping target status
3. update status
4. create deduplicated comment
5. append local sync log

Source of truth for status names:
- `agents/_shared/LINEAR_WORKFLOW.md`

Default local sync log path:
- `reports/optimus-prime/LINEAR_SYNC_LOG.jsonl`

## Script

`/Users/slobodan/Projects/Agents/skills/linear-handoff-sync/scripts/linear_handoff_sync.py`

## Input Contract

```json
{
  "issue_identifier": "MYO-###",
  "target_phase": "agent_working|agent_work_done|agent_testing|agent_test_done|agent_review|agent_review_done|human_review|done|backlog",
  "summary_payload": {
    "task_identifier": "MYO-###",
    "branch": "string|null",
    "head_commit": "sha|null",
    "decision": "ready_for_test|ready_for_review|blocked|ready_for_cloud_review|done|...",
    "checks": [
      {"name": "string", "result": "pass|fail|skip", "details": "string|null"}
    ],
    "blockers": ["string"]
  },
  "comment_template": "optional-template-name-or-inline",
  "dry_run": false
}
```

Optional extensions:
- `status_override_name`: explicit status name override (sets `override_used=true`)
- `linear_workflow_path`: custom workflow mapping path
- `linear_sync_log_path`: custom sync log path
- `linear_endpoint`: custom GraphQL endpoint (default `https://api.linear.app/graphql`)
- `linear_api_key`: API key override (or use `LINEAR_API_KEY` env)

## Idempotency

Event fingerprint input:
- `issue_identifier + target_phase + head_commit + decision`

Tool behavior:
- Adds comment fingerprint marker in comment body.
- Checks local sync log and remote issue comments for the fingerprint.
- If found, skips comment creation and returns `dedup_hit=true`.

## Usage

### Dry run

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/linear-handoff-sync/scripts/linear_handoff_sync.py --input-json - --json-pretty
{
  "issue_identifier": "MYO-155",
  "target_phase": "agent_testing",
  "summary_payload": {
    "task_identifier": "MYO-155",
    "branch": "codex/dev-1/MYO-155",
    "head_commit": "abc123",
    "decision": "ready_for_review",
    "checks": [{"name": "unit", "result": "pass", "details": null}],
    "blockers": []
  },
  "dry_run": true
}
JSON
```

### Live run

```bash
LINEAR_API_KEY="<your-key>" \
python3 /Users/slobodan/Projects/Agents/skills/linear-handoff-sync/scripts/linear_handoff_sync.py \
  --issue-identifier MYO-155 \
  --target-phase agent_testing \
  --summary-payload-json '{"task_identifier":"MYO-155","branch":"codex/dev-1/MYO-155","head_commit":"abc123","decision":"ready_for_review","checks":[{"name":"unit","result":"pass"}],"blockers":[]}' \
  --repo-root /Users/slobodan/Projects/Agents \
  --json-pretty
```

## Failure Behavior

- Unknown phase or missing mapping: config error, no remote writes.
- Issue not found: `not_found` error.
- Status updated but comment fails: `partial_success=true` with `retry_token`.
- Local log append fails: hard failure (for non-dry-run).
