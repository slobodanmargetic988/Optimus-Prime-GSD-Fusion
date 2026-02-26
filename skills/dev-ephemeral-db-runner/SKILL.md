---
name: dev-ephemeral-db-runner
description: Provision, start, and stop deterministic temporary local PostgreSQL instances for developer packets.
metadata:
  short-description: Local ephemeral Postgres lifecycle
---

# Dev Ephemeral DB Runner

## Overview

Use this skill to replace manual `initdb`/`pg_ctl`/`createdb` chains.

It supports deterministic profile-scoped PostgreSQL lifecycle:
- start (idempotent)
- stop
- optional cleanup (`destroy_on_exit`)

Default profile storage root:
- `/tmp/dev-ephemeral-db-runner/<profile_name>/`

## Script

`/Users/slobodan/Projects/Agents/skills/dev-ephemeral-db-runner/scripts/dev_ephemeral_db_runner.py`

## Input Contract

```json
{
  "profile_name": "myo-###",
  "port": 55432,
  "db_name": "myboard_test_v2",
  "host": "127.0.0.1",
  "cleanup_mode": "preserve|destroy_on_exit",
  "shared_memory_compat": true,
  "dry_run": false
}
```

Extended fields:
- `action`: `start|stop` (default `start`)
- `base_dir`: override profile directory root

## Output Contract

```json
{
  "ok": true,
  "tool": "dev-ephemeral-db-runner",
  "profile_name": "myo-133",
  "host": "127.0.0.1",
  "port": 55432,
  "db_name": "myboard_test_v2",
  "dsn": "postgresql+psycopg2://...",
  "pgdata": "/tmp/...",
  "log_file": "/tmp/...",
  "started": true,
  "stop_cmd": "...",
  "warnings": [],
  "errors": []
}
```

## Usage

Start:

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/dev-ephemeral-db-runner/scripts/dev_ephemeral_db_runner.py --input-json - --json-pretty
{
  "action": "start",
  "profile_name": "myo-160",
  "port": 55432,
  "db_name": "myboard_test_v2",
  "host": "127.0.0.1",
  "cleanup_mode": "preserve",
  "shared_memory_compat": true,
  "dry_run": false
}
JSON
```

Stop:

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/dev-ephemeral-db-runner/scripts/dev_ephemeral_db_runner.py --input-json - --json-pretty
{
  "action": "stop",
  "profile_name": "myo-160",
  "port": 55432,
  "db_name": "myboard_test_v2",
  "host": "127.0.0.1",
  "cleanup_mode": "destroy_on_exit",
  "shared_memory_compat": true,
  "dry_run": false
}
JSON
```

## Failure Behavior

- Missing binaries -> `missing_binaries`
- Port bind/start failure -> `port_occupied` or `startup_failed`
- Cluster init failure -> `cluster_init_failed`
- DB creation failure -> `db_create_failed`
