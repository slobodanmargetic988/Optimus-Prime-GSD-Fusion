from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from scripts.strategy_validators import validate_strategy_packet


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_packet_validate.py"
SCHEMA_PATH = REPO_ROOT / "contracts" / "strategy_packet.v1.schema.json"
PACKET_PATH = REPO_ROOT / "strategy" / "current" / "strategy_packet.v1.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_validator_accepts_req061_recommendation_quality_validator_packet() -> None:
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
    assert result["diagnostic_count"] == 0
    assert result["reason_codes"] == []
    assert result["gate"] == {
        "schema_valid": True,
        "constraint_classification_consumable": True,
        "planner_policy_consumable": True,
    }
    assert result["diagnostics"] == []


def test_cli_emits_req061_deterministic_diagnostics_for_low_substance_recommendations(tmp_path: Path) -> None:
    invalid_packet = deepcopy(_read_json(PACKET_PATH))
    invalid_packet["recommendations"][0]["summary"] = "   "
    invalid_packet["recommendations"][0]["rationale"] = "Too short."
    invalid_packet["recommendations"][0]["expected_impact"] = "No citations listed."

    input_path = tmp_path / "invalid.recommendation-quality.strategy_packet.v1.json"
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
        "recommendation_completeness_failed",
        "recommendation_evidence_citations_below_minimum",
        "recommendation_low_substance_rationale",
    ]
    assert payload["gate"] == {
        "schema_valid": True,
        "constraint_classification_consumable": True,
        "planner_policy_consumable": False,
    }
    assert payload["diagnostics"] == [
        {
            "message": (
                "Recommendation evidence citations are below REQ-061 minimum count across "
                "summary/rationale/expected_impact: 0 < 2; detected=[]."
            ),
            "path": "$.recommendations[0].expected_impact",
            "reason_code": "recommendation_evidence_citations_below_minimum",
            "severity": "error",
        },
        {
            "message": "Recommendation rationale is below REQ-061 minimum word count: 2 < 12.",
            "path": "$.recommendations[0].rationale",
            "reason_code": "recommendation_low_substance_rationale",
            "severity": "error",
        },
        {
            "message": (
                "Recommendation field must be a non-empty string for REQ-061 quality gate "
                "completeness."
            ),
            "path": "$.recommendations[0].summary",
            "reason_code": "recommendation_completeness_failed",
            "severity": "error",
        },
    ]
