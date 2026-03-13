# OP Simple Schema Catalog V2

This catalog is the schema reference for OP Simple runtime artifacts.
Each section includes the minimal field set and one valid JSON example.

Runtime freshness rule: every required BOSS-authored artifact must include top-level `cycle_number`, and runtime accepts it only when that value matches the current cycle.

## 1) worker_registry.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract versioning |
| updated_at | string(UTC) | Recency tracking |
| cycle_number | integer | Cycle correlation |
| workers | array | Worker state rows |
| workers[].worker_id | string | Stable worker identity |
| workers[].worktree | string | Workspace location |
| workers[].branch | string | Branch ownership |
| workers[].status | string | Current worker state |
| workers[].current_task_profile | string\|null | Active profile lock |
| workers[].next_task_profile | string\|null | Next profile assignment |
| workers[].current_task_id | string\|null | Current task link |
| workers[].current_packet_id | string\|null | Current packet link |
| workers[].pid | integer\|null | Process visibility |
| workers[].thread_id | string\|null | Dispatch thread/session visibility |
| workers[].last_update | string(UTC) | Freshness/liveness signal |

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-03-06T12:00:00Z",
  "cycle_number": 7,
  "workers": [
    {
      "worker_id": "worker-1",
      "worktree": "/abs/path/workstation-1",
      "branch": "codex/worker-1/task-123",
      "status": "in_progress",
      "current_task_profile": "codex",
      "next_task_profile": "codex",
      "current_task_id": "TASK-123",
      "current_packet_id": "packet-0007-01",
      "pid": 12345,
      "thread_id": "9d6c1a7f-43de-4b3f-a1f4-7c4e3a0a9f88",
      "last_update": "2026-03-06T12:00:00Z"
    }
  ]
}
```

## 2) profile_snapshot.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Snapshot recency |
| profiles | array | Per-profile capacity rows |
| profiles[].alias | string | Profile alias key |
| profiles[].codex_home | string | Profile runtime home |
| profiles[].window_5h_remaining_pct | number | Short-window capacity signal |
| profiles[].window_week_remaining_pct | number | Long-window capacity signal |
| profiles[].hard_gated | boolean | Immediate hard gate signal |
| profiles[].soft_gated | boolean | Soft gate risk signal |
| profiles[].reset_at | string\|null | Expected reset timestamp |

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-03-06T12:00:00Z",
  "profiles": [
    {
      "alias": "codex",
      "codex_home": "/Users/user/.codex",
      "window_5h_remaining_pct": 72.5,
      "window_week_remaining_pct": 91.0,
      "hard_gated": false,
      "soft_gated": false,
      "reset_at": null
    }
  ]
}
```

## 3) cycle_manager_decision.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| cycle_number | integer | Cycle correlation |
| decision | string | Proceed gate (`proceed|skip_cycle`) |
| reason_code | string | Machine-readable reason |
| message | string | Human-readable explanation |
| worker_registry_ready | boolean | Downstream readiness check |
| llm_hardening | object (optional) | LLM prompt/checker telemetry extension |

```json
{
  "schema_version": "1.0",
  "cycle_number": 7,
  "decision": "proceed",
  "reason_code": "registry_ready",
  "message": "worker registry available",
  "worker_registry_ready": true
}
```

Optional `llm_hardening` extension fields:
- `mini_jobs` (integer)
- `prompt_complexity_score` (0-100)
- `checker_result` (`pass|fail|not_applicable`)
- `checker_id` (string)
- `override_applied` (boolean)
- `override_reason_code` (string when override is applied)
- `override_explanation` (string when override is applied)
- `override_evidence_refs` (string array when override is applied)
- `risk_level` (`low|medium|high|critical` when override is applied)
- `fallback_or_followup_action` (string when override is applied)

Runtime propagation note:
- `manager_call_log.jsonl` rows and trace `operation.inputs.llm` include:
  - `hardening_telemetry_state` (`present|missing|unknown`)
  - `hardening_telemetry_source` (artifact key when state is `present`)
- This distinguishes explicit `checker_result="not_applicable"` telemetry from missing `llm_hardening` emission.

