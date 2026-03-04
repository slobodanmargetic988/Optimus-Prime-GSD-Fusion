---
name: create-codex-profile
description: Create a new Codex profile directory (for example `.codex-second`) by copying per-profile identity/usage files (`auth.json`, `sessions`) and symlinking all other `.codex` contents so profiles share the same installed skills/agents/state backend.
---

# Create Codex Profile

## Overview

Use this skill when you want multiple Codex profiles that:
- keep separate login identity and usage tracking
- share the same installed runtime assets and state backend

This matches a workflow like:
1. Create `.codex-second` from `.codex`.
2. Log out/in in Codex Desktop while pointing `CODEX_HOME` to `.codex-second`.
3. Keep `.codex` and `.codex-second` functionally aligned except for session/account data.

## Script

- Preferred runtime path:
  - `"$CODEX_HOME/skills/create-codex-profile/scripts/create_codex_profile.py"`
- Repo-local alternative:
  - `"./skills/create-codex-profile/scripts/create_codex_profile.py"`

## Behavior

The script creates a target profile directory (default naming: `.codex-<profile>`), then:
- copies:
  - `auth.json`
  - `sessions/`
- symlinks:
  - every other top-level item from source `.codex`

Default source profile is:
1. `$CODEX_HOME` (if set)
2. `~/.codex`

## Usage

Set script path:

```bash
PROFILE_SCRIPT="$CODEX_HOME/skills/create-codex-profile/scripts/create_codex_profile.py"
# PROFILE_SCRIPT="./skills/create-codex-profile/scripts/create_codex_profile.py"
```

Create `.codex-second` from current default profile:

```bash
python3 "$PROFILE_SCRIPT" --profile second --json-pretty
```

Create a profile from an explicit source:

```bash
python3 "$PROFILE_SCRIPT" \
  --source-codex-home "$HOME/.codex" \
  --profile second \
  --json-pretty
```

Replace an existing target profile:

```bash
python3 "$PROFILE_SCRIPT" --profile second --replace --json-pretty
```

## Notes

- Input `second`, `.codex-second`, and `codex-second` all resolve to the same profile name.
- The script requires source `auth.json` to exist.
- Use `--replace` only when you intentionally want to recreate the target directory.
