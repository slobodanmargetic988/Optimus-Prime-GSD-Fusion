# Test Train Manager Contracts

## State File (`TEST_TRAIN_STATE.json`)

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-02-27T18:00:00Z",
  "test_train_mode": "off|final-stage|forced-shared-env",
  "test_branch": "test",
  "test_next_branch": "test-next",
  "active_wave": {
    "wave_id": "wave-0007",
    "state": "WAVE_ACTIVE|WAVE_CLOSING|PROMOTION_EVAL|PROMOTE_AND_DEPLOY|WAVE_BOOTSTRAP",
    "started_at": "ISO-8601",
    "closed_at": "ISO-8601",
    "planned_flow_pass_completed": false
  },
  "deployed_test_commit": "sha",
  "queued_test_next_commit": "sha",
  "promotion_eligibility": {
    "eligible": false,
    "reasons": ["planned_flow_pass_not_completed"],
    "evaluated_at": "ISO-8601"
  },
  "deploy_status": {
    "last_result": "none|dry_run|success|failed",
    "last_attempt_at": "ISO-8601",
    "last_success_at": "ISO-8601"
  }
}
```

## Attempts File (`TEST_TASK_ATTEMPTS.json`)

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-02-27T18:00:00Z",
  "tasks": {
    "MYO-123": {
      "failed_attempts": 2,
      "pass_with_rework_count": 1,
      "last_outcome": "failed|blocked|pass_with_rework|passed",
      "last_wave_id": "wave-0007",
      "needs_orchestrator_review": true,
      "escalation_reason": "failed_attempts>=3",
      "updated_at": "ISO-8601"
    }
  }
}
```

## Wave Log (`TEST_WAVE_LOG.jsonl`)

One JSON object per line:

```json
{
  "timestamp": "ISO-8601",
  "wave_id": "wave-0007",
  "event_type": "close_test_wave|evaluate_promotion_gate|promote_test_next_to_test|deploy_test_branch|start_new_test_wave|record_test_outcome|mode_switch|render_wave_summary",
  "payload": {},
  "tool": "test-train-manager",
  "tool_version": "0.1.0"
}
```

## Deploy DB Policy Inputs

Optional deploy-only inputs:

- `db_reset_seed_override`: `none|force_reset_seed|force_skip_reset_seed`
- `db_reset_seed_override_reason`: required when `db_reset_seed_override=force_skip_reset_seed`

`deploy_test_branch` responses include:

- `db_policy`: detector verdict + commit range + chosen decision
- `db_execution`: reset/seed command result when execution was required

`deploy_test_branch` may now return:

- `status=failed_db_policy` for detector/policy/DB-prep failures before app deploy.

## DB Deploy Decisions (`DB_DEPLOY_DECISIONS.jsonl`)

Generated artifact path:

- `reports/optimus-prime/runtime/DB_DEPLOY_DECISIONS.jsonl`

One JSON row per deploy attempt:

```json
{
  "timestamp": "ISO-8601",
  "wave_id": "wave-0007",
  "from_commit": "abc1234",
  "to_commit": "def5678",
  "detector_requires_reset_seed": true,
  "detector_reason": "db_impact_paths_changed",
  "decision": "reset_seed|skip_reset_seed",
  "decision_source": "default_policy|optimus_policy|override",
  "decision_reason": "string",
  "db_command_exit_code": 0,
  "result": "ok|failed|blocked"
}
```
