import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_validators


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_packet_validate.py"
SCHEMA_PATH = REPO_ROOT / "contracts" / "strategy_packet.v1.schema.json"
CURRENT_PACKET_PATH = REPO_ROOT / "strategy" / "current" / "strategy_packet.v1.json"
WRAPPER_SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-052_strategy-packet-v1-generator.sample.json"
)
INVALID_MISSING_SECTION_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy_packet.invalid.missing-section.v1.json"
INVALID_MALFORMED_VALUES_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy_packet.invalid.malformed-values.v1.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_strategy_packet_current_artifact_matches_req_052_sample_packet() -> None:
    wrapper_sample = _read_json(WRAPPER_SAMPLE_PATH)

    assert _read_json(CURRENT_PACKET_PATH) == wrapper_sample["strategy_packet_v1"]["packet"]


def test_strategy_packet_validator_accepts_current_req_052_packet() -> None:
    result = strategy_validators.validate_strategy_packet_paths(CURRENT_PACKET_PATH, SCHEMA_PATH)

    assert result == {
        "ok": True,
        "verdict": "pass",
        "error_count": 0,
        "reason_codes": [],
        "failing_field_paths": [],
        "diagnostics": [],
    }


def test_strategy_packet_validator_reports_machine_readable_field_diagnostics() -> None:
    result = strategy_validators.validate_strategy_packet_paths(INVALID_MALFORMED_VALUES_PATH, SCHEMA_PATH)

    assert result["ok"] is False
    assert result["verdict"] == "fail"
    assert result["error_count"] == 3
    assert result["reason_codes"] == [
        "pattern_mismatch",
        "duplicate_recommendation_id",
        "blank_string_value",
    ]
    assert result["failing_field_paths"] == [
        "$.identity.project_id",
        "$.recommendations[1].recommendation_id",
        "$.strategy.summary",
    ]
    assert result["diagnostics"] == [
        {
            "severity": "error",
            "reason_code": "pattern_mismatch",
            "field_path": "$.identity.project_id",
            "schema_path": "#/properties/identity/properties/project_id/pattern",
            "message": "$.identity.project_id does not match required pattern",
        },
        {
            "severity": "error",
            "reason_code": "duplicate_recommendation_id",
            "field_path": "$.recommendations[1].recommendation_id",
            "schema_path": "#/properties/recommendations",
            "message": "$.recommendations[1].recommendation_id duplicates $.recommendations[0].recommendation_id",
        },
        {
            "severity": "error",
            "reason_code": "blank_string_value",
            "field_path": "$.strategy.summary",
            "schema_path": "#/properties/strategy/properties/summary",
            "message": "$.strategy.summary must be a non-blank string",
        },
    ]


def test_strategy_packet_cli_exits_zero_for_valid_packet() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input", str(CURRENT_PACKET_PATH), "--schema", str(SCHEMA_PATH)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stderr == ""
    assert json.loads(proc.stdout)["verdict"] == "pass"


def test_strategy_packet_cli_fails_with_deterministic_missing_section_diagnostics() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(INVALID_MISSING_SECTION_PATH),
            "--schema",
            str(SCHEMA_PATH),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    assert proc.stderr == ""
    assert json.loads(proc.stdout) == {
        "ok": False,
        "verdict": "fail",
        "error_count": 2,
        "reason_codes": [
            "unexpected_field",
            "missing_required_field",
        ],
        "failing_field_paths": [
            "$.runtime_context",
            "$.source",
        ],
        "diagnostics": [
            {
                "severity": "error",
                "reason_code": "unexpected_field",
                "field_path": "$.runtime_context",
                "schema_path": "#/additionalProperties",
                "message": "$.runtime_context is not allowed",
            },
            {
                "severity": "error",
                "reason_code": "missing_required_field",
                "field_path": "$.source",
                "schema_path": "#/required",
                "message": "$.source is required",
            },
        ],
    }
