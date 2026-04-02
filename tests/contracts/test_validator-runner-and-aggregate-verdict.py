import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "validator-runner-and-aggregate-verdict.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-066_validator-runner-and-aggregate-verdict.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-066_validator-runner-and-aggregate-verdict.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"
PACKET_SAMPLE_PATH = REPO_ROOT / "op-tools" / "strategy" / "examples" / "strategy_packet.sample.v1.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_066_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_066_validator_runner_and_aggregate_verdict(fixture_payload)

    assert module.validate_req_066_validator_runner_and_aggregate_verdict(built_payload) == []
    assert module.validate_req_066_validator_runner_and_aggregate_verdict(sample_payload) == []
    assert built_payload == sample_payload


def test_req_066_aggregate_verdict_collects_blocking_reason_codes() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    fixture_payload.pop("strategy_packet_path")
    fixture_payload["strategy_packet"] = _read_json(PACKET_SAMPLE_PATH)
    fixture_payload["strategy_packet"]["identity"]["project_id"] = "optimus-prime-gsd-fusion"

    out = module.build_req_066_validator_runner_and_aggregate_verdict(fixture_payload)

    assert module.validate_req_066_validator_runner_and_aggregate_verdict(out) == []
    assert out == {
        "requirement_id": "REQ-066",
        "analysis_type": "validator_runner_and_aggregate_verdict",
        "checked_at_utc": "2026-03-16T11:00:00Z",
        "ok": False,
        "verdict": "fail",
        "blocking_reason_codes": ["schema_pattern_mismatch"],
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
                "blocking_reason_codes": ["schema_pattern_mismatch"],
                "diagnostic_count": 1,
                "summary": "Strategy packet is not planner-consumable; 1 blocking diagnostics detected.",
            }
        ],
    }


def test_req_066_contract_doc_references_documented_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-066_validator-runner-and-aggregate-verdict.sample.json" in contract_text
    for key in (
        "blocking_reason_codes",
        "validator_count",
        "passed_validator_count",
        "failed_validator_count",
        "validators",
        "validators[].validator_id",
        "strategy_packet_v1_schema_validator",
        "schema_pattern_mismatch",
    ):
        assert key in contract_text


def test_req_066_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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
