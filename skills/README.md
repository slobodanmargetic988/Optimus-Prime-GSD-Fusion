# Project Skills Catalog

This folder stores portable skill definitions used by agents in this repository.

## Included Skills
- `codex-rate-snapshot`
- `blocker-escalate-to-agents`
- `cycle-tick`
- `custom-thread-spawner`
- `dev-benchmark-runner`
- `dev-check-bundle`
- `dev-handoff-summary-builder`
- `dev-ephemeral-db-runner`
- `dev-openapi-client-sync`
- `dispatch-worker-packet`
- `figma`
- `figma-implement-design`
- `linear`
- `linear-handoff-sync`
- `optimus-cycle-controller`
- `orchestrator-status-snapshot`
- `pdf`
- `playwright`
- `runtime-coordinator`
- `screenshot`
- `sleep`
- `speech`
- `spreadsheet`
- `test-train-manager`
- `tester-handoff-summary-builder`
- `tester-preflight-resolver`
- `tester-targeted-pytest-runner`
- `thread-token-audit`
- `skill-creator`
- `skill-installer`
- `thread-dispatch`
- `workstation-preparation`

## Install To Codex Runtime
For a missing skill `<skill-name>`, copy its folder into `$CODEX_HOME/skills/` (usually `~/.codex/skills/`):

```bash
mkdir -p "$CODEX_HOME/skills"
cp -R <repo-root>/skills/<skill-name> "$CODEX_HOME/skills/<skill-name>"
```

For curated OpenAI skills, you can also use `skill-installer`.

After any skill install, restart Codex so the skill is available in new runs.
