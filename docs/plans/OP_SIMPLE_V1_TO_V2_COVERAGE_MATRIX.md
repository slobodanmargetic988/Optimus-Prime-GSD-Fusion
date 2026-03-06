# OP Simple V1 -> V2 Coverage Matrix (T001-T101)

## Purpose
This document maps V1 backlog intent (T001-T101) to the active V2 spec so we can reach a decision-complete plan before implementation.

## Status Legend
- `LOCKED`: decision is explicitly captured in V2 docs.
- `PARTIAL`: direction exists but is not decision-complete.
- `OPEN`: missing/insufficiently specified for implementation.

## Source of Truth (V2)
- `docs/plans/OP_SIMPLE_EXECUTION_SPEC_V2.md`
- `docs/plans/OP_SIMPLE_TASK_BACKLOG_V2.md`
- `docs/plans/OP_SIMPLE_SESSION_LOCK_2026-03-06.md`

## Coverage Matrix

| V1 Range | V1 Intent Cluster | V2 Mapping | Coverage | Remaining Planning Needed |
|---|---|---|---|---|
| T001-T012 | MVP boundaries, cadence, cycle order baseline, removed-step freeze | V2 spec: `Locked Direction`, `Runtime Model`, `In-Cycle Order`; V2 backlog execution rules | LOCKED | None |
| T013-T014 | Rate-gate placement/policy | V2 spec locks rate-gate stage after BOSS and before dispatcher, owned by profile-manager wait behavior | LOCKED | None |
| T015-T022 | Lane lifecycle, parallelization, role-mix, DONE contract | V2 now locks old plan topology (`phases/requirements/tasks`), lane ID format, phase DAG, lane-level verification adaptation, and configurable parallelism policy | PARTIAL | Finalize explicit lane state machine schema fields and stage transition statuses |
| T023-T026 | `worker_registry` schema and approval | Mentioned conceptually in V2/session lock, not finalized as approved V2 schema artifact | OPEN | Draft minimal V2 schema + field rationale + human approval pass |
| T027-T030 | `profile_snapshot` schema and approval | Mentioned conceptually; no finalized V2 schema doc | OPEN | Draft/approve minimal V2 `profile_snapshot` schema |
| T031-T034 | `profile_assignment` schema and approval | V2 explicitly removes standalone `profile_assignment`; assignment lives in BOSS-updated `worker_registry` fields | LOCKED (policy replaced) | None |
| T035-T038 | `cycle_manager_decision` schema and approval | Cycle-manager behavior exists in V2; no formal schema contract | OPEN | Draft/approve `cycle_manager_decision` schema and fail/timeout semantics |
| T039-T042 | `production_line_register` (BOSS register) schema and approval | BOSS role is locked; no finalized V2 register schema | OPEN | Draft/approve `production_line_register` schema aligned to BOSS ownership |
| T043-T046 | `worker_packet` schema and approval | V2 locks dispatch path and DONE marker; packet schema not finalized | OPEN | Draft/approve worker packet schemas per worker type family |
| T047-T050 | `dispatch_registry` schema (`pid/thread`) | V2 directional decision says LLM-side ownership; schema not finalized | OPEN | Draft/approve dispatch registry schema + clarify authoritative writer/readers |
| T051-T054 | Simplified `plan_packets` schema | V2 locks status enum, old topology shape, and mandatory verification_contract with lane-flow adaptations | PARTIAL | Draft/approve concrete schema doc with final field list/examples |
| T055-T058 | `cycle_summary` schema | V2 summary stage exists; minimum summary fields are now locked, full schema artifact not yet finalized | PARTIAL | Draft/approve summary payload schema and timeout fallback output format |
| T059-T062 | Watchdog schemas and exit signaling | V2 now locks branch source and idle reset rule, but explicit watchdog state/exit schema remains open | PARTIAL | Draft/approve watchdog state + exit signal schema |
| T063-T066 | Workstation artifact (replacing sanitation) | V2/session lock says initialize retained + no runtime sanitation artifact | PARTIAL | Finalize initialize-time workstation prep artifact schema and ownership |
| T067-T068 | Deterministic schema validation/CI lint | V2 changed policy: no in-cycle strict validation for LLM artifacts | LOCKED (policy changed) | Capture replacement tasks: prompt-linked helper validators + deterministic-only validation list |
| T069-T086 | Manager/worker prompt draft/review/approval chain | V2 policy: implement prompts first, approval can follow | PARTIAL | Define prompt contracts (manager + worker families) sufficiently for implementation without approval gate |
| T087-T092 | Runtime scaffold (`op-simple` entrypoint, loop, cycle counter, termination check) | Explicit in V2 backlog checkpoint 1 | LOCKED (planning) | None before implementation |
| T093-T095 | Foreground manager integrations (`cycle/profile/BOSS`) | V2 defines order, ownership, canonical outputs, and minimum contracts for cycle/profile/BOSS | LOCKED | None |
| T096 | Rate-gate wait/continue implementation | V2 cycle text now explicitly includes rate-gate stage and profile-manager ownership | LOCKED | None |
| T097-T098 | Dispatcher async send + runtime tracking | V2 defines fire-and-forget, dispatch launch log, and split (`dispatch_registry` history vs `worker_registry` latest state) with BOSS pid/thread updates | PARTIAL | Finalize concrete schema docs for both registries and event rows |
| T099 | DONE completion detector | V2 assigns ownership to BOSS and explicitly chooses no deterministic DONE evidence handoff artifact | LOCKED (policy replaced) | None |
| T100 | Simplified watchdog no-commit rule | V2 threshold/role/branch-source/reset rule are locked | LOCKED | None |
| T101 | Cycle summary from BOSS payload | V2 summary stage exists and minimum fields are locked; full schema still pending | PARTIAL | Finalize required summary schema and print contract |

## V1 T001-T101 Equivalence Gate for V2
Implementation should start only when all items below are true:
1. All clusters above are `LOCKED` or explicitly replaced by approved V2 policy.
2. Manager I/O contracts are decision-complete for `cycle-manager`, `profile-manager`, `BOSS`, `work-dispatcher`, `watchdog`, `summary`.
3. Minimal schema set is approved (human-readable field rationale + example JSON):
   - `worker_registry`
   - `profile_snapshot`
   - `cycle_manager_decision`
   - `production_line_register`
   - `worker_packet`
   - `dispatch_registry`
   - `plan_packets`
   - `cycle_summary`
   - `watchdog_state` + `watchdog_exit_signal`
   - `workstation_prep` (initialize-time)
4. Timeout/recovery behavior is locked per manager and reflected in one V2 runtime section.
5. Canary acceptance criteria remain locked: 5 consecutive successful cycles, no manual intervention, with real dispatch and DONE observation.

## Remaining Planning Work (Priority Order)
1. Finalize and approve minimal schemas listed above in batches.
2. Lock manager I/O contracts and artifact paths (one contract per manager).
3. Finalize dispatcher partial-failure/runtime-state schema semantics.
4. Finalize summary payload schema and watchdog exit contract schema.
5. Reconcile V2 backlog tasks with this matrix so every `PARTIAL/OPEN` item has a V2 task.

## Recommendation
Use this matrix as the planning checklist. Once all `PARTIAL/OPEN` rows are closed and the equivalence gate is satisfied, V2 can be treated as the functional equivalent of V1 planning through T101.
