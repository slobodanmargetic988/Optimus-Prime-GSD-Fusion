# OP Simple Task Backlog V2

## Status
- Active backlog as of 2026-03-06.
- V1 backlog is frozen at `docs/plans/OP_SIMPLE_TASK_BACKLOG.md`.

## Execution Rules
- Coding cadence: pause every 5 completed coding tasks.
- At each pause: summarize work and list blockers.
- Schema approvals remain explicit human decisions.
- Prompt approvals can happen after implementation.
- Implementation can start once planning-question closure is reached; schema/prompt review continues post-implementation.
- If file relevance is uncertain during cleanup: keep it and mark review-needed.

## Tracker Columns
- `ID | Task | Owner | Depends On | Status | Blocked By | Last Update`

## Status Key
- `READY`, `IN_PROGRESS`, `BLOCKED_HUMAN`, `BLOCKED_DEP`, `DONE`

## Checkpoint 1 (Locked First Vertical)
| ID | Task | Owner | Depends On | Status | Blocked By | Last Update |
|---|---|---|---|---|---|---|
| V2-T001 | Create canonical V2 spec (`OP_SIMPLE_EXECUTION_SPEC_V2.md`) | AI | - | DONE | - | 2026-03-06 |
| V2-T002 | Create V2 backlog and freeze V1 references | AI | V2-T001 | DONE | - | 2026-03-06 |
| V2-T003 | Implement cycle loop skeleton for `/op-simple-build` (`while`, counter, terminate check, sleep) | AI | V2-T001,V2-T002 | DONE | - | 2026-03-06 |
| V2-T004 | Implement manager call framework for cycle-manager/profile-manager/BOSS + manager_call_log | AI | V2-T003 | DONE | - | 2026-03-06 |
| V2-T005 | Implement BOSS-timeout marker lifecycle (`boss_evidence.json`) | AI | V2-T004 | DONE | - | 2026-03-06 |

## Checkpoint 2 (Next)
| ID | Task | Owner | Depends On | Status | Blocked By | Last Update |
|---|---|---|---|---|---|---|
| V2-T006 | Wire dispatcher fire-and-forget path using thread-dispatch | AI | V2-T004 | DONE | - | 2026-03-06 |
| V2-T007 | Wire watchdog + stop priority handling | AI | V2-T003 | DONE | - | 2026-03-06 |
| V2-T008 | Add summary print stage and timeout-skip behavior | AI | V2-T004 | DONE | - | 2026-03-06 |
| V2-T009 | Run first vertical with real packet dispatch and DONE marker observation | AI | V2-T005,V2-T006,V2-T007,V2-T008 | DONE | - | 2026-03-07 |

## Planning Closure (V1 T001-T101 Equivalence)
| ID | Task | Owner | Depends On | Status | Blocked By | Last Update |
|---|---|---|---|---|---|---|
| V2-T012 | Create schema catalog doc (single catalog format) and auto-import previously approved schema decisions | AI | V2-T002 | DONE | - | 2026-03-06 |
| V2-T013 | Reconcile schema conflicts using \"newest explicit user statement wins\" rule | AI | V2-T012 | DONE | - | 2026-03-06 |
| V2-T014 | Finalize manager I/O contracts (cycle-manager, profile-manager snapshot-only, BOSS, dispatcher, watchdog, summary) including `task_execution_state` ownership | AI | V2-T013 | DONE | - | 2026-03-06 |
| V2-T015 | Finalize remaining PARTIAL/OPEN items in coverage matrix and mark equivalence gate status | AI | V2-T014 | READY | - | 2026-03-06 |
| V2-T016 | Human review: approve equivalence gate closure before implementation starts | HUMAN | V2-T015 | DONE | - | 2026-03-07 |

## Phase 2 Placeholder
| ID | Task | Owner | Depends On | Status | Blocked By | Last Update |
|---|---|---|---|---|---|---|
| V2-T010 | Add prompt packs for additional worker types (`integration_tester`, `plan-reviewer`) | AI | V2-T009 | DONE | - | 2026-03-07 |
| V2-T011 | Bootstrap new `tetris` GitHub repo task (deferred until after Checkpoint 1) | JOINT | V2-T005 | DONE | - | 2026-03-07 |
