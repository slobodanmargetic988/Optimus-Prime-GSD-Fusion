---
name: dev-check-bundle
description: Run deterministic task-scoped check commands and return one structured pass/fail/blocked verdict.
metadata:
  short-description: Deterministic multi-check execution + single verdict
---

# Dev Check Bundle

## Overview

Use this skill when a worker packet requires multiple acceptance checks but needs one stable machine-readable outcome.

Behavior:
- Runs provided checks in deterministic order.
- Captures per-check `exit_code`, `duration_ms`, and concise `snippet`.
- Produces one overall verdict: `pass`, `fail`, or `blocked`.
- Supports full-run mode and `stop_on_fail` mode.

## Script

`/Users/slobodan/Projects/Agents/skills/dev-check-bundle/scripts/dev_check_bundle.py`

## Input Contract

```json
{
  "task_identifier": "MYO-###",
  "checks": [
    {"name": "compileall", "cmd": ".venv/bin/python -m compileall app"},
    {"name": "pytest", "cmd": ".venv/bin/pytest tests/unit -q"},
    {"name": "benchmark", "cmd": ".venv/bin/python scripts/benchmark_tasks_minimal.py --json"}
  ],
  "stop_on_fail": false,
  "max_parallel": 1,
  "dry_run": false
}
```

Optional:
- `repo_root` (default current directory)
- `timeout_sec` (global timeout per check)
- per-check `timeout_sec` override

## Output Contract

```json
{
  "ok": true,
  "tool": "dev-check-bundle",
  "task_identifier": "MYO-###",
  "overall": "pass",
  "checks": [
    {"name": "compileall", "result": "pass", "exit_code": 0, "duration_ms": 0, "snippet": "..."}
  ],
  "blockers": [],
  "warnings": [],
  "errors": []
}
```

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/dev-check-bundle/scripts/dev_check_bundle.py --input-json - --json-pretty
{
  "task_identifier": "MYO-163",
  "repo_root": "/Users/slobodan/Projects/Ouroboros",
  "checks": [
    {"name": "compileall", "cmd": ".venv/bin/python -m compileall app"},
    {"name": "pytest", "cmd": ".venv/bin/pytest tests/unit -q"}
  ],
  "stop_on_fail": false,
  "max_parallel": 1,
  "dry_run": false
}
JSON
```

## Failure Behavior

- Missing/invalid payload fields -> `input_error`
- Missing command/dependency or timeout -> `blocked` check result with blocker entry
- Failing check command -> `fail` check result
- If any check is blocked, overall verdict is `blocked`
