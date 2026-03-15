import json
from pathlib import Path

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "context-confidence-scoring.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-022_context-confidence-scoring.sample.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_022_builder_matches_fixture_expected_payload():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_022_context_confidence_scoring(**fixture["input"])
    assert module.validate_req_022_context_confidence_scoring(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_022_call_metadata_is_reproducible_for_identical_invocations():
    fixture = _read_json(FIXTURE_PATH)
    first = module.build_req_022_context_confidence_scoring(**fixture["input"])
    second = module.build_req_022_context_confidence_scoring(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]

    changed_revision_input = dict(fixture["input"])
    changed_revision_input["revision_identity"] = "rev-req022-fixture-r2"
    changed = module.build_req_022_context_confidence_scoring(**changed_revision_input)
    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]


def test_req_022_sample_payload_is_valid_contract_shape():
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_022_context_confidence_scoring(sample) == []
    assert sample["schema_version"] == module.REQ_022_SCHEMA_VERSION
    assert sample["requirement_id"] == module.REQ_022_REQUIREMENT_ID
    assert sample["processing_behavior"]["strategy"] == "context-confidence-scoring-broad-sweep"
    assert "context_confidence" in sample["processing_behavior"]

