import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-revision-history-and-diff-workflow.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-069_strategy-revision-history-and-diff-workflow.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-069_strategy-revision-history-and-diff-workflow.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_069_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_069_strategy_revision_history_and_diff_workflow(fixture_payload["input"])

    assert module.validate_req_069_strategy_revision_history_and_diff_workflow(built_payload) == []
    assert module.validate_req_069_strategy_revision_history_and_diff_workflow(sample_payload) == []
    assert built_payload == sample_payload


def test_req_069_fail_closed_blocks_on_missing_context() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    built_payload = module.build_req_069_strategy_revision_history_and_diff_workflow(
        fixture_payload["missing_context_fail_closed_input"]
    )
    readiness = built_payload["strategy_revision_history_and_diff_workflow"]["planner_readiness"]
    failure = built_payload["strategy_revision_history_and_diff_workflow"]["deterministic_failure"]

    assert readiness["context_ready"] is False
    assert readiness["decision"] == "block_diff_review"
    assert readiness["missing_context_fields"] == ["diff_artifact_refs", "strategy_is_current"]
    assert readiness["gating_reason_codes"] == ["strategy_revision_diff_context_missing"]
    assert failure == {
        "mode": "fail_closed",
        "status": "triggered",
        "reason_code": "strategy_revision_diff_context_missing",
        "planner_action": "halt_before_op_plan",
    }


def test_req_069_fail_open_allows_review_with_warning() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    built_payload = module.build_req_069_strategy_revision_history_and_diff_workflow(
        fixture_payload["missing_context_fail_open_input"]
    )
    readiness = built_payload["strategy_revision_history_and_diff_workflow"]["planner_readiness"]
    failure = built_payload["strategy_revision_history_and_diff_workflow"]["deterministic_failure"]

    assert readiness["context_ready"] is False
    assert readiness["decision"] == "allow_diff_review_with_warning"
    assert readiness["gating_reason_codes"] == ["strategy_revision_diff_context_missing_soft"]
    assert failure == {
        "mode": "fail_open",
        "status": "triggered",
        "reason_code": "strategy_revision_diff_context_missing_soft",
        "planner_action": "continue_with_diff_warning",
    }


def test_req_069_validator_rejects_readiness_alignment_drift() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["strategy_revision_history_and_diff_workflow"]["planner_readiness"]["decision"] = (
        "allow_diff_review_with_warning"
    )

    errors = module.validate_req_069_strategy_revision_history_and_diff_workflow(broken)

    assert (
        "strategy_revision_history_and_diff_workflow.planner_readiness.decision "
        "must be allow_diff_review when context_ready is true"
    ) in errors


def test_req_069_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-069_strategy-revision-history-and-diff-workflow.sample.json" in contract_text
    for key in (
        "strategy_revision_history_and_diff_workflow.revision_history",
        "strategy_revision_history_and_diff_workflow.deterministic_failure",
        "strategy_revision_history_and_diff_workflow.planner_readiness",
        "totals",
    ):
        assert key in contract_text


def test_req_069_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_069_builder_rejects_invalid_strictness() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"strictness"):
        module.build_req_069_strategy_revision_history_and_diff_workflow(fixture_payload["invalid_strictness_input"])
