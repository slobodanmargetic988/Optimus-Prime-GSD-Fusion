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
- First vertical target: real dispatch + DONE marker observed.
- Canary target: 5 successful consecutive cycles with no manual intervention.
- Check-in cadence for coding work: every 5 completed tasks.
