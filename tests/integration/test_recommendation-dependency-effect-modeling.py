import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-dependency-effect-modeling.json"


def _read_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_041_integration_keeps_dependency_models_evidence_backed_and_context_aware() -> None:
    fixture = _read_fixture()
    payload = module.build_req_041_recommendation_dependency_effect_modeling(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        broad_sweep_context={
            "projects_considered": [
                "ground-control-hub",
                "runtime-orchestrator",
                "shared-observability",
            ],
            "cross_project_context": [
                {"project_id": "ground-control-hub"},
                {"project_id": "runtime-orchestrator"},
            ],
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "reports/earth/sweeps/2026-03-15/shared-observability.json",
            ],
            "proposed_cross_project_obligations": [
                {
                    "obligation_id": "obl.req041.shared-observability-sync",
                    "summary": "Coordinate recommendation lineage fanout with shared observability owners.",
                    "project_ids": ["shared-observability"],
                    "evidence_refs": ["reports/earth/sweeps/2026-03-15/shared-observability.json"],
                },
                {
                    "obligation_id": "obl.req041.unverified-runtime-expansion",
                    "summary": "Expand runtime rollout coordination without Earth-sweep backing.",
                    "project_ids": ["runtime-orchestrator"],
                    "evidence_refs": ["contracts/req/REQ-024_strategy-context-bundle-serialization.md"],
                },
            ],
            "unresolved_ideas": [
                {
                    "risk_id": "risk.req041.extra-ground-control-observer",
                    "summary": "Explore whether ground-control-hub needs an additional observer for dependency-effect drift.",
                    "project_ids": ["ground-control-hub"],
                    "evidence_refs": [],
                }
            ],
        },
        modeled_at="2026-03-16T12:45:00Z",
    )

    assert module.validate_req_041_recommendation_dependency_effect_modeling(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    context_usage = processing["context_usage"]

    expected_recommendation_fields = {
        "decision",
        "rationale",
        "evidence_refs",
        "context_project_ids",
        "approved_cross_project_obligations",
        "open_risks",
    }
    assert set(recommendation.keys()) == expected_recommendation_fields
    assert recommendation["decision"] == "model_with_open_risks"
    assert recommendation["evidence_refs"]
    assert set(recommendation["evidence_refs"]).issubset(set(payload["evidence_refs"]))
    assert [row["obligation_id"] for row in recommendation["approved_cross_project_obligations"]] == [
        "obl.req041.shared-observability-sync"
    ]

    risk_ids = {row["risk_id"] for row in recommendation["open_risks"]}
    assert "risk.req041.cross_project_obligation.obl.req041.unverified-runtime-expansion" in risk_ids
    assert "risk.req041.extra-ground-control-observer" in risk_ids

    assert context_usage["cross_project_context_used"] is True
    assert context_usage["modeled_project_ids"] == [
        "ground-control-hub",
        "runtime-orchestrator",
        "shared-observability",
    ]
    assert context_usage["context_project_ids"] == [
        "ground-control-hub",
        "runtime-orchestrator",
        "shared-observability",
    ]
    assert context_usage["earth_sweep_evidence_refs_used"] == [
        "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-15/shared-observability.json",
    ]
    assert context_usage["approved_cross_project_obligation_ids"] == [
        "obl.req041.shared-observability-sync"
    ]

    assert payload["call_metadata"]["canonical_processing_input"]["broad_sweep_context"]["context_project_ids"] == [
        "ground-control-hub",
        "runtime-orchestrator",
        "shared-observability",
    ]
    assert "reports/earth/sweeps/2026-03-15/shared-observability.json" in payload["call_metadata"][
        "llm_call_trace_rows"
    ][0]["input_refs"]

    for row in payload["dependency_effect_models"]:
        assert row["evidence_refs"]
        assert row["affected_project_ids"]
        for effect in row["affected_project_effects"]:
            assert effect["evidence_refs"]
            assert effect["likely_blockers"]
            assert effect["mitigation_hooks"]


def test_req_041_integration_records_open_risk_when_obligation_has_no_earth_sweep_ref() -> None:
    fixture = _read_fixture()
    payload = module.build_req_041_recommendation_dependency_effect_modeling(
        target_project_root=fixture["target_project_root"],
        earth_root=fixture["earth_root"],
        output_root=fixture["output_root"],
        revision_identity=fixture["revision_identity"],
        recommendations=fixture["recommendations"],
        broad_sweep_context={
            "projects_considered": ["runtime-orchestrator"],
            "earth_sweep_evidence_refs": [],
            "proposed_cross_project_obligations": [
                {
                    "obligation_id": "obl.req041.runtime-sync",
                    "summary": "Coordinate runtime rollout assumptions with runtime-orchestrator.",
                    "project_ids": ["runtime-orchestrator"],
                    "evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
                }
            ],
        },
        modeled_at="2026-03-16T12:45:00Z",
    )

    assert module.validate_req_041_recommendation_dependency_effect_modeling(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["approved_cross_project_obligations"] == []
    assert recommendation["decision"] == "model_with_open_risks"
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk.req041.cross_project_obligation.obl.req041.runtime-sync",
            "summary": "Coordinate runtime rollout assumptions with runtime-orchestrator.",
            "reason_code": "non_earth_sweep_evidence_refs",
            "required_evidence_refs": ["reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"],
            "context_project_ids": ["runtime-orchestrator"],
            "evidence_refs": [],
        }
    ]
