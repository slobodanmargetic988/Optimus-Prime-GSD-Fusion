import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-3-gap-and-opportunity-reasoning.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_028_integration_emits_evidence_backed_recommendations_and_cross_project_usage() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_028_call_3_gap_and_opportunity_reasoning(**fixture["input"])

    assert module.validate_req_028_call_3_gap_and_opportunity_reasoning(payload) == []

    context_usage = payload["processing_behavior"]["context_usage"]
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["cross_project_projects_considered"] == [
        "runtime-orchestrator",
        "shared-observability",
    ]
    assert context_usage["dependency_projects_referenced"] == [
        "runtime-orchestrator",
        "shared-observability",
    ]
    assert context_usage["cross_project_refs_used"] == [
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-16/shared-observability.json",
    ]

    call_3_reasoning = payload["processing_behavior"]["call_3_reasoning"]
    assert call_3_reasoning["gap_count"] == 2
    assert call_3_reasoning["opportunity_count"] == 3
    for gap in call_3_reasoning["gap_reasoning"]:
        assert gap["evidence_refs"]
        for opportunity in gap["opportunities"]:
            assert opportunity["ecosystem_level_benefit"]
            assert opportunity["dependency_effects"]
            assert opportunity["evidence_refs"]

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["evidence_refs"] == [
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-16/shared-observability.json",
        "reports/optimus-prime/planning/evidence/TASK-091/TASK_EVIDENCE.json",
    ]

    recommended = recommendation["recommended_opportunities"]
    assert len(recommended) == 3
    for row in recommended:
        assert row["opportunity_id"]
        assert row["gap_id"]
        assert row["summary"]
        assert row["rationale"]
        assert row["ecosystem_level_benefit"]
        assert row["next_step"]
        assert row["linked_context_projects"]
        assert row["dependency_effects"]
        assert row["evidence_refs"]

    earth_refs = set(payload["processing_behavior"]["context_inputs"]["earth_sweep"]["evidence_refs"])
    obligations = recommendation["cross_project_obligations"]
    assert len(obligations) == 4
    for row in obligations:
        assert set(row["evidence_refs"]).intersection(earth_refs)

    open_risks = recommendation["open_risks"]
    assert open_risks == [
        {
            "risk_id": "risk-idea.canary-window-obligation",
            "summary": "Confirm whether a shared canary-window obligation is needed before Call-4 commits ecosystem dependencies.",
            "reason_code": "unresolved_cross_project_idea",
            "project_id": "release-coordination",
            "related_gap_ids": ["gap.runtime-dependency-handshake"],
            "related_opportunity_ids": ["opp.telemetry-runtime-link"],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
        }
    ]
    assert "release-coordination" not in [row["project_id"] for row in obligations]

    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]
    assert payload["call_metadata"]["llm_call_trace_path"] == module.LLM_CALL_TRACE_RELATIVE_PATH
    assert len(trace_rows) == 1
    assert trace_rows[0]["requirement_id"] == module.REQ_028_REQUIREMENT_ID
    assert trace_rows[0]["sequence"] == module.REQ_028_CALL_SEQUENCE
    assert trace_rows[0]["call_objective"] == module.REQ_028_TRACE_CALL_OBJECTIVE
    assert trace_rows[0]["output_refs"]
    assert "ecosystem-visible gaps" in trace_rows[0]["handoff_summary"]
    assert "linked opportunities beyond the local mission" in trace_rows[0]["handoff_summary"]
