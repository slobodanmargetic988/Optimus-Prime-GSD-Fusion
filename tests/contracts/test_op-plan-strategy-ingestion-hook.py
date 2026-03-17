import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "op-plan-strategy-ingestion-hook.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-068_op-plan-strategy-ingestion-hook.sample.json"
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-068_op-plan-strategy-ingestion-hook.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _expand_artifact_envelope(envelope: dict) -> dict:
    artifact_ref = envelope["artifact_ref"]
    payload = _read_json(REPO_ROOT / artifact_ref)
    return {
        "artifact_ref": artifact_ref,
        "payload": payload,
    }


def _expand_fixture_input(payload: dict) -> dict:
    expanded = deepcopy(payload)
    for key in ("final_strategy_artifact", "kpi_target_artifact", "recommendation_id_validator"):
        if key in expanded:
            expanded[key] = _expand_artifact_envelope(expanded[key])
    return expanded


def test_req_068_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_068_op_plan_strategy_ingestion_hook(_expand_fixture_input(fixture_payload["input"]))

    assert module.validate_req_068_op_plan_strategy_ingestion_hook(built_payload) == []
    assert module.validate_req_068_op_plan_strategy_ingestion_hook(sample_payload) == []
    assert built_payload == sample_payload


def test_req_068_traceability_index_preserves_kpi_and_validator_linkage() -> None:
    payload = _read_json(SAMPLE_PATH)
    rows = {
        row["recommendation_id"]: row
        for row in payload["op_plan_strategy_ingestion"]["planner_inputs"]["recommendation_traceability_index"]
    }

    runtime_alignment = rows["rec.align-earth-runtime-canary"]
    assert runtime_alignment["id_validation_status"] == "collision"
    assert runtime_alignment["linked_kpi_target_ids"] == ["kpi.cross-project-integration-latency"]
    assert "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json#diagnostics.id_collisions" in runtime_alignment["validator_diagnostic_refs"]

    telemetry = rows["rec.harden-telemetry-freshness"]
    assert telemetry["id_validation_status"] == "drifted"
    assert telemetry["linked_kpi_target_ids"] == [
        "kpi.cross-project-integration-latency",
        "kpi.telemetry-freshness-slo",
    ]
    assert "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json#final_strategy_synthesis.strategy_packet_inputs" in telemetry["traceability_refs"]


def test_req_068_validator_rejects_missing_verdict_ref() -> None:
    broken = _read_json(SAMPLE_PATH)
    broken["op_plan_strategy_ingestion"]["planner_inputs"]["recommendation_traceability_index"][0][
        "validator_diagnostic_refs"
    ] = [
        "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json#diagnostics.id_collisions"
    ]

    errors = module.validate_req_068_op_plan_strategy_ingestion_hook(broken)

    assert (
        "op_plan_strategy_ingestion.planner_inputs.recommendation_traceability_index[0].validator_diagnostic_refs must include canonical verdict ref"
        in errors
    )


def test_req_068_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-068_op-plan-strategy-ingestion-hook.sample.json" in contract_text
    for key in (
        "op_plan_strategy_ingestion.canonical_strategy_artifacts",
        "op_plan_strategy_ingestion.planner_inputs.strategy_packet_inputs",
        "op_plan_strategy_ingestion.planner_inputs.recommendation_traceability_index",
        "op_plan_strategy_ingestion.planning_alerts",
        "op_plan_strategy_ingestion.planning_alerts.validator_verdict",
        "processing_behavior",
        "processing_behavior.recommendation_generation",
        "processing_behavior.context_usage",
        "totals",
    ):
        assert key in contract_text


def test_req_068_builder_rejects_missing_final_strategy_artifact() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"final_strategy_artifact"):
        module.build_req_068_op_plan_strategy_ingestion_hook(
            _expand_fixture_input(fixture_payload["invalid_missing_final_strategy_artifact_input"])
        )
