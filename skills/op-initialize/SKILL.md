---
name: op-initialize
description: Run map-codebase -> new-project -> plan in one deterministic bootstrap flow.
---

# OP Initialize

Runs planning bootstrap end-to-end and stops with a summary. It does not start build execution.

## Script

`/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py`

## Required Inputs

- `mission`
- `scope`

## Usage

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py \
  --command /op-initialize \
  --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion \
  --mission "Ship MyBoard milestone" \
  --scope "Board workflows and collaboration" \
  --constraint "No legacy compatibility" \
  --json-pretty
```
