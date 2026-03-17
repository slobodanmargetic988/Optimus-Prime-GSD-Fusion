import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "alternative-strategic-scenario-generator.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_integration_req_045_recommendation_fields_are_complete_with_cross_project_context_usage() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_045_alternative_strategic_scenario_generator(**fixture["input"])

    assert module.validate_req_045_alternative_strategic_scenario_generator(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    context_usage = payload["processing_behavior"]["context_usage"]
    contract = payload["alternative_strategic_scenario_generator"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "preferred_branch",
        "fallback_branch",
        "evidence_refs",
        "cross_project_context",
        "obligations",
        "open_risks",
    }

    evidence_refs = recommendation["evidence_refs"]
    earth_refs = contract["evidence_refs"]["earth_sweep"]
    assert evidence_refs
    assert all(ref in evidence_refs for ref in earth_refs)

    cross_project_context = recommendation["cross_project_context"]
    assert cross_project_context["cross_project"] is True
    assert cross_project_context["earth_sweep_evidence_refs"] == earth_refs
    assert cross_project_context["cross_project_scenario_ids"] == ["scenario.cross-project-alignment-first"]
    assert cross_project_context["scenario_ids_with_earth_sweep_evidence"] == [
        "scenario.cross-project-alignment-first",
        "scenario.parallel-discovery-track",
    ]

    obligations = recommendation["obligations"]
    assert obligations
    assert recommendation["open_risks"] == []
    for row in obligations:
        assert row["obligation_id"]
        assert row["scenario_id"] in cross_project_context["cross_project_scenario_ids"]
        assert row["trigger_condition_ids"]
        assert row["evidence_refs"]
        assert all(ref in earth_refs for ref in row["evidence_refs"])

    assert context_usage["cross_project_context_used"] is True
    assert context_usage["cross_project_scenario_ids_used"] == cross_project_context["cross_project_scenario_ids"]
    assert context_usage["cross_project_obligation_ids_used"] == [row["obligation_id"] for row in obligations]
    assert context_usage["cross_project_open_risk_ids"] == []


def test_integration_req_045_records_open_risks_when_cross_project_context_has_no_earth_sweep_evidence() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload_input = copy.deepcopy(fixture["input"])
    payload_input["earth_sweep_evidence_refs"] = []
    for row in payload_input["scenario_candidates"]:
        row["evidence_refs"] = payload_input["target_project_evidence_refs"]

    payload = module.build_req_045_alternative_strategic_scenario_generator(**payload_input)
    recommendation = payload["processing_behavior"]["recommendation"]

    assert module.validate_req_045_alternative_strategic_scenario_generator(payload) == []
    assert recommendation["cross_project_context"]["cross_project"] is False
    assert recommendation["cross_project_context"]["earth_sweep_evidence_refs"] == []
    assert recommendation["obligations"] == []

    open_risks = recommendation["open_risks"]
    assert open_risks
    assert [row["scenario_id"] for row in open_risks] == ["scenario.cross-project-alignment-first"]
    assert {row["reason_code"] for row in open_risks} == {"earth_sweep_evidence_missing"}
