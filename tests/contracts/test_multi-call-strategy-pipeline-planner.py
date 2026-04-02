import json
from pathlib import Path

import pytest

from scripts import strategy_llm_pipeline as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "multi-call-strategy-pipeline-planner.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-025_multi-call-strategy-pipeline-planner.sample.json"
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-025_multi-call-strategy-pipeline-planner.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_025_builder_matches_fixture_expected_payload() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_025_multi_call_strategy_pipeline_planner(**fixture["input"])
    assert module.validate_req_025_multi_call_strategy_pipeline_planner(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_025_call_metadata_is_reproducible_and_depth_sensitive() -> None:
    fixture = _read_json(FIXTURE_PATH)
    first = module.build_req_025_multi_call_strategy_pipeline_planner(**fixture["input"])
    second = module.build_req_025_multi_call_strategy_pipeline_planner(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]
    assert first["call_metadata"]["llm_call_trace_rows"] == second["call_metadata"]["llm_call_trace_rows"]

    changed_depth_input = dict(fixture["input"])
    changed_depth_input["call_depth"] = 3
    changed_depth = module.build_req_025_multi_call_strategy_pipeline_planner(**changed_depth_input)
    assert changed_depth["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed_depth["call_metadata"]["processing_input_sha256"] != first["call_metadata"]["processing_input_sha256"]
    assert changed_depth["call_metadata"]["llm_call_trace_sha256"] != first["call_metadata"]["llm_call_trace_sha256"]
    assert changed_depth["processing_behavior"]["pipeline_plan"]["total_calls"] == 3


def test_req_025_sample_payload_is_valid_contract_shape() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_025_multi_call_strategy_pipeline_planner(sample) == []
    assert sample["schema_version"] == module.REQ_025_SCHEMA_VERSION
    assert sample["requirement_id"] == module.REQ_025_REQUIREMENT_ID
    assert sample["processing_behavior"]["strategy"] == "multi-call-strategy-pipeline-planner"
    assert sample["processing_behavior"]["strict_evidence_discipline"] is True
    assert sample["multi_call_strategy_pipeline_planner_entrypoint"]["call_depth"] == sample["processing_behavior"][
        "pipeline_plan"
    ]["total_calls"]
    assert sample["call_metadata"]["llm_call_trace_path"] == module.LLM_CALL_TRACE_RELATIVE_PATH
    assert len(sample["call_metadata"]["llm_call_trace_rows"]) == sample["processing_behavior"]["pipeline_plan"]["total_calls"]
    assert sample["call_metadata"]["llm_call_trace_rows"][0]["call_objective"] == sample["processing_behavior"][
        "pipeline_plan"
    ]["calls"][0]["purpose"]


def test_req_025_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-025_multi-call-strategy-pipeline-planner.sample.json" in content
    for key in [
        "schema_version",
        "requirement_id",
        "multi_call_strategy_pipeline_planner_entrypoint",
        "processing_behavior",
        "call_metadata",
        "pipeline_plan",
        "calls",
        "depends_on",
        "expected_output",
        "llm_call_trace_path",
        "llm_call_trace_rows",
        "call_objective",
        "input_refs",
        "output_refs",
        "handoff_summary",
    ]:
        assert f"`{key}`" in content


def test_req_025_rejects_missing_evidence_refs_under_strict_discipline() -> None:
    fixture = _read_json(FIXTURE_PATH)
    bad_input = dict(fixture["input"])
    bad_input["evidence_refs"] = []
    with pytest.raises(ValueError, match=r"evidence_refs must contain at least 1 item"):
        module.build_req_025_multi_call_strategy_pipeline_planner(**bad_input)
