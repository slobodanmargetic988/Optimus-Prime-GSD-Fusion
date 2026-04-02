import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "source-traceability-validator.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-064_source-traceability-validator.sample.json"
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-064_source-traceability-validator.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_064_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_064_source_traceability_validator(fixture_payload["input"])

    assert module.validate_req_064_source_traceability_validator(built_payload) == []
    assert module.validate_req_064_source_traceability_validator(sample_payload) == []
    assert built_payload == sample_payload


def test_req_064_validator_rejects_uncited_claims() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["source_traceability_validator"]["recommendations"][0]["claims"][0]["evidence_refs"] = []

    errors = module.validate_req_064_source_traceability_validator(broken)

    assert (
        "source_traceability_validator.recommendations[0].claims[0].evidence_refs "
        "must include at least 1 value(s)"
    ) in errors


def test_req_064_validator_rejects_broken_evidence_references() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["source_traceability_validator"]["recommendations"][0]["evidence_refs"] = ["src.unknown-999"]

    errors = module.validate_req_064_source_traceability_validator(broken)

    assert (
        "source_traceability_validator.recommendations[0].evidence_refs "
        "contains unknown evidence refs: ['src.unknown-999']"
    ) in errors


def test_req_064_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-064_source-traceability-validator.sample.json" in contract_text
    for key in (
        "source_traceability_validator.source_references",
        "source_traceability_validator.recommendations",
        "source_traceability_validator.recommendations[].evidence_refs",
        "source_traceability_validator.recommendations[].claims",
        "source_traceability_validator.recommendations[].claims[].evidence_refs",
        "totals",
    ):
        assert key in contract_text


def test_req_064_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_064_builder_rejects_broken_references() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"unknown evidence refs"):
        module.build_req_064_source_traceability_validator(
            fixture_payload["invalid_broken_reference_input"]
        )
