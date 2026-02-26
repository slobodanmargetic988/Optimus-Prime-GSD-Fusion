---
name: tester-targeted-pytest-runner
description: Run deterministic multi-run targeted pytest commands and derive tester decision hints.
metadata:
  short-description: Targeted pytest orchestration + decision classification
---

# Tester Targeted Pytest Runner

## Overview

Use this skill for tester runtime checks requiring one or more targeted pytest invocations with deterministic output.

Behavior:
- Loads environment from `env_source`.
- Uses explicit `python_bin` and rewrites pytest invocations to `python_bin -m pytest ...`.
- Optionally runs DB host/port precheck.
- Executes configured runs and classifies each as `pass|fail|blocked`.
- Returns deterministic `decision_hint` and `blocker_class` for tester handoff routing.

## Script

`/Users/slobodan/Projects/Agents/skills/tester-targeted-pytest-runner/scripts/tester_targeted_pytest_runner.py`

## Input Contract

```json
{
  "worktree_root": "/path/to/worktree",
  "task_identifier": "MYO-###",
  "env_source": "/path/to/.env",
  "python_bin": "/path/to/python",
  "runs": [
    {"name": "users_auth", "cmd": "pytest tests/users/test_auth.py -q", "required": true},
    {"name": "users_ordering", "cmd": "pytest tests/users/test_ordering.py -q -rs", "required": true}
  ],
  "db_precheck": {"enabled": true, "host": "127.0.0.1", "port": 5432},
  "stop_on_blocked": false,
  "dry_run": false
}
```

## Output Contract

```json
{
  "ok": true,
  "tool": "tester-targeted-pytest-runner",
  "task_identifier": "MYO-###",
  "decision_hint": "ready_for_review|needs_dev_fix|blocked",
  "runs": [
    {"name": "users_auth", "result": "pass|fail|blocked", "exit_code": 0, "duration_ms": 0, "summary": "...", "signature": "optional"}
  ],
  "blocker_class": "none|db_unreachable|sandbox_network|missing_env|test_failure",
  "host_rerun_commands": ["..."],
  "warnings": [],
  "errors": []
}
```

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/tester-targeted-pytest-runner/scripts/tester_targeted_pytest_runner.py --input-json - --json-pretty
{
  "worktree_root": "/Users/slobodan/Projects/Ouroboros/workstations/workstation-2",
  "task_identifier": "MYO-167",
  "env_source": "/Users/slobodan/Projects/Ouroboros/.env",
  "python_bin": "/Users/slobodan/Projects/Ouroboros/.venv/bin/python",
  "runs": [
    {"name": "users_auth", "cmd": "pytest tests/users/test_auth.py -q", "required": true}
  ],
  "db_precheck": {"enabled": true, "host": "127.0.0.1", "port": 5432},
  "stop_on_blocked": false,
  "dry_run": false
}
JSON
```
