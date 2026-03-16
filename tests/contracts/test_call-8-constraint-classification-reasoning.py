import json
from pathlib import Path

import pytest

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-8-constraint-classification-reasoning.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-033_call-8-constraint-classification-reasoning.sample.json"
)
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-033_call-8-constraint-classification-reasoning.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_033_builder_matches_fixture_expected_payload() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_033_call_8_constraint_classification_reasoning(**fixture["input"])
    assert module.validate_req_033_call_8_constraint_classification_reasoning(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_033_sample_payload_is_valid_and_explicitly_grouped_for_planner() -> None:
    fixture = _read_json(FIXTURE_PATH)
    expected = module.build_req_033_call_8_constraint_classification_reasoning(**fixture["input"])
    sample = _read_json(SAMPLE_PATH)

    assert sample == expected
    assert module.validate_req_033_call_8_constraint_classification_reasoning(sample) == []
    assert sample["schema_version"] == module.REQ_033_SCHEMA_VERSION
    assert sample["requirement_id"] == module.REQ_033_REQUIREMENT_ID
    assert sample["processing_behavior"]["strategy"] == module.REQ_033_STRATEGY
    assert sample["processing_behavior"]["call_8_reasoning"]["call_sequence"] == module.REQ_033_CALL_SEQUENCE
    assert sample["processing_behavior"]["call_8_reasoning"]["hard_constraint_count"] == 2
    assert sample["processing_behavior"]["call_8_reasoning"]["soft_preference_count"] == 1
    assert sample["processing_behavior"]["call_8_reasoning"]["speculative_idea_count"] == 1
    recommendation = sample["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "ready-for-planner"
    assert recommendation["planner_contract"]["classification_is_explicit"] is True
    assert len(recommendation["planner_contract"]["hard_constraints"]) == 2
    assert len(recommendation["planner_contract"]["soft_preferences"]) == 1
    assert len(recommendation["planner_contract"]["speculative_ideas"]) == 1
    assert recommendation["open_risks"] == []
    assert sample["call_metadata"]["llm_call_trace_path"] == module.LLM_CALL_TRACE_RELATIVE_PATH
    assert sample["call_metadata"]["llm_call_trace_rows"][0]["call_objective"] == module.REQ_033_TRACE_CALL_OBJECTIVE
    assert len(sample["call_metadata"]["llm_call_trace_rows"][0]["output_refs"]) == 1 + len(module.REQ_033_TRACE_BUCKET_OUTPUTS)
    for expected_output in (module.REQ_033_TRACE_EXPECTED_OUTPUT, *module.REQ_033_TRACE_BUCKET_OUTPUTS):
        assert any(output_ref.endswith(f"::output::{expected_output}") for output_ref in sample["call_metadata"]["llm_call_trace_rows"][0]["output_refs"])


def test_req_033_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-033_call-8-constraint-classification-reasoning.sample.json" in content
    for key in [
        "schema_version",
        "requirement_id",
        "call_8_constraint_classification_reasoning_entrypoint",
        "processing_behavior",
        "context_inputs",
        "context_usage",
        "call_8_reasoning",
        "classification_reasoning",
        "recommendation",
        "planner_contract",
        "hard_constraints",
        "soft_preferences",
        "speculative_ideas",
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


def test_req_033_rejects_unknown_classification_label() -> None:
    fixture = _read_json(FIXTURE_PATH)
    bad_input = dict(fixture["input"])
    bad_candidate = dict(bad_input["constraint_candidates"][0])
    bad_candidate["classification"] = "mandatory"
    bad_input["constraint_candidates"] = [bad_candidate, *bad_input["constraint_candidates"][1:]]
    with pytest.raises(
        ValueError,
        match=r"classification must be one of: hard-constraint, soft-preference, speculative-idea",
    ):
        module.build_req_033_call_8_constraint_classification_reasoning(**bad_input)
