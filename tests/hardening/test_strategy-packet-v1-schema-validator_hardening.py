import copy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKET_SAMPLE_PATH = REPO_ROOT / "op-tools" / "strategy" / "examples" / "strategy_packet.sample.v1.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload() -> dict:
    return {
        "analysis_type": "strategy_packet_v1_schema_validator",
        "now_utc": "2026-03-16T10:30:00Z",
        "schema_path": "contracts/strategy_packet.v1.schema.json",
        "strategy_packet": _read_json(PACKET_SAMPLE_PATH),
    }


def test_req_060_hardening_invalid_strategy_packet_schema_row_rejected_with_deterministic_diagnostics() -> None:
    payload = _payload()
    payload["strategy_packet"]["recommendations"][2]["priority"] = "urgent"

    first = module.build_req_060_strategy_packet_v1_schema_validator(copy.deepcopy(payload))
    second = module.build_req_060_strategy_packet_v1_schema_validator(copy.deepcopy(payload))

    assert first == second
    assert first == {
        "ok": False,
        "checked_at_utc": "2026-03-16T10:30:00Z",
        "verdict": "fail",
        "planner_consumability": "planner_blocked",
        "reason_codes": ["schema_enum_violation"],
        "diagnostic_count": 1,
        "summary": "Strategy packet is not planner-consumable; 1 blocking diagnostics detected.",
        "diagnostics": [
            {
                "severity": "error",
                "reason_code": "schema_enum_violation",
                "field_path": "recommendations[2].priority",
                "message": "'urgent' is not one of ['high', 'medium', 'low']",
            }
        ],
    }


def test_req_060_hardening_duplicate_recommendation_id_collision_is_flagged_with_diff_details() -> None:
    payload = _payload()
    payload["strategy_packet"]["recommendations"][1]["recommendation_id"] = payload["strategy_packet"]["recommendations"][0][
        "recommendation_id"
    ]

    first = module.build_req_060_strategy_packet_v1_schema_validator(copy.deepcopy(payload))
    second = module.build_req_060_strategy_packet_v1_schema_validator(copy.deepcopy(payload))

    assert first == second
    assert first == {
        "ok": False,
        "checked_at_utc": "2026-03-16T10:30:00Z",
        "verdict": "fail",
        "planner_consumability": "planner_blocked",
        "reason_codes": [
            "duplicate_recommendation_id_collision",
            "mapping_artifact_recommendation_ids_mismatch",
            "mapping_references_unknown_packet_recommendation",
        ],
        "diagnostic_count": 3,
        "summary": "Strategy packet is not planner-consumable; 3 blocking diagnostics detected.",
        "diagnostics": [
            {
                "severity": "error",
                "reason_code": "mapping_artifact_recommendation_ids_mismatch",
                "field_path": "recommendation_to_planner_mapping_artifact.recommendation_ids",
                "message": (
                    "recommendation_ids must exactly match the strategy packet recommendation_id set "
                    "for planner consumability; missing_from_packet=['rec.align-earth-runtime-canary'] "
                    "unexpected_in_packet=[]"
                ),
            },
            {
                "severity": "error",
                "reason_code": "mapping_references_unknown_packet_recommendation",
                "field_path": "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings[1].recommendation_id",
                "message": "mapping recommendation_id must reference a recommendation_id declared in recommendations[]",
            },
            {
                "severity": "error",
                "reason_code": "duplicate_recommendation_id_collision",
                "field_path": "recommendations[1].recommendation_id",
                "message": (
                    "recommendation_id 'rec.harden-telemetry-freshness' must be unique; "
                    "collision_indexes=[0, 1] "
                    "missing_from_packet=['rec.align-earth-runtime-canary'] "
                    "unexpected_in_packet=[]"
                ),
            },
        ],
    }


def test_req_060_hardening_broken_evidence_reference_causes_traceability_gate_failure() -> None:
    payload = _payload()
    payload["strategy_packet"]["recommendation_to_planner_mapping_artifact"]["recommendation_to_task_intent_mappings"][0][
        "traceability_refs"
    ] = ["reports/missing.json"]

    first = module.build_req_060_strategy_packet_v1_schema_validator(copy.deepcopy(payload))
    second = module.build_req_060_strategy_packet_v1_schema_validator(copy.deepcopy(payload))

    assert first == second
    assert first == {
        "ok": False,
        "checked_at_utc": "2026-03-16T10:30:00Z",
        "verdict": "fail",
        "planner_consumability": "planner_blocked",
        "reason_codes": ["traceability_gate_failure"],
        "diagnostic_count": 1,
        "summary": "Strategy packet is not planner-consumable; 1 blocking diagnostics detected.",
        "diagnostics": [
            {
                "severity": "error",
                "reason_code": "traceability_gate_failure",
                "field_path": (
                    "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings[0].traceability_refs"
                ),
                "message": (
                    "traceability_refs must exactly cover downstream_audit_trail refs; "
                    "recommendation_id='rec.harden-telemetry-freshness' "
                    "planner_task_intent_handle='intent.telemetry-freshness-hardening' "
                    "missing_refs=['reports/optimus-prime/planning/PLAN_PACKETS.json#execution.telemetry-freshness', "
                    "'reports/quality/req-039-rationale-quality-score.json', "
                    "'reports/runtime/telemetry/freshness-gap-2026-03-15.json', "
                    "'strategy/current/llm_call_trace.jsonl#call-5-001', "
                    "'strategy/current/llm_call_trace.jsonl#rationale-quality-001'] "
                    "unexpected_refs=['reports/missing.json']"
                ),
            }
        ],
    }
