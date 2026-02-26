---
name: sleep
description: Pause execution for a configurable duration or until a target time. Use when an agent must delay work (for example, start in 30 minutes or at a specific local time).
metadata:
  short-description: Configurable wait/sleep helper
---

# Sleep

## Overview

This skill adds a deterministic waiting helper for delayed execution.

Supported wait modes:
- Duration mode: wait for a period (`--for 30m`, `--for 1h30m`)
- Until mode: wait until a target time (`--until "2026-02-21 03:30:00"`, `--until "03:30"`)

The script is:
- `/Users/slobodan/.codex/skills/sleep/scripts/sleep_wait.py`

## Prerequisites
- Python 3.10+ (uses `zoneinfo`)

## Usage

### Duration wait
```bash
python3 /Users/slobodan/.codex/skills/sleep/scripts/sleep_wait.py --for 30m
```

### Wait until local clock time
```bash
python3 /Users/slobodan/.codex/skills/sleep/scripts/sleep_wait.py --until "03:30"
```

If clock time already passed today, it rolls to next day.

### Wait until explicit datetime with timezone
```bash
python3 /Users/slobodan/.codex/skills/sleep/scripts/sleep_wait.py --until "2026-02-21T03:30:00" --tz Europe/Belgrade
```

### Dry run (compute only)
```bash
python3 /Users/slobodan/.codex/skills/sleep/scripts/sleep_wait.py --for 45m --dry-run
```

### Safety cap
```bash
python3 /Users/slobodan/.codex/skills/sleep/scripts/sleep_wait.py --for 10h --max-seconds 14400
```

This exits with an error if computed wait is larger than 4 hours.

## Notes
- Use this skill only when delay is intentional and explicitly requested.
- Prefer `--dry-run` first in automation flows to verify computed timing.

