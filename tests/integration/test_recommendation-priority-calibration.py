import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-priority-calibration.json"


def _read_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_038_integration_keeps_evidence_refs_and_recommendation_fields_complete() -> None:
    fixture = _read_fixture()
    payload = module.build_req_038_recommendation_priority_calibration(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        priority_weights=fixture["priority_weights"],
        broad_sweep_context={
            "projects_considered": ["runtime-orchestrator", "ground-control-hub"],
            "cross_project_context": [
                {"project_id": "runtime-orchestrator"},
                {"project_id": "ground-control-hub"},
            ],
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
            ],
            "proposed_cross_project_obligations": [
                {
                    "obligation_id": "obl.req038.runtime-sync",
                    "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
                    "project_ids": ["runtime-orchestrator"],
                    "evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
                },
                {
                    "obligation_id": "obl.req038.unverified-expansion",
                    "summary": "Expand obligations without Earth sweep backing.",
                    "project_ids": ["ground-control-hub"],
                    "evidence_refs": [],
                },
            ],
            "unresolved_ideas": [
                {
                    "idea_id": "idea.req038.extra-peer-onboarding",
                    "summary": "Explore multi-project onboarding strategy.",
                    "project_ids": ["ground-control-hub"],
                    "evidence_refs": [],
                }
            ],
        },
        calibrated_at="2026-03-16T12:30:00Z",
    )

    assert module.validate_req_038_recommendation_priority_calibration(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    context_usage = processing["context_usage"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "evidence_refs",
        "context_project_ids",
        "approved_cross_project_obligations",
        "open_risks",
    }
    assert recommendation["evidence_refs"]
    assert set(recommendation["evidence_refs"]).issubset(set(payload["evidence_refs"]))

    assert recommendation["decision"] == "prioritize_with_open_risks"
    assert recommendation["context_project_ids"] == ["ground-control-hub", "runtime-orchestrator"]
    assert [row["obligation_id"] for row in recommendation["approved_cross_project_obligations"]] == [
        "obl.req038.runtime-sync"
    ]
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["context_project_ids"] == ["ground-control-hub", "runtime-orchestrator"]
    assert context_usage["approved_cross_project_obligation_ids"] == ["obl.req038.runtime-sync"]
    assert context_usage["earth_sweep_evidence_refs_used"] == [
        "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]

    risk_ids = {row["risk_id"] for row in recommendation["open_risks"]}
    assert "risk.req038.cross_project_obligation.obl.req038.unverified-expansion" in risk_ids
    assert "idea.req038.extra-peer-onboarding" in risk_ids


def test_req_038_integration_records_open_risk_for_missing_earth_sweep_evidence() -> None:
    fixture = _read_fixture()
    payload = module.build_req_038_recommendation_priority_calibration(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        priority_weights=fixture["priority_weights"],
        broad_sweep_context={
            "projects_considered": ["runtime-orchestrator"],
            "earth_sweep_evidence_refs": [],
            "proposed_cross_project_obligations": [
                {
                    "obligation_id": "obl.req038.runtime-sync",
                    "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
                    "project_ids": ["runtime-orchestrator"],
                    "evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
                }
            ],
        },
        calibrated_at="2026-03-16T12:30:00Z",
    )

    assert module.validate_req_038_recommendation_priority_calibration(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["approved_cross_project_obligations"] == []
    assert recommendation["decision"] == "prioritize_with_open_risks"
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk.req038.cross_project_obligation.obl.req038.runtime-sync",
            "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
            "reason_code": "non_earth_sweep_evidence_refs",
            "required_evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
            "context_project_ids": ["runtime-orchestrator"],
            "evidence_refs": [],
        }
    ]
