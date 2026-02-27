# Lane C Upgrade Guide

Upgrades are explicit and manual.

## 1) Build or download a new verified bundle

The bundle must include:

- `bundle_manifest.json`
- `SHA256SUMS`
- `SHA256SUMS.json`
- `payload/`

## 2) Run update

```bash
opctl update \
  --bundle-dir /path/to/optimus-prime-<new-version> \
  --mode global \
  --json-pretty
```

For project-local installs:

```bash
opctl update \
  --bundle-dir /path/to/optimus-prime-<new-version> \
  --mode local \
  --repo-root /path/to/repo \
  --json-pretty
```

## 3) Verify health

```bash
opctl doctor --json-pretty
opctl /op-health --json-pretty
```

If update fails, installer state stores recovery metadata:

- `INSTALL_STATE.json.recovery.last_backup_path`
- `INSTALL_STATE.json.recovery.last_recovery_reason`

