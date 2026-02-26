---
name: workstation-preparation
description: Prepare a clean worker slot worktree for orchestration by creating or resetting workstation-1 through workstation-10 with a requested branch. Use when orchestrator agents need a clean git worktree slot before dispatching a worker.
metadata:
  short-description: Prepare clean workstation slot
---

# Workstation Preparation

## Overview

Use this skill to create or reset worker slot worktrees in a deterministic clean state.

Mandatory policy gate:
- Do not create or reset any worktree slot without explicit user permission.
- If permission is not already explicit in the current request, stop and ask first.
- This requirement follows `agents/_shared/WORKTREE_POLICY.md`.

The skill enforces:
- allowed slot names: `workstation-1` ... `workstation-10`
- hard limit: never create an 11th workstation slot
- clean reset to requested branch and base ref
- post-prepare workstation hydration from tracked asset manifest (symlink/copy)
- per-slot hydration readiness state output for orchestration gating
- optional auto-fallback when a branch is already checked out elsewhere
- optional JSON output for orchestrators
- optional bulk repair of all existing managed slots

## Script

`/Users/slobodan/.codex/skills/workstation-preparation/scripts/prepare_workstation.py`

## Inputs

- `worktree_name` (optional): workstation slot name (`workstation-1` ... `workstation-10`)
- `branch_name` (optional): branch to initialize in that slot
- `base_ref` (optional): source ref for reset/create
- `worktrees_parent` (optional): parent dir for new slot path
- `force_reset_existing` (optional): allow destructive reset of dirty/diverged slot
- `branch_in_use_fallback_suffix` (optional): suffix to resolve branch checkout conflicts (for example `-dev`)
- `repair_all_existing` (optional): reset all managed slots in one run
- `slot_role` (optional): `all|developer|tester|reviewer` for role-filtered hydration
- `assets_manifest_path` (optional): manifest json path
- `assets_state_path` (optional): output state json path
- `skip_assets_hydration` (optional): skip hydration step
- `require_assets_manifest` (optional): fail when manifest is missing
- `output` (optional): `text` (default) or `json`

Defaults:
- if `worktree_name` is omitted, script auto-selects first free standardized slot
- if `branch_name` is omitted, script uses the resolved `worktree_name`
- default manifest path:
  - `<repo-root>/reports/optimus-prime/config/WORKSTATION_ASSETS.json`
- default state path:
  - `<repo-root>/reports/optimus-prime/WORKSTATION_ASSET_STATE.json`

## Usage

### Create or reset one slot
```bash
python3 /Users/slobodan/.codex/skills/workstation-preparation/scripts/prepare_workstation.py \
  --repo-root /path/to/repo \
  --worktree-name workstation-3 \
  --branch-name codex/dev/MYO-200
```

### Auto-select next free standardized slot
```bash
python3 /Users/slobodan/.codex/skills/workstation-preparation/scripts/prepare_workstation.py \
  --repo-root /path/to/repo
```

### Resolve branch already checked out elsewhere
```bash
python3 /Users/slobodan/.codex/skills/workstation-preparation/scripts/prepare_workstation.py \
  --repo-root /path/to/repo \
  --worktree-name workstation-4 \
  --branch-name codex/dev/MYO-200 \
  --branch-in-use-fallback-suffix -dev
```

### Force reset existing slot (destructive cleanup)
```bash
python3 /Users/slobodan/.codex/skills/workstation-preparation/scripts/prepare_workstation.py \
  --repo-root /path/to/repo \
  --worktree-name workstation-2 \
  --branch-name workstation-2 \
  --force-reset-existing
```

### Repair all existing managed slots
```bash
python3 /Users/slobodan/.codex/skills/workstation-preparation/scripts/prepare_workstation.py \
  --repo-root /path/to/repo \
  --repair-all-existing \
  --force-reset-existing
```

### JSON output for orchestration parsing
```bash
python3 /Users/slobodan/.codex/skills/workstation-preparation/scripts/prepare_workstation.py \
  --repo-root /path/to/repo \
  --worktree-name workstation-1 \
  --branch-name codex/dev/MYO-123 \
  --output json
```

### Enforced hydration with required manifest
```bash
python3 /Users/slobodan/.codex/skills/workstation-preparation/scripts/prepare_workstation.py \
  --repo-root /path/to/repo \
  --worktree-name workstation-1 \
  --branch-name codex/dev/MYO-123 \
  --slot-role developer \
  --require-assets-manifest \
  --output json
```

## Notes

- If slot already exists and contains local changes/diverged commits, command fails unless `--force-reset-existing` is passed.
- If requested branch is currently checked out in another worktree, command fails unless `--branch-in-use-fallback-suffix` is provided.
- New slots are created under `<repo-parent>/<repo-name>-workstations` by default. Override with `--worktrees-parent` when needed.
- Manifest format example:
  - `/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/workstation-preparation/references/workstation_assets_manifest.example.json`
