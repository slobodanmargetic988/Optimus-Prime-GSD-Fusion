# Lane C Troubleshooting

## `auth_error`

Cause:
- no usable GitHub token for private releases

Fix:
1. Run `gh auth login`, or
2. Set `GH_TOKEN` or `GITHUB_TOKEN`.

## `release_not_found`

Cause:
- selected channel/version does not exist

Fix:
1. Verify channel (`prerelease|stable`).
2. Verify `--version` matches release tag (accepts `vX.Y.Z` or `X.Y.Z` forms).

## `asset_missing`

Cause:
- release missing required assets (`*.tar.gz`, `bundle_manifest.json`, `SHA256SUMS.json`)

Fix:
1. Re-run tag release workflow.
2. Confirm release assets are attached.

## `checksum_mismatch` or `managed_checksum_mismatch`

Cause:
- downloaded bundle corruption, or
- installed managed file drift/tamper

Fix:
1. Reinstall/update from verified release assets.
2. Re-run `opctl doctor --json-pretty`.

## `doctor_blocked`

Cause:
- one or more readiness checks failed

Fix:
1. Run `opctl doctor --repair --json-pretty`.
2. If still blocked, inspect `checks[].id`, `checks[].details`, `errors[]`.

Note:
- `--repair` does not bypass checksum integrity failures; it repairs only safe filesystem/launcher/state normalization paths.

## Launchers not found (`opctl`/`op`)

Global default:
- `~/.local/bin`

Add to PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```
