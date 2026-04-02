# REQ-049: Strategy JSON Generator

## Purpose
Define the contract and data-model surface for generating the machine-consumable `STRATEGY.json` artifact with a stable schema for downstream tooling.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-049):
  - Emit a deterministic `STRATEGY.json`-shaped machine artifact.
  - Preserve recommendation-level anchors for `recommendation_id`, `rationale`, `impacts`, `risk_ids`, and `evidence_refs`.
  - Preserve risk register anchors and aggregate evidence refs for downstream consumers.
- Out of scope (REQ-049): new packet sections, managers, or orchestration gates beyond STRATEGY.json emission.

## Interface surface
Builder:
- `build_req_049_strategy_json_generator(payload) -> dict`

Validator:
- `validate_req_049_strategy_json_generator(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
`strategy_artifacts_handoff.py` expects an input JSON object:

```json
{
  "analysis_type": "strategy_json_generator",
  "now_utc": "2026-03-16T10:45:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion"
  },
  "strategy_revision": {
    "strategy_id": "strategy.optimus-prime-gsd-fusion",
    "revision": "2026-03-16T10:45:00Z",
    "generated_by": "req-049-strategy-json-generator",
    "source_requirement_ids": [
      "REQ-038",
      "REQ-041",
      "REQ-046"
    ],
    "evidence_refs": [
      "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json"
    ]
  },
  "recommendations": [
    {
      "recommendation_id": "rec.align-earth-runtime-canary",
      "rationale": "Why the recommendation is retained in strategy output.",
      "impacts": [
        "Impact statement"
      ],
      "risk_ids": [
        "risk.cross-project-rollout-drift"
      ],
      "evidence_refs": [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
      ]
    }
  ],
  "risks": [
    {
      "risk_id": "risk.cross-project-rollout-drift",
      "summary": "Risk summary",
      "severity": "high",
      "mitigation": "Mitigation statement",
      "evidence_refs": [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
      ]
    }
  ]
}
```

Rules:
- `analysis_type` must be `strategy_json_generator`.
- `target_project.project_id` must be non-empty.
- `target_project.project_root` must normalize to an absolute path.
- `strategy_revision.source_requirement_ids[]` must be non-empty and unique.
- `recommendations[]` must be non-empty, with unique `recommendation_id`.
- Every recommendation row must include:
  - `recommendation_id`
  - `rationale`
  - `impacts[]`
  - `risk_ids[]`
  - `evidence_refs[]`
- `risks[]` must be non-empty, with unique `risk_id`.
- Every `recommendations[].risk_ids[]` entry must resolve to a defined `risks[].risk_id`.
- `risks[].severity` must be one of `high`, `medium`, `low`.

## Output contract
REQ-049 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `artifact_kind`, `generated_at_utc`
- project anchor: `target_project`
- machine artifact surface: `strategy_json`
- bounded counts: `totals`

`strategy_json` contains:
- `artifact_path`
- `strategy_id`
- `revision`
- `generated_by`
- `source_requirement_ids[]`
- `recommendations[]`
- `risks[]`
- `evidence_refs[]`

Each `strategy_json.recommendations[]` row includes:
- `recommendation_id`
- `rationale`
- `impacts[]`
- `risk_ids[]`
- `evidence_refs[]`

Each `strategy_json.risks[]` row includes:
- `risk_id`
- `summary`
- `severity`
- `mitigation`
- `evidence_refs[]`

`totals` includes:
- `recommendations`
- `risks`
- `impacts`
- `evidence_refs`

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/strategy-json-generator.json`
- Contract tests: `tests/contracts/test_strategy-json-generator.py`
- Output sample: `strategy/current/samples/REQ-049_strategy-json-generator.sample.json`

The structure in `strategy/current/samples/REQ-049_strategy-json-generator.sample.json`
is the canonical contract shape for REQ-049 and documents:
- `strategy_json.recommendations`
- `strategy_json.recommendations[].recommendation_id`
- `strategy_json.recommendations[].rationale`
- `strategy_json.recommendations[].impacts`
- `strategy_json.recommendations[].risk_ids`
- `strategy_json.recommendations[].evidence_refs`
- `strategy_json.risks`
- `strategy_json.evidence_refs`
- `totals`
