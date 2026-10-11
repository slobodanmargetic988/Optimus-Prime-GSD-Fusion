# Private release credential audit

Audit date: 2026-10-11. Repository baseline: `659c6fdbc39291058ea6c6efa0432389f4ffb249`, plus the exact staged publication-preparation source on `codex/free-open-source-desktop`.

**No confirmed credentials were found in the audited Git history or source snapshot.** The repository remains private while the application is tested. This is a dated scan result, not a guarantee that future changes or every possible secret format are safe.

## Scope and evidence

| Check | Scope | Result |
| --- | --- | --- |
| Gitleaks 8.30.1 history scan | 559 commits reachable from 363 local refs, including fetched GitHub branches/tags, local branches, stash, and Codex snapshot refs | No unreviewed findings |
| Additional reflog scan | 565 reachable/reflog commits | No unreviewed findings |
| Complete historical file contents | 2,805 distinct Git blobs, 141,817,135 bytes | No confirmed credentials |
| Publication-candidate working tree | 1,200 tracked and nonignored untracked files at the initial snapshot | No confirmed credentials |
| Final staged source | All 1,205 files extracted directly from the Git index, including this finalized report | No unreviewed findings |
| Commit and annotated-tag messages | All reachable commit messages and both annotated tags | No findings |
| Supplemental patterns | Provider tokens, JWTs, private-key markers, credential-bearing URLs, signed access URLs, sensitive credential filenames | No findings |
| Image text | Local OCR of all 13 reachable image blobs and all 6 final staged images, followed by credential scanning | No findings; OCR can miss text |
| Compressed content inventory | File signatures checked for ZIP, gzip, tar, xz, bzip2, and 7z | No reachable compressed archives found |
| Remote configuration | Credential-bearing HTTP remote URLs | None found |

GitHub branches and tags were fetched before the final history check. The repository was not shallow. No pull requests or advertised pull-request head refs were present. Some audited local refs are not published on GitHub, so this scope is broader than the remote's advertised branch/tag history.

Archive scanning was enabled to depth 2 and recursive decoding to depth 5. Scans ran locally. No source, screenshots, findings, or credentials were uploaded to a scanning service, and no token-validation requests were made.

## Reviewed false positives

The unmodified default scanner reported 64 historical occurrences, corresponding to 34 occurrences in distinct blob versions and 10 in the initial working-tree snapshot. Every occurrence was reviewed:

- Recommendation stability identifiers in the REQ-053 sample and its historical generated contract. The runtime deterministically derives these identifiers from recommendation content using SHA-256; they do not authorize access.
- Two static REQ-057 validation reason codes in historical versions of `scripts/strategy_validators.py`.

The root `.gitleaks.toml` permits only those exact identifier formats in their specific files, using both conditions together. It does not exclude test, fixture, documentation, or log directories. A synthetic regression check verified that a credential-shaped value inserted into an excepted file is still detected, and that an excepted identifier format in an unrelated file is still detected.

The reviewed configuration passed the complete history scan, the initial current-source scan, and the final exact staged-source scan. The staged-source scan was repeated after this report was finalized. No credential rotation or history rewrite was indicated by these results.

## Ongoing protection

`.github/workflows/secret-scan.yml` scans complete fetched history and a complete tracked-source snapshot on pushes, pull requests, and manual runs. It uses a pinned checkout action and a checksum-verified Gitleaks release. Scanner output is fully redacted. Reports are not uploaded as workflow artifacts.

Local credential files, environment files, runtime state, private hosting metadata, generated installers, and inspection output must remain outside the committed source. Repeat the staged-source scan after any further changes, and repeat the history and source scans before changing repository visibility.

## Limits and publication gate

- This result applies to the reviewed staged source and the stated history baseline. Changes made after this audit require another scan.
- Existing history includes local filesystem paths and generated engineering reports. They did not contain detected credentials, but this audit does not remove personal machine names or certify business confidentiality.
- The audit covers Git data and the stated source snapshot. GitHub Actions logs, uploaded release assets, issue attachments, external services, and ignored local files are separate surfaces.
- Pattern scanners and OCR can miss unknown, encrypted, obfuscated, fragmented, or visually unreadable secrets. No scan proves complete absence.
- Do not make the repository public automatically. The owner will choose when testing and publication review are complete.

Raw redacted findings and intermediate extracted content remain in a private local audit directory outside the repository; only this sanitized summary and the preventive configuration belong in Git.
