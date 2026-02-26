---
name: dev-openapi-client-sync
description: Run OpenAPI export plus client regeneration and return deterministic drift report.
metadata:
  short-description: OpenAPI export + client type sync
---

# Dev OpenAPI Client Sync

## Overview

Use this skill for schema/type alignment tasks.

It performs:
- OpenAPI export command
- Client generation command
- Drift detection (`changed_files`)
- Optional strict mode (`fail_on_drift`)

## Script

`/Users/slobodan/Projects/Agents/skills/dev-openapi-client-sync/scripts/dev_openapi_client_sync.py`

## Input Contract

```json
{
  "openapi_output": "/tmp/myboard-openapi/openapi.json",
  "client_root": "web/nuxt-app",
  "generate_command": "npm run generate:api",
  "base_url_override": "file:///tmp/myboard-openapi",
  "fail_on_drift": false,
  "dry_run": false
}
```

Optional:
- `repo_root`
- `export_command` (default fallback: `openapi export --output <openapi_output>`)

## Output Contract

```json
{
  "ok": true,
  "tool": "dev-openapi-client-sync",
  "openapi_generated": true,
  "client_generated": true,
  "changed_files": ["..."],
  "drift_detected": false,
  "warnings": [],
  "errors": []
}
```

## Usage

```bash
cat <<'JSON' | python3 /Users/slobodan/Projects/Agents/skills/dev-openapi-client-sync/scripts/dev_openapi_client_sync.py --input-json - --json-pretty
{
  "repo_root": "/Users/slobodan/Projects/Ouroboros",
  "openapi_output": "/tmp/myboard-openapi/openapi.json",
  "client_root": "web/nuxt-app",
  "export_command": "python manage.py spectacular --file {openapi_output}",
  "generate_command": "npm run generate:api",
  "base_url_override": "file:///tmp/myboard-openapi",
  "fail_on_drift": false,
  "dry_run": false
}
JSON
```

## Failure Behavior

- Missing dependencies/commands -> `env`
- Schema/data format issues -> `data`
- Generation/export execution failure -> `script`
- Strict drift failure (`fail_on_drift=true` + changes) -> `drift_detected`
