# REQ-018 Strategic Debt Signal Extraction

## Requirement intent
- Strategy extracts strategic debt signals that can degrade future velocity if unresolved.
- Each signal includes recurrence and likely blast-radius estimates.
- Scope is limited to contract/data-model fields needed for this extraction surface.

## Input contract
`scripts/strategy_context_sweep.py::extract_strategic_debt_signals` accepts one JSON object with:
- `analysis_type` (optional, when routed through `run` must be `strategic_debt_signal_extraction`)
- `evaluated_at` (optional timestamp; defaults to current UTC)
- `active_project_id` (string, required)
- `thresholds` (object, optional)
- `max_signals` (positive integer, optional)
- `broad_sweep_context` (object, optional)
- `debt_observations` (non-empty array, required)

`thresholds` fields:
- `min_recurrence_count` (non-negative integer; default `3`)
- `min_likely_blast_radius` (non-negative integer; default `2`)

Each `debt_observations[]` row requires:
- `debt_id` (string, unique)
- `summary` (string)
- `recurrence_count` (non-negative integer)
- `likely_blast_radius` (non-negative integer)
- `category` (string, optional; defaults to `unspecified`)
- `evidence_refs` (array of strings, optional)

`broad_sweep_context` fields:
- `projects_considered` (array of strings, optional)
- `evidence_refs_by_project` (object keyed by project id to evidence-ref arrays, optional)
- `cross_project` (boolean, optional; defaults from `projects_considered`)
- `unresolved_ideas` (array of strings or `{summary, evidence_refs}` objects, optional)
- `earth_sweep_source_artifacts` (array of `{artifact_ref, status, evidence_refs}` objects, optional; supports stale source diagnostics)
- `required_context_documents` (array of `{doc_kind, doc_ref, status, project_id, evidence_refs}` objects, optional; supports missing mission/scope/peer-doc diagnostics)

## Output contract
The extraction output is a canonical REQ-018 surface with:
- `ok`
- `requirement_id` (`REQ-018`)
- `schema_version` (`req-018.strategic-debt-signal-extraction.v1`)
- `analysis_type` (`strategic_debt_signal_extraction`)
- `evaluated_at`
- `analysis_anchors`
- `active_project_id`
- `thresholds`
- `max_signals`
- `strategic_debt_signals`
- `excluded_debt_observations`
- `evidence_references`
- `recommendation`
- `totals`

`strategic_debt_signals[]` rows include:
- `signal_id`
- `debt_id`
- `summary`
- `category`
- `recurrence_count`
- `likely_blast_radius`
- `blast_radius_tier`
- `priority_score` (`recurrence_count * likely_blast_radius`)
- `evidence_refs` (citation ids)
- `reason_code`

Behavior guarantees:
- A debt observation is eligible only when recurrence and likely blast radius both satisfy thresholds.
- Eligible observations are ranked by `priority_score desc`, `recurrence_count desc`, `likely_blast_radius desc`, then `debt_id asc`.
- `max_signals` bounds output signals; overflow eligible rows are emitted under `excluded_debt_observations` with `max_signals_cap_reached`.
- `evidence_references` emits deterministic citation IDs (`EVD-0001`, ...) tied to selected strategic debt signals.
- `recommendation` includes `cross_project_context`, `obligations`, and `open_risks`.
- `open_risks[]` rows include `reason_code` and `evidence_refs` so replay diagnostics remain actionable.
- Cross-project obligations are emitted only when Earth-sweep evidence refs are available in `broad_sweep_context`.
- Unresolved cross-project ideas are preserved as `open_risks`; they are not silently promoted into obligations.

## Executable artifacts
- Fixture input: `examples/fixtures/strategic-debt-signal-extraction.json`
- Contract test: `tests/contracts/test_strategic-debt-signal-extraction.py`
- Canonical sample output: `strategy/current/samples/REQ-018_strategic-debt-signal-extraction.sample.json`

## Sample structure
The canonical sample output is stored at:

`strategy/current/samples/REQ-018_strategic-debt-signal-extraction.sample.json`

Its top-level shape is:

```json
{
  "ok": true,
  "requirement_id": "REQ-018",
  "schema_version": "req-018.strategic-debt-signal-extraction.v1",
  "analysis_type": "strategic_debt_signal_extraction",
  "evaluated_at": "2026-03-15T03:20:00Z",
  "analysis_anchors": [],
  "active_project_id": "optimus-prime-gsd-fusion",
  "thresholds": {},
  "max_signals": 3,
  "strategic_debt_signals": [],
  "excluded_debt_observations": [],
  "evidence_references": [],
  "recommendation": {},
  "totals": {}
}
```
