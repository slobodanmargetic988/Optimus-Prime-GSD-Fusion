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
| lane_base_branches | object<string,string> | Lane-id to lane-base-branch map used by watchdog lane monitoring |
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
  "lane_base_branches": {
    "phase-1/lane-a": "lane-phase-1-a"
  },
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

Invariant:
- Before `/op-simple-build` starts, `lane_base_branches` must include every non-empty `tasks[].lane_id`.

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
- `schema_version`, `cycle_number`, `monitored_branch`, `commit_ref`, `last_commit_sha`, `last_commit_at_utc`
- `last_commit_age_minutes`, `watchdog_age_offset_minutes`, `watchdog_age_minutes`
- `watchdog_target_reset_at_utc`, `stale_after_minutes`, `near_stale_threshold_minutes`, `stale`, `near_stale`
- `run_base_hard_age_offset_minutes`, `run_base_hard_age_minutes`, `run_base_hard_target_reset_at_utc`
- `run_base_hard_limit_minutes`, `run_base_hard_warning_minutes`, `run_base_hard_stale`, `near_terminal_hard_limit`
- `terminal_warning_last_emitted_cycle`, `terminal_warning_last_emitted_at_utc`, `terminal_warning_cooldown_cycles`, `terminal_warning_emitted_this_cycle`
- `lane_aggregate_watchdog_age_minutes`, `lane_seen_branch_count`, `lane_missing_branch_count`, `all_monitored_branches_idle_stale`
- `progress_signal`, `progress_changed`, `progress_components`
- `lane_progress_signal`, `lane_progress_changed`, `lane_base_watchdog_registry_ref`

```json
{
  "schema_version": "1.0",
  "cycle_number": 7,
  "monitored_branch": "main",
  "commit_ref": "main",
  "last_commit_sha": "abcdef1234567890",
  "last_commit_at_utc": "2026-03-13T10:00:00Z",
  "last_commit_age_minutes": 121.3,
  "watchdog_age_offset_minutes": 5.0,
  "watchdog_age_minutes": 116.3,
  "watchdog_target_reset_at_utc": "2026-03-13T11:55:00Z",
  "run_base_hard_age_offset_minutes": 5.0,
  "run_base_hard_age_minutes": 116.3,
  "run_base_hard_target_reset_at_utc": "2026-03-13T11:55:00Z",
  "run_base_hard_limit_minutes": 300,
  "run_base_hard_warning_minutes": 280,
  "terminal_warning_last_emitted_cycle": 0,
  "terminal_warning_last_emitted_at_utc": "",
  "terminal_warning_cooldown_cycles": 4,
  "near_terminal_hard_limit": false,
  "terminal_warning_emitted_this_cycle": false,
  "lane_aggregate_watchdog_age_minutes": 20.0,
  "lane_seen_branch_count": 2,
  "lane_missing_branch_count": 0,
  "stale_after_minutes": 150,
  "all_monitored_branches_idle_stale": false,
  "run_base_hard_stale": false,
  "near_stale_threshold_minutes": 140,
  "stale": false,
  "near_stale": false,
  "progress_signal": "3e8b0f...",
  "progress_changed": true,
  "lane_progress_signal": "a901d8...",
  "lane_progress_changed": false,
  "lane_base_watchdog_registry_ref": "/abs/path/.op-simple/current/lane_base_watchdog_registry.json"
}
```

### watchdog_exit_signal.json fields
- `schema_version`, `cycle_number`, `reason_code`, `message`, `monitored_branch`, `commit_ref`
- `last_commit_sha`, `last_commit_at_utc`, `watchdog_age_minutes`, `commit_age_minutes`
- `stale_after_minutes`, `near_stale_threshold_minutes`, `near_stale`
- `run_base_hard_limit_minutes`, `run_base_hard_warning_minutes`, `run_base_hard_age_minutes`, `run_base_hard_stale`
- `lane_aggregate_watchdog_age_minutes`, `lane_seen_branch_count`, `lane_missing_branch_count`, `all_monitored_branches_idle_stale`
- `near_terminal_hard_limit`
- `progress_signal`, `progress_changed`

