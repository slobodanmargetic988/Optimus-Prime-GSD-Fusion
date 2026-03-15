# REQ-014: Deficit and Need Signal Extraction

## Purpose
Define the contract and data model for extracting unmet ecosystem needs that the target project can satisfy with high leverage, scored by impact and urgency, with linked evidence references.

## Scope Anchors
- Surface in scope: `scripts/strategy_context_sweep.py`.
- Strategy behavior in scope: extract unmet ecosystem needs that map to target-project capabilities with high leverage.
- Scoring in scope: impact + urgency per need signal.
- Evidence in scope: deterministic linked evidence references for each included need signal.
- Out of scope: new packet sections, managers, and orchestration gates unrelated to REQ-014.

## Input Contract
`strategy_context_sweep.py` accepts `--input-json <path|->` with this JSON object shape for REQ-014:

```json
{
  "analysis_type": "deficit_and_need_signal_extraction",
  "now_utc": "2026-03-14T21:00:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "capability_tags": ["telemetry", "orchestration", "contracts", "planning"]
  },
  "thresholds": {
    "min_impact_score": 6,
    "min_urgency_score": 6,
    "min_leverage_ratio": 0.5
  },
  "max_signals": 5,
  "broad_sweep_context": {
    "projects_considered": ["earth-north", "earth-south"],
    "evidence_refs_by_project": {
      "earth-north": ["SRC-1001"],
      "earth-south": ["SRC-2001", "SRC-2002"]
    }
  },
  "deficits": [
    {
      "deficit_id": "DEF-001",
      "summary": "Runtime telemetry freshness blind spots slow blocker remediation.",
      "impact_score": 9,
      "urgency_score": 8,
      "required_capability_tags": ["telemetry", "orchestration"],
      "evidence_refs": ["OBS-TELEM-001", "DOC-OPS-002"]
    }
  ]
}
```

Rules:
- `analysis_type` must be `deficit_and_need_signal_extraction` (or payload must include `target_project`/`deficits` for auto-dispatch).
- `target_project.project_id` is required.
- `target_project.capability_tags` must be a non-empty string list.
- `deficits[]` rows require: `deficit_id`, `summary`, `impact_score`, `urgency_score`, `required_capability_tags`, `evidence_refs`.
- `impact_score` and `urgency_score` range: `0..10`.
- Threshold ranges:
  - `thresholds.min_impact_score`: `0..10`
  - `thresholds.min_urgency_score`: `0..10`
  - `thresholds.min_leverage_ratio`: `0..1`
- `max_signals` must be an integer `> 0`.
- `broad_sweep_context` is optional and, when present, must include deterministic cross-project inputs:
  - `projects_considered`: string list.
  - `evidence_refs_by_project`: object keyed by project id with string-list evidence refs.
  - `cross_project` (optional): boolean override; default derives from project count.

## Output Contract
REQ-014 output contains:
- metadata: `ok`, `tool`, `tool_version`, `analysis_type`, `checked_at_utc`
- anchors: `analysis_anchors`
- effective config: `target_project`, `thresholds`, `max_signals`
- extracted signals: `need_signals[]`
- bounded exclusions: `excluded_deficits[]`
- linked evidence table: `evidence_references[]`
- deterministic recommendation and counts: `recommendation`, `totals`
- recommendation completeness:
  - `recommendation.cross_project_context` (normalized broad-sweep usage)
  - `recommendation.obligations` (evidence-grounded only)
  - `recommendation.open_risks` (unresolved cross-project ideas when Earth-sweep refs are missing)

Need signal row shape:

```json
{
  "signal_id": "NEED-0001",
  "deficit_id": "DEF-001",
  "summary": "Runtime telemetry freshness blind spots slow blocker remediation.",
  "impact_score": 9,
  "urgency_score": 8,
  "priority_score": 72,
  "required_capability_tags": ["telemetry", "orchestration"],
  "matched_capability_tags": ["telemetry", "orchestration"],
  "leverage_ratio": 1.0,
  "evidence_refs": ["EVD-0001", "EVD-0002"],
  "reason_code": "eligible_need_signal"
}
```

Extraction rules:
- `priority_score = impact_score * urgency_score`.
- `leverage_ratio = matched_capability_tags / required_capability_tags`.
- A deficit is eligible only when all pass:
  - `impact_score >= thresholds.min_impact_score`
  - `urgency_score >= thresholds.min_urgency_score`
  - `leverage_ratio >= thresholds.min_leverage_ratio`
- Eligible deficits are sorted by `priority_score desc`, then `impact_score desc`, then `urgency_score desc`, then `deficit_id asc`.
- `max_signals` caps included signals; overflow deficits are excluded with `max_signals_cap_reached`.

Evidence linkage:
- Each included signal creates deterministic `evidence_references[]` citation ids (`EVD-0001`, ...).
- Signal `evidence_refs[]` link to those citation ids.
- Citation rows map back to upstream evidence via `upstream_evidence_ref` and `deficit_id`.
- Cross-project obligations must include Earth-sweep evidence refs; if refs are missing, unresolved items are emitted as `open_risks` instead of obligations.

## Deterministic Fixtures and Samples
- Input fixture: `examples/fixtures/deficit-and-need-signal-extraction.json`
- Contract tests: `tests/contracts/test_deficit-and-need-signal-extraction.py`
- Output sample: `strategy/current/samples/REQ-014_deficit-and-need-signal-extraction.sample.json`

Documented sample structure (`REQ-014_deficit-and-need-signal-extraction.sample.json`) includes:
- top-level metadata and `analysis_type`,
- `need_signals[]` with impact/urgency/leverage/priority and citation links,
- `excluded_deficits[]` with deterministic threshold failure reasons,
- `evidence_references[]` with stable citation ids and upstream evidence mapping,
- `recommendation` and bounded `totals` for measurable contract verification.
