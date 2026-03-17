# REQ-069: Strategy Revision History and Diff Workflow

## Purpose
Define the contract and data-model surface for persisting strategy revision history snapshots and deterministic diff artifacts over time, with governance review gates that prevent random directional shifts.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-069):
  - Persist normalized `revision_history` snapshots across strategy revisions.
  - Emit deterministic `diff_artifacts` linking prior and current revisions.
  - Detect directional shifts per `change_domain` and require governance review references for shifts.
  - Emit a bounded `governance_review` decision surface to support review workflows.
- Out of scope (REQ-069): net-new packet sections, managers, orchestration gates, or non-revision/diff behaviors.

## Interface surface
Builder:
- `build_req_069_strategy_revision_history_and_diff_workflow(payload) -> dict`

Validator:
- `validate_req_069_strategy_revision_history_and_diff_workflow(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
REQ-069 expects:

```json
{
  "analysis_type": "strategy_revision_history_and_diff_workflow",
  "now_utc": "2026-03-17T09:45:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "broad_sweep_context": {
    "projects_considered": ["runtime-orchestrator"],
    "earth_sweep_evidence_refs": ["reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"]
  },
  "revision_snapshots": [
    {
      "revision_id": "strategy-2026-03-14",
      "recorded_at_utc": "2026-03-14T08:00:00Z",
      "strategy_summary": "Baseline strategy summary.",
      "focus_anchors": ["mission_scope", "runtime_lane"],
      "evidence_refs": ["strategy/history/strategy-2026-03-14/STRATEGY.json"]
    }
  ],
  "diff_requests": [
    {
      "diff_id": "diff.runtime.r14-r15",
      "from_revision_id": "strategy-2026-03-14",
      "to_revision_id": "strategy-2026-03-15",
      "change_domain": "runtime_lane",
      "directional_shift": "decrease",
      "changed_anchors": ["runtime_lane.queue_backlog"],
      "summary": "Runtime backlog decreased.",
      "evidence_refs": ["reports/runtime/runtime-status-2026-03-15.json#queue_backlog"]
    }
  ]
}
```

Rules:
- `analysis_type` must be `strategy_revision_history_and_diff_workflow` when provided.
- `target_project.project_root` must be an absolute path.
- `revision_snapshots[]` must contain at least one row with unique `revision_id` values.
- `revision_snapshots[]` rows must include `recorded_at_utc`, `strategy_summary`, `focus_anchors[]`, and `evidence_refs[]`.
- `diff_requests[]` must contain at least one row with unique `diff_id` values.
- Each diff must reference existing `revision_snapshots[].revision_id` values and progress forward in revision order.
- `directional_shift` must be one of `increase`, `decrease`, or `maintain`.

## Output contract
REQ-069 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- target anchor: `target_project`
- artifact payload: `strategy_revision_history_and_diff_workflow`
- reasoning payload: `processing_behavior`
- bounded counts: `totals`

`strategy_revision_history_and_diff_workflow` contains:
- `revision_history[]`
- `diff_artifacts[]`
- `governance_review`

Each `revision_history[]` row includes:
- `revision_id`
- `recorded_at_utc`
- `strategy_summary`
- `focus_anchors[]`
- `evidence_refs[]`

Each `diff_artifacts[]` row includes:
- `sequence_position`
- `diff_id`
- `diff_artifact_id`
- `from_revision_id`
- `to_revision_id`
- `change_domain`
- `directional_shift`
- `previous_directional_shift`
- `direction_change_detected`
- `governance_review_ref`
- `guardrail_status`
- `changed_anchors[]`
- `summary`
- `evidence_refs[]`

`guardrail_status` rules:
- `stable_direction`: no direction change detected for the domain.
- `governance_reviewed`: direction changed and `governance_review_ref` is present.
- `blocked_needs_governance_review`: direction changed without `governance_review_ref`.

`governance_review` includes:
- `decision` (`proceed` or `hold`)
- `rationale`
- `review_required_diff_ids[]`
- `approved_diff_ids[]`
- `blocked_diff_ids[]`

`processing_behavior` includes deterministic reasoning fields:
- `strategy`
- `context_inputs.broad_sweep_context`
- `cross_project_context_usage`
- `recommendation`

`processing_behavior.recommendation` includes:
- `decision`
- `rationale`
- `confidence`
- `evidence_refs[]`
- `recommended_actions[]`
- `cross_project_obligations[]`
- `open_risks[]`

`totals` includes:
- `revision_snapshots`
- `diff_artifacts`
- `domains_tracked`
- `review_required`
- `blocked_directional_shifts`

Behavior:
- `revision_history` is sorted by `recorded_at_utc` then `revision_id`.
- `diff_artifacts` sequence is deterministic and encoded by `sequence_position`.
- Direction changes are derived per `change_domain` from prior emitted domain direction.
- Governance review supports explicit approval and blocks random directional shifts without governance references.
- Cross-project obligations are emitted only when Earth-sweep evidence refs are available.
- Missing Earth-sweep context and unresolved governance review items are surfaced as `open_risks`.
- `governance_review` and `totals` counts must equal derived directional-shift sets.

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/strategy-revision-history-and-diff-workflow.json`
- Contract tests: `tests/contracts/test_strategy-revision-history-and-diff-workflow.py`
- Output sample: `strategy/current/samples/REQ-069_strategy-revision-history-and-diff-workflow.sample.json`

The structure in `strategy/current/samples/REQ-069_strategy-revision-history-and-diff-workflow.sample.json`
is the canonical contract shape for REQ-069 and documents:
- `strategy_revision_history_and_diff_workflow.revision_history`
- `strategy_revision_history_and_diff_workflow.diff_artifacts`
- `strategy_revision_history_and_diff_workflow.diff_artifacts[].guardrail_status`
- `strategy_revision_history_and_diff_workflow.diff_artifacts[].direction_change_detected`
- `strategy_revision_history_and_diff_workflow.governance_review`
- `strategy_revision_history_and_diff_workflow.governance_review.review_required_diff_ids`
- `totals`
