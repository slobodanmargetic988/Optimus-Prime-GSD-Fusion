# REQ-023: Context Compaction for LLM Call Budget

## Purpose
Define the contract and data-model surface for compacting broad-sweep strategy context into bounded, high-signal packets for multi-call reasoning without dropping hard constraints or mandatory traceability pointers.

## Scope Anchors
- Surface in scope: `scripts/strategy_context_sweep.py`
- Contract fixture in scope: `examples/fixtures/context-compaction-for-llm-call-budget.json`
- Contract tests in scope: `tests/contracts/test_context-compaction-for-llm-call-budget.py`
- Output sample in scope: `strategy/current/samples/REQ-023_context-compaction-for-llm-call-budget.sample.json`
- Out of scope: new managers, new gates, or packet sections unrelated to compaction, hard-constraint preservation, or traceability coverage

## Input Contract
REQ-023 extends the existing broad-sweep context payload with two optional fields:

```json
{
  "hard_constraints": [
    {
      "constraint_id": "preserve-traceability-pointers",
      "statement": "Preserve evidence refs needed to trace each compacted packet back to the original sweep.",
      "evidence_refs": [
        "reports/optimus-prime/planning/evidence/TASK-072/TASK_EVIDENCE.json"
      ]
    }
  ],
  "llm_call_budget": {
    "max_context_packets": 3,
    "max_focus_points_per_packet": 2,
    "max_evidence_refs_per_packet": 3
  }
}
```

Rules:
- `hard_constraints` is optional; when present it must be a list of objects with unique `constraint_id`, non-empty `statement`, and normalized `evidence_refs`.
- `llm_call_budget` is optional; defaults are:
  - `max_context_packets = 3`
  - `max_focus_points_per_packet = 2`
  - `max_evidence_refs_per_packet = 3`
- All broad-sweep inputs already accepted by `scripts/strategy_context_sweep.py` remain valid compaction sources.

## Output Contract
The builder emits a top-level `context_compaction_for_llm_call_budget` surface plus `processing_behavior.context_compaction`:

```json
{
  "processing_behavior": {
    "context_compaction": {
      "compaction_strategy": "high-signal-packets-for-multi-call-reasoning",
      "llm_call_budget": {
        "max_context_packets": 3,
        "max_focus_points_per_packet": 2,
        "max_evidence_refs_per_packet": 3
      },
      "mandatory_traceability_refs": [
        "reports/earth/sweeps/2026-03-15/portfolio.json"
      ],
      "hard_constraints": [
        {
          "constraint_id": "preserve-traceability-pointers",
          "statement": "Preserve evidence refs needed to trace each compacted packet back to the original sweep.",
          "evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-072/TASK_EVIDENCE.json"
          ]
        }
      ],
      "compacted_packets": [
        {
          "packet_id": "packet-01",
          "packet_kind": "risk",
          "summary": "Resolve open risks before broad replay expansion.",
          "focus_points": [
            "Earth sweep source artifact is stale"
          ],
          "project_ids": [],
          "source_action_ids": [],
          "source_obligation_ids": [],
          "source_risk_ids": [
            "risk-earth-source-7fdf112ec591"
          ],
          "hard_constraint_ids": [
            "preserve-traceability-pointers"
          ],
          "traceability_refs": [
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"
          ],
          "evidence_focus_refs": [
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"
          ],
          "next_steps": [
            "Resolve risk-earth-source-7fdf112ec591 and refresh required evidence refs."
          ]
        }
      ],
      "coverage": {
        "recommended_action_ids": [
          "compact-context-traceability"
        ],
        "covered_action_ids": [
          "compact-context-traceability"
        ],
        "uncovered_action_ids": [],
        "cross_project_obligation_ids": [
          "obligation-compact-context-traceability"
        ],
        "covered_obligation_ids": [
          "obligation-compact-context-traceability"
        ],
        "uncovered_obligation_ids": [],
        "open_risk_ids": [
          "risk-earth-source-7fdf112ec591"
        ],
        "covered_risk_ids": [
          "risk-earth-source-7fdf112ec591"
        ],
        "uncovered_risk_ids": [],
        "hard_constraint_ids": [
          "preserve-traceability-pointers"
        ],
        "covered_hard_constraint_ids": [
          "preserve-traceability-pointers"
        ],
        "uncovered_hard_constraint_ids": []
      }
    }
  }
}
```

Behavior:
- `mandatory_traceability_refs` preserves the full traceability pointer set needed to replay packet provenance.
- Every packet carries `hard_constraint_ids`, so hard constraints stay visible even when source groups are merged to fit the call budget.
- `evidence_focus_refs` is budget-bounded for prompt packing; `traceability_refs` remains the non-lossy provenance surface.
- `coverage.uncovered_*` lists must remain empty for valid REQ-023 output.

## Deterministic Fixtures and Samples
- Input fixture: `examples/fixtures/context-compaction-for-llm-call-budget.json`
- Output sample: `strategy/current/samples/REQ-023_context-compaction-for-llm-call-budget.sample.json`

`strategy/current/samples/REQ-023_context-compaction-for-llm-call-budget.sample.json` is the reference structure for REQ-023 output shape and documents the exact `processing_behavior.context_compaction` packet surface.
