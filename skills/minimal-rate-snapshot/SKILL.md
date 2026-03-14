---
name: minimal-rate-snapshot
description: Scan local Codex profile directories, call the ChatGPT usage endpoint per profile auth token, and emit a compact per-profile JSON snapshot with hard/soft gating decisions. Use when you need a quick multi-profile rate status check.
metadata:
  short-description: Minimal Codex profile rate snapshot
---

# Minimal Rate Snapshot

## Overview

Use this skill to quickly inspect all local Codex profiles and produce a compact JSON snapshot.

The bundled script:
- discovers profile folders (`.codex` and `.codex-*`) from the local machine
- excludes default `.codex` when multiple profiles exist
- reads `auth.json` (or `config/auth.json`) to get access tokens
- calls `https://chatgpt.com/backend-api/wham/usage` with Python HTTP requests for each discovered profile
- retries failed usage calls up to 2 additional times (3 total attempts)
- outputs one JSON object per profile with profile identity and gating decision

## Script

`/Users/slobodan/.codex/skills/minimal-rate-snapshot/scripts/minimal_rate_snapshot.py`

## Inputs

- `--minimal` (optional)
  - outputs only `alias`, `codex_home`, and `gated` for each profile
- `--table` (optional)
  - outputs a human-readable table with: `alias | remaining 5h | remaining weekly | email`
  - `remaining` is computed as `100 - used_percent`
- `--json-pretty` (optional)
  - pretty-prints the JSON output

## Gating Rules

- `false` (not gated): primary `< 60` and secondary `< 80`
- `soft-gated`: primary `60..92` or secondary `80..96`
- `hard-gated`: primary `> 92` or secondary `> 96`
- `not-available`: usage API failed on all 3 attempts

If profile auth is missing, the profile is treated as `hard-gated`.

## Usage

```bash
python3 /Users/slobodan/.codex/skills/minimal-rate-snapshot/scripts/minimal_rate_snapshot.py --json-pretty
```

```bash
python3 /Users/slobodan/.codex/skills/minimal-rate-snapshot/scripts/minimal_rate_snapshot.py --minimal --json-pretty
```

```bash
python3 /Users/slobodan/.codex/skills/minimal-rate-snapshot/scripts/minimal_rate_snapshot.py --table
```

## Output

Default output is a JSON array; each object includes:
- `email`
- `primary_window` (`used_percent`, `reset_at`)
- `secondary_window` (`used_percent`, `reset_at`)
- `alias`
- `codex_home`
- `gated` (`false`, `soft-gated`, `hard-gated`, `not-available`)

With `--table`, output columns are:
- `alias`
- `remaining 5h`
- `remaining weekly`
- `email`
