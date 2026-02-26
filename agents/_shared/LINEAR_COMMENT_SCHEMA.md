# Shared Linear Comment Schema
Last Updated: 2026-02-21 01:40 CET

Use this schema for all orchestrator/worker comments in Linear to keep comments machine-parseable.

## Required Wrapper
- Include this marker line before any schema payload:
  - `<!-- AGENT_EVENT_V1 -->`
- Include one fenced YAML block after marker.

## Packet Types
- Orchestrator task packet comments:
  - `event: task_packet`
  - `packet_type`: `DEV_TASK` | `TEST_TASK` | `REVIEW_TASK`
  - must include assignment context fields:
    - `worker_slot`
    - `worktree_root`
    - `branch`
- Worker runtime comments:
  - `event`: `start` | `heartbeat` | `handoff` | `done` | `blocked` | `failed` | `not_ready`

## Required YAML Fields (All Events)
- `tracking_mode`
- `task_identifier`
- `issue_id`
- `role`
- `event`
- `branch`
- `head_commit`
- `checks`
- `decision`
- `packet_version`

## Runtime Fields (Required For Worker Runtime Events)
- `worker_slot` (for example `dev-1`, `test-1`, `review-1`)
- `worktree_path`
- `session_id` (dispatcher/session handle when available)
- `handoff_to` (required for `handoff`)

## Example (Developer Handoff)
````markdown
<!-- AGENT_EVENT_V1 -->
```yaml
tracking_mode: linear
task_identifier: UOW-022
issue_id: PAY-22
role: backend-developer
event: handoff
worker_slot: dev-1
worktree_path: /Users/slobodan/Projects/Oroboros/.worktrees/dev-1
session_id: 019c7f00-demo
handoff_to: backend-tester
branch: codex/dev-1/PAY-22
head_commit: abc1234
checks:
  - "pytest -q: pass"
  - "ruff check: pass"
decision: ready_for_testing
packet_version: 3
```
````

## Parsing Rule
- If multiple schema comments exist, consume the newest comment containing `AGENT_EVENT_V1`.
