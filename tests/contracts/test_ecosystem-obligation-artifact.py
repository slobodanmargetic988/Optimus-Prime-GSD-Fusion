import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "ecosystem-obligation-artifact.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-058_ecosystem-obligation-artifact.sample.json"
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-058_ecosystem-obligation-artifact.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_058_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_058_ecosystem_obligation_artifact(fixture_payload["input"])

    assert module.validate_req_058_ecosystem_obligation_artifact(built_payload) == []
    assert module.validate_req_058_ecosystem_obligation_artifact(sample_payload) == []
    assert built_payload == sample_payload


def test_req_058_obligations_distinguish_produce_and_consume_with_prerequisites() -> None:
    sample_payload = _read_json(SAMPLE_PATH)
    rows = {
        row["obligation_id"]: row
        for row in sample_payload["ecosystem_obligation_artifact"]["ecosystem_obligations"]
    }

    consume_row = rows["obl.consume-runtime-heartbeats"]
    assert consume_row["responsibility"] == "consume"
    assert consume_row["dependency_prerequisites"] == [
        "dep.runtime-heartbeat-contract",
        "dep.state-artifact-cadence",
    ]

    produce_row = rows["obl.produce-strategy-health-summary"]
    assert produce_row["responsibility"] == "produce"
    assert produce_row["dependency_prerequisites"] == [
        "dep.analytics-schema-v2",
        "dep.runtime-heartbeat-contract",
    ]
    assert sample_payload["totals"]["produce_responsibilities"] == 1
    assert sample_payload["totals"]["consume_responsibilities"] == 1


def test_req_058_validator_rejects_missing_dependency_prerequisites() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["ecosystem_obligation_artifact"]["ecosystem_obligations"][0]["dependency_prerequisites"] = []

    errors = module.validate_req_058_ecosystem_obligation_artifact(broken)

    assert (
        "ecosystem_obligation_artifact.ecosystem_obligations[0].dependency_prerequisites "
        "must include at least 1 value(s)"
    ) in errors


def test_req_058_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-058_ecosystem-obligation-artifact.sample.json" in contract_text
    for key in (
        "ecosystem_obligation_artifact.ecosystem_obligations",
        "ecosystem_obligation_artifact.ecosystem_obligations[].responsibility",
        "ecosystem_obligation_artifact.ecosystem_obligations[].dependency_prerequisites",
        "totals",
    ):
        assert key in contract_text


def test_req_058_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_058_builder_rejects_unknown_responsibility() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"responsibility"):
        module.build_req_058_ecosystem_obligation_artifact(
            fixture_payload["invalid_unknown_responsibility_input"]
        )
