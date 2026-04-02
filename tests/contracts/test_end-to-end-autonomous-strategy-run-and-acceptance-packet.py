import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "end-to-end-autonomous-strategy-run-and-acceptance-packet.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-070_end-to-end-autonomous-strategy-run-and-acceptance-packet.sample.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "req"
    / "REQ-070_end-to-end-autonomous-strategy-run-and-acceptance-packet.md"
)
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_070_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(
        fixture_payload["input"]
    )

    assert module.validate_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(built_payload) == []
    assert module.validate_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(sample_payload) == []
    assert built_payload == sample_payload


def test_req_070_sample_captures_current_history_validator_and_acceptance_anchors() -> None:
    sample_payload = _read_json(SAMPLE_PATH)
    packet = sample_payload["end_to_end_strategy_run_acceptance_packet"]

    assert [row["artifact_id"] for row in packet["current_artifacts"]] == [
        "current.strategy-notes",
        "current.strategy-packet",
    ]
    assert [row["artifact_id"] for row in packet["history_artifacts"]] == [
        "history.strategy-run",
    ]
    assert [row["artifact_id"] for row in packet["validator_artifacts"]] == [
        "validator.contract-report",
        "validator.packet-ready",
    ]
    assert packet["planner_consumability"] == {
        "consumability_verdict": "planner-consumable",
        "evidence_refs": [
            "strategy/current/strategy_packet.json#recommendations"
        ],
        "ready_for_planner": True,
        "recommendation_ids": [
            "rec.req070.current-history-validator",
            "rec.req070.peer-awareness",
        ],
        "recommendation_mapping_complete": True,
        "recommendation_mapping_refs": [
            "strategy/current/strategy_packet.json#recommendations"
        ],
    }
    assert packet["ecosystem_awareness"]["peer_project_ids"] == [
        "earth-analytics-hub",
        "earth-core-runtime",
    ]
    assert sample_payload["totals"] == {
        "current_artifacts": 2,
        "history_artifacts": 1,
        "validator_artifacts": 2,
        "planner_recommendations": 2,
        "peer_projects_considered": 2,
        "open_risks": 1,
        "evidence_refs": 9,
    }


def test_req_070_validator_rejects_missing_history_rows() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["end_to_end_strategy_run_acceptance_packet"]["history_artifacts"] = []

    errors = module.validate_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(broken)

    assert "end_to_end_strategy_run_acceptance_packet.history_artifacts must include at least one row" in errors
    assert "totals.history_artifacts must equal history artifact row count" in errors


def test_req_070_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-070_end-to-end-autonomous-strategy-run-and-acceptance-packet.sample.json" in contract_text
    for key in (
        "end_to_end_strategy_run_acceptance_packet.current_artifacts",
        "end_to_end_strategy_run_acceptance_packet.history_artifacts",
        "end_to_end_strategy_run_acceptance_packet.validator_artifacts",
        "end_to_end_strategy_run_acceptance_packet.planner_consumability",
        "end_to_end_strategy_run_acceptance_packet.ecosystem_awareness",
        "end_to_end_strategy_run_acceptance_packet.open_risks",
        "totals",
    ):
        assert key in contract_text


def test_req_070_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(fixture_payload["input"]), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stderr == ""
    assert json.loads(proc.stdout) == _read_json(SAMPLE_PATH)


def test_req_070_builder_rejects_invalid_peer_context() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"peer_project_ids"):
        module.build_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(
            fixture_payload["invalid_missing_peer_context_input"]
        )
