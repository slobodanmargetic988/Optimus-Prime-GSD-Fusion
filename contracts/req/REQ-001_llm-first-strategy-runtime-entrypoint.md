# REQ-001 LLM-first Strategy Runtime Entrypoint

Status: Implemented  
Requirement ID: `REQ-001`

## Scope anchors

This contract is limited to:

- LLM-first strategy runtime mode.
- Long-thinking execution mode (not deterministic-only heuristic summarization).
- Invocation anchors:
  - `target_project_root`
  - `earth_root`
  - `output_root`
  - `revision_identity`
- Reproducible call metadata derived from canonical invocation input.

## Entrypoint surface

Implementation file: `scripts/strategy_context_sweep.py`

Builder function:

- `build_req_001_runtime_entrypoint(...) -> dict`

Validator function:

- `validate_req_001_runtime_entrypoint(payload) -> list[str]`

CLI:

```bash
python3 scripts/strategy_context_sweep.py \
  --target-project-root /workspace/projects/optimus-prime \
  --earth-root /workspace/projects/Earth \
  --output-root /workspace/projects/optimus-prime/strategy/current/out \
  --revision-identity f29cfceb25e813f9bf6eb745c3b14ecbd35f0515 \
  --output-path strategy/current/samples/REQ-001_llm-first-strategy-runtime-entrypoint.sample.json
```

## Payload contract

Top-level required keys:

- `schema_version` (must equal `req-001.llm-first-strategy-runtime-entrypoint.v1`)
- `requirement_id` (must equal `REQ-001`)
- `strategy_runtime_entrypoint` (object)
- `call_metadata` (object)

`strategy_runtime_entrypoint` required keys:

- `runtime_mode` (must equal `llm-first`)
- `execution_mode` (must equal `long-thinking`)
- `target_project_root` (absolute path)
- `earth_root` (absolute path)
- `output_root` (absolute path)
- `revision_identity` (non-empty string)

`call_metadata` required keys:

- `reproducibility` (must equal `deterministic-input-fingerprint`)
- `canonical_input_sha256` (sha256 over canonical invocation input)
- `reproducible_call_id` (must equal `req001-` + first 16 chars of digest)
- `canonical_input` (normalized invocation anchors + fixed mode fields)

## Sample structure

Sample artifact path:

- `strategy/current/samples/REQ-001_llm-first-strategy-runtime-entrypoint.sample.json`

Sample fixture path:

- `examples/fixtures/llm-first-strategy-runtime-entrypoint.json`

Sample JSON shape:

```json
{
  "schema_version": "req-001.llm-first-strategy-runtime-entrypoint.v1",
  "requirement_id": "REQ-001",
  "strategy_runtime_entrypoint": {
    "runtime_mode": "llm-first",
    "execution_mode": "long-thinking",
    "target_project_root": "/abs/path/to/project",
    "earth_root": "/abs/path/to/Earth",
    "output_root": "/abs/path/to/output",
    "revision_identity": "git-or-runtime-revision-id"
  },
  "call_metadata": {
    "reproducibility": "deterministic-input-fingerprint",
    "canonical_input_sha256": "sha256hex",
    "reproducible_call_id": "req001-0123456789abcdef",
    "canonical_input": {
      "earth_root": "/abs/path/to/Earth",
      "execution_mode": "long-thinking",
      "output_root": "/abs/path/to/output",
      "revision_identity": "git-or-runtime-revision-id",
      "runtime_mode": "llm-first",
      "target_project_root": "/abs/path/to/project"
    }
  }
}
```
