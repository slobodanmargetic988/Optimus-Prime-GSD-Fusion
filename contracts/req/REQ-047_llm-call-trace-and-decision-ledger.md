# REQ-047: LLM Call Trace And Decision Ledger

## Purpose
Define the contract and data-model surface that records call-level LLM trace metadata plus a decision ledger linked to final output artifacts for auditability and replay analysis.

## Scope anchors
- Surface in scope: `scripts/strategy_llm_pipeline.py`.
- In scope (REQ-047):
  - Normalize machine-readable `llm_call_trace_rows`.
  - Record deterministic `decision_ledger` entries that reference trace rows.
  - Link each trace row and each decision to declared `final_output_artifacts`.
  - Emit a deterministic `traceability_index` for replay analysis.
- Out of scope (REQ-047): net-new packet sections, managers, gates, or orchestration behavior outside this contract surface.

## Interface surface
Builder:
- `build_req_047_llm_call_trace_and_decision_ledger(payload) -> dict`

Validator:
- `validate_req_047_llm_call_trace_and_decision_ledger(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_llm_pipeline.py --input-json <path|->`

## Input contract
`strategy_llm_pipeline.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "llm_call_trace_and_decision_ledger",
  "now_utc": "2026-03-16T12:00:00Z",
  "llm_call_trace_rows": [
    {
      "checked_at_utc": "2026-03-16T12:00:00Z",
      "requirement_id": "REQ-035",
      "analysis_type": "evidence_citation_discipline_in_reasoning_calls",
      "call_id": "call-2",
      "call_objective": "Human-facing call objective",
      "target_project_id": "optimus-prime",
      "peer_project_ids": ["apollo"],
      "input_refs": ["reports/.../TASK_EVIDENCE.json"],
      "output_refs": ["reports/optimus-prime/final/strategy-packet.json"],
      "artifacts": [
        {
          "kind": "output_snapshot",
          "path": "strategy/current/llm_call_trace_artifacts/req-035/call-2/output.normalized.json",
          "sha256": "lowercase64hex"
        }
      ],
      "handoff_summary": "Human-facing handoff summary",
      "totals": {
        "strategic_claims": 3
      }
    }
  ],
  "final_output_artifacts": [
    {
      "artifact_ref": "reports/optimus-prime/final/strategy-packet.json",
      "artifact_role": "final_strategy_packet",
      "sha256": "lowercase64hex"
    }
  ],
  "decision_ledger": [
    {
      "decision_id": "dec.emit-final-strategy-packet",
      "decision_type": "emit",
      "summary": "Human-facing decision summary",
      "rationale": "Why the artifact is emitted or held.",
      "source_call_refs": ["REQ-035::call::call-2"],
      "final_output_artifact_refs": ["reports/optimus-prime/final/strategy-packet.json"],
      "evidence_refs": ["reports/.../TASK_EVIDENCE.json"]
    }
  ]
}
```

Rules:
- `analysis_type` must be `llm_call_trace_and_decision_ledger`.
- `llm_call_trace_rows[]`, `final_output_artifacts[]`, and `decision_ledger[]` are required and non-empty.
- Each trace row is strict and normalized to `optimus-prime.llm-call-trace.v1`.
- Each trace row derives a deterministic `call_ref` as `REQ-<id>::call::<call_id>`.
- `decision_ledger[].source_call_refs[]` must reference declared trace-row `call_ref` values.
- `decision_ledger[].final_output_artifact_refs[]` must reference declared `final_output_artifacts[].artifact_ref` values.
- Every trace row must link to at least one final output artifact through the decision ledger.
- Every final output artifact must appear in at least one decision-ledger entry.
- The builder is strict: unexpected keys are rejected to keep scope bounded to REQ-047 anchors.

## Output contract
REQ-047 output payload contains:
- metadata: `ok`, `schema_version`, `requirement_id`, `analysis_type`, `call_id`, `checked_at_utc`
- normalized trace rows: `llm_call_trace_rows[]`
- normalized final output artifact index: `final_output_artifacts[]`
- ledger surface: `llm_call_trace_and_decision_ledger`
- bounded totals: `totals`

Each normalized `llm_call_trace_rows[]` entry includes:
- `call_ref`
- `linked_final_output_artifact_refs[]`
- the original trace metadata anchors needed for replay analysis

`llm_call_trace_and_decision_ledger` contains:
- `call_objective`
- `decision_ledger[]`
- `traceability_index[]`

`traceability_index[]` is deterministic and contains:
- `final_output_artifact_ref`
- `artifact_role`
- `decision_ids[]`
- `source_call_refs[]`

## Deterministic fixtures and samples
- Input fixture: `examples/fixtures/llm-call-trace-and-decision-ledger.json`
- Contract tests: `tests/contracts/test_llm-call-trace-and-decision-ledger.py`
- Output sample: `strategy/current/samples/REQ-047_llm-call-trace-and-decision-ledger.sample.json`

The structure in `strategy/current/samples/REQ-047_llm-call-trace-and-decision-ledger.sample.json`
is the canonical contract shape for REQ-047.
