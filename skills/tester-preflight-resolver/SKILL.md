---
name: tester-preflight-resolver
description: Resolve tester branch checkout with deterministic fallback and lineage validation before tests.
metadata:
  short-description: Tester preflight branch/lineage/fallback gate
---

# Tester Preflight Resolver

## Overview

Use this skill before any tester packet execution to validate branch readiness.

Behavior:
- Validates git worktree context and packet anchors.
- Attempts checkout of assigned branch.
- Resolves deterministic fallback branch (`<assigned>-test`) when assigned branch is active in another worktree.
- Verifies lineage (`start_from_commit` ancestor of resolved HEAD).
- Optionally verifies `target_head_commit` match.

## Script

`/Users/slobodan/Projects/Agents/skills/tester-preflight-resolver/scripts/tester_preflight_resolver.py`

## Input Contract

```json
{
  "worktree_root": "/path/to/worktree",
  "task_identifier": "MYO-###",
  "branch_name": "codex/<slot>/<issue>",
  "start_from_branch": "main",
  "start_from_commit": "sha",
  "target_head_commit": "optional sha",
  "fallback_suffix": "-test",
  "allow_fallback": true,
  "dry_run": false
}
```

## Output Contract

```json
{
  "ok": true,
  "tool": "tester-preflight-resolver",
  "resolved_branch": "codex/...|codex/...-test",
  "fallback_used": false,
  "resolved_head_commit": "sha",
  "lineage_ok": true,
  "head_matches_target": true,
  "next_step": "run_tests|blocked",
  "warnings": [],
  "errors": []
}
```

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/tester-preflight-resolver/scripts/tester_preflight_resolver.py --input-json - --json-pretty
{
  "worktree_root": "/Users/slobodan/Projects/Ouroboros/workstations/workstation-2",
  "task_identifier": "MYO-166",
  "branch_name": "codex/dev-2/myo-166",
  "start_from_branch": "main",
  "start_from_commit": "abcdef1234",
  "target_head_commit": null,
  "fallback_suffix": "-test",
  "allow_fallback": true,
  "dry_run": false
}
JSON
```
