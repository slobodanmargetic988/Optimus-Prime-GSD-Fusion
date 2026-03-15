# REQ-020: Risk Signal Normalization

Requirement ID: `REQ-020`

## Purpose
Normalize strategy risk signals from four anchors only:
- blockers
- retries
- watchdog exits
- regression patterns

This surface preserves gate-review reason-code taxonomy compatibility by emitting canonical `reason_code` values and retaining original source reason codes in `source_reason_codes`.

## Scope Lock
- In scope: normalization and aggregation of risk signals from the four anchors above.
- Out of scope: new packet sections, managers, or gates outside REQ-020.

## Input Contract
`strategy_context_sweep.py` accepts REQ-020 builder input via `--input-json` with:

```json
{
  "risk_signals": [
    {
      "signal_source": "blocker|retry|watchdog_exit|regression_pattern",
      "reason_code": "string",
      "summary": "string",
      "severity": "low|medium|high|critical",
      "occurrence_count": 1,
      "evidence_refs": ["string"],
      "first_observed_at_utc": "ISO-8601 UTC timestamp",
      "last_observed_at_utc": "ISO-8601 UTC timestamp"
    }
  ],
  "normalized_at_utc": "ISO-8601 UTC timestamp"
}
```

Notes:
- `signal_source` aliases are normalized (`blockers` -> `blocker`, `watchdog-exit` -> `watchdog_exit`, `regression` -> `regression_pattern`).
- `reason_code` aliases are normalized to canonical gate-review-compatible reason codes.
- Signals are aggregated by `(signal_source, reason_code, summary)` and `occurrence_count` is summed.

## Output Contract
REQ-020 output shape:

- `schema_version` = `req-020.risk-signal-normalization.v1`
- `requirement_id` = `REQ-020`
- `analysis_anchors` = `["blockers", "retries", "watchdog_exits", "regression_patterns"]`
- `risk_signal_normalization`
  - `normalized_at_utc`
  - `signals[]`
    - `normalized_signal_id`
    - `signal_source`
    - `reason_code`
    - `source_reason_codes[]`
    - `summary`
    - `severity`
    - `occurrence_count`
    - `evidence_refs[]`
    - `first_observed_at_utc`
    - `last_observed_at_utc`
  - `reason_code_taxonomy`
    - `compatibility_target` = `gate_review_reason_codes`
    - `canonical_reason_codes[]`
    - `source_reason_code_aliases_applied[]`
  - `summary`
    - `total_input_signals`
    - `total_normalized_signals`
    - `source_counts`
    - `severity_counts`
- `source`
  - `tool`
  - `tool_version`
- `call_metadata`
  - deterministic canonical-input digest fields

## Determinism And Compatibility
- Canonical input digest is deterministic and stable for identical normalized input.
- Canonical `reason_code` taxonomy remains gate-review-compatible.
- Source taxonomy is preserved through `source_reason_codes` for review traceability.

## Sample Structure
Output sample:
- `strategy/current/samples/REQ-020_risk-signal-normalization.sample.json`

That sample file is the documented structure baseline for REQ-020 contract validation.
