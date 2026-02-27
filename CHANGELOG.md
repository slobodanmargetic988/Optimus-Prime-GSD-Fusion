# Changelog

## Unreleased

## 0.3.0-rc.1 - 2026-02-27

- Lane C private-first release client for install/update (`gh auth token` -> `GH_TOKEN` -> `GITHUB_TOKEN`).
- Added remote release source flags to installer/updater:
  - `--repo-owner`
  - `--repo-name`
  - `--channel prerelease|stable`
  - `--version`
- Added install-state manifest metadata and strict doctor checksum integrity audits.
- Added private release publishing workflow and private smoke matrix workflow.
- Added release readiness validator (`scripts/release/validate_release_readiness.py`).

## 0.2.0 - 2026-02-27

- Lane C start: GitHub-first installable product foundation.
- Added deterministic release bundle builder with `bundle_manifest.json`, `SHA256SUMS`, and `SHA256SUMS.json`.
- Added install lifecycle commands: install, update, uninstall, doctor.
- Added product CLI wrapper `opctl_product.py` with `/op-*` passthrough + `doctor|update|uninstall|version`.
- Added initial release workflow/checklist scaffolding and installation docs.
