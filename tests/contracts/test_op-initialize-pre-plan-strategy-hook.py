import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "op-initialize-pre-plan-strategy-hook.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-067_op-initialize-pre-plan-strategy-hook.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-067_op-initialize-pre-plan-strategy-hook.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_067_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_067_op_initialize_pre_plan_strategy_hook(fixture_payload["input"])

    assert module.validate_req_067_op_initialize_pre_plan_strategy_hook(built_payload) == []
    assert module.validate_req_067_op_initialize_pre_plan_strategy_hook(sample_payload) == []
    assert built_payload == sample_payload


def test_req_067_fail_closed_blocks_on_missing_context() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    built_payload = module.build_req_067_op_initialize_pre_plan_strategy_hook(
        fixture_payload["missing_context_fail_closed_input"]
    )
    readiness = built_payload["pre_plan_strategy_hook"]["planner_readiness"]
    failure = built_payload["pre_plan_strategy_hook"]["deterministic_failure"]

    assert readiness["context_ready"] is False
    assert readiness["decision"] == "block_planning"
    assert readiness["missing_context_fields"] == ["strategy_artifact_refs", "strategy_is_current"]
    assert readiness["gating_reason_codes"] == ["pre_plan_strategy_context_missing"]
    assert failure == {
        "mode": "fail_closed",
        "status": "triggered",
        "reason_code": "pre_plan_strategy_context_missing",
        "planner_action": "halt_before_op_plan",
    }


def test_req_067_fail_open_allows_planning_with_warning() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    built_payload = module.build_req_067_op_initialize_pre_plan_strategy_hook(
        fixture_payload["missing_context_fail_open_input"]
    )
    readiness = built_payload["pre_plan_strategy_hook"]["planner_readiness"]
    failure = built_payload["pre_plan_strategy_hook"]["deterministic_failure"]

    assert readiness["context_ready"] is False
    assert readiness["decision"] == "allow_planning_with_warning"
    assert readiness["gating_reason_codes"] == ["pre_plan_strategy_context_missing_soft"]
    assert failure == {
        "mode": "fail_open",
        "status": "triggered",
        "reason_code": "pre_plan_strategy_context_missing_soft",
        "planner_action": "continue_with_strategy_warning",
    }


def test_req_067_validator_rejects_readiness_alignment_drift() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["pre_plan_strategy_hook"]["planner_readiness"]["decision"] = "allow_planning_with_warning"

    errors = module.validate_req_067_op_initialize_pre_plan_strategy_hook(broken)

    assert (
        "pre_plan_strategy_hook.planner_readiness.decision must be allow_planning when context_ready is true"
        in errors
    )


def test_req_067_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-067_op-initialize-pre-plan-strategy-hook.sample.json" in contract_text
    for key in (
        "pre_plan_strategy_hook.strategy_context",
        "pre_plan_strategy_hook.deterministic_failure",
        "pre_plan_strategy_hook.planner_readiness",
        "totals",
    ):
        assert key in contract_text


def test_req_067_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_067_builder_rejects_invalid_strictness() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"strictness"):
        module.build_req_067_op_initialize_pre_plan_strategy_hook(fixture_payload["invalid_strictness_input"])
