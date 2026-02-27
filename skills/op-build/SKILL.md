---
name: op-build
description: Run autonomous Optimus build loop with strict planning preflight and strategy escalation.
---

# OP Build

Runs autonomous build orchestration from planning artifacts until terminal completion or hard stop.

## Script

`/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py`

## Usage

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py \
  --command /op-build \
  --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion \
  --json-pretty
```

Bounded run mode (resume-safe):

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py \
  --command /op-build \
  --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion \
  --max-build-cycles 3 \
  --json-pretty
```