```json
{
  "schema_version": "1.0",
  "cycle_number": 16,
  "reason_code": "stale_base_branch_commit",
  "message": "no new commit observed across monitored run/lane branches for base threshold 150 minutes; run-base age=151.0m lane-aggregate age=150.8m",
  "monitored_branch": "main",
  "commit_ref": "main",
  "watchdog_age_minutes": 151.0,
  "commit_age_minutes": 176.0,
  "run_base_hard_limit_minutes": 300,
  "run_base_hard_warning_minutes": 280,
  "run_base_hard_age_minutes": 151.0,
  "run_base_hard_stale": false,
  "lane_aggregate_watchdog_age_minutes": 150.8,
  "lane_seen_branch_count": 2,
  "lane_missing_branch_count": 0,
  "all_monitored_branches_idle_stale": true,
  "stale_after_minutes": 150,
  "near_stale_threshold_minutes": 140,
  "near_stale": false,
  "near_terminal_hard_limit": false,
  "progress_signal": "3e8b0f...",
  "progress_changed": false
}
```

Terminal reason codes emitted by watchdog:
- `stale_base_branch_commit`
- `stale_run_base_hard_limit`

### lane_base_watchdog_registry.json fields
- `schema_version`, `updated_at`, `cycle_number`, `plan_cycle_number`
- `lane_base_branches` (lane-id to branch map)
- `lanes[]`:
  - `lane_id`, `lane_base_branch`, `exists`, `ever_seen`
  - `first_seen_at`, `first_seen_cycle`
  - `last_seen_commit_sha`, `last_seen_commit_at_utc`, `last_seen_cycle`
- `aggregate`:
  - `seen_lane_count`, `missing_lane_count`
  - `latest_seen_commit_sha`, `latest_seen_commit_at_utc`, `latest_seen_commit_age_minutes`
  - `watchdog_age_offset_minutes`, `watchdog_age_minutes`, `watchdog_target_reset_at_utc`
  - `progress_signal`, `progress_changed`, `progress_components`

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-03-14T08:00:00Z",
  "cycle_number": 12,
  "plan_cycle_number": 12,
  "lane_base_branches": {
    "phase-1/lane-a": "lane-phase-1-a",
    "phase-2/lane-b": "lane-phase-2-b"
  },
  "lanes": [
    {
      "lane_id": "phase-1/lane-a",
      "lane_base_branch": "lane-phase-1-a",
      "exists": true,
      "ever_seen": true,
      "first_seen_at": "2026-03-14T07:10:00Z",
      "first_seen_cycle": 9,
      "last_seen_commit_sha": "abcdef1234",
      "last_seen_commit_at_utc": "2026-03-14T07:58:00Z",
      "last_seen_cycle": 12
    }
  ],
  "aggregate": {
    "seen_lane_count": 2,
    "missing_lane_count": 0,
    "latest_seen_commit_sha": "abcdef1234",
    "latest_seen_commit_at_utc": "2026-03-14T07:58:00Z",
    "latest_seen_commit_age_minutes": 2.0,
    "watchdog_age_offset_minutes": 2.0,
    "watchdog_age_minutes": 0.0,
    "watchdog_target_reset_at_utc": "2026-03-14T08:00:00Z",
    "progress_signal": "a901d8...",
    "progress_changed": true,
    "progress_components": {
      "phase-1/lane-a": "abcdef1234",
      "phase-2/lane-b": "0123456789"
    }
  }
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
- When a terminal stop reason is resolved (`project_done`, `insurmountable_blocker`, watchdog reason such as `stale_base_branch_commit` or `stale_run_base_hard_limit`), `cycle_summary.stop_reason` must be persisted and non-empty for that cycle.

### task_execution_state.json additions (merge progression engine)

- Optional task fields written by deterministic merge progression:
  - `lane_fan_in_accepted_at`
  - `lane_fan_in_cycle`
  - `lane_to_run_merged_at`
  - `lane_to_run_merge_cycle`
