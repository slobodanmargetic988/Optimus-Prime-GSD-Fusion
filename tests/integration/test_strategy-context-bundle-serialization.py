import copy
import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-context-bundle-serialization.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bundle_from_payload(payload: dict) -> dict:
    return json.loads(payload["strategy_context_bundle_serialization"]["serialized_context_bundle"])


def test_req_024_integration_keeps_evidence_refs_and_recommendation_fields_complete():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_024_strategy_context_bundle_serialization(**fixture["input"])
    assert module.validate_req_024_strategy_context_bundle_serialization(payload) == []

    bundle = _bundle_from_payload(payload)
    processing_behavior = bundle["strategy_context"]["processing_behavior"]
    recommendation = processing_behavior["recommendation"]

    assert recommendation["evidence_refs"] == processing_behavior["context_usage"]["evidence_refs_used"]
    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }

    for row in recommendation["recommended_actions"]:
        assert set(row.keys()) == {
            "action_id",
            "summary",
            "rationale",
            "action_scope",
            "next_step",
            "evidence_refs",
        }
        assert row["evidence_refs"]

    for row in recommendation["cross_project_obligations"]:
        assert set(row.keys()) == {"obligation_id", "project_id", "summary", "evidence_refs"}
        assert row["evidence_refs"]

    for row in bundle["strategy_context"]["open_risks"]:
        assert set(row.keys()) == {"risk_id", "summary", "reason_code", "evidence_refs"}
        assert row["evidence_refs"]


def test_req_024_integration_uses_cross_project_context_in_deterministic_order():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_024_strategy_context_bundle_serialization(**fixture["input"])
    assert module.validate_req_024_strategy_context_bundle_serialization(payload) == []

    bundle = _bundle_from_payload(payload)
    processing_behavior = bundle["strategy_context"]["processing_behavior"]
    context_inputs = processing_behavior["context_inputs"]
    context_usage = processing_behavior["context_usage"]

    assert [row["project_id"] for row in context_inputs["cross_project_context"]] == [
        "ground-control-hub",
        "runtime-orchestrator",
    ]
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["cross_project_projects_considered"] == [
        "ground-control-hub",
        "runtime-orchestrator",
    ]
    assert context_usage["cross_project_refs_used"] == [
        "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]
    assert [row["project_id"] for row in processing_behavior["recommendation"]["cross_project_obligations"]] == [
        "runtime-orchestrator"
    ]


def test_req_024_integration_records_open_risk_when_cross_project_action_lacks_earth_sweep_evidence():
    fixture = _read_json(FIXTURE_PATH)
    test_input = copy.deepcopy(fixture["input"])
    processing_inputs = test_input["strategy_context"]["processing_behavior"]["context_inputs"]
    processing_inputs["earth_sweep"]["evidence_refs"] = []

    payload = module.build_req_024_strategy_context_bundle_serialization(**test_input)
    assert module.validate_req_024_strategy_context_bundle_serialization(payload) == []

    bundle = _bundle_from_payload(payload)
    recommendation = bundle["strategy_context"]["processing_behavior"]["recommendation"]

    assert recommendation["decision"] == "proceed-with-open-risks"
    assert [row["action_id"] for row in recommendation["recommended_actions"]] == [
        "action-local-bundle-hardening",
    ]
    assert recommendation["cross_project_obligations"] == []
    assert [row["reason_code"] for row in recommendation["open_risks"]] == [
        "missing_earth_sweep_evidence_refs",
    ]
    assert recommendation["open_risks"][0]["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]
