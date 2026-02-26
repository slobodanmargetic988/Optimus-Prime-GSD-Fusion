# Blocker Event Contract

Updated: 2026-02-26

Paths:
- event stream: `reports/optimus-prime/BLOCKERS.jsonl`
- aggregate index: `reports/optimus-prime/BLOCKER_INDEX.json`
- adaptation report: `reports/optimus-prime/BLOCKER_ADAPTATION_CANDIDATES.md`

## Event Row Schema (`BLOCKERS.jsonl`)

```json
{
  "timestamp": "2026-02-26T22:00:00Z",
  "task_identifier": "MYO-205",
  "worker_slot": "test-1",
  "worker_role": "tester",
  "stage": "runtime",
  "blocker_code": "runtime_start_failed",
  "category": "infra",
  "summary": "Nuxt startup EMFILE",
  "signature": "EMFILE: too many open files",
  "fingerprint": "runtime|runtime_start_failed|EMFILE: too many open files",
  "retryable": true,
  "runtime_id": "rt-shared-default-web",
  "evidence_paths": [
    "reports/optimus-prime/logs/runtime-default-web.log"
  ],
  "source_tool": "runtime-coordinator"
}
```

## Required Fields

- `timestamp`
- `blocker_code`
- `category`
- `summary`
- `fingerprint`
- `stage`

## Category Values

- `infra`
- `runtime`
- `env`
- `dependency`
- `code`
- `test`
- `review`
- `orchestration`
- `external`
- `unknown`

## Index Schema (`BLOCKER_INDEX.json`)

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-02-26T22:10:00Z",
  "source": {
    "blockers_path": "reports/optimus-prime/BLOCKERS.jsonl",
    "rows_processed": 42,
    "rows_malformed": 1
  },
  "entries": [
    {
      "fingerprint": "runtime|runtime_start_failed|EMFILE: too many open files",
      "first_seen": "2026-02-26T20:10:00Z",
      "last_seen": "2026-02-26T22:00:00Z",
      "count": 7,
      "category": "infra",
      "blocker_code": "runtime_start_failed",
      "stages": ["runtime"],
      "tasks": ["MYO-205", "MYO-216"],
      "latest_summary": "Nuxt startup EMFILE",
      "recommended_playbook": "Use shared runtime preview mode; forbid per-tester dev/watch startup"
    }
  ]
}
```

## Aggregation Rules

- Group by `fingerprint`.
- Update `count`, `first_seen`, `last_seen`, unique stages, and unique tasks.
- Preserve latest summary/signature for operator context.
- Surface top recurring fingerprints into adaptation report.
