# Shared Linear Workflow
Last Updated: 2026-02-24 19:42 CET

Use this file as the single source of truth for Linear workflow status names across all agents.
If you change status names in Linear, update this file once and reuse it through `linear_workflow_path`.

## Default Path
- `/Users/slobodan/Projects/Agents/agents/_shared/LINEAR_WORKFLOW.md`

## Status Map (Canonical)
- `agent_working_status`: `Agent working`
- `agent_work_done_status`: `Agent work DONE`
- `agent_testing_status`: `Agent testing`
- `agent_test_done_status`: `Agent test DONE`
- `agent_review_status`: `Agent review`
- `agent_review_done_status`: `Agent review DONE`
- `human_review_status`: `Human Review`

## Fallbacks
- `fallback_in_progress_status`: `In Progress`
- `fallback_ready_for_test_statuses`: `Agent work DONE`, `Agent testing`
- `fallback_ready_for_review_statuses`: `Agent test DONE`, `Agent review DONE`, `Human Review`

## Handoff Comment Contract
- Developer handoff comment must include:
  - `handoff_to` (for example `backend-tester`, `frontend-tester`)
  - `branch` (exact git branch testers should use)
  - `head_commit` (short SHA or full SHA)
- Tester not-ready comment should be concise and include:
  - reason task is not ready
  - expected status or handoff signal

## Resolution Rules
1. If `linear_workflow_path` is provided and readable, agents load status names from that file.
2. If explicit status inputs are also provided (for example `linear_ready_for_test_status`, `linear_ready_statuses`), explicit inputs override this file.
3. If neither exists, agents use built-in defaults from their own definitions.

## Blocker Escalation Rules
- Operational blockers that cannot be autonomously resolved must be tracked in Linear project `Agents`.
- Blocker issues must be assigned to `me` (or explicit `blocker_assignee` override when provided).
- Blocker issue body must include:
  - reproduction context
  - current impact
  - attempted mitigation
  - exact user action requested
- Orchestrator must explicitly notify the user in chat to review newly created/updated blocker issue(s).
