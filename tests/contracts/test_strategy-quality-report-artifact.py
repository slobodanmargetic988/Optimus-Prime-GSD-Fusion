import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-quality-report-artifact.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-059_strategy-quality-report-artifact.sample.json"
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-059_strategy-quality-report-artifact.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_059_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_059_strategy_quality_report_artifact(fixture_payload["input"])

    assert module.validate_req_059_strategy_quality_report_artifact(built_payload) == []
    assert module.validate_req_059_strategy_quality_report_artifact(sample_payload) == []
    assert built_payload == sample_payload


def test_req_059_gate_verdicts_include_machine_readable_failures() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    built_payload = module.build_req_059_strategy_quality_report_artifact(fixture_payload["input_with_gate_failures"])
    verdicts = built_payload["strategy_quality_report_artifact"]["gate_verdicts"]

    assert verdicts["citation_coverage_pass"] is False
    assert verdicts["contradiction_pass"] is False
    assert verdicts["confidence_distribution_pass"] is False
    assert verdicts["overall_pass"] is False
    assert verdicts["failed_gate_ids"] == [
        "citation_coverage",
        "contradiction_status",
        "confidence_distribution",
    ]


def test_req_059_validator_rejects_mismatched_failed_gate_ids() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["strategy_quality_report_artifact"]["gate_verdicts"]["failed_gate_ids"] = ["contradiction_status"]

    errors = module.validate_req_059_strategy_quality_report_artifact(broken)

    assert "gate_verdicts.failed_gate_ids must match computed failed gate ids" in errors


def test_req_059_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-059_strategy-quality-report-artifact.sample.json" in contract_text
    for key in (
        "strategy_quality_report_artifact.citation_coverage",
        "strategy_quality_report_artifact.contradiction_status",
        "strategy_quality_report_artifact.confidence_distribution",
        "strategy_quality_report_artifact.gate_verdicts",
        "strategy_quality_report_artifact.gate_verdicts.overall_pass",
        "strategy_quality_report_artifact.gate_verdicts.failed_gate_ids",
        "gate_policy",
        "totals",
    ):
        assert key in contract_text


def test_req_059_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_059_builder_rejects_out_of_range_gate_policy() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"min_citation_coverage_ratio"):
        module.build_req_059_strategy_quality_report_artifact(fixture_payload["invalid_gate_policy_input"])
