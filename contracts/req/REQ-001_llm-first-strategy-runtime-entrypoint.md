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
- Broad-sweep context inputs:
  - `target_project_evidence_refs`
  - `earth_sweep_evidence_refs`
  - `cross_project_context`
  - `candidate_recommendations`
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
  --context-input-path strategy/current/samples/REQ-001_llm-first-context-input.sample.json \
  --output-path strategy/current/samples/REQ-001_llm-first-strategy-runtime-entrypoint.sample.json
```

## Payload contract

Top-level required keys:

- `schema_version` (must equal `req-001.llm-first-strategy-runtime-entrypoint.v1`)
- `requirement_id` (must equal `REQ-001`)
- `strategy_runtime_entrypoint` (object)
- `processing_behavior` (object)
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
- `processing_input_sha256` (sha256 over canonical processing input)
- `processing_call_id` (must equal `req001-processing-` + first 16 chars of digest)
- `canonical_processing_input` (normalized broad-sweep context input)

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
  "processing_behavior": {
    "strategy": "llm-first-broad-sweep",
    "reasoning_mode": "long-thinking",
    "heuristic_summarization_only": false,
    "context_inputs": {
      "target_project": {"project_root": "/abs/path/to/project", "evidence_refs": []},
      "earth_sweep": {"earth_root": "/abs/path/to/Earth", "evidence_refs": []},
      "cross_project_context": [],
      "candidate_recommendations": []
    },
    "context_usage": {
      "target_project_context_used": false,
      "earth_sweep_context_used": false,
      "cross_project_context_used": false,
      "target_project_refs_used": [],
      "earth_sweep_refs_used": [],
      "cross_project_refs_used": [],
      "cross_project_projects_considered": [],
      "evidence_refs_used": []
    },
    "recommendation": {
      "decision": "insufficient-context",
      "rationale": "No actionable evidence-backed strategy actions were found in the provided context sweep.",
      "confidence": "low",
      "evidence_refs": [],
      "recommended_actions": [],
      "cross_project_obligations": [],
      "open_risks": []
    }
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
    },
    "processing_input_sha256": "sha256hex",
    "processing_call_id": "req001-processing-0123456789abcdef",
    "canonical_processing_input": {
      "target_project_evidence_refs": [],
      "earth_sweep_evidence_refs": [],
      "cross_project_context": [],
      "candidate_recommendations": []
    }
  }
}
```
