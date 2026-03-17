import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "kpi-target-artifact.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-056_kpi-target-artifact.sample.json"
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-056_kpi-target-artifact.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_056_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_056_kpi_target_artifact(fixture_payload["input"])

    assert module.validate_req_056_kpi_target_artifact(built_payload) == []
    assert module.validate_req_056_kpi_target_artifact(sample_payload) == []
    assert built_payload == sample_payload


def test_req_056_targets_link_back_to_recommendations_and_assumptions() -> None:
    sample_payload = _read_json(SAMPLE_PATH)
    rows = {row["target_id"]: row for row in sample_payload["kpi_target_artifact"]["kpi_targets"]}

    telemetry_target = rows["kpi.telemetry-freshness-slo"]
    assert telemetry_target["expected_direction"] == "decrease"
    assert telemetry_target["confidence_level"] == "high"
    assert telemetry_target["originating_recommendation_ids"] == ["rec.harden-telemetry-freshness"]
    assert telemetry_target["assumption_ids"] == [
        "assumption.runtime-ownership-confirmed",
        "assumption.telemetry-path-stable",
    ]

    cross_project_target = rows["kpi.cross-project-integration-latency"]
    assert cross_project_target["baseline_reference"].startswith("reports/earth/sweeps/")
    assert cross_project_target["confidence_level"] == "medium"
    assert cross_project_target["originating_recommendation_ids"] == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
    ]


def test_req_056_validator_rejects_missing_assumption_linkage() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["kpi_target_artifact"]["kpi_targets"][0]["assumption_ids"] = []

    errors = module.validate_req_056_kpi_target_artifact(broken)

    assert "kpi_target_artifact.kpi_targets[0].assumption_ids must include at least 1 value(s)" in errors


def test_req_056_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-056_kpi-target-artifact.sample.json" in contract_text
    for key in (
        "kpi_target_artifact.kpi_targets",
        "kpi_target_artifact.kpi_targets[].expected_direction",
        "kpi_target_artifact.kpi_targets[].baseline_reference",
        "kpi_target_artifact.kpi_targets[].confidence_level",
        "kpi_target_artifact.kpi_targets[].originating_recommendation_ids",
        "kpi_target_artifact.kpi_targets[].assumption_ids",
        "totals",
    ):
        assert key in contract_text


def test_req_056_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_056_builder_rejects_unknown_confidence_level() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"confidence_level"):
        module.build_req_056_kpi_target_artifact(fixture_payload["invalid_unknown_confidence_input"])
