import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-packet-v1-schema-validator.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-060_strategy-packet-v1-schema-validator.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-060_strategy-packet-v1-schema-validator.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"
PACKET_SAMPLE_PATH = REPO_ROOT / "op-tools" / "strategy" / "examples" / "strategy_packet.sample.v1.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_060_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_060_strategy_packet_v1_schema_validator(fixture_payload)

    assert module.validate_req_060_strategy_packet_v1_schema_validator(built_payload) == []
    assert built_payload == sample_payload


def test_req_060_validator_returns_machine_readable_canonical_id_diagnostics() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    fixture_payload.pop("strategy_packet_path")
    fixture_payload["strategy_packet"] = _read_json(PACKET_SAMPLE_PATH)
    fixture_payload["strategy_packet"]["identity"]["project_id"] = "optimus-prime-gsd-fusion"

    out = module.build_req_060_strategy_packet_v1_schema_validator(fixture_payload)

    assert module.validate_req_060_strategy_packet_v1_schema_validator(out) == []
    assert out == {
        "ok": False,
        "checked_at_utc": "2026-03-16T10:30:00Z",
        "verdict": "fail",
        "planner_consumability": "planner_blocked",
        "reason_codes": ["schema_pattern_mismatch"],
        "diagnostic_count": 1,
        "summary": "Strategy packet is not planner-consumable; 1 blocking diagnostics detected.",
        "diagnostics": [
            {
                "severity": "error",
                "reason_code": "schema_pattern_mismatch",
                "field_path": "identity.project_id",
                "message": "'optimus-prime-gsd-fusion' does not match '^prj\\\\.[a-z0-9][a-z0-9-]{1,95}$'",
            }
        ],
    }


def test_req_060_contract_doc_references_documented_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-060_strategy-packet-v1-schema-validator.sample.json" in contract_text
    for key in (
        "reason_codes",
        "diagnostic_count",
        "diagnostics",
        "identity.project_id",
        "packet_recommendation_missing_mapping",
    ):
        assert key in contract_text


def test_req_060_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(fixture_payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stderr == ""
    assert json.loads(proc.stdout) == _read_json(SAMPLE_PATH)
