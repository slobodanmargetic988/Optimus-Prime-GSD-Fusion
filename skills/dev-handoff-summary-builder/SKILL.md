---
name: dev-handoff-summary-builder
description: Build strict developer worker handoff summary payloads from git/check artifacts.
metadata:
  short-description: Strict developer handoff JSON builder
---

# Dev Handoff Summary Builder

## Overview

Use this skill to generate the final Optimus developer handoff payload in strict required format.

Behavior:
- Resolves current `HEAD` commit.
- Counts changed files from `start_from_commit..HEAD`.
- Consumes `dev-check-bundle` output directly (`checks[]`, `overall`, `blockers`).
- Produces deterministic JSON with required summary keys.

## Script

`/Users/slobodan/Projects/Agents/skills/dev-handoff-summary-builder/scripts/dev_handoff_summary_builder.py`

## Input Contract

```json
{
  "task_identifier": "MYO-###",
  "branch": "codex/dev-2/myo-133",
  "start_from_branch": "main",
  "start_from_commit": "sha",
  "checks_json_path": "optional/path/to/dev-check-bundle.json",
  "decision_hint": "ready_for_test|blocked|auto",
  "blockers": ["optional"],
  "dry_run": false
}
```

Optional:
- `repo_root` (default current directory)

## Output Contract

```json
{
  "task_identifier": "MYO-###",
  "branch": "...",
  "start_from_branch": "...",
  "start_from_commit": "...",
  "head_commit": "...",
  "files_changed_count": 0,
  "checks": {"name": "result"},
  "decision": "ready_for_test|blocked",
  "blockers": []
}
```

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/dev-handoff-summary-builder/scripts/dev_handoff_summary_builder.py --input-json - --json-pretty
{
  "task_identifier": "MYO-164",
  "branch": "codex/dev-2/myo-164",
  "start_from_branch": "main",
  "start_from_commit": "abcdef1234567890",
  "checks_json_path": "reports/checks/myo-164.json",
  "decision_hint": "auto",
  "blockers": [],
  "dry_run": false,
  "repo_root": "/Users/slobodan/Projects/Ouroboros"
}
JSON
```

## Decision Rules

- `auto`: derive from checks/blockers (`blocked` if any blocker or non-`pass` check result exists).
- `blocked`: force blocked.
- `ready_for_test`: accepted only when derived state is clean; otherwise overridden to `blocked`.