- `blockers[]` may contain deterministic merge blockers with:
  - `blocker_id`
  - `lane_id`
  - `reason_code` (for example `lane_run_merge_pending_commit_not_in_run_base`)
  - `status` (`open|resolved`)
  - `owner`
  - `message`
  - `details`

### worker_registry.json additions (merge progression engine)

- Optional worker fields written by deterministic merge progression:
  - `fan_in_status` (`accepted`)
  - `fan_in_cycle`
  - `fan_in_accepted_at`
  - `merge_lane_last_merged_at`
  - `merge_lane_last_merged_cycle`

## 14) mergeability_report.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| cycle_number | integer | Cycle identity |
| cycle_mode | string | Runtime mode for this mergeability snapshot |
| run_base_ref | string | Run-base branch/ref under evaluation |
| run_base_sha | string | Run-base commit anchor |
| lane_shas | object<string,array<string>> | Per-lane queued source commits still waiting on deterministic merge success or merge-manager resolution |
| unmerged_commit_count | integer | Aggregate queued merge-debt signal |
| merge_blockers | array | Explicit runtime-known blockers preventing deterministic lane/run merge closure |
| gate_owner | string | Current owner for merge truth (`runtime` when blockers exist, otherwise `none`) |
| lane_status | object | Per-lane deterministic merge state (`fan_in_status`, tester gate, lane->run state, including blocked fan-in debt) |
| lane_merge_gate_pending_cleared_count | integer | Compatibility field; always `0` in runtime-owned merge flow |
| progression | object | Queue/progression counters (`task_to_lane_queue_items`, `lane_to_run_queue_items`, `lane_ready_for_run_merge`) |
| progress_fingerprint | string | Deterministic mergeability digest |
| mergeability_advanced | boolean | Whether mergeability fingerprint changed from previous cycle |

Invariant:
- Runtime writes `mergeability_report.json` every cycle, including timeout/unhappy-path cycles where feasible.
- Runtime merge truth is git ancestry + active merge queue, not done worker branch names.
- `lane_shas` must only include queue-backed unresolved source commits.
- Lanes with active same-lane `task_to_lane` queue debt must not report `lane_to_run_merge_status=ready`.

## 15) merge_queue.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| cycle_number | integer | Last cycle that rewrote the queue |
| items | array<object> | Active deterministic merge failures waiting for merge-manager cadence |

Per-item fields:

| Field | Type | Why it exists |
|---|---|---|
| queue_item_id | string | Stable identity derived from `kind + target_branch + source_commit` |
| kind | string | `task_to_lane` or `lane_to_run` |
| lane_id | string | Lane owning the merge opportunity |
| task_id | string\|null | Task identity for `task_to_lane` items |
| target_branch | string | Branch the runtime expected to merge into |
| source_commit | string | Canonical source commit that must become ancestor of `target_branch` |
| source_ref | string\|null | Optional human-facing source branch/ref |
| first_failed_cycle | integer | First cycle this queue item was created |
| last_failed_cycle | integer | Most recent cycle that retried and failed it |
| attempt_count | integer | Deterministic retry counter |
| failure_reason_code | string | Failure classification (`git_merge_conflict`, `source_commit_missing`, etc.) |
| failure_message | string | Human-facing failure summary |
| status | string | Active queue items remain `queued` |
| updated_at | string(UTC) | Last queue mutation timestamp |

Invariant:
- Queue identity is source-commit scoped.
- Runtime must deduplicate repeated failures for the same `kind + target_branch + source_commit`.

## 16) unmergable_merges.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| cycle_number | integer | Last cycle that rewrote the file |
| items | array<object> | Queue items consumed by merge-manager but not resolved |

Additional per-item fields beyond `merge_queue.json`:

| Field | Type | Why it exists |
|---|---|---|
| moved_at | string(UTC) | When merge-manager disposition moved the item out of active queue |
| moved_cycle | integer | Cycle where the move occurred |
| last_manager_reason | string | Why merge-manager left the item unresolved |
| manager_report_ref | string | Absolute path to the merge-manager report used for disposition |

