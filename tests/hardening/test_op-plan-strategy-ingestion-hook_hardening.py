import json
from copy import deepcopy
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "op-plan-strategy-ingestion-hook.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _expand_artifact_envelope(envelope: dict) -> dict:
    artifact_ref = envelope["artifact_ref"]
    return {
        "artifact_ref": artifact_ref,
        "payload": _read_json(REPO_ROOT / artifact_ref),
    }


def _expanded_fixture_input(key: str = "integration_input") -> dict:
    fixture = _read_json(FIXTURE_PATH)
    payload = deepcopy(fixture[key])
    for artifact_key in ("final_strategy_artifact", "kpi_target_artifact", "recommendation_id_validator"):
        payload[artifact_key] = _expand_artifact_envelope(payload[artifact_key])
    return payload


def test_req_068_hardening_artifact_regeneration_has_no_semantic_drift_on_no_change_rerun() -> None:
    payload = _expanded_fixture_input()

    run_one = module.build_req_068_op_plan_strategy_ingestion_hook(deepcopy(payload))
    run_two = module.build_req_068_op_plan_strategy_ingestion_hook(deepcopy(payload))

    assert module.validate_req_068_op_plan_strategy_ingestion_hook(run_one) == []
    assert module.validate_req_068_op_plan_strategy_ingestion_hook(run_two) == []

    serialized_one = json.dumps(run_one, sort_keys=True, separators=(",", ":"))
    serialized_two = json.dumps(run_two, sort_keys=True, separators=(",", ":"))
    assert serialized_one == serialized_two

    assert [row.get("reason_code") for row in run_one["processing_behavior"]["recommendation"]["open_risks"]] == [
        row.get("reason_code") for row in run_two["processing_behavior"]["recommendation"]["open_risks"]
    ]


def test_req_068_hardening_rejects_incomplete_recommendation_mapping_set_for_planner_hook() -> None:
    built = module.build_req_068_op_plan_strategy_ingestion_hook(_expanded_fixture_input())

    strategy_recommendation_ids = {
        recommendation_id
        for row in built["op_plan_strategy_ingestion"]["planner_inputs"]["strategy_packet_inputs"]
        for recommendation_id in row["recommendation_ids"]
    }
    traceability_recommendation_ids = {
        row["recommendation_id"]
        for row in built["op_plan_strategy_ingestion"]["planner_inputs"]["recommendation_traceability_index"]
    }
    assert strategy_recommendation_ids == traceability_recommendation_ids

    broken = deepcopy(built)
    packet_row = broken["op_plan_strategy_ingestion"]["planner_inputs"]["strategy_packet_inputs"][0]
    packet_row["recommendation_ids"] = list(packet_row["recommendation_ids"]) + ["rec.synthetic-gap"]
    packet_row["recommendation_count"] = int(packet_row["recommendation_count"]) + 1

    errors_one = module.validate_req_068_op_plan_strategy_ingestion_hook(broken)
    errors_two = module.validate_req_068_op_plan_strategy_ingestion_hook(broken)

    assert errors_one == errors_two
    assert (
        "op_plan_strategy_ingestion.planner_inputs.recommendation_traceability_index must cover the complete "
        "strategy_packet_inputs recommendation mapping set"
    ) in errors_one
    assert (
        "op_plan_strategy_ingestion.planner_inputs.recommendation_traceability_index "
        "missing recommendation_ids: ['rec.synthetic-gap']"
    ) in errors_one


def test_req_068_hardening_acceptance_payload_keeps_required_evidence_refs_and_open_risk_handling() -> None:
    built = module.build_req_068_op_plan_strategy_ingestion_hook(_expanded_fixture_input())
    recommendation = built["processing_behavior"]["recommendation"]
    assert recommendation["open_risks"]

    evidence_refs = set(recommendation["evidence_refs"])
    for row in recommendation["open_risks"]:
        assert row["reason_code"]
        for required_ref in row.get("required_evidence_refs", []):
            assert required_ref in evidence_refs
        for risk_ref in row.get("evidence_refs", []):
            assert risk_ref in evidence_refs

    broken = deepcopy(built)
    open_risk = broken["processing_behavior"]["recommendation"]["open_risks"][0]
    ref_to_drop = (open_risk.get("evidence_refs") or open_risk.get("required_evidence_refs") or [])[0]
    broken["processing_behavior"]["recommendation"]["evidence_refs"] = [
        ref
        for ref in broken["processing_behavior"]["recommendation"]["evidence_refs"]
        if ref != ref_to_drop
    ]

    errors_one = module.validate_req_068_op_plan_strategy_ingestion_hook(broken)
    errors_two = module.validate_req_068_op_plan_strategy_ingestion_hook(broken)

    assert errors_one == errors_two
    assert any(
        "processing_behavior.recommendation.open_risks[0].evidence_refs must be included in "
        "processing_behavior.recommendation.evidence_refs" in message
        or "processing_behavior.recommendation.open_risks[0].required_evidence_refs must be included in "
        "processing_behavior.recommendation.evidence_refs" in message
        for message in errors_one
    )
