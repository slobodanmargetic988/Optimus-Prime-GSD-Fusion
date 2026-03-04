---
name: test-train-manager
description: Manage shared test-train wave state, promotion gate, test-next->test promotion, deploy execution, loop escalation counters, and wave summaries.
metadata:
  short-description: Shared test-train wave/state controller
---

# Test Train Manager

## Overview

Use this skill to run the shared-environment testing train model:
- maintain deterministic wave state (`TEST_TRAIN_STATE.json`)
- track per-task loop attempts (`TEST_TASK_ATTEMPTS.json`)
- log wave lifecycle events (`TEST_WAVE_LOG.jsonl`)
- generate human summary (`TEST_WAVE_SUMMARY.md`)
- evaluate promotion gate and perform `test-next -> test` promotion
- execute pipeline-configured test deploy command

## Script

`/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/skills/test-train-manager/scripts/test_train_manager.py`

## Core Actions

- `bootstrap`
- `sync_state`
- `close_test_wave`
- `evaluate_promotion_gate`
- `promote_test_next_to_test`
- `deploy_test_branch`
- `start_new_test_wave`
- `record_test_outcome`
- `render_wave_summary`

## Minimal Input

```json
{
  "repo_root": "/Users/slobodan/projects/Optimus-Prime-GSD-Fusion",
  "action": "evaluate_promotion_gate",
  "test_branch": "test",
  "test_next_branch": "test-next",
  "test_train_mode": "final-stage",
  "test_train_pipeline_path": "reports/optimus-prime/config/TEST_TRAIN_PIPELINE.json",
  "dry_run": false
}
```

Legacy `shared_test_base_url` and `deploy_test_branch_cmd` inputs are rejected in test-train mode.

## Promotion Gate Logic

Promotion is eligible when:
1. active wave has `planned_flow_pass_completed=true`
2. no critical active env/runtime/test-train blocker is present

Task-level failures do not block promotion; they are handled through loop escalation counters.

## Loop Escalation Thresholds

- `failed_attempts >= 3` OR
- `pass_with_rework_count >= 2`

Escalation writes a structured `test_loop_escalation` blocker event.
