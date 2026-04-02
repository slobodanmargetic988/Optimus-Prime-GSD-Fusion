import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-id-uniqueness-validator.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_062_processing_behavior_uses_broad_sweep_context_with_complete_recommendation() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    payload = module.build_req_062_recommendation_id_uniqueness_validator(fixture_payload["integration_input"])
    assert module.validate_req_062_recommendation_id_uniqueness_validator(payload) == []

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
        "cross_project_obligations",
        "open_risks",
    }

    assert len(recommendation["cross_project_obligations"]) == 1
    obligation = recommendation["cross_project_obligations"][0]
    assert obligation["obligation_id"].startswith("obligation.")
    assert obligation["project_id"] == "earth-core-runtime"
    assert obligation["recommendation_ids"] == ["rec.align-earth-runtime-canary"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in obligation["evidence_refs"]

    reason_codes = [row["reason_code"] for row in recommendation["open_risks"]]
    assert "recommendation_id_collision" in reason_codes
    assert "recommendation_id_drift" in reason_codes
    assert "unresolved_cross_project_idea" in reason_codes

    assert (
        "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json#diagnostics.id_collisions"
        in recommendation["evidence_refs"]
    )
    assert (
        "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json#diagnostics.id_drift"
        in recommendation["evidence_refs"]
    )
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/shared-observability/signals-2026-03-14.json" in recommendation["evidence_refs"]

    assert usage["cross_project_context_used"] is True
    assert usage["projects_considered"] == [
        "earth-core-runtime",
        "earth-shared-observability",
    ]
    assert usage["earth_sweep_context_used"] is True
    assert "rec.align-earth-runtime-canary" in usage["linked_recommendation_ids_used"]

    assert generation["recommendation_fields_complete"] is True
    assert generation["required_recommendation_fields"] == [
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "cross_project_obligations",
        "open_risks",
    ]
    assert generation["cross_project_context_used"] is True
    assert generation["evidence_refs_used"] == recommendation["evidence_refs"]


def test_req_062_cross_project_dependency_without_earth_evidence_becomes_open_risk() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    payload = module.build_req_062_recommendation_id_uniqueness_validator(
        fixture_payload["integration_missing_earth_input"]
    )
    assert module.validate_req_062_recommendation_id_uniqueness_validator(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    usage = payload["processing_behavior"]["context_usage"]

    assert recommendation["decision"] == "collect-earth-evidence"
    assert recommendation["cross_project_obligations"] == []

    missing_earth_risks = [
        row for row in recommendation["open_risks"] if row["reason_code"] == "missing_earth_sweep_evidence_refs"
    ]
    assert len(missing_earth_risks) == 1
    assert missing_earth_risks[0]["project_id"] == "earth-core-runtime"
    assert missing_earth_risks[0]["linked_recommendation_ids"] == ["rec.align-earth-runtime-canary"]
    assert missing_earth_risks[0]["required_evidence_refs"] == ["missing:earth-sweep-evidence-ref"]

    assert usage["cross_project_context_used"] is True
    assert usage["projects_considered"] == ["earth-core-runtime"]
