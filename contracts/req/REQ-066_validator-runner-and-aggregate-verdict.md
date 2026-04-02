# REQ-066: Validator Runner And Aggregate Verdict

## Purpose
Define the contract and data-model surface for a validator runner that executes all registered validators and emits one aggregate verdict artifact with per-validator pass/fail status and blocking reason codes.

## Scope anchors
- Surface in scope: `scripts/strategy_artifacts_handoff.py`.
- In scope (REQ-066):
  - Execute every validator registered by the strategy handoff surface.
  - Emit one aggregate verdict artifact.
  - Preserve per-validator pass/fail status and blocking reason codes.
- Out of scope (REQ-066): net-new packet sections, managers, orchestration flows, or gates outside the registered validator runner surface.

## Interface surface
Builder:
- `build_req_066_validator_runner_and_aggregate_verdict(payload) -> dict`

Validator:
- `validate_req_066_validator_runner_and_aggregate_verdict(payload) -> list[str]`

CLI:
- `python3 scripts/strategy_artifacts_handoff.py --input-json <path|->`

## Input contract
`strategy_artifacts_handoff.py` expects an input JSON object with these anchors:

```json
{
  "analysis_type": "validator_runner_and_aggregate_verdict",
  "now_utc": "2026-03-16T11:00:00Z",
  "strategy_packet_path": "op-tools/strategy/examples/strategy_packet.sample.v1.json",
  "schema_path": "contracts/strategy_packet.v1.schema.json"
}
```

Rules:
- `analysis_type` must be `validator_runner_and_aggregate_verdict`.
- `now_utc` must be a non-empty UTC timestamp string; it is copied into `checked_at_utc`.
- The runner forwards validator-specific input anchors to every registered validator.
- The current registry executes:
  - `REQ-060`
  - `strategy_packet_v1_schema_validator`
- REQ-060 input rules remain in force for forwarded packet/schema fields:
  - provide exactly one of `strategy_packet` or `strategy_packet_path`
  - provide at most one of `schema` or `schema_path`
  - when `schema_path` is omitted, the default schema path is `contracts/strategy_packet.v1.schema.json`

## Output contract
REQ-066 output payload contains:
- `requirement_id`
- `analysis_type`
- `checked_at_utc`
- `ok`
- `verdict`
- `blocking_reason_codes`
- `validator_count`
- `passed_validator_count`
- `failed_validator_count`
- `summary`
- `validators`

Output behavior:
- `requirement_id` is `REQ-066`.
- `analysis_type` is `validator_runner_and_aggregate_verdict`.
- `ok = true` means all validators passed.
- `ok = false` means at least one validator returned a blocking failure.
- `verdict` is `pass` or `fail`.
- `blocking_reason_codes[]` is the sorted unique union of failing validator reason codes.
- `validator_count` must equal `len(validators)`.
- `passed_validator_count + failed_validator_count` must equal `validator_count`.

Each `validators[]` row includes:
- `validator_id`
- `requirement_id`
- `analysis_type`
- `ok`
- `verdict`
- `blocking_reason_codes`
- `diagnostic_count`
- `summary`

Per-validator behavior:
- `validator_id` identifies the validator execution row; current canonical value is `strategy_packet_v1_schema_validator`.
- Passing validators emit:
  - `ok = true`
  - `verdict = pass`
  - `blocking_reason_codes = []`
  - `diagnostic_count = 0`
- Failing validators emit:
  - `ok = false`
  - `verdict = fail`
  - non-empty `blocking_reason_codes[]`
  - positive `diagnostic_count`

Aggregate verdict behavior:
- When all validators pass:
  - `verdict = pass`
  - `failed_validator_count = 0`
  - `blocking_reason_codes = []`
- When any validator fails:
  - `verdict = fail`
  - `failed_validator_count >= 1`
  - `blocking_reason_codes[]` preserves blocking reason codes such as `schema_pattern_mismatch`

## Sample structure
Deterministic fixture:
- `examples/fixtures/validator-runner-and-aggregate-verdict.json`

Deterministic sample artifact:
- `strategy/current/samples/REQ-066_validator-runner-and-aggregate-verdict.sample.json`

The structure in `strategy/current/samples/REQ-066_validator-runner-and-aggregate-verdict.sample.json`
is the canonical contract shape for REQ-066, including:
- `blocking_reason_codes`
- `validator_count`
- `passed_validator_count`
- `failed_validator_count`
- `validators`
- `validators[].validator_id`
- `validators[].blocking_reason_codes`
