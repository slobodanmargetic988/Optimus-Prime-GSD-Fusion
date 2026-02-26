---
name: dev-benchmark-runner
description: Run benchmark scripts deterministically with bounded retries and write structured evidence artifacts.
metadata:
  short-description: Repeatable benchmark execution + evidence JSON
---

# Dev Benchmark Runner

## Overview

Use this skill to replace manual reruns and ad-hoc parsing for developer benchmark packets.

Behavior:
- Builds deterministic benchmark command
- Executes with bounded retries on transient failures
- Classifies failures (`env|db|script|data`)
- Parses metrics (`p50_ms`, `p95_ms`, `mean_ms`)
- Writes stable artifact JSON

## Script

`/Users/slobodan/Projects/Agents/skills/dev-benchmark-runner/scripts/dev_benchmark_runner.py`

## Input Contract

```json
{
  "script": "scripts/benchmark_tasks_minimal.py",
  "dataset_size": 150,
  "iterations": 12,
  "warmup": 3,
  "max_retries": 2,
  "artifact_path": "reports/product-plan/evidence/benchmark.json",
  "dry_run": false
}
```

Optional:
- `repo_root` (default current dir)

## Output Contract

```json
{
  "ok": true,
  "tool": "dev-benchmark-runner",
  "attempts": 2,
  "command": "...",
  "artifact_path": "...json",
  "metrics": {"p50_ms": 0, "p95_ms": 0, "mean_ms": 0},
  "comparison": {"minimal_vs_tasks_percent_improvement": 0},
  "warnings": [],
  "errors": []
}
```

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/dev-benchmark-runner/scripts/dev_benchmark_runner.py --input-json - --json-pretty
{
  "script": "scripts/benchmark_tasks_minimal.py",
  "dataset_size": 150,
  "iterations": 12,
  "warmup": 3,
  "max_retries": 2,
  "artifact_path": "reports/product-plan/evidence/benchmark.json",
  "dry_run": false,
  "repo_root": "/Users/slobodan/Projects/Ouroboros"
}
JSON
```

## Failure Behavior

- Missing script/dependencies -> `env`
- DB/connectivity transient errors -> `db` (retry bounded)
- Missing data inputs -> `data`
- Unclassified script failure -> `script`
