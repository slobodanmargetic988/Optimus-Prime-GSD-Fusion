import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-feasibility-scoring.json"


def _read_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_040_integration_emits_evidence_refs_and_complete_recommendation() -> None:
    fixture = _read_fixture()
    payload = module.build_req_040_recommendation_feasibility_scoring(**fixture["input"])

    assert module.validate_req_040_recommendation_feasibility_scoring(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    feasibility = payload["feasibility_assessment"]
    risk_policy = payload["risk_policy"]

    assert sorted(recommendation.keys()) == [
        "confidence",
        "decision",
        "evidence_refs",
        "open_risks",
        "rationale",
        "recommended_actions",
    ]
    assert recommendation["decision"] == "defer-high-risk-recommendations"
    assert recommendation["confidence"] == "medium"
    assert isinstance(recommendation["rationale"], str) and recommendation["rationale"]
    assert isinstance(recommendation["recommended_actions"], list) and recommendation["recommended_actions"]

    assert recommendation["evidence_refs"] == feasibility["evidence_refs"]
    assert recommendation["open_risks"] == risk_policy["open_risks"]
    assert recommendation["open_risks"]
    assert all(row["required_evidence_refs"] for row in recommendation["open_risks"])

    recommendation_rows = {
        row["recommendation_id"]: row
        for row in feasibility["recommendations"]
    }
    ordered_ids = payload["sequencing_policy"]["ordered_recommendation_ids"]
    assert [
        action["action_id"]
        for action in recommendation["recommended_actions"]
    ] == [f"sequence-{recommendation_id}" for recommendation_id in ordered_ids]

    for action in recommendation["recommended_actions"]:
        assert set(action.keys()) == {
            "action_id",
            "summary",
            "rationale",
            "next_step",
            "evidence_refs",
        }
        recommendation_id = action["action_id"].replace("sequence-", "", 1)
        assert action["summary"] == recommendation_rows[recommendation_id]["summary"]
        assert action["evidence_refs"] == recommendation_rows[recommendation_id]["evidence_refs"]


def test_req_040_integration_uses_broad_sweep_context_deterministically() -> None:
    fixture = _read_fixture()

    first = module.build_req_040_recommendation_feasibility_scoring(**fixture["input"])
    second = module.build_req_040_recommendation_feasibility_scoring(**fixture["input"])

    assert first["processing_behavior"]["context_inputs"] == second["processing_behavior"]["context_inputs"]
    assert first["processing_behavior"]["context_usage"] == second["processing_behavior"]["context_usage"]
    assert first["processing_behavior"]["recommendation"] == second["processing_behavior"]["recommendation"]

    context_inputs = first["processing_behavior"]["context_inputs"]
    context_usage = first["processing_behavior"]["context_usage"]
    recommendation = first["processing_behavior"]["recommendation"]

    expected_broad_sweep_context = {
        "target_project_root": fixture["input"]["target_project_root"],
        "earth_root": fixture["input"]["earth_root"],
        "output_root": fixture["input"]["output_root"],
        "revision_identity": fixture["input"]["revision_identity"],
    }
    assert context_inputs["broad_sweep_context"] == expected_broad_sweep_context

    assert context_usage["broad_sweep_context_used"] is True
    assert context_usage["broad_sweep_context_scope"] == "earth-wide"
    assert context_usage["target_project_root"] == expected_broad_sweep_context["target_project_root"]
    assert context_usage["earth_root"] == expected_broad_sweep_context["earth_root"]
    assert context_usage["output_root"] == expected_broad_sweep_context["output_root"]
    assert context_usage["revision_identity"] == expected_broad_sweep_context["revision_identity"]
    assert context_usage["evidence_refs_used"] == recommendation["evidence_refs"]

    assert context_usage["recommendation_count"] == len(first["feasibility_assessment"]["recommendations"])
    assert context_usage["dependency_count"] == len(context_inputs["dependency_readiness"])
    assert "approved_cross_project_obligations" not in recommendation
    assert all(risk["required_evidence_refs"] for risk in first["risk_policy"]["open_risks"])
