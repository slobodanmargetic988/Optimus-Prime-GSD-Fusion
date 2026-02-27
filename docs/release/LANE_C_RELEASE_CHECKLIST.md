# Lane C Release Checklist

## Pre-Release

1. `VERSION` updated.
2. `CHANGELOG.md` updated for target version.
3. Bundle builder test passes.
4. Install lifecycle tests pass.
5. OP matrix still green.

## Build Artifacts

1. Build bundle:
   - `python3 -m scripts.release.build_lane_c_bundle --repo-root <repo> --out-dir <dist>`
2. Confirm outputs:
   - `bundle_manifest.json`
   - `SHA256SUMS`
   - `SHA256SUMS.json`
   - `<bundle>.tar.gz`
3. Verify checksums and manifest required fields.

## Release Notes

1. Include version and date.
2. Include install/update/uninstall command examples.
3. Include known limitations (GitHub-first distribution, macOS+Linux scope).

## Post-Release Verification

1. Fresh global install from release bundle succeeds.
2. Update from prior version succeeds.
3. Uninstall removes only managed files.
4. `opctl doctor` returns expected status.
5. `/op-*` workflow commands still emit unchanged Lane B JSON contract.

