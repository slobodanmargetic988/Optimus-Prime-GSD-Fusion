# Lane C Quickstart

## Build a Release Bundle

```bash
python3 -m scripts.release.build_lane_c_bundle \
  --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion \
  --out-dir /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/dist \
  --json-pretty
```

## Install (Global Mode)

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/install/op_install.py \
  --bundle-dir /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/dist/optimus-prime-0.2.0 \
  --mode global \
  --json-pretty
```

This installs:

- product payload under `~/.optimus-prime/install/current`
- launchers under `~/.local/bin/opctl` and `~/.local/bin/op`
- managed skills/templates into `${CODEX_HOME:-~/.codex}`
- install state at `~/.optimus-prime/install/INSTALL_STATE.json`

## Validate

```bash
~/.local/bin/opctl doctor --json-pretty
~/.local/bin/opctl /op-status --json-pretty
```

## Local Project Mode

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/install/op_install.py \
  --bundle-dir /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/dist/optimus-prime-0.2.0 \
  --mode local \
  --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion \
  --json-pretty
```

