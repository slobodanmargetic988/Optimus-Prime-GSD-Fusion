# Lane A Addendum — Workstation Asset Hydration + Readiness Gate

Updated: 2026-02-26

## Problem
Worker runs fail due to missing non-git runtime assets inside worktrees (`.env`, auth state, local runtime folders, package caches, etc.).

## Goal
Make workstation initialization deterministic by hydrating each slot from a tracked asset manifest and writing per-slot readiness state used by orchestrator dispatch gates.

## Design

### 1) Tracked desired-state manifest
Default path:
- `reports/optimus-prime/config/WORKSTATION_ASSETS.json`

Schema:
- `assets[]` with fields:
  - `id`
  - `source`
  - `target`
  - `mode` (`symlink|copy`)
  - `required` (`true|false`)
  - `roles` (`all|developer|tester|reviewer`)

### 2) Runtime actual-state tracker
Default path:
- `reports/optimus-prime/WORKSTATION_ASSET_STATE.json`

Contains per-slot:
- readiness (`ready`)
- applied assets
- missing required/optional assets
- timestamps

### 3) Workstation skill behavior
`workstation-preparation` now:
1. prepares/resets slot
2. hydrates assets from manifest unless explicitly skipped
3. writes readiness state
4. fails when required assets are missing (if manifest exists and required assets fail)

### 4) Orchestrator dispatch rule
Optimus should dispatch worker only when slot readiness is `true` in state file.

## Implementation in this repo
- Script patched:
  - `skills/workstation-preparation/scripts/prepare_workstation.py`
- Manifest example added:
  - `skills/workstation-preparation/references/workstation_assets_manifest.example.json`
- Tests added:
  - `skills/workstation-preparation/tests/test_prepare_workstation_assets.py`

## Acceptance Criteria
- Workstation prepare run can hydrate symlink/copy assets from manifest.
- Required missing assets are surfaced deterministically and block readiness.
- State file is updated per slot per run.
- Hydration is idempotent.
- Role-specific entries are honored.

## Next (Optimus policy)
- Set `--require-assets-manifest` in orchestrator calls.
- Gate dispatch on `WORKSTATION_ASSET_STATE.json` slot readiness.
- Add suggestion loop: unresolved missing assets -> append recommendation entries for manifest review.
