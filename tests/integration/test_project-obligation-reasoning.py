from copy import deepcopy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "project-obligation-reasoning.json"


def _base_input() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_043_integration_emits_evidence_backed_obligations_and_open_risks() -> None:
    payload = module.build_req_043_project_obligation_reasoning(**_base_input())

    assert module.validate_req_043_project_obligation_reasoning(payload) == []

    processing = payload["processing_behavior"]
    context_usage = processing["context_usage"]
    recommendation = processing["recommendation"]
    obligations = recommendation["project_obligations"]
    open_risks = recommendation["open_risks"]

    assert context_usage["bounded_context_used"] is True
    assert context_usage["earth_sweep_context_used"] is True
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["counterparty_projects_considered"] == [
        "analytics-hub",
        "runtime-orchestrator",
    ]
    assert context_usage["obligation_ids_considered"] == [
        "obl.analytics-feedback-consume",
        "obl.deploy-summary-expose",
        "obl.replay-manifest-expose",
    ]

    for field in ("decision", "rationale", "confidence", "evidence_refs", "project_obligations", "open_risks"):
        assert field in recommendation

    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["evidence_refs"] == [
        "reports/earth/sweeps/2026-03-16/analytics-hub.json",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/optimus-prime/contracts/analytics-feedback-ingestion.md",
        "reports/optimus-prime/planning/evidence/TASK-151/TASK_EVIDENCE.json",
    ]
    assert [row["obligation_id"] for row in obligations] == [
        "obl.analytics-feedback-consume",
        "obl.replay-manifest-expose",
    ]

    for obligation in obligations:
        assert obligation["contract_expectations"]["required_fields"]
        assert all(
            key in obligation["ownership_boundary"]
            for key in (
                "current_project_role",
                "current_project_owner",
                "counterparty_role",
                "counterparty_owner",
                "boundary_rule",
            )
        )
        assert obligation["evidence_refs"]
        assert any(ref.startswith("reports/earth/") for ref in obligation["evidence_refs"])

    assert open_risks == [
        {
            "risk_id": "risk-obl.deploy-summary-expose",
            "reason_code": "missing_cross_project_context",
            "summary": "Expose deployment drift summaries to deployment controller.",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/analytics-hub.json",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                "reports/optimus-prime/planning/evidence/TASK-151/TASK_EVIDENCE.json",
            ],
        }
    ]

    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]
    assert len(trace_rows) == 1
    assert trace_rows[0]["call_objective"] == module.REQ_043_ANALYSIS_TYPE
    assert trace_rows[0]["handoff_summary"] == (
        "Call 1 emits project obligation reasoning with 2 obligation(s) and 1 open risk(s)."
    )


def test_req_043_integration_replay_is_stable_across_input_order_changes() -> None:
    first = module.build_req_043_project_obligation_reasoning(**_base_input())

    second_input = deepcopy(_base_input())
    second_input["cross_project_context"] = list(reversed(second_input["cross_project_context"]))
    second_input["project_obligation_candidates"] = list(reversed(second_input["project_obligation_candidates"]))
    second = module.build_req_043_project_obligation_reasoning(**second_input)

    assert module.validate_req_043_project_obligation_reasoning(first) == []
    assert module.validate_req_043_project_obligation_reasoning(second) == []
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == second["call_metadata"]["processing_call_id"]
    assert first["call_metadata"]["llm_call_trace_rows"] == second["call_metadata"]["llm_call_trace_rows"]
    assert (
        first["processing_behavior"]["context_usage"]["open_risk_ids_emitted"]
        == second["processing_behavior"]["context_usage"]["open_risk_ids_emitted"]
        == ["risk-obl.deploy-summary-expose"]
    )
    assert (
        [row["obligation_id"] for row in first["processing_behavior"]["recommendation"]["project_obligations"]]
        == [row["obligation_id"] for row in second["processing_behavior"]["recommendation"]["project_obligations"]]
        == ["obl.analytics-feedback-consume", "obl.replay-manifest-expose"]
    )
