# OP Simple Task Backlog

> Freeze Notice (2026-03-06): This file is V1 historical context.
> Active tracker: `docs/plans/OP_SIMPLE_TASK_BACKLOG_V2.md`.

## Execution Rules
- Work in batches of 5 completed tasks, then pause.
- After each batch: summarize completed work, list blockers, ask for direction.
- No schema is final without explicit human approval.
- Keep schemas minimal and human-understandable.
- Execute tasks in ID order; only skip forward when current task is `BLOCKED_HUMAN` or `BLOCKED_DEP`.

## Status Key
- `READY`: can be done now.
- `IN_PROGRESS`: currently being implemented.
- `BLOCKED_HUMAN`: waiting on user decision/approval.
- `BLOCKED_DEP`: waiting on dependency.
- `DONE`: completed.

## Blocker Taxonomy
- `schema`: schema draft/review/approval blockers.
- `prompt`: prompt draft/review/approval blockers.
- `policy`: product or runtime policy decision blockers.
- `runtime`: environment/execution-time blockers.

## Tracker Format Lock
- Approved tracker columns for operational use:
  - `ID | Task | Owner | Depends On | Status | Blocked By | Last Update`
- `Blocked By` is free-text.
- `Last Update` format is date-only (`YYYY-MM-DD`).

## Backlog

