import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "execution-resource-context-ingestion.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-019_execution-resource-context-ingestion.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-019_execution-resource-context-ingestion.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_019_builder_matches_expected_contract_anchors() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_019_execution_resource_context_ingestion(**fixture["input"])
    assert module.validate_req_019_execution_resource_context_ingestion(payload) == []

    anchors = fixture["expected_contract_anchors"]
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["processing_behavior"]["strategy"] == anchors["strategy"]

    sequencing = payload["resource_policy"]["sequencing_policy_suggestions"]
    assert sequencing["ordered_action_ids"] == anchors["ordered_action_ids"]
    assert sequencing["reason_codes"] == anchors["sequencing_reason_codes"]

    selected_models = {
        row["action_id"]: row["selected_model"]
        for row in payload["resource_policy"]["model_routing_policy_suggestions"]
    }
    assert selected_models == anchors["selected_models_by_action"]


def test_req_019_call_metadata_reproducible_for_identical_input() -> None:
    fixture = _read_json(FIXTURE_PATH)

    first = module.build_req_019_execution_resource_context_ingestion(**fixture["input"])
    second = module.build_req_019_execution_resource_context_ingestion(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]

    changed = dict(fixture["input"])
    changed["revision_identity"] = "rev-req019-fixture-r2"
    changed_payload = module.build_req_019_execution_resource_context_ingestion(**changed)
    assert changed_payload["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed_payload["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]


def test_req_019_sample_payload_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_019_execution_resource_context_ingestion(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-019_execution-resource-context-ingestion.sample.json" in contract_text
