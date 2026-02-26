---
name: cycle-tick
description: Evaluate rate gates/throttle and return deterministic cycle dispatch + sleep decision with cycle/rate log appends.
metadata:
  short-description: Cycle gate + sleep decision engine
---

# Cycle Tick

## Overview

Use this skill to replace manual cycle loop gate/sleep/log chaining.

Inputs include threshold policy and cycle metadata. Output includes deterministic action enum:
- `continue_dispatch`
- `continue_with_soft_cap`
- `hold_and_sleep_until_reset`
- `wind_down_no_new_dispatch`

Default state files under `reports/optimus-prime/`:
- `PROFILE_RATE_REGISTRY.json`
- `WORKER_REGISTRY.json`
- `CYCLE_LOG.jsonl`
- `RATE_STATUS_LOG.jsonl`

## Script

`/Users/slobodan/Projects/Agents/skills/cycle-tick/scripts/cycle_tick.py`

## Input Contract

```json
{
  "repo_root": "string",
  "cycle_number": 60,
  "status_profiles_scope": "all-configured-plus-primary",
  "rate_gate_5h_percent": 15,
  "rate_gate_weekly_percent": 10,
  "soft_rate_gate_5h_percent": 40,
  "soft_rate_gate_weekly_percent": 25,
  "soft_rate_gated_max_running_workers": 3,
  "rate_reset_wait_max_hours": 4,
  "sleep_minutes": 5,
  "allow_dispatch": true,
  "user_steering_active": false,
  "dry_run": false
}
```

## Policy Highlights

- Missing/invalid rate snapshot => conservative no-dispatch action.
- Soft throttle limits new dispatch only; no worker termination behavior.
- `user_steering_active=true` disables sleep recommendation.
- Threshold validation runs before any writes.

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/cycle-tick/scripts/cycle_tick.py --input-json - --json-pretty
{
  "repo_root": "/Users/slobodan/Projects/Agents",
  "cycle_number": 60,
  "status_profiles_scope": "all-configured-plus-primary",
  "rate_gate_5h_percent": 15,
  "rate_gate_weekly_percent": 10,
  "soft_rate_gate_5h_percent": 40,
  "soft_rate_gate_weekly_percent": 25,
  "soft_rate_gated_max_running_workers": 3,
  "rate_reset_wait_max_hours": 4,
  "sleep_minutes": 5,
  "allow_dispatch": true,
  "user_steering_active": false,
  "dry_run": true
}
JSON
```

## Output Contract

Key fields:
- `cycle_number`
- `action`
- `dispatch_allowed`
- `effective_max_running_workers`
- `profile_running_mode`
- `gated_profiles`
- `soft_gated_profiles`
- `sleep_recommendation`
- `logs_written`
- `human_summary_line`
- `warnings` / `errors`

## Failure Behavior

- Invalid thresholds => validation error, no log writes.
- Missing rate snapshot => `wind_down_no_new_dispatch` with explicit warning.
- Log write failure => `ok=false` with `log_write_failed` error.