| ID | Task | Owner | Depends On | Status |
|---|---|---|---|---|
| T001 | Define MVP done criteria for OP Simple | HUMAN | - | DONE |
| T002 | Confirm implementation cadence (5 tasks then pause) | HUMAN | - | DONE |
| T003 | Freeze MVP vs post-MVP scope line | HUMAN | T001 | DONE |
| T004 | Create execution tracker format (`task_id`, `status`, `blocked_by`) | AI | - | DONE |
| T005 | Add dependency graph fields to tracker | AI | T004 | DONE |
| T006 | Approve tracker format | HUMAN | T004,T005 | DONE |
| T007 | Define blocker taxonomy (`schema`, `prompt`, `policy`, `runtime`) | AI | - | DONE |
| T008 | Approve blocker taxonomy | HUMAN | T007 | DONE |
| T009 | Write final new-cycle order spec (current agreed model) | AI | - | DONE |
| T010 | Approve cycle order spec | HUMAN | T009 | DONE |
| T011 | Freeze removed old OP-build step list | AI | T009 | DONE |
| T012 | Approve removed-step freeze | HUMAN | T011 | DONE |
| T013 | Place rate-gate wait logic in exact cycle position | JOINT | T009 | DONE |
| T014 | Approve final rate-gate placement | HUMAN | T013 | DONE |
| T015 | Finalize lane lifecycle spec (8-task lane flow) | AI | T009 | DONE |
| T016 | Approve lane lifecycle spec | HUMAN | T015 | DONE |
| T017 | Define dependency/parallelization decision policy | AI | T015 | DONE |
| T018 | Approve dependency/parallelization policy | HUMAN | T017 | DONE |
| T019 | Define worker role-mix policy boundaries | AI | T015 | DONE |
| T020 | Approve worker role-mix boundaries | HUMAN | T019 | DONE |
| T021 | Define DONE commit marker contract | AI | T015 | DONE |
| T022 | Approve DONE marker contract | HUMAN | T021 | DONE |
| T023 | Schema draft: `worker_registry` (minimal fields) | AI | T009 | DONE |
| T024 | Explain each `worker_registry` field and why it exists | AI | T023 | DONE |
| T025 | Human review/revise `worker_registry` schema | HUMAN | T024 | DONE |
| T026 | Human final approval `worker_registry` schema | HUMAN | T025 | DONE |
| T027 | Schema draft: `profile_snapshot` | AI | T009 | READY |
| T028 | Explain each `profile_snapshot` field | AI | T027 | READY |
| T029 | Human review/revise `profile_snapshot` | HUMAN | T028 | BLOCKED_HUMAN |
| T030 | Human final approval `profile_snapshot` | HUMAN | T029 | BLOCKED_HUMAN |
| T031 | Schema draft: `profile_assignment` (`next-task-profile`, `current-task-profile`) | AI | T009 | READY |
| T032 | Explain each `profile_assignment` field | AI | T031 | READY |
| T033 | Human review/revise `profile_assignment` | HUMAN | T032 | BLOCKED_HUMAN |
| T034 | Human final approval `profile_assignment` | HUMAN | T033 | BLOCKED_HUMAN |
| T035 | Schema draft: `cycle_manager_decision` | AI | T009 | READY |
| T036 | Explain each `cycle_manager_decision` field | AI | T035 | READY |
| T037 | Human review/revise `cycle_manager_decision` | HUMAN | T036 | BLOCKED_HUMAN |
| T038 | Human final approval `cycle_manager_decision` | HUMAN | T037 | BLOCKED_HUMAN |
| T039 | Schema draft: `production_line_register` | AI | T009,T015 | READY |
| T040 | Explain each `production_line_register` field | AI | T039 | READY |
| T041 | Human review/revise `production_line_register` | HUMAN | T040 | BLOCKED_HUMAN |
| T042 | Human final approval `production_line_register` | HUMAN | T041 | BLOCKED_HUMAN |
| T043 | Schema draft: `worker_packet` | AI | T015,T021 | READY |
| T044 | Explain each `worker_packet` field | AI | T043 | READY |
| T045 | Human review/revise `worker_packet` | HUMAN | T044 | BLOCKED_HUMAN |
| T046 | Human final approval `worker_packet` | HUMAN | T045 | BLOCKED_HUMAN |
| T047 | Schema draft: `dispatch_registry` (`pid`, `thread_id`) | AI | T009 | READY |
| T048 | Explain each `dispatch_registry` field | AI | T047 | READY |
| T049 | Human review/revise `dispatch_registry` | HUMAN | T048 | BLOCKED_HUMAN |
| T050 | Human final approval `dispatch_registry` | HUMAN | T049 | BLOCKED_HUMAN |
| T051 | Schema draft: simplified `plan_packets` | AI | T015 | READY |
| T052 | Explain each simplified `plan_packets` field | AI | T051 | READY |
| T053 | Human review/revise simplified `plan_packets` | HUMAN | T052 | BLOCKED_HUMAN |
| T054 | Human final approval simplified `plan_packets` | HUMAN | T053 | BLOCKED_HUMAN |
| T055 | Schema draft: `cycle_summary` payload | AI | T039 | READY |
| T056 | Explain each `cycle_summary` field | AI | T055 | READY |
| T057 | Human review/revise `cycle_summary` | HUMAN | T056 | BLOCKED_HUMAN |
| T058 | Human final approval `cycle_summary` | HUMAN | T057 | BLOCKED_HUMAN |
| T059 | Schema draft: `watchdog_state` + `watchdog_exit_signal` | AI | T009 | READY |
| T060 | Explain each watchdog field | AI | T059 | READY |
| T061 | Human review/revise watchdog schemas | HUMAN | T060 | BLOCKED_HUMAN |
| T062 | Human final approval watchdog schemas | HUMAN | T061 | BLOCKED_HUMAN |
| T063 | Schema draft: workstation sanitation artifact | AI | T009 | READY |
| T064 | Explain workstation sanitation fields | AI | T063 | READY |
| T065 | Human review/revise sanitation schema | HUMAN | T064 | BLOCKED_HUMAN |
| T066 | Human final approval sanitation schema | HUMAN | T065 | BLOCKED_HUMAN |
| T067 | Implement JSON schema validators for all approved schemas | AI | T026,T030,T034,T038,T042,T046,T050,T054,T058,T062,T066 | BLOCKED_DEP |
| T068 | Add schema lint command and CI hook | AI | T067 | BLOCKED_DEP |
| T069 | Prompt draft: `cycle-manager` | AI | T038 | BLOCKED_DEP |
| T070 | Human review/revise `cycle-manager` prompt | HUMAN | T069 | BLOCKED_HUMAN |
| T071 | Human final approval `cycle-manager` prompt | HUMAN | T070 | BLOCKED_HUMAN |
| T072 | Prompt draft: `profile-manager` | AI | T034 | BLOCKED_DEP |
| T073 | Human review/revise `profile-manager` prompt | HUMAN | T072 | BLOCKED_HUMAN |
| T074 | Human final approval `profile-manager` prompt | HUMAN | T073 | BLOCKED_HUMAN |
| T075 | Prompt draft: `production-line-manager` | AI | T042,T054 | BLOCKED_DEP |
| T076 | Human review/revise `production-line-manager` prompt | HUMAN | T075 | BLOCKED_HUMAN |
| T077 | Human final approval `production-line-manager` prompt | HUMAN | T076 | BLOCKED_HUMAN |
| T078 | Prompt draft: worker dev packet | AI | T046,T021 | BLOCKED_DEP |
| T079 | Human review/revise worker dev prompt | HUMAN | T078 | BLOCKED_HUMAN |
| T080 | Human final approval worker dev prompt | HUMAN | T079 | BLOCKED_HUMAN |
| T081 | Prompt draft: worker tester packet | AI | T046,T021 | BLOCKED_DEP |
| T082 | Human review/revise worker tester prompt | HUMAN | T081 | BLOCKED_HUMAN |
| T083 | Human final approval worker tester prompt | HUMAN | T082 | BLOCKED_HUMAN |
| T084 | Prompt draft: worker reviewer packet | AI | T046,T021 | BLOCKED_DEP |
| T085 | Human review/revise worker reviewer prompt | HUMAN | T084 | BLOCKED_HUMAN |
| T086 | Human final approval worker reviewer prompt | HUMAN | T085 | BLOCKED_HUMAN |
| T087 | Scaffold `op-simple` command entrypoint and module layout | AI | T009,T010 | BLOCKED_DEP |
| T088 | Implement initialize-time workstation prep script path | AI | T066 | BLOCKED_DEP |
| T089 | Human approve workstation prep strategy (script shape and controls) | HUMAN | T088 | BLOCKED_HUMAN |
| T090 | Implement plain while-loop runtime skeleton | AI | T087 | BLOCKED_DEP |
| T091 | Implement cycle counter increment (pure code) | AI | T090 | BLOCKED_DEP |
| T092 | Implement termination-file stop check | AI | T090 | BLOCKED_DEP |
| T093 | Integrate foreground `cycle-manager` call | AI | T071,T090 | BLOCKED_DEP |
| T094 | Integrate `profile-manager` snapshot + assignment | AI | T074,T090 | BLOCKED_DEP |
| T095 | Integrate `production-line-manager` packet/register generation | AI | T077,T090 | BLOCKED_DEP |
| T096 | Implement rate-gate wait/continue gate | AI | T014,T090 | BLOCKED_DEP |
| T097 | Implement `work-dispatcher` async send engine | AI | T050,T095 | BLOCKED_DEP |
| T098 | Persist dispatch runtime tracking (`pid`, `thread_id`) | AI | T097 | BLOCKED_DEP |
| T099 | Implement DONE-marker completion detector | AI | T022,T095 | BLOCKED_DEP |
| T100 | Implement simplified watchdog (10-cycle no-commit rule) | AI | T062,T090 | BLOCKED_DEP |
| T101 | Implement cycle summary output from production-line payload | AI | T058,T095 | BLOCKED_DEP |
| T102 | Implement pre-LLM input gate (active vs idle workers, ready tasks, budget) | AI | T023,T030,T095 | BLOCKED_DEP |
| T103 | Add strict fallback policy when manager output invalid | AI | T067,T093,T094,T095 | BLOCKED_DEP |
| T104 | Human approve fallback policy (retry/skip/fail-fast thresholds) | HUMAN | T103 | BLOCKED_HUMAN |
| T105 | Integration test: linear lane dependencies | AI | T099,T095 | BLOCKED_DEP |
| T106 | Integration test: parallel lane dependencies | AI | T099,T095 | BLOCKED_DEP |
| T107 | Integration test: profile lock mid-task | AI | T094,T099 | BLOCKED_DEP |
| T108 | Integration test: dispatch tracking (`pid/thread_id`) | AI | T098 | BLOCKED_DEP |
| T109 | Integration test: rate-gate wait path | AI | T096 | BLOCKED_DEP |
| T110 | Integration test: termination-file stop | AI | T092 | BLOCKED_DEP |
| T111 | Integration test: watchdog exit signal | AI | T100 | BLOCKED_DEP |
| T112 | Dry-run simulation on sample project | AI | T101,T105,T106,T107,T108,T109,T110,T111 | BLOCKED_DEP |
| T113 | Human review dry-run artifacts/results | HUMAN | T112 | BLOCKED_HUMAN |
| T114 | Apply revisions from dry-run feedback | AI | T113 | BLOCKED_HUMAN |
| T115 | Re-run simulation after revisions | AI | T114 | BLOCKED_DEP |
| T116 | Human go/no-go for real project pilot | HUMAN | T115 | BLOCKED_HUMAN |
| T117 | Define Stage B (tester-heavy 80->95) exact scope | HUMAN | T116 | BLOCKED_HUMAN |
| T118 | Draft Stage B manager/prompt/schema deltas | AI | T117 | BLOCKED_HUMAN |
| T119 | Human approve Stage B deltas | HUMAN | T118 | BLOCKED_HUMAN |
| T120 | Define final-mile policy (95->100 is user-prompt driven) | JOINT | T117 | BLOCKED_HUMAN |
