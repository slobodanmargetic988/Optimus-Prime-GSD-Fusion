import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-4-recommendation-synthesis.json"


def _load_fixture_input() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return json.loads(json.dumps(fixture["input"]))


def test_req_029_recommendation_drafts_are_complete_and_use_cross_project_context() -> None:
    payload = module.build_req_029_call_4_recommendation_synthesis(**_load_fixture_input())

    assert module.validate_req_029_call_4_recommendation_synthesis(payload) == []

    synthesis = payload["recommendation_synthesis"]
    drafts = synthesis["recommendation_drafts"]
    usage = payload["processing_behavior"]["context_usage"]
    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]

    assert len(drafts) == 4
    assert synthesis["open_risks"] == []
    assert synthesis["summary"] == {
        "source_call_count": 3,
        "candidate_recommendation_count": 4,
        "draft_count": 4,
        "open_risk_count": 0,
    }

    expected_draft_fields = {
        "recommendation_id",
        "source_call_id",
        "source_output_ref",
        "source_candidate_id",
        "summary",
        "rationale",
        "impact",
        "risk",
        "evidence_refs",
    }
    for row in drafts:
        assert set(row.keys()) == expected_draft_fields
        assert row["recommendation_id"].startswith("rec-call-4-")
        assert row["source_call_id"] in {"call-1", "call-2", "call-3"}
        assert row["source_output_ref"]
        assert row["source_candidate_id"]
        assert row["summary"]
        assert row["rationale"]
        assert row["impact"]
        assert row["risk"]
        assert row["evidence_refs"]

    assert usage["earlier_call_outputs_used"] is True
    assert usage["source_call_ids_used"] == ["call-1", "call-2", "call-3"]
    assert usage["cross_project_context_used"] is True
    assert usage["cross_project_project_ids_used"] == ["runtime-orchestrator"]
    assert usage["earth_sweep_evidence_refs_used"] == [
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
    ]
    assert "reports/optimus-prime/planning/VERIFICATION.md" in usage["target_project_evidence_refs_used"]
    assert "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json" in usage["evidence_refs_used"]
    assert usage["open_risk_ids_emitted"] == []

    assert [row["call_id"] for row in trace_rows] == ["call-1", "call-2", "call-3", "call-4"]
    assert [row["sequence"] for row in trace_rows] == [1, 2, 3, 4]
    assert trace_rows[0]["output_refs"] == ["REQ-026::call::call-1::output::situational_analysis"]
    assert trace_rows[1]["input_refs"][0] == "REQ-026::call::call-1::output::situational_analysis"
    assert trace_rows[2]["input_refs"][0] == "REQ-027::call::call-2::output::constraint_refinement"
    assert trace_rows[3]["input_refs"][:3] == [
        "REQ-026::call::call-1::output::situational_analysis",
        "REQ-027::call::call-2::output::constraint_refinement",
        "REQ-028::call::call-3::output::execution_alignment",
    ]
    assert "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json" in trace_rows[3]["input_refs"]
    assert trace_rows[3]["handoff_summary"] == (
        "Call 4 hands off recommendation_synthesis via REQ-029::call::call-4::output::recommendation_synthesis "
        "as the terminal recommendation synthesis output with 4 draft(s) and 0 open risk(s)."
    )


def test_req_029_cross_project_candidate_without_earth_evidence_becomes_open_risk() -> None:
    payload_input = _load_fixture_input()
    payload_input["earlier_call_outputs"][2]["candidate_recommendations"][0]["evidence_refs"] = [
        "reports/optimus-prime/planning/VERIFICATION.md"
    ]

    payload = module.build_req_029_call_4_recommendation_synthesis(**payload_input)

    assert module.validate_req_029_call_4_recommendation_synthesis(payload) == []

    synthesis = payload["recommendation_synthesis"]
    usage = payload["processing_behavior"]["context_usage"]

    assert [row["recommendation_id"] for row in synthesis["recommendation_drafts"]] == [
        "rec-call-4-call-1-unknown-resolution",
        "rec-call-4-call-2-contract-surface-lock",
        "rec-call-4-call-2-verification-refresh",
    ]
    assert synthesis["open_risks"] == [
        {
            "risk_id": "risk-rec-call-4-call-3-runtime-coordination",
            "source_call_id": "call-3",
            "source_output_ref": "REQ-028::call::call-3::output::execution_alignment",
            "source_candidate_id": "runtime-coordination",
            "project_id": "runtime-orchestrator",
            "summary": "Route shared runtime follow-up through the existing runtime-orchestrator coordination path.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [
                "reports/optimus-prime/planning/VERIFICATION.md"
            ],
        }
    ]
    assert synthesis["summary"] == {
        "source_call_count": 3,
        "candidate_recommendation_count": 4,
        "draft_count": 3,
        "open_risk_count": 1,
    }
    assert usage["cross_project_context_used"] is True
    assert usage["cross_project_project_ids_used"] == ["runtime-orchestrator"]
    assert usage["earth_sweep_evidence_refs_used"] == []
    assert usage["open_risk_ids_emitted"] == ["risk-rec-call-4-call-3-runtime-coordination"]
    assert payload["call_metadata"]["llm_call_trace_rows"][3]["handoff_summary"] == (
        "Call 4 hands off recommendation_synthesis via REQ-029::call::call-4::output::recommendation_synthesis "
        "as the terminal recommendation synthesis output with 3 draft(s) and 1 open risk(s)."
    )
