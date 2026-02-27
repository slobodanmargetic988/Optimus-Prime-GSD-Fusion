---
name: op-new-project
description: Initialize project planning baseline artifacts; auto-runs map-codebase on existing repos when stale/missing.
---

# OP New Project

Creates baseline planning artifacts under `reports/optimus-prime/planning/`.

## Script

`/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py`

## Required Inputs

- `mission`
- `scope`

## Usage

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py \
  --command /op-new-project \
  --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion \
  --mission "Ship MyBoard milestone" \
  --scope "Board workflows and collaboration" \
  --constraint "No legacy compatibility" \
  --json-pretty
```
