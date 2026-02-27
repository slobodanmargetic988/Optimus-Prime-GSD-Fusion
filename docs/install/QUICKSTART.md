# Lane C Quickstart (Private Repo First)

## 1) Authenticate for private release access

Use one of:

```bash
gh auth login
```

or:

```bash
export GH_TOKEN="<token>"
# or
export GITHUB_TOKEN="<token>"
```

Token resolution order in installer/update:
1. `gh auth token`
2. `GH_TOKEN`
3. `GITHUB_TOKEN`

## 2) Install from private prerelease (recommended)

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/install/op_install.py \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --mode global \
  --json-pretty
```

Version-pinned install:

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/install/op_install.py \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --version 0.3.0-rc.1 \
  --mode global \
  --json-pretty
```

## 3) Validate

```bash
~/.local/bin/opctl doctor --json-pretty
~/.local/bin/opctl /op-status --json-pretty
```

## 4) Local project install mode

```bash
python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/install/op_install.py \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --mode local \
  --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion \
  --json-pretty
```

## 5) Fallback local bundle mode

```bash
python3 -m scripts.release.build_lane_c_bundle \
  --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion \
  --out-dir /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/dist \
  --json-pretty

python3 /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/scripts/install/op_install.py \
  --bundle-dir /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/dist/optimus-prime-0.2.0 \
  --mode global \
  --json-pretty
```
