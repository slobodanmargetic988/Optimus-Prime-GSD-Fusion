# Lane C Upgrade Guide (Private Repo)

Updates are explicit/manual by design.

## Upgrade from private prerelease channel

```bash
opctl update \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --mode global \
  --json-pretty
```

Version pin:

```bash
opctl update \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --version 0.3.0-rc.2 \
  --mode global \
  --json-pretty
```

Local mode:

```bash
opctl update \
  --repo-owner slobodanmargetic988 \
  --repo-name Optimus-Prime-GSD-Fusion \
  --channel prerelease \
  --mode local \
  --repo-root /Users/slobodan/Projects/Optimus-Prime-GSD-Fusion \
  --json-pretty
```

## Fallback bundle-based update

```bash
opctl update \
  --bundle-dir /path/to/optimus-prime-<new-version> \
  --mode global \
  --json-pretty
```

## Post-update checks

```bash
opctl doctor --json-pretty
opctl /op-health --json-pretty
```

If update fails, inspect install state recovery:

- `INSTALL_STATE.json.recovery.last_backup_path`
- `INSTALL_STATE.json.recovery.last_recovery_reason`