## 4) production_line_register.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Snapshot recency |
| cycle_number | integer | Cycle correlation |
| assignments | array | BOSS assignment outputs |
| assignments[].worker_id | string | Target worker |
| assignments[].lane_id | string | Lane ownership |
| assignments[].task_id | string | Task linkage |
| assignments[].packet_id | string | Packet linkage |
| assignments[].profile_alias | string | Profile chosen for work |
| assignments[].assignment_state | string | `assigned|unassigned|deferred` |
| assignments[].reason | string | Why assigned/unassigned/deferred |

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-03-06T12:00:00Z",
  "cycle_number": 7,
  "assignments": [
    {
      "worker_id": "worker-1",
      "lane_id": "phase-1/lane-a",
      "task_id": "TASK-123",
      "packet_id": "packet-0007-01",
      "profile_alias": "codex",
      "assignment_state": "assigned",
      "reason": "dependency-ready"
    }
  ]
}
```

## 5) worker_packet(s)

| Field | Type | Why it exists |
|---|---|---|
| packet_id | string | Packet identity |
| worker_id | string | Worker target |
| lane_id | string | Lane context |
| task_id | string | Task context |
| profile_alias | string | Profile target |
| prompt | string | Worker instruction payload |
| required_done_marker | string | Completion marker contract |

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-03-06T12:00:00Z",
  "packets": [
    {
      "packet_id": "packet-0007-01",
      "worker_id": "worker-1",
      "lane_id": "phase-1/lane-a",
      "task_id": "TASK-123",
      "profile_alias": "codex",
      "prompt": "Implement task TASK-123 and commit with required marker.",
      "required_done_marker": "[DONE][lane:phase-1/lane-a][task:TASK-123]"
    }
  ]
}
```

## 6) dispatch_registry.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| events | array | Dispatch attempt history |
| events[].cycle_number | integer | Cycle correlation |
| events[].worker_id | string | Worker target |
| events[].packet_id | string | Packet link |
| events[].thread_id | string\|null | Thread/session visibility |
| events[].pid | integer\|null | Process visibility |
| events[].status | string | `launched|launch_failed|unknown` |
| events[].timestamp | string(UTC) | Event time |
| events[].message | string | Event details |

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-03-06T12:00:00Z",
  "events": [
    {
      "cycle_number": 7,
      "worker_id": "worker-1",
      "packet_id": "packet-0007-01",
      "thread_id": "9d6c1a7f-43de-4b3f-a1f4-7c4e3a0a9f88",
      "pid": 12345,
      "status": "launched",
      "timestamp": "2026-03-06T12:00:00Z",
      "message": "dispatch started"
    }
  ]
}
```

## 7) plan_packets.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| cycle_number | integer | Cycle correlation |
| phase | string | Multi-phase mode marker |
| phases | array | Phase DAG |
| requirements | array | Requirement inventory |
| tasks | array | Task planning rows |
| tasks[].task_id | string | Task identity |
| tasks[].phase_id | string | Phase membership |
| tasks[].lane_id | string | Lane membership |
| tasks[].status | string | `pending|in_progress|done|blocked` |
| tasks[].requirement_ids | array | Requirement links (may be empty) |
| tasks[].depends_on | array | Dependency graph |
| tasks[].verification_contract | object | Verification expectation contract |

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-03-06T12:00:00Z",
  "cycle_number": 7,
  "phase": "multi-phase",
  "phases": [
    {
      "phase_id": "phase-1",
      "task_ids": ["TASK-123"],
      "depends_on_phase_ids": []
    }
  ],
  "requirements": [
    {
      "id": "REQ-1",
      "title": "Core flow"
    }
  ],
  "tasks": [
    {
      "task_id": "TASK-123",
      "phase_id": "phase-1",
      "lane_id": "phase-1/lane-a",
      "status": "pending",
      "requirement_ids": ["REQ-1"],
      "depends_on": [],
      "verification_contract": {
        "mode": "implementation_green",
        "dev_expectation": "expect_pass",
        "test_expectation": "expect_pass",
        "review_expectation": "expect_pass",
        "expected_failure_reason_codes": ["tdd_expected_failure_observed"],
        "infra_failure_reason_codes": ["verification_environment_error", "verification_command_target_missing"]
      }
    }
  ]
}
```

