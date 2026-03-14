# Project Skills Catalog

This folder stores portable skill definitions used by agents in this repository.

## Included Skills
- `codex-rate-snapshot`
- `minimal-rate-snapshot`
- `create-codex-profile`
- `blocker-escalate-to-agents`
- `cycle-tick`
- `dev-benchmark-runner`
- `dev-check-bundle`
- `dev-handoff-summary-builder`
- `dev-ephemeral-db-runner`
- `dev-openapi-client-sync`
- `dispatch-worker-packet`
- `linear`
- `linear-handoff-sync`
- `optimus-cycle-controller`
- `orchestrator-status-snapshot`
- `op-build`
- `op-initialize`
- `op-map-codebase`
- `op-new-project`
- `op-plan`
- `pdf`
- `playwright`
- `runtime-coordinator`
- `sleep`
- `test-train-manager`
- `tester-handoff-summary-builder`
- `tester-preflight-resolver`
- `tester-targeted-pytest-runner`
- `thread-token-audit`
- `thread-dispatch`
- `workstation-preparation`

> Note: this catalog documents only skills bundled in this repository. External
> runtime-provided skills can exist in `$CODEX_HOME/skills` but are not listed here.

## Install To Codex Runtime
For a missing skill `<skill-name>`, copy its folder into `$CODEX_HOME/skills/` (usually `~/.codex/skills/`):

```bash
mkdir -p "$CODEX_HOME/skills"
cp -R <repo-root>/skills/<skill-name> "$CODEX_HOME/skills/<skill-name>"
```

For curated OpenAI skills, you can also use `skill-installer`.

After any skill install, restart Codex so the skill is available in new runs.
