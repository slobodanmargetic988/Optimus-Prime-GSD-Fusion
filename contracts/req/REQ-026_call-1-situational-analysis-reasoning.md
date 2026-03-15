# REQ-026: Call-1 Situational Analysis Reasoning

Status: Implemented  
Requirement ID: `REQ-026`

## Scope anchors

This requirement is limited to the Call-1 assessment surface that:

- ingests authoritative target-project mission and scope,
- ingests bounded planning evidence and runtime evidence,
- produces a situational assessment of current project state, and
- emits explicit unknowns that later calls must resolve.

Out of scope:

- new managers,
- new gates,
- new packet sections unrelated to Call-1 assessment,
- later-call resolution behavior beyond explicit unknown handoff.

## Interface surface

Implementation file:

- `scripts/strategy_llm_pipeline.py`

Builder:

- `build_req_026_call_1_situational_analysis_reasoning(...) -> dict`

Validator:

- `validate_req_026_call_1_situational_analysis_reasoning(payload) -> list[str]`

CLI:

```bash
python3 scripts/strategy_llm_pipeline.py \
  --input-json examples/fixtures/call-1-situational-analysis-reasoning.json \
  --output-json strategy/current/samples/REQ-026_call-1-situational-analysis-reasoning.sample.json \
  --json-pretty
```

## Input contract

Accepted builder input shape:

```json
{
  "analysis_type": "call_1_situational_analysis_reasoning",
  "call_id": "call-1",
  "checked_at_utc": "2026-03-16T09:30:00Z",
  "target_project": {
    "project_id": "optimus-prime-gsd-fusion",
    "mission": {
      "text": "Keep autonomous delivery loops deterministic and observable.",
      "source": "mission.md"
    },
    "scope": {
      "text": "Focus this wave on contract surfaces, execution evidence, and bounded follow-up.",
      "source": "scope.md"
    }
  },
  "planning_evidence": {
    "artifacts": [
      {
        "artifact_id": "PLAN-001",
        "summary": "Planner packet exists and covers contract work.",
        "status": "ready",
        "source_ref": "reports/optimus-prime/planning/PLAN_PACKETS.json",
        "signals": [
          "Planner packet exceeds the planning gate.",
          "Contract work is explicitly represented."
        ],
        "unknowns": [
          {
            "question": "Has packet drift been reconciled against the current task state?",
            "why_it_matters": "Call-2 needs a stable implementation target before expanding execution actions."
          }
        ]
      }
    ]
  },
  "runtime_evidence": {
    "artifacts": [
      {
        "artifact_id": "RUN-001",
        "summary": "Latest canary run completed with degraded recovery behavior.",
        "status": "degraded",
        "source_ref": "reports/optimus-prime/planning/VERIFICATION.md",
        "signals": [
          "Primary canary completed.",
          "Fallback recovery still needs tuning."
        ],
        "unknowns": [
          {
            "question": "Is the observed degraded runtime behavior still present on the current branch head?",
            "why_it_matters": "Call-2 must know whether follow-up work targets an active runtime issue or stale evidence."
          }
        ]
      }
    ]
  }
}
```

Rules:

- `analysis_type` must be `call_1_situational_analysis_reasoning`.
- `call_id` must be `call-1`.
- `target_project.project_id` is required.
- `target_project.mission` and `target_project.scope` are required authoritative anchors.
- Each mission/scope anchor may be a non-empty string or an object with non-empty `text` and optional `source`.
- `planning_evidence.artifacts[]` must contain at least one artifact with:
  - `artifact_id`
  - `summary`
  - `status` in `ready | partial | blocked`
  - `source_ref`
  - non-empty `signals[]`
- `runtime_evidence.artifacts[]` must contain at least one artifact with:
  - `artifact_id`
  - `summary`
  - `status` in `healthy | degraded | blocked`
  - `source_ref`
  - non-empty `signals[]`
- Artifact `unknowns[]` may contain:
  - non-empty question strings, or
  - objects with `question` and `why_it_matters`.
- Call-1 output must include at least one explicit unknown for later calls.

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
- `situational_analysis`
- `unknowns`
- `source`

`situational_analysis` required sections:

- `target_project`
  - `project_id`
  - `mission.text`
  - `mission.source`
  - `mission.authoritative`
  - `scope.text`
  - `scope.source`
  - `scope.authoritative`
  - `anchor_summary`
- `planning_state`
  - `status`
  - `artifact_ids[]`
  - `evidence_refs[]`
  - `key_signals[]`
- `runtime_state`
  - `status`
  - `artifact_ids[]`
  - `evidence_refs[]`
  - `key_signals[]`
- `reasoning`
  - `assessment_status` in `grounded | needs-follow-up | blocked`
  - `anchor_set`
  - `state_summary`
  - `evidence_basis[]`
  - `follow_up_required`

`unknowns[]` row shape:

```json
{
  "unknown_id": "unknown.001",
  "category": "planning",
  "question": "Has packet drift been reconciled against the current task state?",
  "why_it_matters": "Call-2 needs a stable implementation target before expanding execution actions.",
  "must_be_resolved_by": "call-2",
  "provenance": {
    "evidence_type": "planning",
    "artifact_id": "PLAN-002",
    "source_ref": "reports/optimus-prime/planning/TASK_EXECUTION_STATE.json"
  }
}
```

Normalization rules:

- `planning_state.status` is:
  - `blocked` if any planning artifact is `blocked`,
  - else `partial` if any planning artifact is `partial`,
  - else `ready`.
- `runtime_state.status` is:
  - `blocked` if any runtime artifact is `blocked`,
  - else `degraded` if any runtime artifact is `degraded`,
  - else `healthy`.
- `reasoning.assessment_status` is:
  - `blocked` if planning or runtime state is blocked,
  - else `needs-follow-up` if planning is partial or runtime is degraded,
  - else `grounded`.
- `reasoning.anchor_set` is fixed to:
  - `mission`
  - `scope`
  - `planning_evidence`
  - `runtime_evidence`
- `unknowns[].must_be_resolved_by` is fixed to `call-2`.

## Sample structure

Deterministic fixture:

- `examples/fixtures/call-1-situational-analysis-reasoning.json`

Deterministic sample artifact:

- `strategy/current/samples/REQ-026_call-1-situational-analysis-reasoning.sample.json`

The canonical sample structure in `strategy/current/samples/REQ-026_call-1-situational-analysis-reasoning.sample.json`
contains:

- top-level REQ-026 metadata,
- `situational_analysis.target_project` with authoritative mission/scope anchors,
- `situational_analysis.planning_state` and `situational_analysis.runtime_state`,
- `situational_analysis.reasoning` with bounded Call-1 assessment output,
- `unknowns[]` with explicit later-call follow-up requirements,
- `source` counts for measurable contract verification.
