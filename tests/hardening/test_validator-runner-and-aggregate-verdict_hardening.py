import copy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "validator-runner-and-aggregate-verdict.json"
PACKET_SAMPLE_PATH = REPO_ROOT / "op-tools" / "strategy" / "examples" / "strategy_packet.sample.v1.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload() -> dict:
    payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    payload.pop("strategy_packet_path")
    payload["strategy_packet"] = _read_json(PACKET_SAMPLE_PATH)
    payload["now_utc"] = "2026-03-16T10:30:00Z"
    return payload


def test_req_066_hardening_invalid_strategy_packet_schema_row_rejected_with_deterministic_diagnostics() -> None:
    payload = _payload()
    payload["strategy_packet"]["recommendations"][2]["priority"] = "urgent"

    first = module.build_req_066_validator_runner_and_aggregate_verdict(copy.deepcopy(payload))
    second = module.build_req_066_validator_runner_and_aggregate_verdict(copy.deepcopy(payload))

    assert first == second
    assert first == {
        "requirement_id": "REQ-066",
        "analysis_type": "validator_runner_and_aggregate_verdict",
        "checked_at_utc": "2026-03-16T10:30:00Z",
        "ok": False,
        "verdict": "fail",
        "blocking_reason_codes": ["schema_enum_violation"],
        "validator_count": 1,
        "passed_validator_count": 0,
        "failed_validator_count": 1,
        "summary": "1 of 1 validators reported blocking failures.",
        "validators": [
            {
                "validator_id": "strategy_packet_v1_schema_validator",
                "requirement_id": "REQ-060",
                "analysis_type": "strategy_packet_v1_schema_validator",
                "ok": False,
                "verdict": "fail",
                "blocking_reason_codes": ["schema_enum_violation"],
                "diagnostic_count": 1,
                "summary": "Strategy packet is not planner-consumable; 1 blocking diagnostics detected.",
            }
        ],
    }


def test_req_066_hardening_duplicate_recommendation_id_collision_is_flagged_with_diff_details() -> None:
    payload = _payload()
    payload["strategy_packet"]["recommendations"][1]["recommendation_id"] = payload["strategy_packet"]["recommendations"][0][
        "recommendation_id"
    ]

    first = module.build_req_066_validator_runner_and_aggregate_verdict(copy.deepcopy(payload))
    second = module.build_req_066_validator_runner_and_aggregate_verdict(copy.deepcopy(payload))

    assert first == second
    assert first == {
        "requirement_id": "REQ-066",
        "analysis_type": "validator_runner_and_aggregate_verdict",
        "checked_at_utc": "2026-03-16T10:30:00Z",
        "ok": False,
        "verdict": "fail",
        "blocking_reason_codes": [
            "duplicate_recommendation_id_collision",
            "mapping_artifact_recommendation_ids_mismatch",
            "mapping_references_unknown_packet_recommendation",
        ],
        "validator_count": 1,
        "passed_validator_count": 0,
        "failed_validator_count": 1,
        "summary": "1 of 1 validators reported blocking failures.",
        "validators": [
            {
                "validator_id": "strategy_packet_v1_schema_validator",
                "requirement_id": "REQ-060",
                "analysis_type": "strategy_packet_v1_schema_validator",
                "ok": False,
                "verdict": "fail",
                "blocking_reason_codes": [
                    "duplicate_recommendation_id_collision",
                    "mapping_artifact_recommendation_ids_mismatch",
                    "mapping_references_unknown_packet_recommendation",
                ],
                "diagnostic_count": 3,
                "summary": "Strategy packet is not planner-consumable; 3 blocking diagnostics detected.",
            }
        ],
    }


def test_req_066_hardening_broken_evidence_reference_causes_traceability_gate_failure() -> None:
    payload = _payload()
    payload["strategy_packet"]["recommendation_to_planner_mapping_artifact"]["recommendation_to_task_intent_mappings"][0][
        "traceability_refs"
    ] = ["reports/missing.json"]

    first = module.build_req_066_validator_runner_and_aggregate_verdict(copy.deepcopy(payload))
    second = module.build_req_066_validator_runner_and_aggregate_verdict(copy.deepcopy(payload))

    assert first == second
    assert first == {
        "requirement_id": "REQ-066",
        "analysis_type": "validator_runner_and_aggregate_verdict",
        "checked_at_utc": "2026-03-16T10:30:00Z",
        "ok": False,
        "verdict": "fail",
        "blocking_reason_codes": ["traceability_gate_failure"],
        "validator_count": 1,
        "passed_validator_count": 0,
        "failed_validator_count": 1,
        "summary": "1 of 1 validators reported blocking failures.",
        "validators": [
            {
                "validator_id": "strategy_packet_v1_schema_validator",
                "requirement_id": "REQ-060",
                "analysis_type": "strategy_packet_v1_schema_validator",
                "ok": False,
                "verdict": "fail",
                "blocking_reason_codes": ["traceability_gate_failure"],
                "diagnostic_count": 1,
                "summary": "Strategy packet is not planner-consumable; 1 blocking diagnostics detected.",
            }
        ],
    }
