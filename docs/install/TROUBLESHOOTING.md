# Lane C Troubleshooting

## `auth_error`

Cause:
- no usable GitHub token for the authenticated release installer

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

## `strategy_manifest_missing`

Cause:
- `/op-strategy` was called directly, or `/op-initialize` was called with an explicit missing `--strategy-manifest-file`.

Fix:
1. Create `strategy/STRATEGY_MANIFEST.md` in the target project, or
2. Pass `--strategy-manifest-file /path/to/manifest.md`, or
3. Pass `--skip-strategy` for a planning/build smoke test without strategy.

Note:
- `/op-initialize` skips strategy automatically when no default manifest exists and no explicit strategy flag is passed.

## `override_required`

Cause:
- existing `reports/optimus-prime/planning` artifacts were detected.

Fix:
1. Re-run with `--override-old-plan` only when replacing the old plan is intentional.
2. Use `opctl /op-status --repo-root <project> --json-pretty` first when you are not sure whether a prior OP run exists.

## Codex command or profile errors

Cause:
- Codex CLI is not on `PATH`,
- no authenticated Codex home exists,
- `CODEX_HOME` points to the wrong profile,
- selected aliases do not map to `.codex*` homes with `auth.json`.

Fix:
1. Run `codex --help`.
2. Confirm `~/.codex/auth.json` exists, or set `CODEX_HOME` to the intended Codex home.
3. For multiple accounts, create homes such as `~/.codex-second` and pass `--selected-aliases "codex,second"`.

## Launchers not found (`opctl`/`op`)

Global default:
- `~/.local/bin`

Add to PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```
