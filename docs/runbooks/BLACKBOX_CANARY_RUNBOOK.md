# Blackbox Canary Runbook

This runbook enables non-interactive Blackbox execution for OP canary runs.

## Lanes

- `free` lane (no API key): fair-use and rate-gating can apply.
- `api_key` lane (keychain-backed): credit-metered usage.

## Wrapper Commands (Non-Interactive)

- Free lane wrapper:

```bash
env -u BLACKBOX_API_KEY -u OPENAI_API_KEY blackbox -m blackboxai/minimax/minimax-free -p "<prompt>"
```

- API-key lane wrapper:

```bash
BLACKBOX_API_KEY="$(security find-generic-password -a "$USER" -s BLACKBOXAI_KEY -w)" blackbox -m blackboxai/minimax/minimax-m2.5 -p "<prompt>"
```

Both wrappers are prompt-driven and do not open model picker dialogs.

## New Executor Log Policy

- New executor-path logs are written under `/Users/slobodan/projects/LOGS/op-executors/`.
- A periodic “checked recently” guard is applied to avoid constant churn.
- If cumulative size exceeds 3 GB, older files are truncated per runtime maintenance policy until the total is back under threshold.

## Canary Commands (Target Repo)

Target repo: `/Users/slobodan/projects/Earth/Tetris`

- `/op-simple-build` with free lane:

```bash
caffeinate -dimsu opctl /op-simple-build --repo-root /Users/slobodan/projects/Earth/Tetris --executor-provider blackbox --blackbox-lane free --executor-model blackboxai/minimax/minimax-free --max-build-cycles 1 --json-pretty
```

- `/op-simple-build` with API-key lane:

```bash
caffeinate -dimsu opctl /op-simple-build --repo-root /Users/slobodan/projects/Earth/Tetris --executor-provider blackbox --blackbox-lane api_key --executor-model blackboxai/minimax/minimax-m2.5 --max-build-cycles 1 --json-pretty
```

- `/op-build` with free lane:

```bash
caffeinate -dimsu opctl /op-build --repo-root /Users/slobodan/projects/Earth/Tetris --executor-provider blackbox --blackbox-lane free --executor-model blackboxai/minimax/minimax-free --max-build-cycles 1 --json-pretty
```

- `/op-build` with API-key lane:

```bash
caffeinate -dimsu opctl /op-build --repo-root /Users/slobodan/projects/Earth/Tetris --executor-provider blackbox --blackbox-lane api_key --executor-model blackboxai/minimax/minimax-m2.5 --max-build-cycles 1 --json-pretty
```

## Worker Override Mode

Default behavior uses the same build-selected executor for managers and workers.

Enable worker override capability explicitly:

```bash
caffeinate -dimsu opctl /op-simple-build --repo-root /Users/slobodan/projects/Earth/Tetris --executor-provider blackbox --blackbox-lane free --allow-worker-executor-override --max-build-cycles 1 --json-pretty
```

When `--allow-worker-executor-override` is omitted, worker-level provider/model fields are ignored.
