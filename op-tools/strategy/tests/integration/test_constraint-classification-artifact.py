from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.strategy_validators import validate_strategy_packet

SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_packet_validate.py"
SCHEMA_PATH = REPO_ROOT / "contracts" / "strategy_packet.v1.schema.json"
PACKET_PATH = REPO_ROOT / "strategy" / "current" / "strategy_packet.v1.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_validator_accepts_req055_constraint_classification_artifact_packet() -> None:
    packet = _read_json(PACKET_PATH)
    schema = _read_json(SCHEMA_PATH)

    result = validate_strategy_packet(
        packet,
        schema,
        input_path=str(PACKET_PATH.relative_to(REPO_ROOT)),
        schema_path=str(SCHEMA_PATH.relative_to(REPO_ROOT)),
    )

    assert result["ok"] is True
    assert result["verdict"] == "pass"
    assert result["reason_codes"] == []
    assert result["diagnostic_count"] == 0
    assert result["gate"] == {
        "schema_valid": True,
        "constraint_classification_consumable": True,
        "planner_policy_consumable": True,
        "op_initialize_pre_plan_strategy_hook_consumable": True,
    }
    assert result["diagnostics"] == []


def test_cli_emits_deterministic_semantic_diagnostics_for_invalid_constraint_artifact(tmp_path: Path) -> None:
    invalid_packet = deepcopy(_read_json(PACKET_PATH))
    invalid_packet["constraints"]["hard_constraints"][0]["classification"] = "soft"
    invalid_packet["constraints"]["planner_policy"]["mandatory_guardrail_ids"] = []

    input_path = tmp_path / "invalid.strategy_packet.v1.json"
    input_path.write_text(json.dumps(invalid_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input", str(input_path), "--schema", str(SCHEMA_PATH)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["verdict"] == "fail"
    assert payload["reason_codes"] == [
        "constraint_bucket_classification_mismatch",
        "planner_policy_alignment_mismatch",
        "pre_plan_mandatory_guardrail_missing",
    ]
    assert payload["gate"] == {
        "schema_valid": True,
        "constraint_classification_consumable": False,
        "planner_policy_consumable": False,
        "op_initialize_pre_plan_strategy_hook_consumable": False,
    }
    assert payload["diagnostics"] == [
        {
            "message": "hard_constraints entries must declare classification 'hard', found 'soft'.",
            "path": "$.constraints.hard_constraints[0].classification",
            "reason_code": "constraint_bucket_classification_mismatch",
            "severity": "error",
        },
        {
            "message": "mandatory_guardrail_ids must equal ['guardrail-task-floor'].",
            "path": "$.constraints.planner_policy.mandatory_guardrail_ids",
            "reason_code": "planner_policy_alignment_mismatch",
            "severity": "error",
        },
        {
            "message": "Pre-plan hook requires at least one mandatory guardrail constraint ID.",
            "path": "$.constraints.planner_policy.mandatory_guardrail_ids",
            "reason_code": "pre_plan_mandatory_guardrail_missing",
            "severity": "error",
        },
    ]


def test_cli_emits_schema_failure_with_field_path_for_malformed_constraint_artifact(tmp_path: Path) -> None:
    invalid_packet = deepcopy(_read_json(PACKET_PATH))
    del invalid_packet["constraints"]["speculative_constraints"]

    input_path = tmp_path / "schema-invalid.strategy_packet.v1.json"
    input_path.write_text(json.dumps(invalid_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input", str(input_path), "--schema", str(SCHEMA_PATH)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["verdict"] == "fail"
    assert payload["reason_codes"] == ["schema_validation_failed"]
    assert payload["gate"] == {
        "schema_valid": False,
        "constraint_classification_consumable": False,
        "planner_policy_consumable": False,
        "op_initialize_pre_plan_strategy_hook_consumable": False,
    }
    assert payload["diagnostics"] == [
        {
            "message": "'speculative_constraints' is a required property",
            "path": "$.constraints",
            "reason_code": "schema_validation_failed",
            "severity": "error",
        }
    ]
