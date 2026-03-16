import json
from pathlib import Path

import pytest

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-3-gap-and-opportunity-reasoning.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-028_call-3-gap-and-opportunity-reasoning.sample.json"
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-028_call-3-gap-and-opportunity-reasoning.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_028_builder_matches_fixture_expected_payload() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_028_call_3_gap_and_opportunity_reasoning(**fixture["input"])
    assert module.validate_req_028_call_3_gap_and_opportunity_reasoning(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_028_call_metadata_is_reproducible_and_sensitive_to_revision_identity() -> None:
    fixture = _read_json(FIXTURE_PATH)
    first = module.build_req_028_call_3_gap_and_opportunity_reasoning(**fixture["input"])
    second = module.build_req_028_call_3_gap_and_opportunity_reasoning(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]

    changed_input = dict(fixture["input"])
    changed_input["revision_identity"] = "rev-req028-fixture-r2"
    changed = module.build_req_028_call_3_gap_and_opportunity_reasoning(**changed_input)
    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]


def test_req_028_sample_payload_is_valid_contract_shape() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_028_call_3_gap_and_opportunity_reasoning(sample) == []
    assert sample["schema_version"] == module.REQ_028_SCHEMA_VERSION
    assert sample["requirement_id"] == module.REQ_028_REQUIREMENT_ID
    assert sample["processing_behavior"]["strategy"] == module.REQ_028_STRATEGY
    assert sample["processing_behavior"]["call_3_reasoning"]["call_sequence"] == module.REQ_028_CALL_SEQUENCE
    gap_reasoning = sample["processing_behavior"]["call_3_reasoning"]["gap_reasoning"]
    assert gap_reasoning[0]["opportunities"][0]["ecosystem_level_benefit"]
    assert gap_reasoning[0]["opportunities"][0]["dependency_effects"]


def test_req_028_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-028_call-3-gap-and-opportunity-reasoning.sample.json" in content
    for key in [
        "schema_version",
        "requirement_id",
        "call_3_gap_and_opportunity_reasoning_entrypoint",
        "processing_behavior",
        "context_inputs",
        "context_usage",
        "call_3_reasoning",
        "gap_reasoning",
        "opportunities",
        "ecosystem_level_benefit",
        "dependency_effects",
        "call_metadata",
        "canonical_input_sha256",
        "processing_input_sha256",
    ]:
        assert f"`{key}`" in content


def test_req_028_rejects_local_only_gap_reasoning_without_earth_sweep_evidence() -> None:
    fixture = _read_json(FIXTURE_PATH)
    bad_input = dict(fixture["input"])
    bad_input["earth_sweep_evidence_refs"] = []
    with pytest.raises(ValueError, match=r"earth_sweep_evidence_refs must contain at least 1 item"):
        module.build_req_028_call_3_gap_and_opportunity_reasoning(**bad_input)
