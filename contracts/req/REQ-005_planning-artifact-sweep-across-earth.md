# REQ-005: Planning Artifact Sweep Across Earth

## Purpose
Define the contract and data model for sweeping planning artifacts across relevant projects and preserving freshness metadata so stale inputs can be downgraded or excluded deterministically.

## Scope Anchors
- Artifacts in scope: `plan_packets`, `state`, `roadmap`, `requirements`.
- Surface in scope: `scripts/strategy_context_sweep.py`.
- Out of scope: adding new packet sections, managers, or execution gates.

## Input Contract
`strategy_context_sweep.py` accepts `--input-json <path|->` with this JSON object shape:

```json
{
  "now_utc": "2026-03-14T21:00:00Z",
  "stale_after_seconds": {
    "plan_packets": 600,
    "state": 300,
    "roadmap": 86400,
    "requirements": 604800
  },
  "decision_policy": {
    "stale": "downgrade",
    "missing": "exclude"
  },
  "projects": [
    {
      "project_id": "earth-north",
      "root_path": "/abs/project/root",
      "artifacts": {
        "plan_packets": "strategy/current/PLAN_PACKETS.json",
        "state": "strategy/current/STATE.json",
        "roadmap": "docs/plans/ROADMAP.md",
        "requirements": "docs/plans/REQUIREMENTS.md"
      }
    }
  ]
}
```

Rules:
- `projects[]` must include all four artifact keys.
- Artifact paths may be absolute or relative to `root_path`.
- `decision_policy.stale|missing` allowed values: `include|downgrade|exclude`.
- If `now_utc` is omitted, runtime UTC clock is used.

## Output Contract
The script prints JSON with:
- sweep metadata: `ok`, `tool`, `tool_version`, `checked_at_utc`
- effective policy and thresholds
- per-project artifact freshness/decision rows
- aggregate totals

Per artifact output row:

```json
{
  "path": "/abs/path/to/artifact",
  "exists": true,
  "last_modified_utc": "2026-03-14T20:58:00Z",
  "age_seconds": 120,
  "stale_after_seconds": 600,
  "freshness": "fresh",
  "decision": "include"
}
```

Freshness and decision mapping:
- `fresh` => `include`
- `stale` => `decision_policy.stale`
- `missing` => `decision_policy.missing`

## Deterministic Fixtures and Samples
- Input fixture: `examples/fixtures/planning-artifact-sweep-across-earth.json`
- Output sample: `strategy/current/samples/REQ-005_planning-artifact-sweep-across-earth.sample.json`

The output sample structure is authoritative for REQ-005 contract verification and mirrors `strategy_context_sweep.py` return shape.
