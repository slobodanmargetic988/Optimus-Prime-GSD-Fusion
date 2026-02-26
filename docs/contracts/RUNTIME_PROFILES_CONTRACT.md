# Runtime Profiles Contract

Updated: 2026-02-26

Path:
- `reports/optimus-prime/config/RUNTIME_PROFILES.json`

## Schema (v1)

```json
{
  "schema_version": "1.0",
  "profiles": [
    {
      "profile_id": "default-web",
      "kind": "web",
      "start_cmd": "npm run preview",
      "healthcheck": {
        "type": "url",
        "value": "http://127.0.0.1:4173/health"
      },
      "stop_cmd": "pkill -f 'npm run preview'",
      "env": {
        "PW_FRONTEND_MODE": "preview"
      },
      "supports_shared": true,
      "supports_isolated": true,
      "default_for_playwright": true,
      "default_base_url": "http://127.0.0.1:4173",
      "mutating_flow_policy": "serialized",
      "test_accounts": []
    }
  ]
}
```

## Field Rules

- `profile_id`: unique string.
- `kind`: `web|api|fullstack|custom`.
- `healthcheck.type`: `url|cmd|none`.
- `supports_shared`: if false, resolver must not choose shared mode.
- `supports_isolated`: if false, resolver must not choose isolated mode.
- `default_for_playwright`: preferred profile for browser flows.
- `mutating_flow_policy`: `serialized|account_pool|isolated`.

## Strategy Resolution Inputs

Resolver should consume:
- `requires_browser` (bool)
- `task_kind` (`ui_flow|api|unit|integration|other`)
- `mutating_flow` (bool)
- optional `runtime_strategy_override`
- optional `runtime_profile_id`
- optional `external_base_url`

## Resolver Outputs

- `runtime_strategy`: `none|external_url|shared_runtime|isolated_runtime`
- `runtime_profile_id`
- `runtime_id` (for shared/isolated)
- `base_url` (when applicable)
- `tester_must_not_start_runtime` (bool)
- `lease_id` (when lease policy applies)
