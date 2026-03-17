import copy
import json
from pathlib import Path

from scripts import strategy_validators as validators


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKET_PATH = REPO_ROOT / "strategy" / "current" / "strategy_packet.v1.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "strategy_packet.v1.schema.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_packet(packet: dict, tmp_path: Path) -> dict:
    packet_path = tmp_path / "strategy_packet.v1.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validators.validate_strategy_packet_files(packet_path, SCHEMA_PATH)


def test_req_063_hardening_invalid_strategy_packet_schema_row_is_rejected_with_deterministic_diagnostics(
    tmp_path: Path,
) -> None:
    invalid_packet = copy.deepcopy(_read_json(PACKET_PATH))
    invalid_packet["recommendations"][0]["priority"] = "urgent"

    run_one = _validate_packet(invalid_packet, tmp_path)
    run_two = _validate_packet(invalid_packet, tmp_path)

    for payload in (run_one, run_two):
        assert payload["ok"] is False
        assert payload["planner_consumability"] == "planner_blocked"
        assert payload["reason_codes"] == ["schema_enum_violation"]
        assert payload["diagnostics"] == [
            {
                "severity": "error",
                "reason_code": "schema_enum_violation",
                "field_path": "recommendations[0].priority",
                "message": "'urgent' is not one of ['high', 'medium', 'low']",
            }
        ]

    assert run_one["reason_codes"] == run_two["reason_codes"]
    assert run_one["diagnostics"] == run_two["diagnostics"]


def test_req_063_hardening_duplicate_recommendation_id_collision_includes_diff_details(
    tmp_path: Path,
) -> None:
    invalid_packet = copy.deepcopy(_read_json(PACKET_PATH))
    invalid_packet["recommendations"][1]["recommendation_id"] = invalid_packet["recommendations"][0]["recommendation_id"]
    invalid_packet["recommendations"][1]["priority"] = "low"
    invalid_packet["recommendations"][1]["summary"] = "Duplicate recommendation payload for collision replay coverage."

    run_one = _validate_packet(invalid_packet, tmp_path)
    run_two = _validate_packet(invalid_packet, tmp_path)

    expected_diagnostics = [
        {
            "severity": "error",
            "reason_code": "strategy_recommendation_id_duplicate",
            "field_path": "recommendations[1].recommendation_id",
            "message": (
                "recommendations[1].recommendation_id duplicates recommendation_id "
                "'rec.route-cross-project-rate-limits' first declared at "
                "recommendations[0].recommendation_id; differing fields: ['expected_impact', 'priority', "
                "'rationale', 'risk_level', 'summary']."
            ),
        }
    ]

    for payload in (run_one, run_two):
        assert payload["ok"] is False
        assert payload["planner_consumability"] == "planner_blocked"
        assert payload["reason_codes"] == ["strategy_recommendation_id_duplicate"]
        assert payload["diagnostics"] == expected_diagnostics

    assert run_one["reason_codes"] == run_two["reason_codes"]
    assert run_one["diagnostics"] == run_two["diagnostics"]


def test_req_063_hardening_broken_evidence_reference_causes_traceability_gate_failure(
    tmp_path: Path,
) -> None:
    invalid_packet = copy.deepcopy(_read_json(PACKET_PATH))
    invalid_packet["blocker_handling_policy_artifact"]["policies"][0]["evidence_refs"][0] = (
        "reports/earth/sweeps/2026-03-15/missing-runtime-orchestrator.json"
    )

    run_one = _validate_packet(invalid_packet, tmp_path)
    run_two = _validate_packet(invalid_packet, tmp_path)

    expected_diagnostics = [
        {
            "severity": "error",
            "reason_code": "strategy_traceability_ref_missing",
            "field_path": "blocker_handling_policy_artifact.policies[0].evidence_refs[0]",
            "message": (
                "blocker_handling_policy_artifact.policies[0].evidence_refs[0] references missing file "
                "'reports/earth/sweeps/2026-03-15/missing-runtime-orchestrator.json'."
            ),
        }
    ]

    for payload in (run_one, run_two):
        assert payload["ok"] is False
        assert payload["planner_consumability"] == "planner_blocked"
        assert payload["reason_codes"] == ["strategy_traceability_ref_missing"]
        assert payload["gate"] == {
            "schema_valid": True,
            "req_057_blocker_policy_consumable": True,
        }
        assert payload["diagnostics"] == expected_diagnostics

    assert run_one["reason_codes"] == run_two["reason_codes"]
    assert run_one["diagnostics"] == run_two["diagnostics"]
