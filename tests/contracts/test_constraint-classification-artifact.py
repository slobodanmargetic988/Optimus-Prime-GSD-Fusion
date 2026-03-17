import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "constraint-classification-artifact.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-055_constraint-classification-artifact.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-055_constraint-classification-artifact.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_055_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_055_constraint_classification_artifact(fixture_payload["input"])

    assert module.validate_req_055_constraint_classification_artifact(built_payload) == []
    assert module.validate_req_055_constraint_classification_artifact(sample_payload) == []
    assert built_payload == sample_payload


def test_req_055_policy_disambiguates_mandatory_and_optional_constraints() -> None:
    sample_payload = _read_json(SAMPLE_PATH)
    classified = sample_payload["constraint_classification"]
    planner_policy = classified["planner_policy"]

    assert planner_policy["mandatory_guardrail_ids"] == ["guardrail-task-floor"]
    assert planner_policy["optional_guidance_ids"] == [
        "guidance-batch-size",
        "speculative-cross-project-sync",
    ]
    assert [row["policy_role"] for row in classified["hard_constraints"]] == ["mandatory_guardrail"]
    assert [row["policy_role"] for row in classified["soft_constraints"]] == ["optional_guidance"]
    assert [row["policy_role"] for row in classified["speculative_constraints"]] == ["optional_guidance"]


def test_req_055_validator_rejects_policy_alignment_drift() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["constraint_classification"]["planner_policy"]["mandatory_guardrail_ids"] = []

    errors = module.validate_req_055_constraint_classification_artifact(broken)

    assert (
        "constraint_classification.planner_policy.mandatory_guardrail_ids must match hard_constraints" in errors
    )


def test_req_055_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-055_constraint-classification-artifact.sample.json" in contract_text
    for key in (
        "constraint_classification.hard_constraints",
        "constraint_classification.soft_constraints",
        "constraint_classification.speculative_constraints",
        "constraint_classification.planner_policy",
        "totals",
    ):
        assert key in contract_text


def test_req_055_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_055_builder_rejects_unknown_classification() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"classification"):
        module.build_req_055_constraint_classification_artifact(
            fixture_payload["invalid_unknown_classification_input"]
        )
