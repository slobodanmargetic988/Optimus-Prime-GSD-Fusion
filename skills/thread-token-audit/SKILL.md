---
name: thread-token-audit
description: Summarize project token burn by reading THREAD_HISTORY.log and matching worker thread ids to Codex session JSONL token_count events.
metadata:
  short-description: Project/session token usage audit from thread history
---

# Thread Token Audit

## Overview

Use this skill to calculate:
- total token burn for a project
- token burn per worker type
- token burn per slot
- token burn per worker thread session

Primary source:
- `reports/optimus-prime/THREAD_HISTORY.log` with format:
  - `slot | worker type | thread-id`

Outputs:
- `reports/optimus-prime/THREAD_TOKEN_USAGE_SUMMARY.json`
- `reports/optimus-prime/THREAD_TOKEN_USAGE_SUMMARY.md`

## Script

`/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/skills/thread-token-audit/scripts/thread_token_audit.py`

## Input Contract

```json
{
  "repo_root": "/Users/slobodan/projects/Optimus-Prime-GSD-Fusion",
  "thread_history_path": "reports/optimus-prime/THREAD_HISTORY.log",
  "worker_registry_path": "reports/optimus-prime/WORKER_REGISTRY.json",
  "output_json_path": "reports/optimus-prime/THREAD_TOKEN_USAGE_SUMMARY.json",
  "output_markdown_path": "reports/optimus-prime/THREAD_TOKEN_USAGE_SUMMARY.md",
  "codex_homes": {
    "codex": "/Users/slobodan/.codex",
    "codex-second": "/Users/slobodan/.codex-second"
  }
}
```

Notes:
- `repo_root` is required.
- `codex_homes` is optional; when omitted, aliases are inferred from worker registry and defaults (`codex -> ~/.codex`, `alias -> ~/.<alias>`).

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/projects/Optimus-Prime-GSD-Fusion/skills/thread-token-audit/scripts/thread_token_audit.py --input-json - --json-pretty
{
  "repo_root": "/Users/slobodan/projects/Optimus-Prime-GSD-Fusion"
}
JSON
```

## Failure Behavior

- Missing thread history file -> hard error.
- Missing/unresolved session files -> recorded as unresolved sessions (audit still succeeds).
