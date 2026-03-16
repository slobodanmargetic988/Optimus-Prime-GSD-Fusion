import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "kpi-target-artifact.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_056_processing_behavior_uses_broad_sweep_context_with_complete_recommendation() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    payload = module.build_req_056_kpi_target_artifact(fixture_payload["integration_input"])
    assert module.validate_req_056_kpi_target_artifact(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]
    generation = processing["recommendation_generation"]

    assert recommendation["decision"] == "proceed-with-open-risks"
    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "linked_kpi_target_ids",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["linked_kpi_target_ids"] == [
        "kpi.cross-project-integration-latency",
        "kpi.telemetry-freshness-slo",
    ]
    assert len(recommendation["cross_project_obligations"]) == 1
    obligation = recommendation["cross_project_obligations"][0]
    assert obligation["obligation_id"].startswith("obligation.")
    assert obligation["project_id"] == "earth-core-runtime"
    assert obligation["linked_kpi_target_ids"] == [
        "kpi.cross-project-integration-latency",
    ]
    assert obligation["recommendation_ids"] == [
        "rec.align-earth-runtime-canary",
    ]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in obligation["evidence_refs"]

    assert len(recommendation["open_risks"]) == 1
    open_risk = recommendation["open_risks"][0]
    assert open_risk["risk_id"].startswith("risk.")
    assert (
        open_risk["summary"]
        == "Validate earth-shared-observability ownership handoff before committing additional KPI dependencies."
    )
    assert open_risk["reason_code"] == "unresolved_cross_project_idea"
    assert open_risk["project_id"] == "earth-shared-observability"
    assert open_risk["linked_kpi_target_ids"] == [
        "kpi.cross-project-integration-latency",
    ]
    assert open_risk["linked_recommendation_ids"] == [
        "rec.align-earth-runtime-canary",
    ]
    assert open_risk["evidence_refs"] == [
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]
    assert "reports/earth/sweeps/shared-observability/signals-2026-03-14.json" in open_risk["required_evidence_refs"]

    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/shared-observability/signals-2026-03-14.json" in recommendation["evidence_refs"]
    assert (
        "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json#strategy_packet_inputs"
        in recommendation["evidence_refs"]
    )

    assert usage["cross_project_context_used"] is True
    assert usage["projects_considered"] == [
        "earth-core-runtime",
        "earth-shared-observability",
    ]
    assert usage["earth_sweep_context_used"] is True
    assert usage["linked_recommendation_ids_used"] == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
    ]
    assert generation["recommendation_fields_complete"] is True
    assert generation["required_recommendation_fields"] == [
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "linked_kpi_target_ids",
        "cross_project_obligations",
        "open_risks",
    ]
    assert generation["cross_project_context_used"] is True
    assert generation["evidence_refs_used"] == recommendation["evidence_refs"]


def test_req_056_cross_project_dependency_without_earth_evidence_becomes_open_risk() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    payload = module.build_req_056_kpi_target_artifact(fixture_payload["integration_missing_earth_input"])
    assert module.validate_req_056_kpi_target_artifact(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    usage = payload["processing_behavior"]["context_usage"]

    assert recommendation["decision"] == "collect-earth-evidence"
    assert recommendation["cross_project_obligations"] == []
    assert len(recommendation["open_risks"]) == 1
    open_risk = recommendation["open_risks"][0]
    assert open_risk["risk_id"].startswith("risk.")
    assert open_risk["summary"] == "Cross-project KPI dependency for earth-core-runtime lacks Earth-sweep evidence refs."
    assert open_risk["reason_code"] == "missing_earth_sweep_evidence_refs"
    assert open_risk["project_id"] == "earth-core-runtime"
    assert open_risk["linked_kpi_target_ids"] == [
        "kpi.cross-project-integration-latency",
    ]
    assert open_risk["linked_recommendation_ids"] == [
        "rec.align-earth-runtime-canary",
    ]
    assert open_risk["evidence_refs"] == []
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in open_risk[
        "required_evidence_refs"
    ]
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
