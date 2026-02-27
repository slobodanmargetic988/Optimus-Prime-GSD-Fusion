# Optimus Cycle Controller Contracts

## 1) Input Contract (`--input-json`)

```json
{
  "repo_root": "string",
  "sleep_minutes": 5,
  "profile_aliases": ["codex", "codex-second"],
  "rate_gate_5h_percent": 15,
  "rate_gate_weekly_percent": 10,
  "soft_rate_gate_5h_percent": 40,
  "soft_rate_gate_weekly_percent": 25,
  "soft_rate_gated_max_running_workers": 3,
  "control_flags_dir": "string",
  "events_path": "string",
  "heartbeat_path": "string",
  "final_state_path": "string",
  "lock_path": "string",
  "worker_registry_path": "string",
  "cycle_log_path": "string",
  "handoff_log_path": "string",
  "rate_registry_path": "string",
  "rate_status_log_path": "string",
  "allow_autonomous_ops": false,
  "max_cycles": 0,
  "dry_run": false,
  "emit_stdout": true
}
```

## 2) Event Stream Contract (`EVENTS.jsonl`)

One JSON object per line:

```json
{
  "timestamp": "2026-02-27T00:00:00Z",
  "cycle_number": 12,
  "event_type": "snapshot|directive|sleep|warning|terminal",
  "action_code": "string",
  "payload": {},
  "requires_optimus_action": true
}
```

Directive payload may include:
- `show_snapshot`
- `dispatch_filter`
- `soft_throttle`
- `review_dispatch_queue`
- `runtime_strategy_resolve`
- `refresh_blocker_index`
- `sync_linear_phase` (when latest handoff state maps to a deterministic Linear phase transition)
- `close_test_wave`
- `evaluate_promotion_gate`
- `promote_test_next_to_test`
- `deploy_test_branch`
- `start_new_test_wave`

## 3) Heartbeat Contract (`HEARTBEAT.json`)

```json
{
  "timestamp": "2026-02-27T00:00:00Z",
  "cycle_number": 12,
  "status": "running|terminal",
  "active_workers_summary": {
    "active_count": 2,
    "active_slots": ["dev-1", "test-1"],
    "total_known_workers": 6
  },
  "profiles_state": [],
  "warnings": [],
  "pending_directives_count": 3,
  "allow_autonomous_ops": false
}
```

## 4) Final State Contract (`FINAL_STATE.json`)

```json
{
  "terminal_reason": "project_done|insurmountable_blocker|all_rate_gates_blocking",
  "evidence_file": "/abs/path/to/evidence.json",
  "last_cycle_number": 42,
  "profiles_state": [],
  "active_workers_summary": {},
  "pending_directives": [],
  "generated_at": "2026-02-27T00:00:00Z"
}
```

## 5) Evidence File Schemas

### `PROJECT_DONE.json`

```json
{
  "status": "done",
  "evidence": "brief deterministic completion proof",
  "source": "optional"
}
```

### `INSURMOUNTABLE_BLOCKER.json`

```json
{
  "status": "blocked",
  "reason": "why this cannot be resolved autonomously",
  "requested_action": "optional"
}
```

### `ALL_RATE_GATES_BLOCKING.json` (controller-generated)

```json
{
  "status": "all_rate_gates_blocking",
  "reason": "all configured profiles are hard-gated",
  "generated_at": "2026-02-27T00:00:00Z",
  "profiles": []
}
```

## 6) Stop Authorization Rule

Optimus may only stop when:
- `FINAL_STATE.json` exists, and
- `terminal_reason` is one of the allowed terminal reasons, and
- `evidence_file` is present and non-empty, and
- evidence file exists and validates against the terminal reason schema.

CLI verification mode:

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/optimus-cycle-controller/scripts/optimus_cycle_controller.py \
  --verify-final-state /abs/path/to/FINAL_STATE.json
```

Otherwise, stop is unauthorized.
