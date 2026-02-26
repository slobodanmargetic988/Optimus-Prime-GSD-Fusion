# Shared Tracking Mode Contract
Last Updated: 2026-02-21 01:40 CET

Use this contract to keep agent coordination deterministic with and without Linear.

## Canonical Modes
- `tracking_mode: linear`
  - Canonical state: Linear issue status + structured Linear comments.
  - Worker agents must read the latest role task packet comment before execution.
  - Worker agents must write structured event comments for handoff/results.
- `tracking_mode: local`
  - Canonical state: per-issue local files only.
  - `state.yaml` at `/reports/issues/<ISSUE-OR-TASK-ID>/state.yaml`
  - `events.jsonl` at `/reports/issues/<ISSUE-OR-TASK-ID>/events.jsonl`
  - Worker agents append events to `events.jsonl` and update `state.yaml`.

## Non-Canonical Files
- Shared sprint reports under `/reports/SPRINT_*` are snapshots only.
- Only orchestrator should write shared sprint report snapshots.
- Worker agents must not edit shared sprint report files.

## Role Task Packets
- Orchestrator publishes role-specific task packets as needed:
  - `DEV_TASK`
  - `TEST_TASK`
  - `REVIEW_TASK` (optional, only when review is explicitly requested)
- Packet body must be structured and include:
  - `task_identifier`
  - `tracking_mode`
  - `role`
  - `worker_slot`
  - `worktree_root`
  - `branch`
  - acceptance criteria / test scope
  - `packet_version`

## Structured Event Minimum Fields
- `tracking_mode`
- `task_identifier`
- `role`
- `event`
- `worker_slot`
- `worktree_path`
- `handoff_to` (when handoff event)
- `branch`
- `head_commit`
- `checks`
- `decision`
- `packet_version`

## Resolution Rules
1. Explicit current prompt inputs override all defaults.
2. If readable, this file defines default tracking behavior.
3. If missing, fallback:
   - when `linear_issue_id` is provided, use `tracking_mode=linear`
   - otherwise use `tracking_mode=local`
