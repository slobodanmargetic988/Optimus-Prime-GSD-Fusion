# Lane C Implementation Status

Updated: 2026-02-27

## Vision Alignment
1. Lane C does not redefine planning/build behavior from Lane B.
2. Installed product must preserve the same two-step operator flow:
   - `/op-initialize` for bootstrap/planning,
   - `/op-build` for autonomous execution.
3. Lane C scope is packaging/distribution/installer reliability, not runtime policy drift.

## Implemented

- Deterministic release bundle builder:
  - `scripts/release/build_lane_c_bundle.py`
  - emits `bundle_manifest.json`, `SHA256SUMS`, `SHA256SUMS.json`, `.tar.gz`
- Release readiness validator:
  - `scripts/release/validate_release_readiness.py`
- Installer lifecycle commands:
  - `scripts/install/op_install.py`
  - `scripts/install/op_update.py`
  - `scripts/install/op_uninstall.py`
  - `scripts/install/op_doctor.py`
- Private release fetch/auth support:
  - new module `scripts/install/release_client.py`
  - deterministic token resolution order:
    1. `gh auth token`
    2. `GH_TOKEN`
    3. `GITHUB_TOKEN`
- Installer/updater source modes:
  - local bundle: `--bundle-dir`
  - private release: `--repo-owner --repo-name --channel [--version]`
- Install state metadata extensions (`INSTALL_STATE.json`):
  - `source`
  - `source_ref`
  - `installed_manifest_path`
  - `installed_manifest_sha256`
  - `installed_checksums_sha256`
- Doctor integrity deepening:
  - `managed_manifest_integrity`
  - `managed_files_checksum_integrity`
  - checksum drift blocks (`doctor_blocked`) and is not auto-repaired
- Product wrapper command:
  - `scripts/op/opctl_product.py`
  - `/op-*` passthrough unchanged + `doctor|update|uninstall|version`
- Release workflow completed:
  - `.github/workflows/lane_c_release.yml`
  - publishes release assets on tags, marks `-rc.` tags as prerelease
  - emits release metadata artifact
- Private smoke workflow added:
  - `.github/workflows/lane_c_private_smoke.yml`
  - matrix: `ubuntu-latest|macos-latest` x `global|local`
- Docs updated:
  - `docs/install/QUICKSTART.md`
  - `docs/install/UPGRADE.md`
  - `docs/install/TROUBLESHOOTING.md`
  - `docs/release/LANE_C_RELEASE_CHECKLIST.md`

## Current Coverage

- Distribution channel: private GitHub Releases (canonical prerelease channel).
- Platforms: macOS + Linux.
- Install modes: `global|local`.
- Integrity enforcement:
  - bundle verification at install/update
  - installed manifest/checksum parity checks in doctor.

## Remaining to Mark Lane C Complete

- Run first real private prerelease publish (`vX.Y.Z-rc.N`) through `lane_c_release.yml`.
- Run `lane_c_private_smoke.yml` against published prerelease assets and capture green matrix evidence.
- Reconcile final status wording in overview docs after first successful private release cycle.
