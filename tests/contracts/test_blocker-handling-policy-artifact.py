import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "blocker-handling-policy-artifact.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-057_blocker-handling-policy-artifact.sample.json"
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-057_blocker-handling-policy-artifact.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_057_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_057_blocker_handling_policy_artifact(fixture_payload["input"])

    assert module.validate_req_057_blocker_handling_policy_artifact(built_payload) == []
    assert module.validate_req_057_blocker_handling_policy_artifact(sample_payload) == []
    assert built_payload == sample_payload


def test_req_057_policies_include_escalation_owner_and_fallback_anchors() -> None:
    sample_payload = _read_json(SAMPLE_PATH)
    rows = {row["policy_id"]: row for row in sample_payload["blocker_handling_policy_artifact"]["policies"]}

    rate_limit_policy = rows["policy.cross-project-rate-limit"]
    assert rate_limit_policy["escalation_trigger"] == {
        "trigger_type": "attempts_exhausted",
        "threshold": 3,
        "window": "cycles",
    }
    assert rate_limit_policy["owner_hints"] == ["boss-manager", "runtime-coordinator"]
    assert rate_limit_policy["fallback_paths"] == [
        "pause-and-retry-window",
        "reroute-to-lower-rate-profile",
    ]

    contract_policy = rows["policy.validation-contract-mismatch"]
    assert contract_policy["escalation_trigger"]["trigger_type"] == "guardrail_violation"
    assert contract_policy["owner_hints"] == ["developer-worker", "planner-worker"]
    assert contract_policy["fallback_paths"] == ["open-blocker-ticket", "request-contract-refresh"]


def test_req_057_validator_rejects_missing_fallback_paths() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["blocker_handling_policy_artifact"]["policies"][0]["fallback_paths"] = []

    errors = module.validate_req_057_blocker_handling_policy_artifact(broken)

    assert "blocker_handling_policy_artifact.policies[0].fallback_paths must include at least 1 value(s)" in errors


def test_req_057_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-057_blocker-handling-policy-artifact.sample.json" in contract_text
    for key in (
        "blocker_handling_policy_artifact.policies",
        "blocker_handling_policy_artifact.policies[].escalation_trigger.trigger_type",
        "blocker_handling_policy_artifact.policies[].escalation_trigger.threshold",
        "blocker_handling_policy_artifact.policies[].escalation_trigger.window",
        "blocker_handling_policy_artifact.policies[].owner_hints",
        "blocker_handling_policy_artifact.policies[].fallback_paths",
        "totals",
    ):
        assert key in contract_text


def test_req_057_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_057_builder_rejects_unknown_trigger_type() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"trigger_type"):
        module.build_req_057_blocker_handling_policy_artifact(fixture_payload["invalid_unknown_trigger_input"])
