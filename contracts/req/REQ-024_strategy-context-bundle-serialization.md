# REQ-024: Strategy Context Bundle Serialization

Requirement ID: `REQ-024`

## Purpose
Serialize strategy context into a versioned machine-readable bundle consumed by downstream LLM call chain stages.

## Scope Lock
- In scope: deterministic strategy context bundle serialization and validation for downstream LLM call chain ingestion.
- Out of scope: introducing new managers, packet sections, or gates outside REQ-024.

## Input Contract
`strategy_context_sweep.py` accepts REQ-024 builder input via `--input-json` with:

```json
{
  "analysis_type": "strategy_context_bundle_serialization",
  "strategy_context": {
    "<strategy-context-fields>": "<JSON-compatible values>"
  },
  "llm_call_chain": {
    "chain_id": "string",
    "stages": [
      {
        "stage_id": "string",
        "purpose": "string",
        "model": "string",
        "prompt_artifact_ref": "string",
        "required_context_keys": ["string"]
      }
    ]
  },
  "bundle_generated_at_utc": "ISO-8601 UTC timestamp (optional)"
}
```

Notes:
- `strategy_context` must be a non-empty JSON object and JSON-serializable.
- `llm_call_chain.stages` are normalized into deterministic order by `stage_id` and stage metadata.
- `required_context_keys` are normalized as sorted unique strings.
- If `bundle_generated_at_utc` is omitted, builder fallback is `1970-01-01T00:00:00Z`.

## Output Contract
REQ-024 output shape:

- `schema_version` = `req-024.strategy-context-bundle-serialization.v1`
- `requirement_id` = `REQ-024`
- `strategy_context_bundle_serialization`
  - `bundle_schema_version` = `strategy-context-bundle.v1`
  - `serialization_format` = `json-canonical-v1`
  - `bundle_generated_at_utc`
  - `llm_call_chain`
    - `chain_id`
    - `stages[]`
      - `stage_id`
      - `purpose`
      - `model`
      - `prompt_artifact_ref`
      - `required_context_keys[]`
  - `context_bundle_sha256`
  - `context_bundle_byte_length`
  - `serialized_context_bundle`
- `source`
  - `tool`
  - `tool_version`
- `call_metadata`
  - deterministic canonical-input digest fields

## Determinism And Validator Ingestion
- Serialized context bundle is canonical JSON (`sort_keys`, compact separators) to support replay diffing.
- `context_bundle_sha256` and `context_bundle_byte_length` must match serialized payload bytes.
- Validator replays the payload from `call_metadata.canonical_input` and requires byte-for-byte payload equality.

## Sample Structure
Output sample:
- `strategy/current/samples/REQ-024_strategy-context-bundle-serialization.sample.json`

That sample file is the documented structure baseline for REQ-024 contract validation.
