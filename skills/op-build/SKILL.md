---
name: op-build
description: Run autonomous Optimus build loop with strict planning preflight and strategy escalation.
---

# OP Build

Runs autonomous build orchestration from planning artifacts until terminal completion or hard stop.

Current runtime path:
- `/op-build` defaults to `--start-policy auto`: it resumes valid OP Simple state when possible, otherwise executes `/op-simple-build` as a fresh run (initialize pre-step when needed).
- `/op-resume` resumes OP Simple state only.
- Legacy `/op-resume` fallback to non-`.op-simple` state is removed.

## Script

`/Users/slobodan/projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py`

## Usage

```bash
caffeinate -dimsu python3 /Users/slobodan/projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py \
  --command /op-build \
  --repo-root /Users/slobodan/projects/Optimus-Prime-GSD-Fusion \
  --json-pretty
```

Bounded run mode (resume-safe):

```bash
caffeinate -dimsu python3 /Users/slobodan/projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py \
  --command /op-build \
  --repo-root /Users/slobodan/projects/Optimus-Prime-GSD-Fusion \
  --max-build-cycles 3 \
  --json-pretty
```

Codex alias pool run (recommended for multi-profile/account operation):

```bash
caffeinate -dimsu python3 /Users/slobodan/projects/Optimus-Prime-GSD-Fusion/scripts/op/opctl.py \
  --command /op-build \
  --repo-root /Users/slobodan/projects/Optimus-Prime-GSD-Fusion \
  --executor-provider codex \
  --selected-aliases "nine,ten" \
  --json-pretty
```

## Alias vs Profile Flags

- `--executor-provider` selects backend (`codex`, `openrouter`, `blackbox`).
- `--selected-aliases` selects Codex alias homes (`.codex-*`) used for profile/rate selection.
- `--profile` sets Codex config profile name within the selected alias home.
- Do not pass alias names to `--profile` (example: `six`, `seven`, `nine` are aliases, not Codex config profile names).
