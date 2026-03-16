import json
from pathlib import Path

import pytest

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-6-kpi-impact-estimation-reasoning.json"


def _load_fixture_input() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return json.loads(json.dumps(fixture["input"]))


def test_req_031_kpi_estimates_are_evidence_backed_and_cross_project_aware() -> None:
    payload = module.build_req_031_call_6_kpi_impact_estimation_reasoning(**_load_fixture_input())

    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(payload) == []

    estimation = payload["kpi_impact_estimation"]
    usage = payload["processing_behavior"]["context_usage"]
    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]

    assert usage["source_call_ids_used"] == ["call-1", "call-2", "call-3", "call-4", "call-5", "call-6"]
    assert usage["earth_sweep_context_used"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["cross_project_project_ids_used"] == ["runtime-orchestrator"]
    assert usage["earth_sweep_evidence_refs_used"] == [
        "reports/earth/sweeps/2026-03-16/portfolio.json",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
    ]
    assert "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json" in usage["evidence_refs_used"]
    assert "reports/earth/sweeps/2026-03-16/portfolio.json" in usage["evidence_refs_used"]

    expected_recommendation_fields = {
        "recommendation_id",
        "summary",
        "adoption_status",
        "adoption_window",
        "project_id",
        "requires_earth_evidence",
        "evidence_refs",
    }
    for row in estimation["recommendation_adoptions"]:
        assert set(row.keys()) == expected_recommendation_fields
        assert row["recommendation_id"]
        assert row["summary"]
        assert row["adoption_status"] in {"planned", "conditional", "pilot"}
        assert row["adoption_window"]
        assert row["evidence_refs"]

    cross_project_recommendation = next(
        row for row in estimation["recommendation_adoptions"] if row["recommendation_id"] == "rec.runtime-sync"
    )
    assert cross_project_recommendation == {
        "recommendation_id": "rec.runtime-sync",
        "summary": "Coordinate replay hardening with runtime-orchestrator.",
        "adoption_status": "conditional",
        "adoption_window": "next-30-days",
        "project_id": "runtime-orchestrator",
        "requires_earth_evidence": True,
        "evidence_refs": [
            "REQ-029::call::call-4::output::recommendation_synthesis",
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        ],
    }

    estimates_by_id = {row["estimate_id"]: row for row in estimation["kpi_estimates"]}
    assert set(estimates_by_id) == {
        "estimate::rec.local-replay-hardening::kpi.mean-time-to-diagnose",
        "estimate::rec.local-replay-hardening::kpi.replay-failure-rate",
        "estimate::rec.runtime-sync::kpi.replay-failure-rate",
    }
    assert usage["estimate_ids_emitted"] == list(sorted(estimates_by_id))
    assert usage["low_confidence_estimate_ids"] == ["estimate::rec.runtime-sync::kpi.replay-failure-rate"]

    local_diagnosis_estimate = estimates_by_id["estimate::rec.local-replay-hardening::kpi.mean-time-to-diagnose"]
    assert local_diagnosis_estimate["confidence"] == "high"
    assert local_diagnosis_estimate["caveats"] == [
        "Estimate assumes the branch keeps emitting comparable failure artifacts."
    ]
    assert local_diagnosis_estimate["evidence_refs"] == [
        "REQ-029::call::call-4::output::recommendation_synthesis",
        "reports/optimus-prime/planning/evidence/TASK-103/TASK_EVIDENCE.json",
        "reports/optimus-prime/planning/STATE.json",
        "REQ-030::call::call-5::output::adoption_decision",
    ]

    local_failure_estimate = estimates_by_id["estimate::rec.local-replay-hardening::kpi.replay-failure-rate"]
    assert local_failure_estimate["confidence"] == "medium"
    assert local_failure_estimate["caveats"] == [
        "Estimate assumes replay instrumentation changes land without expanding the failure envelope.",
        "Estimate should be revisited if the recommendation slips beyond the next planned wave.",
    ]
    assert local_failure_estimate["evidence_refs"] == [
        "REQ-029::call::call-4::output::recommendation_synthesis",
        "reports/optimus-prime/planning/evidence/TASK-103/TASK_EVIDENCE.json",
        "reports/optimus-prime/planning/VERIFICATION.md",
    ]

    cross_project_estimate = estimates_by_id["estimate::rec.runtime-sync::kpi.replay-failure-rate"]
    assert cross_project_estimate["confidence"] == "low"
    assert cross_project_estimate["caveats"] == [
        "Estimate can overstate benefit if shared runtime evidence goes stale before rollout.",
        "Estimate depends on runtime-orchestrator adopting the same recovery interpretation in the same window.",
    ]
    assert cross_project_estimate["evidence_refs"] == [
        "REQ-029::call::call-4::output::recommendation_synthesis",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/optimus-prime/planning/VERIFICATION.md",
        "reports/earth/sweeps/2026-03-16/portfolio.json",
    ]
    assert cross_project_estimate["evidence_backed_assumptions"] == [
        {
            "assumption_id": "assump.runtime-failure-rate",
            "statement": (
                "Cross-project runtime coordination should reduce replay failure recurrence once shared runtime "
                "recovery assumptions stop diverging."
            ),
            "evidence_refs": [
                "REQ-029::call::call-4::output::recommendation_synthesis",
                "reports/earth/sweeps/2026-03-16/portfolio.json",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
        }
    ]

    assert trace_rows[-1]["call_id"] == "call-6"
    assert trace_rows[-1]["input_refs"] == [
        "REQ-026::call::call-1::output::situational_analysis",
        "REQ-027::call::call-2::output::constraint_refinement",
        "REQ-028::call::call-3::output::execution_alignment",
        "REQ-029::call::call-4::output::recommendation_synthesis",
        "REQ-030::call::call-5::output::adoption_decision",
        "reports/optimus-prime/planning/STATE.json",
        "reports/optimus-prime/planning/VERIFICATION.md",
        "reports/optimus-prime/planning/evidence/TASK-103/TASK_EVIDENCE.json",
        "reports/earth/sweeps/2026-03-16/portfolio.json",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
    ]
    assert trace_rows[-1]["handoff_summary"] == (
        "Call 6 hands off kpi_impact_estimation via REQ-031::call::call-6::output::kpi_impact_estimation "
        "as the terminal KPI estimation output with 3 estimate(s)."
    )


def test_req_031_cross_project_estimate_without_earth_evidence_is_rejected() -> None:
    payload_input = _load_fixture_input()
    payload_input["earth_sweep_evidence_refs"] = []
    for row in payload_input["recommendation_adoptions"]:
        if row["recommendation_id"] == "rec.runtime-sync":
            row["evidence_refs"] = ["REQ-029::call::call-4::output::recommendation_synthesis"]

    with pytest.raises(module.Req031Error) as exc_info:
        module.build_req_031_call_6_kpi_impact_estimation_reasoning(**payload_input)

    assert str(exc_info.value) == (
        "recommendation_adoptions[1] requires Earth evidence but no Earth-scoped refs were supplied"
    )
