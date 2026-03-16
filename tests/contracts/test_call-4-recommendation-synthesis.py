import json
from pathlib import Path

import pytest

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-4-recommendation-synthesis.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-029_call-4-recommendation-synthesis.sample.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "req"
    / "REQ-029_call-4-recommendation-synthesis.md"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_029_builder_emits_bounded_recommendation_drafts() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_029_call_4_recommendation_synthesis(**fixture["input"])

    assert module.validate_req_029_call_4_recommendation_synthesis(payload) == []

    anchors = fixture["expected_contract_anchors"]
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["checked_at_utc"] == anchors["checked_at_utc"]

    synthesis = payload["recommendation_synthesis"]
    assert synthesis["target_project"]["project_id"] == anchors["project_id"]
    assert synthesis["source_calls"] == anchors["source_calls"]
    assert [row["recommendation_id"] for row in synthesis["recommendation_drafts"]] == anchors["recommendation_ids"]
    assert synthesis["summary"]["candidate_recommendation_count"] == anchors["candidate_recommendation_count"]
    assert synthesis["summary"]["source_call_count"] == anchors["source_call_count"]
    assert synthesis["summary"]["draft_count"] == anchors["candidate_recommendation_count"]

    processing = payload["processing_behavior"]
    assert processing["strategy"] == anchors["processing_strategy"]
    assert processing["reasoning_mode"] == anchors["reasoning_mode"]
    assert processing["strict_evidence_discipline"] is True
    assert processing["synthesis_rules"]["recommendation_id_schema"] == anchors["recommendation_id_schema"]
    assert processing["synthesis_rules"]["required_draft_fields"] == anchors["required_draft_fields"]
    assert payload["source"]["evidence_ref_count"] == anchors["evidence_ref_count"]

    for row in synthesis["recommendation_drafts"]:
        assert row["recommendation_id"].startswith("rec-call-4-")
        assert row["rationale"]
        assert row["impact"]
        assert row["risk"]


def test_req_029_sample_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_029_call_4_recommendation_synthesis(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-029_call-4-recommendation-synthesis.sample.json" in contract_text


def test_req_029_rejects_candidate_ids_outside_slug_schema() -> None:
    fixture = _read_json(FIXTURE_PATH)
    fixture["input"]["earlier_call_outputs"][0]["candidate_recommendations"][0]["candidate_id"] = "Bad_ID"

    with pytest.raises(module.Req029Error, match="candidate_id must match"):
        module.build_req_029_call_4_recommendation_synthesis(**fixture["input"])
