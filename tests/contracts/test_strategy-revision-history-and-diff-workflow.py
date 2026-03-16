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


def test_req_069_directional_shift_guardrails_require_governance_for_domain_flips() -> None:
    sample_payload = _read_json(SAMPLE_PATH)
    workflow = sample_payload["strategy_revision_history_and_diff_workflow"]
    rows = {row["diff_id"]: row for row in workflow["diff_artifacts"]}

    blocked = rows["diff.scope.r15-r16"]
    assert blocked["direction_change_detected"] is True
    assert blocked["previous_directional_shift"] == "maintain"
    assert blocked["governance_review_ref"] == ""
    assert blocked["guardrail_status"] == "blocked_needs_governance_review"

    approved = rows["diff.runtime.r15-r16"]
    assert approved["direction_change_detected"] is True
    assert approved["previous_directional_shift"] == "decrease"
    assert approved["governance_review_ref"] == "reports/governance/reviews/GR-204-runtime-lane.md"
    assert approved["guardrail_status"] == "governance_reviewed"

    assert workflow["governance_review"] == {
        "decision": "hold",
        "rationale": (
            "review_required=2 approved=1 blocked=1; "
            "directional shifts without governance references are blocked."
        ),
        "review_required_diff_ids": ["diff.runtime.r15-r16", "diff.scope.r15-r16"],
        "approved_diff_ids": ["diff.runtime.r15-r16"],
        "blocked_diff_ids": ["diff.scope.r15-r16"],
    }


def test_req_069_validator_rejects_mismatched_blocked_totals() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["totals"]["blocked_directional_shifts"] = 0

    errors = module.validate_req_069_strategy_revision_history_and_diff_workflow(broken)

    assert "totals.blocked_directional_shifts must equal governance_review.blocked_diff_ids count" in errors


def test_req_069_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-069_strategy-revision-history-and-diff-workflow.sample.json" in contract_text
    for key in (
        "strategy_revision_history_and_diff_workflow.revision_history",
        "strategy_revision_history_and_diff_workflow.diff_artifacts",
        "strategy_revision_history_and_diff_workflow.diff_artifacts[].guardrail_status",
        "strategy_revision_history_and_diff_workflow.diff_artifacts[].direction_change_detected",
        "strategy_revision_history_and_diff_workflow.governance_review",
        "strategy_revision_history_and_diff_workflow.governance_review.review_required_diff_ids",
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


def test_req_069_builder_rejects_unknown_revision_reference() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"to_revision_id"):
        module.build_req_069_strategy_revision_history_and_diff_workflow(
            fixture_payload["invalid_unknown_revision_input"]
        )
