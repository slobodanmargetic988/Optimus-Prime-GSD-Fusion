# Lane C Release Checklist

## Pre-Release

1. `VERSION` updated.
2. `CHANGELOG.md` updated for target version.
3. Bundle builder test passes.
4. Install lifecycle tests pass.
5. OP matrix still green.
6. Tag format chosen correctly:
   - prerelease: `vX.Y.Z-rc.N`
   - stable: `vX.Y.Z`
7. `python3 -m scripts.release.validate_release_readiness --repo-root <repo> --version <X.Y.Z[-rc.N]>` passes.

## Build Artifacts

1. Build bundle (local dry run optional):
   - `python3 -m scripts.release.build_lane_c_bundle --repo-root <repo> --out-dir <dist> --version <X.Y.Z[-rc.N]>`
2. Confirm required outputs:
   - `bundle_manifest.json`
   - `SHA256SUMS`
   - `SHA256SUMS.json`
   - `<bundle>.tar.gz`
3. Verify checksums and manifest required fields.

## Publish

1. Push tag:
   - `git tag vX.Y.Z-rc.N && git push origin vX.Y.Z-rc.N`
2. Verify workflow `.github/workflows/lane_c_release.yml` succeeded.
3. Verify release metadata artifact (`lane-c-release-metadata`) exists.
4. Verify release assets exist:
   - `*.tar.gz`
   - `bundle_manifest.json`
   - `SHA256SUMS.json`
   - `SHA256SUMS`

## Release Notes

1. Include version and date.
2. Include private-install/update examples using `--repo-owner/--repo-name`.
3. Include known limitations (GitHub-first distribution, macOS+Linux scope, private auth required).

## Post-Release Verification

1. `lane_c_private_smoke.yml` passes for:
   - `ubuntu-latest` + `global|local`
   - `macos-latest` + `global|local`
2. Fresh global install from release succeeds.
3. Update from prior version succeeds.
4. Uninstall removes only managed files.
5. `opctl doctor` returns expected status.
6. `/op-*` workflow commands still emit unchanged Lane B JSON contract.
