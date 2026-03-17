import json
from copy import deepcopy
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "op-plan-strategy-ingestion-hook.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _expand_artifact_envelope(envelope: dict) -> dict:
    payload = _read_json(REPO_ROOT / envelope["artifact_ref"])
    return {
        "artifact_ref": envelope["artifact_ref"],
        "payload": payload,
    }


def _expand_fixture_input(payload: dict) -> dict:
    expanded = deepcopy(payload)
    for key in ("final_strategy_artifact", "kpi_target_artifact", "recommendation_id_validator"):
        expanded[key] = _expand_artifact_envelope(expanded[key])
    return expanded


def test_req_068_processing_behavior_uses_broad_sweep_context_with_complete_recommendation() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    payload = module.build_req_068_op_plan_strategy_ingestion_hook(
        _expand_fixture_input(fixture_payload["integration_input"])
    )
    assert module.validate_req_068_op_plan_strategy_ingestion_hook(payload) == []

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
        "strategy_packet_input_ids",
        "planner_ready_recommendation_ids",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["strategy_packet_input_ids"] == [
        "pkt.9e0c566d663e",
        "pkt.c3c7c38214ae",
    ]
    assert recommendation["planner_ready_recommendation_ids"] == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
    ]

    assert len(recommendation["cross_project_obligations"]) == 1
    obligation = recommendation["cross_project_obligations"][0]
    assert obligation["obligation_id"].startswith("obligation.")
    assert obligation["project_id"] == "earth-core-runtime"
    assert obligation["strategy_packet_input_ids"] == ["pkt.c3c7c38214ae"]
    assert obligation["recommendation_ids"] == ["rec.align-earth-runtime-canary"]
    assert obligation["evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
    ]

    assert len(recommendation["open_risks"]) == 1
    open_risk = recommendation["open_risks"][0]
    assert open_risk["reason_code"] == "unresolved_idea_open_risk"
    assert open_risk["project_id"] == "earth-shared-observability"
    assert open_risk["linked_recommendation_ids"] == ["rec.review-reuse-contracts"]
    assert "reports/earth/sweeps/shared-observability/signals-2026-03-14.json" in open_risk["evidence_refs"]

    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/shared-observability/signals-2026-03-14.json" in recommendation["evidence_refs"]
    assert (
        "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json#final_strategy_synthesis.strategy_packet_inputs"
        in recommendation["evidence_refs"]
    )
    assert (
        "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json#diagnostics.id_collisions"
        in recommendation["evidence_refs"]
    )
    assert (
        "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json#diagnostics.id_drift"
        in recommendation["evidence_refs"]
    )

    assert usage["cross_project_context_used"] is True
    assert usage["projects_considered"] == [
        "earth-core-runtime",
        "earth-shared-observability",
    ]
    assert usage["earth_sweep_context_used"] is True
    assert usage["strategy_packet_input_ids_used"] == recommendation["strategy_packet_input_ids"]
    assert usage["linked_recommendation_ids_used"] == recommendation["planner_ready_recommendation_ids"]

    assert generation["recommendation_fields_complete"] is True
    assert generation["required_recommendation_fields"] == [
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "strategy_packet_input_ids",
        "planner_ready_recommendation_ids",
        "cross_project_obligations",
        "open_risks",
    ]
    assert generation["cross_project_context_used"] is True
    assert generation["evidence_refs_used"] == recommendation["evidence_refs"]


def test_req_068_cross_project_packet_without_earth_evidence_becomes_open_risk() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    payload = _expand_fixture_input(fixture_payload["integration_input"])

    cross_project_packet = payload["final_strategy_artifact"]["payload"]["final_strategy_synthesis"]["strategy_packet_inputs"][0]
    cross_project_packet["evidence_refs"] = [
        "reports/quality/req-039-rationale-quality-score.json",
    ]

    built = module.build_req_068_op_plan_strategy_ingestion_hook(payload)
    assert module.validate_req_068_op_plan_strategy_ingestion_hook(built) == []

    recommendation = built["processing_behavior"]["recommendation"]
    usage = built["processing_behavior"]["context_usage"]

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
    assert usage["projects_considered"] == [
        "earth-core-runtime",
        "earth-shared-observability",
    ]
