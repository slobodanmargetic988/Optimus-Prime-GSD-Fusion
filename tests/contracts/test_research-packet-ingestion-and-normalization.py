import json
from pathlib import Path

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "research-packet-ingestion-and-normalization.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-008_research-packet-ingestion-and-normalization.sample.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "req"
    / "REQ-008_research-packet-ingestion-and-normalization.md"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_008_builder_normalizes_expected_contract_anchors():
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_008_research_packet_ingestion_and_normalization(**fixture["input"])
    assert module.validate_req_008_research_packet_ingestion_and_normalization(payload) == []

    anchors = fixture["expected_contract_anchors"]
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["research_packet_identity"]["event_id"] == anchors["research_event_id"]
    assert payload["source"]["normalized_at_utc"] == anchors["normalized_at_utc"]

    assumptions = payload["strategy_context"]["assumptions"]
    unknowns = payload["strategy_context"]["unknowns"]
    risks = payload["strategy_context"]["risk_evidence"]

    assert [row["assumption_id"] for row in assumptions] == anchors["assumption_ids"]
    assert [row["unknown_id"] for row in unknowns] == anchors["unknown_ids"]
    assert [row["risk_evidence_id"] for row in risks] == anchors["risk_evidence_ids"]
    assert [row["cross_project_context_id"] for row in payload["strategy_context"]["cross_project_context"]] == anchors[
        "cross_project_context_ids"
    ]
    assert [row["open_risk_id"] for row in payload["strategy_context"]["open_risks"]] == anchors["open_risk_ids"]

    by_recommendation = {
        row["recommendation_id"]: row for row in payload["recommendation_rationale_provenance"]
    }
    for expected_row in anchors["recommendation_rationale_links"]:
        row = by_recommendation[expected_row["recommendation_id"]]
        assert row["rationale_field"] == "rationale"
        assert row["linked_assumption_ids"] == expected_row["linked_assumption_ids"]
        assert row["linked_risk_evidence_ids"] == expected_row["linked_risk_evidence_ids"]
        assert row["research_provenance"]["linked_topic_ids"] == expected_row["linked_topic_ids"]
        assert row["linked_cross_project_context_ids"] == expected_row["linked_cross_project_context_ids"]
        assert row["linked_open_risk_ids"] == expected_row["linked_open_risk_ids"]
        assert row["recommendation_fields"] == expected_row["recommendation_fields"]


def test_req_008_sample_payload_and_contract_doc_are_aligned():
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_008_research_packet_ingestion_and_normalization(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-008_research-packet-ingestion-and-normalization.sample.json" in contract_text


def test_req_008_cli_writes_contract_valid_payload(tmp_path: Path):
    fixture = _read_json(FIXTURE_PATH)
    input_path = tmp_path / "req008-input.json"
    input_path.write_text(json.dumps(fixture["input"], indent=2) + "\n", encoding="utf-8")

    output_path = tmp_path / "req008-output.json"
    exit_code = module.main(
        [
            "--input-json",
            str(input_path),
            "--output-json",
            str(output_path),
            "--json-pretty",
        ]
    )
    assert exit_code == 0

    output_payload = _read_json(output_path)
    assert module.validate_req_008_research_packet_ingestion_and_normalization(output_payload) == []

    risk_artifact_ids = {
        ref["artifact_id"]
        for risk_row in output_payload["strategy_context"]["risk_evidence"]
        for ref in risk_row["evidence_refs"]
    }
    for row in output_payload["recommendation_rationale_provenance"]:
        linked_unknown_ids = row["linked_unknown_ids"]
        assert linked_unknown_ids == ["unknown.001", "unknown.002"]
        row_artifact_ids = {ref["artifact_id"] for ref in row["provenance_refs"]}
        assert row_artifact_ids == risk_artifact_ids