Invariant:
- Deterministic runtime never writes directly to `unmergable_merges.json`; only merge-manager consumption moves items there.

## 17) merge_manager_report.json

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| updated_at | string(UTC) | Recency |
| cycle_number | integer | Merge-manager cycle identity |
| status | string | Runtime-normalized disposition (`consumed`, `manager_failed`, `invalid_report`, etc.) |
| summary | string | Human-facing outcome summary |
| queue_count_before | integer | Active queue size before manager run |
| queue_count_after | integer | Active queue size after runtime disposition |
| resolved_items | array<object> | Queue items runtime accepted as resolved |
| unresolved_items | array<object> | Queue items runtime moved to `unmergable_merges.json` |
| manager_status | string | Raw manager execution status |
| manager_timeout | boolean | Timeout signal for forensic handling |
| manager_message | string | Raw manager message |
| manager_reason_code | string | Raw manager reason code |

Invariant:
- A valid manager-produced consumption report must account for every active queue item exactly once across `resolved_items` and `unresolved_items`.
- Runtime must independently verify git proof before accepting `resolved_items`.

## 18) merge_journal.jsonl

Append-only JSONL event stream. Each row includes:

| Field | Type | Why it exists |
|---|---|---|
| schema_version | string | Contract version |
| timestamp | string(UTC) | Event time |
| cycle_number | integer | Cycle identity |
| event | string | `merged`, `skip`, `queued`, `deferred`, `retired`, `manager_resolved`, or `manager_unresolved` |
| kind | string | `task_to_lane` or `lane_to_run` |
| lane_id | string | Lane owning the merge action |
| task_id | string\|null | Task identity when relevant |
| target_branch | string | Merge target branch |
| source_commit | string | Source commit under evaluation |
| source_ref | string\|null | Optional source branch/ref |
| queue_item_id | string\|null | Queue linkage when relevant |
| status | string | Human-facing state summary |
| message | string | Human-facing event summary |
| details | object | Supplemental fields (`merged_sha`, `failure_reason_code`, conflicted file list, etc.) |

Invariant:
- Runtime appends a journal row for every deterministic merge skip/success/queue action and every merge-manager disposition.
- Runtime also appends journal rows when lane->run is deferred due to active task fan-in debt and when obsolete queue items are retired automatically.

## 19) terminal_capsule.json

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
- Non-timeout fail-closed BOSS cycles must also emit `terminal_capsule.json` with `stop_reason=""` and failure `reason_code`.

## 20) timeout_adaptation_state.json

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
| last_boss_runtime_checks.eligible_profile_count | integer | Number of eligible snapshot profiles at runtime check time |
| last_boss_runtime_checks.selected_profile_found_in_snapshot | boolean | Whether selected alias resolved to a snapshot row |
| last_boss_runtime_checks.selected_profile_eligible | boolean\|null | Eligibility of selected profile row |
| last_boss_runtime_checks.selected_profile_ineligible_reason | string\|null | Why selected profile is ineligible |
| last_boss_runtime_checks.selected_profile_hard_gated | boolean\|null | Hard-gate marker for selected profile |

Invariant:
- After two consecutive BOSS timeouts, adaptation must activate (`adaptation_active=true`).
- If multiple eligible aliases exist, `rotation_required=true` and next BOSS selection must avoid `last_timeout_profile_alias`.

## 21) restart_determinism_state.json (Packet 3 internals)

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
- `process_kill_resume` classification must use pre-lock run-lock evidence so stale PID context is not lost during lock acquisition.

## 22) Packet 4 scaffold writers (runtime internals)

Runtime includes scaffold writers (not auto-executed in this implementation pass) for:

- `packet4_gate_evidence_bundle_<YYYY-MM-DD>.json/.md`
- `packet4_kpi_trend_summary_<YYYY-MM-DD>.json/.md`
- `packet4_gate_recommendation_<YYYY-MM-DD>.md`

Naming aligns with:

- `/Users/slobodan/projects/Earth/PHASE2_ARTIFACT_NAMING_CONTRACT_V1.md`
