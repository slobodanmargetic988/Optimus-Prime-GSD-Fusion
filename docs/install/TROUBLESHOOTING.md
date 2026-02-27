# Lane C Troubleshooting

## `checksum_mismatch` during install/update

Cause:

- bundle file corruption
- wrong `SHA256SUMS.json` for payload

Fix:

1. Rebuild bundle with `build_lane_c_bundle.py`.
2. Re-run install/update using the rebuilt bundle directory.

## `state_missing` on update/uninstall

Cause:

- install state not found at expected path

Fix:

1. For global mode verify `~/.optimus-prime/install/INSTALL_STATE.json`.
2. For local mode verify `<repo>/.optimus-prime/install/INSTALL_STATE.json`.
3. If missing, reinstall first.

## `doctor` returns blocked

Run:

```bash
opctl doctor --repair --json-pretty
```

If still blocked, inspect:

- `checks[].id`
- `checks[].details`
- `errors[]`

and apply the indicated manual fix.

## Launchers not found (`opctl`/`op`)

Global default launcher path:

- `~/.local/bin`

Add to shell PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