## 8) task_execution_state.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| cycle_number | integer | Cycle correlation |
| tasks | array | Runtime state rows |
| blockers | array | Cycle-level blocker rows |
| attempts | object | Cycle-level stage counters |
| last_handoff_outcome | object | Last cycle-level handoff outcome |
| tasks[].task_id | string | Task identity |
| tasks[].status | string | `pending|in_progress|done|blocked` |

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-03-06T12:00:00Z",
  "cycle_number": 7,
  "blockers": [],
  "attempts": {
    "dev": 1,
    "lane_test": 0,
    "test_fix": 0,
    "lane_review": 0,
    "review_fix": 0,
    "deep_review": 0,
    "deep_fix": 0
  },
  "last_handoff_outcome": {
    "status": "success",
    "reason_codes": [],
    "timestamp": "2026-03-06T11:58:00Z"
  },
  "tasks": [
    {
      "task_id": "TASK-123",
      "status": "in_progress"
    }
  ]
}
```

## 9) cycle_summary.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| cycle_number | integer | Cycle identity |
| manager_statuses | object | Per-manager status map |
| task_counts | object | Pending/in-progress/done/blocked counts |
| dispatch_counts | object | Dispatch result counts |
| project_done | boolean | Terminal done marker from BOSS |
| insurmountable_blocker | boolean | Terminal blocker marker from BOSS |
| termination | object | Optional structured terminal reason |
| stop_reason | string | Optional normalized stop reason |
| notes | string | Summary note |

```json
{
  "schema_version": "1.0",
  "cycle_number": 7,
  "manager_statuses": {
    "BOSS": {"status": "ok", "note": ""},
    "work-dispatcher": {"status": "ok", "note": "dispatch cycle completed"},
    "watchdog": {"status": "ok", "note": "watchdog healthy"},
    "summary": {"status": "ok", "note": "summary written"}
  },
  "task_counts": {
    "pending": 3,
    "in_progress": 2,
    "done": 1,
    "blocked": 0
  },
  "dispatch_counts": {
    "attempted": 2,
    "launched": 2,
    "launch_failed": 0,
    "unknown": 0
  },
  "project_done": false,
  "insurmountable_blocker": false,
  "termination": {},
  "stop_reason": "",
  "notes": "cycle healthy"
}
```

## 10) watchdog_state.json + watchdog_exit_signal.json

### watchdog_state.json fields
- `schema_version`, `cycle_number`, `monitored_branch`, `last_commit_sha`, `last_commit_seen_cycle`, `idle_cycles`, `threshold_cycles`

```json
{
  "schema_version": "1.0",
  "cycle_number": 7,
  "monitored_branch": "main",
  "last_commit_sha": "abcdef1234567890",
  "last_commit_seen_cycle": 6,
  "idle_cycles": 1,
  "threshold_cycles": 10
}
```

### watchdog_exit_signal.json fields
- `schema_version`, `cycle_number`, `reason_code`, `message`, `monitored_branch`, `idle_cycles`

```json
{
  "schema_version": "1.0",
  "cycle_number": 16,
  "reason_code": "no_new_commits",
  "message": "no new commits detected for 20 cycles",
  "monitored_branch": "main",
  "idle_cycles": 10
}
```

## 11) workstation_prep.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| prepared_at | string(UTC) | Artifact write time |
| workstations | array | Prep rows |
| workstations[].workstation_id | string | Workstation identity |
| workstations[].branch | string | Branch prepared on |
| workstations[].worktree | string | Worktree path |
| workstations[].prepared_at | string(UTC) | Per-row prep time |
| workstations[].status | string | Prep status |
| workstations[].preparation_notes | string | Human-readable prep notes |
| workstations[].git_head_sha | string | Commit anchor at prep time |

```json
{
  "schema_version": "1.0",
  "prepared_at": "2026-03-06T12:00:00Z",
  "workstations": [
    {
      "workstation_id": "workstation-1",
      "branch": "main",
      "worktree": "/abs/path/workstation-1",
      "prepared_at": "2026-03-06T12:00:00Z",
      "status": "prepared",
      "preparation_notes": "initialize baseline",
      "git_head_sha": "abcdef1234567890"
    }
  ]
}
```

## 12) wrapup_manager_report.json

Common top-level fields:
- `schema_version`
- `updated_at`
- `cycle_number`
- `status`
- `stop_reason`
- `run_base_branch`
- `summary`

Optional telemetry extension:
- `llm_hardening` object with the same optional keys defined in section `3) cycle_manager_decision.json`.

## 13) Packet 2A/3/4 hardening extensions (2026-03-13)

### cycle_manager_decision.json additions

- `cycle_mode` (`normal|merge_recovery|terminal_stale`)

### cycle_summary.json additions

- `cycle_mode` (`normal|merge_recovery|terminal_stale`)
- `timeout_state` object:
  - `consecutive_boss_timeouts`
  - `timeout_threshold`
  - `adaptation_active`
  - `rotation_required_next_cycle`
  - `last_timeout_cycle`
  - `last_timeout_profile_alias`
  - `last_timeout_reason`
- `profile_rotation_evidence` object (last BOSS alias selection decision and eligibility reasoning)
- `boss_runtime_context_evidence` object (binary/profile context checks)

Invariant:
- When a terminal stop reason is resolved (`project_done`, `insurmountable_blocker`, `watchdog_idle_stop`), `cycle_summary.stop_reason` must be persisted and non-empty for that cycle.

## 14) mergeability_report.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| cycle_number | integer | Cycle identity |
| cycle_mode | string | Runtime mode for this mergeability snapshot |
| run_base_ref | string | Run-base branch/ref under evaluation |
| run_base_sha | string | Run-base commit anchor |
| lane_shas | object<string,array<string>> | Per-lane unmerged branch head SHAs |
| unmerged_commit_count | integer | Aggregate unmerged commit signal |
| merge_blockers | array | Explicit blockers preventing lane->run merge |
| gate_owner | string | Current owner for merge-gate progression |
| lane_status | object | Per-lane deterministic stage state |
| lane_merge_gate_pending_cleared_count | integer | Auto-cleared pending merge-gate rows in this cycle |
| progression | object | Stage counters (`done_worker_commits`, `lane_fan_in_ready`, `lane_tester_gate_passed`, `lane_to_run_merge_ready`) |
| progress_fingerprint | string | Deterministic mergeability digest |
| mergeability_advanced | boolean | Whether mergeability fingerprint changed from previous cycle |

Invariant:
- Runtime writes `mergeability_report.json` every cycle, including timeout/unhappy-path cycles where feasible.

## 15) terminal_capsule.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| cycle_number | integer | Cycle identity |
| reason_code | string | Terminal/unhappy-path reason |
| stop_reason | string | Resolved stop reason when terminal |
| cycle_mode | string | Runtime mode in that cycle |
| manager | string\|null | Manager associated with capsule reason |
| manager_status | string | Manager status (`ok|failed|timeout|...`) |
| manager_timeout | boolean | Timeout flag |
| manager_message | string | Forensic manager message |
| manager_stdout_path | string\|null | Captured stdout path |
| manager_stderr_path | string\|null | Captured stderr path |
| manager_duration_seconds | number\|null | Execution duration |
| manager_statuses | object | Per-manager cycle status map |
| dispatch_counts | object | Dispatch counters for cycle context |
| watchdog_signal | object | Watchdog signal snapshot |
| details | object | Extra forensics (merge refs, timeout notes, etc.) |
| timeout_state | object | Timeout streak/adaptation metadata snapshot |

Invariant:
- Timeout cycles must still emit `terminal_capsule.json`, `cycle_summary.json`, and `cycle_manager_decision.json`.

## 16) timeout_adaptation_state.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| consecutive_boss_timeouts | integer | Streak counter |
| timeout_threshold | integer | Adaptation threshold (current value: `2`) |
| adaptation_active | boolean | Whether timeout adaptation is active |
| rotation_required | boolean | Whether next BOSS cycle must rotate alias when alternates are eligible |
| last_timeout_cycle | integer\|null | Last timeout cycle index |
| last_timeout_profile_alias | string | Timed-out profile alias |
| last_timeout_reason | string | Last timeout reason |
| eligible_profile_aliases | array<string> (optional) | Eligible aliases seen during timeout update |
| last_rotation_decision | object | Alias selection evidence (selected alias, rejected reason, candidate eligibility) |
| last_boss_runtime_checks | object | Binary/profile-context validity evidence |

Invariant:
- After two consecutive BOSS timeouts, adaptation must activate (`adaptation_active=true`).
- If multiple eligible aliases exist, `rotation_required=true` and next BOSS selection must avoid `last_timeout_profile_alias`.

## 17) restart_determinism_state.json (Packet 3 internals)

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| scenario | string | `fresh_start|watchdog_resume|process_kill_resume|checkpoint_replay` |
| resume_mode | boolean | Resume invocation mode |
| checkpoint_fingerprint | string | Deterministic checkpoint hash |
| last_applied_cycle | integer | Last cycle with restart hook update |
| idempotent_continuation | boolean | Whether current resume replay is idempotent |
| invariants | object | Per-scenario invariant checks and last verification timestamps |
| continuation_log | array | Rolling continuation checkpoints and hook events |

Invariant:
- Repeated resume with identical checkpoint fingerprint and scenario should set `idempotent_continuation=true`.
