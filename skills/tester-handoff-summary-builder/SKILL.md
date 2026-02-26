---
name: tester-handoff-summary-builder
description: Build strict tester handoff summary payload from preflight and targeted test outputs.
metadata:
  short-description: Strict tester summary payload generator
---

# Tester Handoff Summary Builder

## Overview

Use this skill to generate final tester handoff output in strict Optimus format.

Behavior:
- Validates required payload fields.
- Merges checks from `tester-preflight-resolver` and `tester-targeted-pytest-runner` outputs.
- Enforces deterministic tester decision enum.
- Emits concise summary object ready for Optimus parser.

## Script

`/Users/slobodan/Projects/Agents/skills/tester-handoff-summary-builder/scripts/tester_handoff_summary_builder.py`

## Input Contract

```json
{
  "task_identifier": "MYO-###",
  "resolved_branch": "codex/...",
  "start_from_branch": "main",
  "start_from_commit": "sha",
  "head_commit": "sha",
  "preflight_json_path": "optional",
  "test_results_json_path": "optional",
  "decision_override": "optional",
  "findings": ["optional"],
  "blockers": ["optional"],
  "dry_run": false
}
```

## Output Contract

```json
{
  "task_identifier": "MYO-###",
  "branch": "codex/...",
  "start_from_branch": "...",
  "start_from_commit": "...",
  "head_commit": "...",
  "checks": [
    {"name": "preflight", "result": "pass"},
    {"name": "users_auth", "result": "blocked"}
  ],
  "decision": "ready_for_review|needs_dev_fix|blocked",
  "findings": ["..."],
  "blockers": ["..."]
}
```

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/tester-handoff-summary-builder/scripts/tester_handoff_summary_builder.py --input-json - --json-pretty
{
  "task_identifier": "MYO-168",
  "resolved_branch": "codex/dev-2/myo-168",
  "start_from_branch": "main",
  "start_from_commit": "abcdef1234",
  "head_commit": "0123456789ab",
  "preflight_json_path": "reports/tester/preflight.json",
  "test_results_json_path": "reports/tester/targeted-runs.json",
  "decision_override": null,
  "findings": [],
  "blockers": [],
  "dry_run": false
}
JSON
```
