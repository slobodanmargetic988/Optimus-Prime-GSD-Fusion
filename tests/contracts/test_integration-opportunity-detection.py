import json
from pathlib import Path

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "integration-opportunity-detection.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-015_integration-opportunity-detection.sample.json"
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-015_integration-opportunity-detection.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_015_builder_normalizes_expected_contract_anchors():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_015_integration_opportunity_detection(**fixture["input"])
    assert module.validate_req_015_integration_opportunity_detection(payload) == []

    anchors = fixture["expected_contract_anchors"]
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["target_project"]["project_id"] == anchors["target_project_id"]
    assert payload["source"]["normalized_at_utc"] == anchors["normalized_at_utc"]

    opportunities = payload["integration_opportunities"]
    assert [row["integration_opportunity_id"] for row in opportunities] == anchors["integration_opportunity_ids"]
    assert [row["peer_project_id"] for row in opportunities] == anchors["peer_project_ids"]

    expected_fields = anchors["required_interaction_contract_fields"]
    for row in opportunities:
        contract = row["expected_interaction_contract"]
        assert sorted(contract.keys()) == sorted(expected_fields)
        assert row["dependency_side_effect_notes"]
        assert row["evidence_refs"]
        assert row["target_project_id"] == anchors["target_project_id"]
        assert row["peer_project_id"] != anchors["target_project_id"]


def test_req_015_sample_payload_and_contract_doc_are_aligned():
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_015_integration_opportunity_detection(sample) == []

    fixture = _read_json(FIXTURE_PATH)
    rebuilt = module.build_req_015_integration_opportunity_detection(**fixture["input"])
    assert sample == rebuilt

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-015_integration-opportunity-detection.sample.json" in contract_text
