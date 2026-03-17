# REQ-034: Cross-Call Memory Handoff Contract

Status: Implemented  
Requirement ID: `REQ-034`

## Scope anchors

This requirement is limited to the cross-call memory handoff surface that:

- carries structured memory forward from prior calls,
- keeps the context window bounded by explicit entry and citation budgets,
- requires every retained memory item to keep citation refs, and
- prevents contradiction drift and context leakage before memory reaches the current call.

Out of scope:

- new managers, gates, or orchestration packets,
- uncited long-horizon memory persistence outside the current call chain, and
- any net-new section unrelated to bounded cross-call memory handoff.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_034_cross_call_memory_handoff_contract(...) -> dict`

Validator:

- `validate_req_034_cross_call_memory_handoff_contract(payload) -> list[str]`

CLI:

```bash
python3 scripts/strategy_llm_pipeline.py \
  --input-json examples/fixtures/cross-call-memory-handoff-contract.json \
  --output-json strategy/current/samples/REQ-034_cross-call-memory-handoff-contract.sample.json \
  --json-pretty
```

Documented sample structure:

- `strategy/current/samples/REQ-034_cross-call-memory-handoff-contract.sample.json`

## Input contract

Accepted builder input shape:

```json
{
  "analysis_type": "cross_call_memory_handoff_contract",
  "call_id": "call-4",
  "checked_at_utc": "2026-03-16T16:00:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion"
  },
  "current_call": {
    "call_id": "call-4",
    "objective": "Carry bounded cited memory from earlier calls into the current reasoning pass without contradiction drift or context leakage."
  },
  "call_chain": [
    {
      "sequence": 1,
      "call_id": "call-1",
      "phase": "analysis",
      "output_ref": "REQ-026::call::call-1::output::situational_analysis"
    },
    {
      "sequence": 4,
      "call_id": "call-4",
      "phase": "handoff",
      "output_ref": "REQ-034::call::call-4::output::cross_call_memory_handoff"
    }
  ],
  "allowed_context_refs": [
    "reports/optimus-prime/planning/STATE.json",
    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
    "scope.md"
  ],
  "memory_budget": {
    "max_entries": 3,
    "max_citation_refs_per_entry": 2
  },
  "prior_call_memory": [
    {
      "call_id": "call-2",
      "output_ref": "REQ-027::call::call-2::output::constraint_refinement",
      "summary": "Call-2 narrowed which facts must survive into later reasoning.",
      "handoff_items": [
        {
          "memory_id": "mem.scope-lock.v1",
          "memory_key": "scope-lock",
          "kind": "decision",
          "summary": "Keep implementation limited to the REQ-034 contract surface.",
          "position": "req-034-only",
          "carry_forward": true,
          "supersedes_memory_ids": [],
          "citation_refs": [
            "REQ-027::call::call-2::output::constraint_refinement",
            "scope.md"
          ]
        }
      ]
    }
  ]
}
```

Rules:

- `analysis_type` must be `cross_call_memory_handoff_contract`.
- `call_id`, when supplied, must match `current_call.call_id`.
- `target_project.project_id` is required.
- `current_call.call_id` and `current_call.objective` are required.
- `call_chain[]` must contain at least one prior call plus the current call, with contiguous `sequence` values, and the last row must be the current call.
- `allowed_context_refs[]` must be non-empty.
- `memory_budget.max_entries` and `memory_budget.max_citation_refs_per_entry` must be positive integers.
- `prior_call_memory[]` must include exactly one row for each prior call in `call_chain[]`.
- `prior_call_memory[].output_ref` must match the corresponding `call_chain[]` row.
- Every `handoff_items[]` row must include:
  - `memory_id`
  - `memory_key`
  - `kind` in `constraint | decision | fact | risk`
  - `summary`
  - `position`
  - boolean `carry_forward`
  - `supersedes_memory_ids[]`
  - non-empty `citation_refs[]`
- `citation_refs[]` must stay inside the bounded context set formed by `allowed_context_refs[]` plus the call-chain `output_ref` values.
- Later memory on the same `memory_key` may replace earlier memory. If the `position` changes, the later row must explicitly supersede the earlier `memory_id`; otherwise the builder blocks contradiction drift.

## Output contract

Top-level required keys:

- `ok`
- `tool`
- `tool_version`
- `schema_version`
- `requirement_id`
- `analysis_type`
- `call_id`
- `checked_at_utc`
- `cross_call_memory_handoff`
- `processing_behavior`
- `source`

`cross_call_memory_handoff` required sections:

- `target_project.project_id`
- `current_call.call_id`
- `current_call.objective`
- `source_calls[]`
- `handoff_items[]`
- `bounded_context`
- `summary`

`handoff_items[]` row shape:

```json
{
  "memory_id": "mem.scope-lock.v1",
  "memory_key": "scope-lock",
  "kind": "decision",
  "summary": "Keep implementation limited to the REQ-034 contract and data-model surface.",
  "position": "req-034-only",
  "source_call_id": "call-2",
  "source_output_ref": "REQ-027::call::call-2::output::constraint_refinement",
  "source_call_sequence": 2,
  "carry_forward": true,
  "supersedes_memory_ids": [],
  "citation_refs": [
    "REQ-027::call::call-2::output::constraint_refinement",
    "scope.md"
  ]
}
```

Normalization rules:

- Output `call_id` must equal `cross_call_memory_handoff.current_call.call_id`.
- Only bounded, cited, retained memory items are emitted.
- `citation_refs[]` is trimmed to `bounded_context.max_citation_refs_per_entry`.
- `handoff_items[]` must stay within `bounded_context.max_entries`.
- Later memory may replace earlier memory with the same `memory_key`.
- Later contradictory memory without explicit supersession is blocked and recorded as an open risk.
- Memory that cites refs outside the bounded context window is blocked and recorded as an open risk.

`bounded_context` required keys:

- `max_entries`
- `max_citation_refs_per_entry`
- `source_call_count`
- `input_item_count`
- `retained_item_count`
- `dropped_item_count`
- `dropped_due_to_budget_count`
- `citation_ref_count`
- `citation_refs_truncated_count`

`summary` required keys:

- `source_call_count`
- `input_item_count`
- `retained_item_count`
- `superseded_item_count`
- `open_risk_count`

`processing_behavior` required sections:

- `strategy` = `cross-call-memory-handoff`
- `reasoning_mode` = `deterministic-bounded-memory-handoff`
- `strict_evidence_discipline` = `true`
- `context_inputs`
  - `current_call`
  - `call_chain`
  - `prior_call_memory`
  - `allowed_context_refs`
  - `memory_budget`
- `context_usage`
  - `source_call_ids_used`
  - `source_output_refs_used`
  - `allowed_context_refs_used`
  - `retained_memory_ids`
  - `superseded_memory_ids`
  - `open_risk_ids_emitted`
  - `reason_codes_emitted`
  - `evidence_refs_used`
- `handoff_rules`
  - `required_handoff_fields`
  - `allowed_entry_kinds`
  - `max_entries`
  - `max_citation_refs_per_entry`
  - `contradiction_requires_supersession`
  - `citation_refs_required`
- `diagnostics.open_risks[]`
  - `risk_id`
  - `reason_code`
  - `summary`
  - `memory_id`
  - `memory_key`
  - `source_call_id`
  - `required_citation_refs[]`

## Evidence notes

Executable contract evidence lives in:

- `examples/fixtures/cross-call-memory-handoff-contract.json`
- `tests/contracts/test_cross-call-memory-handoff-contract.py`

The sample payload structure is documented by:

- `strategy/current/samples/REQ-034_cross-call-memory-handoff-contract.sample.json`
