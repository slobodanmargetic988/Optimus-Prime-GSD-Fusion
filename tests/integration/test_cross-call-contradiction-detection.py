import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "cross-call-contradiction-detection.json"


def _read_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_036_integration_emits_evidence_refs_and_complete_recommendation() -> None:
    fixture = _read_fixture()
    payload = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )

    assert module.validate_req_036_cross_call_contradiction_detection(payload) == []

    processing = payload["processing_behavior"]
    report = payload["contradiction_report"]
    recommendation = processing["recommendation"]

    assert sorted(recommendation.keys()) == [
        "confidence",
        "decision",
        "evidence_refs",
        "open_risks",
        "rationale",
        "recommended_actions",
    ]
    assert recommendation["decision"] == "requires-resolution-before-final-synthesis"
    assert recommendation["confidence"] == "low"
    assert isinstance(recommendation["rationale"], str) and recommendation["rationale"]
    assert isinstance(recommendation["recommended_actions"], list) and recommendation["recommended_actions"]

    report_evidence_refs = report["evidence_refs"]
    assert report_evidence_refs
    assert recommendation["evidence_refs"] == report_evidence_refs
    for action in recommendation["recommended_actions"]:
        assert set(action.keys()) == {
            "action_id",
            "summary",
            "rationale",
            "next_step",
            "evidence_refs",
        }
        assert action["evidence_refs"] == report_evidence_refs

    assert recommendation["open_risks"] == report["open_risks"]
    assert len(recommendation["open_risks"]) == report["unresolved_contradictions"]
    assert all(row["reason_code"] == "cross_call_contradiction" for row in recommendation["open_risks"])



def test_req_036_integration_uses_broad_sweep_context_deterministically() -> None:
    fixture = _read_fixture()

    first = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )
    second = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )

    assert first["processing_behavior"]["context_inputs"] == second["processing_behavior"]["context_inputs"]
    assert first["processing_behavior"]["context_usage"] == second["processing_behavior"]["context_usage"]

    context_inputs = first["processing_behavior"]["context_inputs"]
    context_usage = first["processing_behavior"]["context_usage"]

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

    assert context_usage["call_count"] == 3
    assert context_usage["call_ids_considered"] == ["call-1", "call-2", "call-3"]
    assert context_usage["contradiction_claim_ids"] == ["claim-lane-parallelism", "claim-token-headroom"]

    unresolved = first["contradiction_report"]["open_risks"]
    assert unresolved
    assert all(row["required_evidence_refs"] for row in unresolved)
    assert "approved_cross_project_obligations" not in first["processing_behavior"]["recommendation"]

    first_trace = first["llm_call_trace"]
    second_trace = second["llm_call_trace"]
    assert first_trace == second_trace
    assert first_trace["row_count"] == context_usage["call_count"]
    assert [row["call_id"] for row in first_trace["rows"]] == context_usage["call_ids_considered"]
