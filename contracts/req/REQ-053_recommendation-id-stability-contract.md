# REQ-053: Recommendation ID Stability Contract

## Purpose
Define the contract and data-model surface for proving that recommendation IDs remain stable across no-change reruns and evolve deterministically when the substantive recommendation basis changes.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-053):
  - Compare a baseline recommendation set against bounded rerun scenarios.
  - Derive a deterministic `stability_key` from the documented recommendation basis fields.
  - Prove `same stability basis => same recommendation_id`.
  - Prove `changed stability basis => changed recommendation_id`.
- Out of scope (REQ-053): net-new packet sections, managers, orchestration gates, or recommendation routing changes outside this contract surface.

## Interface surface
Builder:
- `build_req_053_recommendation_id_stability_contract(payload) -> dict`

Validator:
- `validate_req_053_recommendation_id_stability_contract(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
`strategy_artifacts_handoff.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "recommendation_id_stability_contract",
  "now_utc": "2026-03-16T10:20:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "broad_sweep_context": {
    "earth_sweep_evidence_refs": [
      "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
    ],
    "projects_considered": [
      "earth-core-runtime"
    ],
    "cross_project_obligations": [
      {
        "target_project_id": "earth-core-runtime",
        "recommendation_ids": [
          "rec.align-earth-runtime-canary"
        ],
        "earth_sweep_evidence_refs": [
          "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
        ]
      }
    ],
    "unresolved_ideas": [
      {
        "idea_id": "idea.telemetry-shared-observability-follow-up",
        "summary": "Human-facing unresolved idea summary",
        "target_project_id": "earth-shared-observability",
        "recommendation_ids": [
          "rec.harden-telemetry-freshness"
        ],
        "earth_sweep_evidence_refs": [
          "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
        ]
      }
    ]
  },
  "baseline_revision": {
    "revision_id": "strategy-2026-03-15T08:00:00Z",
    "recommendations": [
      {
        "lineage_key": "lineage.telemetry-freshness",
        "recommendation_id": "rec.harden-telemetry-freshness",
        "summary": "Human-facing recommendation summary",
        "rationale": "Human-facing recommendation rationale",
        "packet_kind": "target-project",
        "peer_project_id": "",
        "lane": "execution",
        "priority": "high",
        "evidence_refs": [
          "reports/runtime/telemetry/freshness-gap-2026-03-15.json"
        ]
      }
    ]
  },
  "rerun_scenarios": [
    {
      "scenario_id": "scenario.no-change",
      "scenario_kind": "no-change",
      "description": "Replay with no substantive recommendation change.",
      "recommendations": []
    }
  ]
}
```

Rules:
- `analysis_type` must be `recommendation_id_stability_contract`.
- `target_project.project_id` must be non-empty.
- `target_project.project_root` must normalize to an absolute path.
- `broad_sweep_context` is optional. When present, it must normalize deterministic Earth-sweep evidence refs, projects considered, evidence-backed cross-project obligations, and unresolved ideas.
- `baseline_revision.revision_id` must be a non-empty string.
- `baseline_revision.recommendations[]` must be a non-empty list.
- `rerun_scenarios[]` must be a non-empty list.
- Each recommendation snapshot is strict and limited to:
  - `lineage_key`
  - `recommendation_id`
  - `summary`
  - `rationale`
  - `packet_kind`
  - `peer_project_id`
  - `lane`
  - `priority`
  - `evidence_refs[]`
- `lineage_key` must match `lineage.<lowercase-hyphenated-id>`.
- `recommendation_id` must match `rec.<lowercase-hyphenated-id>`.
- `packet_kind` must be `target-project` or `cross-project`.
- `peer_project_id` is required for `cross-project` recommendations and must be empty for `target-project`.
- `priority` must be `high`, `medium`, or `low`.
- `scenario_id` must match `scenario.<lowercase-hyphenated-id>`.
- `scenario_kind` must be `no-change` or `substantive-change`.
- `evidence_refs[]` must be non-empty and are trace-only inputs; they do not participate in the REQ-053 stability basis.
- Broad-sweep context must not silently invent cross-project obligations without Earth-sweep evidence refs. Unresolved ideas stay visible as explicit `open_risks`.

## Output contract
REQ-053 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- synthesis target: `target_project`
- stability surface: `recommendation_id_stability`
- bounded counts: `totals`

`recommendation_id_stability` contains:
- `baseline_revision_id`
- `stability_basis_fields`
- `baseline_recommendations`
- `scenario_results`
- `cross_project_context_usage`
- `open_risks`

`stability_basis_fields` is fixed to:
- `summary`
- `rationale`
- `packet_kind`
- `peer_project_id`
- `lane`
- `priority`

Each `baseline_recommendations[]` row includes:
- `lineage_key`
- `recommendation_id`
- `stability_key`
- `stability_basis`
- `evidence_refs`
- `earth_sweep_evidence_refs`
- `recommendation_field_completeness`

Each `scenario_results[]` row includes:
- `scenario_id`
- `scenario_kind`
- `description`
- `recommendation_results[]`
- `stable_recommendation_ids[]`
- `evolved_recommendation_ids[]`
- `added_recommendation_ids[]`
- `removed_recommendation_ids[]`

Each `recommendation_results[]` row includes:
- `lineage_key`
- `baseline_recommendation_id`
- `scenario_recommendation_id`
- `baseline_stability_key`
- `scenario_stability_key`
- `id_status`
- `changed_fields[]`
- `baseline_evidence_refs`
- `scenario_evidence_refs`
- `baseline_earth_sweep_evidence_refs`
- `scenario_earth_sweep_evidence_refs`
- `baseline_recommendation_field_completeness`
- `scenario_recommendation_field_completeness`

`cross_project_context_usage` contains:
- `cross_project_context_provided`
- `cross_project_context_used`
- `projects_considered`
- `earth_sweep_evidence_refs_considered`
- `cross_project_obligation_count`
- `unresolved_idea_count`
- `recommendation_ids_with_context`

`open_risks[]` reuses the deterministic open-risk surface:
- `open_risk_id`
- `recommendation_id`
- `summary`
- `reason_code`
- `project_id`
- `required_evidence_refs`
- `evidence_refs`
- `linked_recommendation_ids`
- `call_trace_lineage`
- `contributing_call_ids`

Generation behavior:
- `stability_key` is a deterministic hash over the documented REQ-053 stability basis only.
- When a rerun recommendation keeps the same stability basis, it must keep the same `recommendation_id`.
- When a rerun recommendation changes the stability basis, it must change `recommendation_id`.
- `no-change` scenarios must preserve the baseline lineage set exactly and emit only `stable` results.
- `substantive-change` scenarios may emit `stable`, `evolved`, `added`, or `removed` results.
- `changed_fields[]` follows the documented `stability_basis_fields` order.
- `baseline_recommendations[]` and `recommendation_results[]` must surface sorted, de-duplicated evidence refs plus explicit field-completeness proof.
- `cross_project_context_usage` must reflect whether broad-sweep context was provided and which recommendation ids used that context.
- Cross-project recommendations missing Earth-sweep evidence refs must surface as `open_risks[]` with deterministic `required_evidence_refs`.
- `unresolved_ideas[]` from broad-sweep context must surface as `open_risks[]`, not silent obligations.

`totals` includes:
- `baseline_recommendations`
- `scenario_count`
- `stable_results`
- `evolved_results`
- `added_results`
- `removed_results`
- `open_risk_count`

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/recommendation-id-stability-contract.json`
- Contract tests: `tests/contracts/test_recommendation-id-stability-contract.py`
- Integration tests: `tests/integration/test_recommendation-id-stability-contract.py`
- Output sample: `strategy/current/samples/REQ-053_recommendation-id-stability-contract.sample.json`

The structure in `strategy/current/samples/REQ-053_recommendation-id-stability-contract.sample.json`
is the canonical contract shape for REQ-053 and documents:
- `recommendation_id_stability.stability_basis_fields`
- `recommendation_id_stability.baseline_recommendations`
- `recommendation_id_stability.scenario_results`
- `recommendation_id_stability.scenario_results[].recommendation_results`
- `recommendation_id_stability.cross_project_context_usage`
- `recommendation_id_stability.open_risks`
- `totals`
