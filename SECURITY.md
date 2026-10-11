# Security

Optimus runs local agents that can edit files and execute commands with your
permissions. Only open projects you trust, inspect attached instructions, and
review generated changes before deploying them. Provider credentials belong in
the provider's login/configuration or the desktop OS credential store, never in
project files or Git commits.

## Reporting a vulnerability

During private testing, invited collaborators should contact the maintainer
privately and arrange a disclosure channel before sharing sensitive details.
GitHub's private vulnerability reporting feature is not available while this
repository is private. Enable it when the repository is made public; then use
**Report a vulnerability** under its **Security** tab. Do not create a public
issue containing credentials, exploit details or private project data.

Include the affected version, operating system, a minimal reproduction, the
potential impact and suggested mitigation if known. Use synthetic credentials
and example data in reproductions. If an actual key was exposed, revoke or rotate
it with the provider; removing a file or rewriting history does not revoke a key.

## Supported versions

The desktop app is in prerelease testing. Security fixes target the latest
development version and the latest release, once published. Older snapshots are
not separately maintained. No response-time commitment is currently offered.

## Before publishing a release

Check the exact source snapshot and all Git refs that will become public with a
secret scanner. Review findings without printing secret values. Inspect release
assets, fixtures, screenshots and logs as well as source files. Resolve findings
and rotate exposed credentials before publication. Re-run the scan after changes;
a clean scan is evidence from the configured detectors, not proof that every
possible secret has been detected.
