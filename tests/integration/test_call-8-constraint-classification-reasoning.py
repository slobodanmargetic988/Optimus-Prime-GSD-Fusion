import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-8-constraint-classification-reasoning.json"
EARTH_REFS = [
    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
    "reports/earth/sweeps/2026-03-16/shared-observability.json",
]
TASK_111_EVIDENCE_REF = "reports/optimus-prime/planning/evidence/TASK-111/TASK_EVIDENCE.json"
TRACE_SOURCE_REFS = [
    "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json#/call_metadata/llm_call_trace_rows",
    "strategy/current/samples/REQ-028_call-3-gap-and-opportunity-reasoning.sample.json#/processing_behavior/recommendation/recommended_opportunities",
    "strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json#/processing_behavior/recommendation/escalation_triggers",
    "strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json#/processing_behavior/recommendation/fallback_sequence",
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_033_integration_emits_explicit_classification_groups_and_traceable_context() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_033_call_8_constraint_classification_reasoning(**fixture["input"])

    assert module.validate_req_033_call_8_constraint_classification_reasoning(payload) == []

    context_usage = payload["processing_behavior"]["context_usage"]
    assert context_usage["target_project_context_used"] is True
    assert context_usage["earth_sweep_context_used"] is True
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["candidate_ids_considered"] == [
        "constraint.no-new-managers",
        "constraint.trace-citations-required",
        "preference.fallback-aware-ordering",
        "idea.shared-constraint-summary",
    ]
    assert context_usage["classifications_present"] == [
        "hard-constraint",
        "soft-preference",
        "speculative-idea",
    ]
    assert context_usage["cross_project_projects_considered"] == [
        "runtime-orchestrator",
        "shared-observability",
    ]
    assert context_usage["cross_project_refs_used"] == EARTH_REFS
    assert context_usage["evidence_refs_used"] == [*EARTH_REFS, TASK_111_EVIDENCE_REF]

    call_8_reasoning = payload["processing_behavior"]["call_8_reasoning"]
    assert call_8_reasoning["call_sequence"] == module.REQ_033_CALL_SEQUENCE
    assert call_8_reasoning["reasoning_focus"] == module.REQ_033_REASONING_FOCUS
    assert call_8_reasoning["hard_constraint_count"] == 2
    assert call_8_reasoning["soft_preference_count"] == 1
    assert call_8_reasoning["speculative_idea_count"] == 1
    for row in call_8_reasoning["classification_reasoning"]:
        assert row["candidate_id"]
        assert row["summary"]
        assert row["classification_rationale"]
        assert row["planner_implication"]
        assert row["source_output_refs"]
        assert row["evidence_refs"]

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "ready-for-planner"
    assert recommendation["rationale"]
    assert recommendation["confidence"] == "high"
    assert recommendation["evidence_refs"] == [*EARTH_REFS, TASK_111_EVIDENCE_REF]
    assert recommendation["open_risks"] == []

    planner_contract = recommendation["planner_contract"]
    assert planner_contract["classification_is_explicit"] is True
    assert len(planner_contract["hard_constraints"]) == 2
    assert len(planner_contract["soft_preferences"]) == 1
    assert len(planner_contract["speculative_ideas"]) == 1
    for key in ("hard_constraints", "soft_preferences", "speculative_ideas"):
        for row in planner_contract[key]:
            assert row["recommendation_id"].startswith("rec-call-8-")
            assert row["candidate_id"]
            assert row["summary"]
            assert row["planner_implication"]
            assert row["classification_rationale"]
            assert row["source_output_refs"]
            assert row["evidence_refs"]

    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]
    assert payload["call_metadata"]["llm_call_trace_path"] == module.LLM_CALL_TRACE_RELATIVE_PATH
    assert len(trace_rows) == 1
    assert trace_rows[0]["requirement_id"] == module.REQ_033_REQUIREMENT_ID
    assert trace_rows[0]["sequence"] == module.REQ_033_CALL_SEQUENCE
    assert trace_rows[0]["call_objective"] == module.REQ_033_TRACE_CALL_OBJECTIVE
    for ref in [*EARTH_REFS, TASK_111_EVIDENCE_REF, *TRACE_SOURCE_REFS]:
        assert ref in trace_rows[0]["input_refs"]
    assert len(trace_rows[0]["output_refs"]) == 1 + len(module.REQ_033_TRACE_BUCKET_OUTPUTS)
    for expected_output in (module.REQ_033_TRACE_EXPECTED_OUTPUT, *module.REQ_033_TRACE_BUCKET_OUTPUTS):
        assert any(output_ref.endswith(f"::output::{expected_output}") for output_ref in trace_rows[0]["output_refs"])
    assert "hard constraint" in trace_rows[0]["handoff_summary"]
    assert "soft preference" in trace_rows[0]["handoff_summary"]
    assert "speculative idea" in trace_rows[0]["handoff_summary"]
    assert "planner contract reuse" in trace_rows[0]["handoff_summary"]


def test_req_033_mixed_source_output_classification_becomes_open_risk() -> None:
    fixture = _read_json(FIXTURE_PATH)
    mutated_input = copy.deepcopy(fixture["input"])
    shared_source_output_ref = (
        "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json#/call_metadata/llm_call_trace_rows"
    )
    mutated_input["constraint_candidates"][2]["source_output_refs"] = [shared_source_output_ref]

    payload = module.build_req_033_call_8_constraint_classification_reasoning(**mutated_input)

    assert module.validate_req_033_call_8_constraint_classification_reasoning(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "resolve-classification-collision"
    assert recommendation["confidence"] == "low"
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-strategy-current-samples-req-025-multi-call-strategy-pipeline-planner-sample-json-call-metadata-llm-call-trace-rows",
            "summary": "A single source output ref was assigned to multiple classification buckets.",
            "reason_code": "mixed_classification_source_ref",
            "source_output_ref": shared_source_output_ref,
            "candidate_ids": [
                "constraint.trace-citations-required",
                "preference.fallback-aware-ordering",
            ],
            "classifications": [
                "hard-constraint",
                "soft-preference",
            ],
            "required_evidence_refs": [*EARTH_REFS, TASK_111_EVIDENCE_REF],
        }
    ]
    assert recommendation["planner_contract"]["classification_is_explicit"] is True
    assert len(recommendation["planner_contract"]["hard_constraints"]) == 2
    assert len(recommendation["planner_contract"]["soft_preferences"]) == 1
    assert len(recommendation["planner_contract"]["speculative_ideas"]) == 1
    assert payload["processing_behavior"]["context_usage"]["cross_project_context_used"] is True


def test_req_033_trace_rows_are_jsonl_serializable_and_replay_stable() -> None:
    fixture = _read_json(FIXTURE_PATH)

    first_payload = module.build_req_033_call_8_constraint_classification_reasoning(**fixture["input"])
    second_payload = module.build_req_033_call_8_constraint_classification_reasoning(**fixture["input"])

    first_rows = first_payload["call_metadata"]["llm_call_trace_rows"]
    second_rows = second_payload["call_metadata"]["llm_call_trace_rows"]
    first_jsonl = module._jsonl_dumps(first_rows)
    second_jsonl = module._jsonl_dumps(second_rows)

    assert first_rows == second_rows
    assert first_jsonl == second_jsonl
    assert [json.loads(line) for line in first_jsonl.splitlines() if line.strip()] == first_rows
