---
name: codex-rate-snapshot
description: Read Codex session JSONL token_count events and profile auth.json files to produce normalized rate-limit snapshots for one or more CODEX_HOME profiles. Use when orchestrator agents need reliable rate gating without parsing the interactive /status TUI.
metadata:
  short-description: Read Codex profile rate snapshots
---

# Codex Rate Snapshot

## Overview

Use this skill to read rate-limit data from Codex session logs (`*.jsonl`) instead of scraping the interactive `/status` UI.

The bundled script:
- resolves one or more profile aliases to `CODEX_HOME`
- finds the newest session JSONL for each profile
- reads the latest `token_count` event with `payload.rate_limits`
- computes remaining percentages for 5h and weekly windows
- reads profile identity from `auth.json` (best effort)
- applies configurable rate gates and outputs normalized JSON

This is intended for orchestrators (for example `optimus-prime`) to make dispatch decisions with low token cost.

## Script

`/Users/slobodan/.codex/skills/codex-rate-snapshot/scripts/read_codex_rate_snapshots.py`

## Inputs

- `--profile alias=PATH_OR_DEFAULT` (repeatable)
  - `default` means the active default profile (`$CODEX_HOME` if set, otherwise `~/.codex`)
  - examples: `codex=default`, `codex-second=$HOME/.codex-second`
- `--gate-5h-percent` (optional, default `15`)
- `--gate-weekly-percent` (optional, default `10`)
- `--soft-gate-5h-percent` (optional, default `40`)
- `--soft-gate-weekly-percent` (optional, default `25`)
- `--soft-max-active-workers` (optional, default `3`)
- `--wait-max-hours` (optional, default `4`)
- `--json-pretty` (optional)

## Usage

### Single profile (default Codex home)
```bash
python3 /Users/slobodan/.codex/skills/codex-rate-snapshot/scripts/read_codex_rate_snapshots.py \
  --profile codex=default
```

### Multiple profiles with custom gates
```bash
python3 /Users/slobodan/.codex/skills/codex-rate-snapshot/scripts/read_codex_rate_snapshots.py \
  --profile codex=default \
  --profile codex-second=$HOME/.codex-second \
  --profile codex-third=$HOME/.codex-third \
  --gate-5h-percent 15 \
  --gate-weekly-percent 10 \
  --soft-gate-5h-percent 40 \
  --soft-gate-weekly-percent 25 \
  --soft-max-active-workers 3 \
  --wait-max-hours 4 \
  --json-pretty
```

## Output (JSON)

Top-level fields include:
- `generated_at`
- `gate_thresholds`
- `soft_concurrency` (soft throttle thresholds + recommended active-worker cap when soft-gated)
- `profiles` (map keyed by alias)
- `profile_running_mode` (`single-profile`, `single-user`, `multiple-users`, or `unknown`)
- `eligible_profiles`
- `gated_profiles`
- `soft_concurrency_gated_profiles`

Each profile entry includes:
- `codex_home`
- `account_identity` (best effort from `auth.json`)
- `session_file`
- `five_hour` and `weekly` windows (`used_percent`, `remaining_percent`, `reset_at`, `gated`)
- `recommended_action` (`continue`, `wait_until_reset`, `wind_down`)
- `soft_concurrency_gated` (true when 5h/weekly remaining is under soft throttle thresholds)
- `wait_until_reset_candidate` and `wait_seconds` when applicable

## Notes

- If a profile has no readable session JSONL or no parsable `token_count` event, the profile is marked ineligible (`recommended_action=wind_down`).
- Identity detection is best effort and should not block parsing unless your orchestrator explicitly requires it.
- This skill reads local files only; it does not call Codex `/status`.
