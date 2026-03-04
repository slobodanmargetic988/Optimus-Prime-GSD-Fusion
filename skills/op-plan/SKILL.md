---
name: op-plan
description: Generate plan packets and strict plan-check gate artifacts from baseline planning state.
---

# OP Plan

Generates `PLAN_PACKETS.json`, `PLAN_CHECK.json`, `TEST_CONTRACT.md`, and `PLAYWRIGHT_UAT_MATRIX.md`.

## Script

`/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py`

## Usage

```bash
python3 /Users/slobodan/projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py \
  --command /op-plan \
  --repo-root /Users/slobodan/projects/Optimus-Prime-GSD-Fusion \
  --json-pretty
```
