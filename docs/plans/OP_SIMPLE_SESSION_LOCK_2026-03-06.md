# OP Simple Session Lock - 2026-03-06

This file locks decisions approved in chat so they are not lost across sessions.

## Locked Decisions
- Active branch: `codex/simple-op`; do not touch `main`.
- New runtime command: `/op-simple-build`.
- Keep `/op-initialize` mostly as-is; rewrite focuses on build-cycle runtime.
- Replace old build behavior on this branch; no backward compatibility target here.
- Keep rule for existing files during cleanup: keep only what supports initialize or new cycle managers.
- Delete rule: remove legacy `/op-build` orchestration not referenced by initialize or `/op-simple-build`.
- Uncertain files: keep and mark review-needed.
- BOSS naming lock: production-line-manager is renamed to `BOSS`.
- Cycle order lock: `cycle-manager -> profile-manager -> BOSS -> work-dispatcher -> watchdog -> summary`.
- Cycle pacing: fixed 5-minute sleep.
- Stop priority: terminate file > project_done > insurmountable_blocker > watchdog.
- DONE marker: `[DONE][lane:<id>][task:<id>]`.
- BOSS owns done/liveness interpretation; dispatcher is fire-and-forget.
- BOSS timeout marker exists and is timeout-only (`boss_evidence.json`).
- No deterministic in-cycle schema/lint enforcement for LLM artifacts.
- Schema contracts still exist and remain human-approved.
- Prompt files location: `scripts/op_simple/prompts/` with manager/worker split.
- Artifact root: `./.op-simple/` with `current/` canonical outputs.
- History snapshots are enabled by default with unlimited retention.
- First vertical target: real dispatch + DONE marker observed.
- Canary target: 5 successful consecutive cycles with no manual intervention.
- Check-in cadence for coding work: every 5 completed tasks.
- Rate-gate stage runs after BOSS and before dispatcher.
- Rate-gate wait ownership stays in profile-manager behavior.
- One canonical output file per manager under `.op-simple/current/`.
- Dispatcher writes deterministic launch receipts to `dispatch_launch_log.jsonl`.
- Dispatcher does not write deterministic failure artifacts for reassignment.
- OP code does not write deterministic DONE evidence artifacts; BOSS gathers evidence directly.
- Cycle summary minimum fields: `cycle_number`, `manager_statuses`, `task_counts`, `dispatch_counts`, `notes`.
- Watchdog branch source: `.op-simple/current/initialize_state.json`.
- Watchdog idle counter resets on any new commit on monitored branch.
- Workstation prep artifact is written once by initialize code before cycle start.
- Manager timeout budgets:
  - `cycle-manager` 5m
  - `profile-manager` 7m
  - `BOSS` 12m
  - `watchdog` 2m
  - `summary` 2m
- Prior schema decisions can be auto-imported as locked unless contradicted.
- Conflict resolution rule: newest explicit user statement wins.
- Preferred schema documentation format: single catalog with fields+rationale+example JSON per artifact.
