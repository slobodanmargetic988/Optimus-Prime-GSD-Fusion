---
name: blocker-escalate-to-agents
description: Create or update unresolved blocker issues in Linear project Agents with deterministic dedup and operator callout text.
metadata:
  short-description: Deterministic blocker escalation
---

# Blocker Escalate To Agents

## Overview

Use this skill to standardize unresolved blocker escalation.

Behavior:
- Computes deterministic dedup key.
- Finds matching open blocker issue in `Agents` project.
- Updates existing issue or creates new issue.
- Assigns to `me` by default.
- Always writes local escalation log (or returns explicit log-write error).
- Returns reusable callout text for orchestrator chat.

## Script

`/Users/slobodan/Projects/Agents/skills/blocker-escalate-to-agents/scripts/blocker_escalate_to_agents.py`

## Input Contract

```json
{
  "blocker_kind": "workflow|infra|rate_limit|review_noise|worktree|other",
  "title": "string",
  "reproduction_context": "string",
  "impact": "string",
  "attempted_mitigation": ["string"],
  "requested_user_action": "string",
  "related_task_identifier": "MYO-###|null",
  "severity": "low|medium|high",
  "project_name": "Agents",
  "assignee": "me",
  "dedup_key": "optional-string",
  "dry_run": false,
  "repo_root": "string"
}
```

Optional:
- `linear_api_key` (or use `LINEAR_API_KEY` env)
- `linear_endpoint` (default `https://api.linear.app/graphql`)
- `local_log_path` (default `reports/optimus-prime/BLOCKER_ESCALATION_LOG.jsonl`)

## Dedup

- If `dedup_key` provided, use as-is.
- Otherwise generate from normalized:
  - blocker kind
  - title
  - related task identifier
  - primary symptom phrase

## Output Contract

Fields include:
- `action` (`create|update`)
- `issue_identifier`
- `issue_url`
- `dedup_key`
- `linear_sync_logged`
- `callout_text`
- `warnings` / `errors`

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/blocker-escalate-to-agents/scripts/blocker_escalate_to_agents.py --input-json - --json-pretty
{
  "blocker_kind": "worktree",
  "title": "Branch checkout blocked by active worktree",
  "reproduction_context": "Assigned branch is active in another worktree and checkout is denied.",
  "impact": "Developer worker cannot continue the task on intended branch.",
  "attempted_mitigation": ["Retried checkout", "Validated branch is active elsewhere"],
  "requested_user_action": "Please confirm fallback branch policy for this task.",
  "related_task_identifier": "MYO-158",
  "severity": "high",
  "project_name": "Agents",
  "assignee": "me",
  "dry_run": true,
  "repo_root": "/Users/slobodan/Projects/Agents"
}
JSON
```

## Failure Behavior

- Linear unavailable: writes pending retry event to local log.
- Project missing: explicit setup error.
- Assignee unresolved: warning + fallback to unassigned issue write attempt.
