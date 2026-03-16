# REQ-030: Call-5 Sequencing And Lane Design Reasoning

## Purpose
Define the contract and data-model surface for Call-5 reasoning that assigns recommendations into execution lanes and produces an explicit sequencing order under current constraints.

## Scope anchors
- Surface in scope: `scripts/strategy_llm_pipeline.py`.
- In scope (REQ-030 Call-5):
  - Design **execution lanes** with per-lane goals and why-now rationale.
  - Produce an explicit **sequence order** for recommendations across lanes.
  - Each lane/sequence item includes **expected coordination dependencies**.
- Out of scope (REQ-030): net-new packet sections, managers, or orchestration gates outside this sequencing/lane-design surface.

## Interface surface
Builder:
- `build_req_030_call_5_sequencing_and_lane_design_reasoning(payload) -> dict`

Validator:
- `validate_req_030_call_5_sequencing_and_lane_design_reasoning(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_llm_pipeline.py --input-json <path|->`

## Input contract
`strategy_llm_pipeline.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "call_5_sequencing_and_lane_design_reasoning",
  "now_utc": "2026-03-16T12:00:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "constraints": {
    "max_parallel_lanes": 2,
    "max_active_work_items": 4,
    "notes": ["..."]
  },
  "recommendations": [
    {
      "recommendation_id": "rec.example",
      "summary": "Human-facing summary",
      "rationale": "Why this is recommended",
      "expected_impact": "Expected impact statement",
      "risk_level": "low"
    }
  ],
  "sequencing_and_lane_design_reasoning": {
    "lanes": [
      {
        "lane_name": "Contract Lane",
        "lane_kind": "contract",
        "lane_goal": "Lock the contract/data-model surface first.",
        "why_now": "Explains why this lane is needed now.",
        "recommendation_ids": ["rec.example"],
        "coordination_dependencies": [
          {
            "dependency_kind": "prerequisite",
            "depends_on": "rec.other",
            "summary": "What coordination is expected and why."
          }
        ]
      }
    ],
    "sequence": [
      {
        "order": 1,
        "recommendation_id": "rec.example",
        "lane_name": "Contract Lane",
        "why_now": "Why this item is scheduled now.",
        "coordination_dependencies": []
      }
    ]
  }
}
```

Rules:
- `analysis_type` must be `call_5_sequencing_and_lane_design_reasoning`.
- `now_utc` becomes `checked_at_utc` in the output for deterministic verification.
- `constraints.max_parallel_lanes` and `constraints.max_active_work_items` must be positive integers.
- `constraints.notes[]` is an optional list of non-empty strings (normalized to sorted unique).
- `recommendations[]` rows are strict; unexpected keys are rejected.
- `risk_level` must be one of: `high|medium|low`.
- `sequencing_and_lane_design_reasoning.lanes[].recommendation_ids[]` must reference declared `recommendations[].recommendation_id`.
- `sequencing_and_lane_design_reasoning.sequence[].lane_name` must match a declared lane.
- `sequencing_and_lane_design_reasoning.sequence[].order` must be a unique positive integer.
- The builder is strict: unexpected keys are rejected to keep scope bounded to REQ-030 anchors.

## Output contract
REQ-030 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- identity anchors: `target_project`, `constraints`
- normalized inputs: `recommendations[]`
- reasoning surface: `sequencing_and_lane_design_reasoning.lanes[]`, `sequencing_and_lane_design_reasoning.sequence[]`
- bounded totals: `totals`

Lane rows:
- deterministic `lane_id` (`lane.<id>`) derived from `target_project.project_id` + `lane_name`
- `lane_name`, `lane_kind`, `lane_goal`, `why_now`
- `recommendation_ids[]` (sorted unique)
- `coordination_dependencies[]` with deterministic `dependency_id` (`dep.<id>`) and `depends_on_type` (`recommendation|external`)

Sequence rows:
- deterministic `sequence_id` (`seq.<id>`) derived from target+lane+recommendation+order
- `order`, `recommendation_id`, `lane_id`, `lane_name`, `why_now`
- `coordination_dependencies[]` with deterministic `dependency_id` (`dep.<id>`) and `depends_on_type`

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/call-5-sequencing-and-lane-design-reasoning.json`
- Contract tests: `tests/contracts/test_call-5-sequencing-and-lane-design-reasoning.py`
- Output sample: `strategy/current/samples/REQ-030_call-5-sequencing-and-lane-design-reasoning.sample.json`

The structure in `strategy/current/samples/REQ-030_call-5-sequencing-and-lane-design-reasoning.sample.json`
is the canonical contract shape for REQ-030 Call-5.
