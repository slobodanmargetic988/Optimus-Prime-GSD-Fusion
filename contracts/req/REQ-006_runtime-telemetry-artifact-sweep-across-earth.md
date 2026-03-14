# REQ-006: Runtime Telemetry Artifact Sweep Across Earth

## Purpose
Define the contract and data model for sweeping runtime telemetry artifacts across projects so strategy can reason about throughput, blockers, and failure patterns with citation-ready evidence references.

## Scope Anchors
- Artifacts in scope: `runtime_traces`, `cycle_summaries`.
- Surface in scope: `scripts/strategy_context_sweep.py`.
- Requirement boundary: preserve source references for later recommendation evidence citation.
- Out of scope: adding net-new packet sections, managers, or orchestration gates.

## Input Contract
`strategy_context_sweep.py` accepts `--input-json <path|->` with this JSON object shape:

```json
{
  "now_utc": "2026-03-14T21:00:00Z",
  "stale_after_seconds": {
    "runtime_traces": 600,
    "cycle_summaries": 300
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
        "runtime_traces": [
          { "source_id": "trace-main", "path": "reports/optimus-prime/runtime/trace.jsonl" }
        ],
        "cycle_summaries": [
          { "source_id": "summary-current", "path": "reports/optimus-prime/CYCLE_SUMMARY.json" }
        ]
      }
    }
  ]
}
```

Rules:
- `projects[].artifacts.runtime_traces` and `projects[].artifacts.cycle_summaries` must both be non-empty lists.
- Each source row requires `source_id` and `path`.
- Source paths may be absolute or relative to `root_path`.
- `decision_policy.stale|missing` values: `include|downgrade|exclude`.
- If `now_utc` is omitted, runtime UTC clock is used.

## Output Contract
The script prints JSON with:
- sweep metadata: `ok`, `tool`, `tool_version`, `checked_at_utc`
- effective thresholds/policy: `stale_after_seconds`, `decision_policy`
- per-project source evaluations under `projects[].artifacts`
- flattened citation-ready references under `source_references`
- deterministic cross-project telemetry rollup under `broad_sweep_context`
- deterministic recommendation payload under `recommendation`
- aggregate counts under `totals`

Per-source output row:

```json
{
  "source_id": "trace-main",
  "path": "/abs/project/root/reports/optimus-prime/runtime/trace.jsonl",
  "exists": true,
  "last_modified_utc": "2026-03-14T20:58:00Z",
  "age_seconds": 120,
  "stale_after_seconds": 600,
  "freshness": "fresh",
  "decision": "include",
  "source_reference": {
    "citation_id": "SRC-0001",
    "project_id": "earth-north",
    "artifact_type": "runtime_traces",
    "source_id": "trace-main",
    "path": "/abs/project/root/reports/optimus-prime/runtime/trace.jsonl",
    "analysis_anchors": ["throughput", "blockers", "failure_patterns"]
  }
}
```

Freshness and decision mapping:
- `fresh` => `include`
- `stale` => `decision_policy.stale`
- `missing` => `decision_policy.missing`

Recommendation guardrails:
- `recommendation.evidence_refs` must point to citation ids present in `source_references`.
- `recommendation.obligations[].evidence_refs` must be non-empty.
- `recommendation.cross_project_context` mirrors the top-level `broad_sweep_context`.
- If cross-project reasoning cannot be completed from Earth sweep evidence, record an entry in `recommendation.open_risks` rather than emitting an evidence-free obligation.

## Deterministic Fixtures and Samples
- Input fixture: `examples/fixtures/runtime-telemetry-artifact-sweep-across-earth.json`
- Output sample: `strategy/current/samples/REQ-006_runtime-telemetry-artifact-sweep-across-earth.sample.json`

The sample file is the documented REQ-006 structure baseline. It includes:
- top-level `source_references[]` citation records (`citation_id`, source identity, freshness decision),
- project-local source rows with embedded `source_reference`,
- top-level `broad_sweep_context` plus mirrored recommendation context,
- recommendation evidence refs/obligations/open risks with deterministic fields,
- bounded totals for projects and runtime telemetry sources.
