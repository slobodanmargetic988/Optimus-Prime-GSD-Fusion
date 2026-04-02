import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-feasibility-scoring.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-040_recommendation-feasibility-scoring.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-040_recommendation-feasibility-scoring.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_040_builder_matches_expected_contract_anchors() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_040_recommendation_feasibility_scoring(**fixture["input"])
    anchors = fixture["expected_contract_anchors"]

    assert module.validate_req_040_recommendation_feasibility_scoring(payload) == []
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["processing_behavior"]["strategy"] == anchors["strategy"]
    assert payload["sequencing_policy"]["ordered_recommendation_ids"] == anchors["ordered_recommendation_ids"]
    assert payload["sequencing_policy"]["reason_codes"] == anchors["sequencing_reason_codes"]
    assert payload["risk_policy"]["global_policy"] == anchors["global_risk_policy"]
    assert payload["feasibility_assessment"]["overall_feasibility_score"] == anchors["overall_feasibility_score"]
    assert payload["feasibility_assessment"]["score_breakdown"] == anchors["score_breakdown"]

    rows = {
        row["recommendation_id"]: row
        for row in payload["feasibility_assessment"]["recommendations"]
    }
    assert {
        recommendation_id: rows[recommendation_id]["feasibility_label"]
        for recommendation_id in sorted(rows)
    } == anchors["feasibility_labels"]
    assert {
        recommendation_id: rows[recommendation_id]["risk_policy"]
        for recommendation_id in sorted(rows)
    } == anchors["risk_policies"]


def test_req_040_feasibility_controls_sequencing_and_risk_policy() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_040_recommendation_feasibility_scoring(**fixture["input"])

    recommendation_rows = {
        row["recommendation_id"]: row
        for row in payload["feasibility_assessment"]["recommendations"]
    }

    assert recommendation_rows["rec.enable-read-path"]["sequencing_bucket"] == "immediate"
    assert recommendation_rows["rec.enable-read-path"]["risk_policy"] == "standard"

    assert recommendation_rows["rec.expand-write-path"]["sequencing_bucket"] == "defer"
    assert recommendation_rows["rec.expand-write-path"]["risk_policy"] == "defer-until-controls"
    assert "resource_constraint_exceeded" in recommendation_rows["rec.expand-write-path"]["reason_codes"]

    open_risk_ids = {row["recommendation_id"] for row in payload["risk_policy"]["open_risks"]}
    assert "rec.expand-write-path" in open_risk_ids


def test_req_040_call_metadata_reproducibility_behavior() -> None:
    fixture = _read_json(FIXTURE_PATH)

    first = module.build_req_040_recommendation_feasibility_scoring(**fixture["input"])
    second = module.build_req_040_recommendation_feasibility_scoring(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]

    changed_input = dict(fixture["input"])
    changed_input["dependency_readiness"] = [
        *fixture["input"]["dependency_readiness"],
        fixture["determinism_probe"]["append_dependency"],
    ]
    changed = module.build_req_040_recommendation_feasibility_scoring(**changed_input)

    assert changed["call_metadata"]["canonical_input_sha256"] == first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] == first["call_metadata"]["reproducible_call_id"]
    assert changed["call_metadata"]["processing_input_sha256"] != first["call_metadata"]["processing_input_sha256"]


def test_req_040_sample_payload_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_040_recommendation_feasibility_scoring(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-040_recommendation-feasibility-scoring.sample.json" in contract_text
    for key in [
        "schema_version",
        "requirement_id",
        "recommendation_feasibility_scoring",
        "processing_behavior",
        "feasibility_assessment",
        "sequencing_policy",
        "risk_policy",
        "context_bundle",
        "call_metadata",
    ]:
        assert f"`{key}`" in contract_text
