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


def test_validator_marks_req067_pre_plan_hook_context_consumable_for_current_strategy_packet() -> None:
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
    assert result["gate"]["op_initialize_pre_plan_strategy_hook_consumable"] is True


def test_cli_reports_deterministic_req067_pre_plan_hook_diagnostics_for_non_consumable_packet(
    tmp_path: Path,
) -> None:
    invalid_packet = deepcopy(_read_json(PACKET_PATH))
    invalid_packet["strategy"]["link_map_ref"] = ""
    invalid_packet["constraints"]["planner_policy"]["mandatory_guardrail_ids"] = []
    invalid_packet["constraints"]["planner_policy"]["optional_guidance_ids"] = []

    input_path = tmp_path / "invalid.req067.strategy_packet.v1.json"
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
        "planner_policy_alignment_mismatch",
        "pre_plan_constraint_context_empty",
        "pre_plan_mandatory_guardrail_missing",
        "pre_plan_strategy_artifact_refs_missing",
    ]
    assert payload["gate"] == {
        "schema_valid": True,
        "constraint_classification_consumable": False,
        "planner_policy_consumable": False,
        "op_initialize_pre_plan_strategy_hook_consumable": False,
    }
    assert payload["diagnostics"] == [
        {
            "message": (
                "Pre-plan hook requires non-empty constraint context; planner_policy must provide "
                "mandatory_guardrail_ids and/or optional_guidance_ids."
            ),
            "path": "$.constraints.planner_policy",
            "reason_code": "pre_plan_constraint_context_empty",
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
        {
            "message": "optional_guidance_ids must equal ['guidance-batch-size', 'speculative-cross-project-sync'].",
            "path": "$.constraints.planner_policy.optional_guidance_ids",
            "reason_code": "planner_policy_alignment_mismatch",
            "severity": "error",
        },
        {
            "message": (
                "Pre-plan hook requires strategy artifact references; strategy.link_map_ref must be "
                "a non-empty string."
            ),
            "path": "$.strategy.link_map_ref",
            "reason_code": "pre_plan_strategy_artifact_refs_missing",
            "severity": "error",
        },
    ]
