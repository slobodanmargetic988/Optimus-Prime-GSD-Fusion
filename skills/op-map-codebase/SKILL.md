---
name: op-map-codebase
description: Build deterministic codebase mapping artifacts for Optimus planning bootstrap.
---

# OP Map Codebase

Use this command to map an existing repository into planning artifacts.

## Script

`/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py`

## Usage

```bash
python3 /Users/slobodan/projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py \
  --command /op-map-codebase \
  --repo-root /Users/slobodan/projects/Optimus-Prime-GSD-Fusion \
  --json-pretty
```

CLI wrapper:

```bash
/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.sh /op-map-codebase --json-pretty
```
