import json
from pathlib import Path

import pytest

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-7-blocker-and-risk-policy-reasoning.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json"
)
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-032_call-7-blocker-and-risk-policy-reasoning.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_032_builder_matches_fixture_expected_payload() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_032_call_7_blocker_and_risk_policy_reasoning(**fixture["input"])
    assert module.validate_req_032_call_7_blocker_and_risk_policy_reasoning(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_032_sample_matches_builder_output_and_contains_escalation_and_fallback_paths() -> None:
    fixture = _read_json(FIXTURE_PATH)
    expected = module.build_req_032_call_7_blocker_and_risk_policy_reasoning(**fixture["input"])
    sample = _read_json(SAMPLE_PATH)

    assert sample == expected
    assert module.validate_req_032_call_7_blocker_and_risk_policy_reasoning(sample) == []
    assert sample["schema_version"] == module.REQ_032_SCHEMA_VERSION
    assert sample["requirement_id"] == module.REQ_032_REQUIREMENT_ID
    assert sample["processing_behavior"]["strategy"] == module.REQ_032_STRATEGY
    assert sample["processing_behavior"]["call_7_reasoning"]["call_sequence"] == module.REQ_032_CALL_SEQUENCE
    assert sample["processing_behavior"]["call_7_reasoning"]["blocker_count"] == 2
    assert sample["processing_behavior"]["recommendation"]["decision"] == "fallback-then-escalate"
    assert sample["processing_behavior"]["recommendation"]["escalation_triggers"]
    assert sample["processing_behavior"]["recommendation"]["fallback_sequence"]
    assert sample["call_metadata"]["llm_call_trace_path"] == module.LLM_CALL_TRACE_RELATIVE_PATH
    assert sample["call_metadata"]["llm_call_trace_rows"][0]["call_objective"] == module.REQ_032_TRACE_CALL_OBJECTIVE


def test_req_032_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-032_call-7-blocker-and-risk-policy-reasoning.sample.json" in content
    for key in [
        "schema_version",
        "requirement_id",
        "call_7_blocker_and_risk_policy_reasoning_entrypoint",
        "processing_behavior",
        "context_inputs",
        "blocker_candidates",
        "risk_policy_candidates",
        "context_usage",
        "call_7_reasoning",
        "blocker_reasoning",
        "escalation_triggers",
        "fallback_paths",
        "applicable_policies",
        "recommendation",
        "fallback_sequence",
        "open_risks",
        "call_metadata",
        "canonical_input_sha256",
        "processing_input_sha256",
        "llm_call_trace_path",
        "llm_call_trace_rows",
        "call_objective",
        "input_refs",
        "output_refs",
        "handoff_summary",
    ]:
        assert f"`{key}`" in content


def test_req_032_rejects_policy_without_known_blocker() -> None:
    fixture = _read_json(FIXTURE_PATH)
    bad_input = dict(fixture["input"])
    bad_policy = dict(bad_input["risk_policy_candidates"][0])
    bad_policy["blocker_id"] = "blocker.missing"
    bad_input["risk_policy_candidates"] = [bad_policy, *bad_input["risk_policy_candidates"][1:]]
    with pytest.raises(ValueError, match=r"blocker_id must reference a known blocker_id"):
        module.build_req_032_call_7_blocker_and_risk_policy_reasoning(**bad_input)
