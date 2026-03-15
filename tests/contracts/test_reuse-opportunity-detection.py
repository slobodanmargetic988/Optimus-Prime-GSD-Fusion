import json
from pathlib import Path

import pytest

from scripts.strategy_context_sweep import detect_reuse_opportunities


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "reuse-opportunity-detection.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-016_reuse-opportunity-detection.sample.json"
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-016_reuse-opportunity-detection.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_016_detects_reuse_opportunities_with_adoption_and_constraints() -> None:
    payload = _read_json(FIXTURE_PATH)
    output = detect_reuse_opportunities(payload, evaluated_at="2026-03-15T01:30:00Z")

    assert set(output.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "evaluated_at",
        "active_project_id",
        "reuse_index",
        "reuse_recommendations",
        "no_reuse_detected",
        "evidence_refs",
        "decision",
        "summary",
    }
    assert output["requirement_id"] == "REQ-016"
    assert output["surface"] == "reuse_opportunity_detection"
    assert output["schema_version"] == "req-016.reuse-opportunity-detection.v1"
    assert output["evaluated_at"] == "2026-03-15T01:30:00Z"
    assert output["decision"] == "partial_reuse_recommended"

    recommendations = output["reuse_recommendations"]
    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation["capability_id"] == "ground-graph-snapshot-ingestion"
    assert recommendation["required_interfaces"] == ["json-canonical-v1", "lineage-anchor-index"]

    reuse_candidates = recommendation["reuse_candidates"]
    assert len(reuse_candidates) == 1
    candidate = reuse_candidates[0]
    assert candidate["source_project_id"] != output["active_project_id"]
    assert candidate["adoption_path"]
    assert candidate["compatibility_constraints"]

    assert output["no_reuse_detected"] == [
        {
            "capability_id": "reuse-signal-ranking",
            "intent": "Reuse ranking heuristics for cross-project recommendation ordering.",
            "required_interfaces": ["risk-weight-v2"],
            "reason": "no_compatible_existing_functionality",
        }
    ]


def test_req_016_sample_matches_detection_output_for_fixture() -> None:
    payload = _read_json(FIXTURE_PATH)
    expected = detect_reuse_opportunities(payload, evaluated_at="2026-03-15T01:30:00Z")
    sample = _read_json(SAMPLE_PATH)
    assert sample == expected


def test_req_016_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-016_reuse-opportunity-detection.sample.json" in content
    for key in [
        "requirement_id",
        "surface",
        "schema_version",
        "evaluated_at",
        "active_project_id",
        "reuse_index",
        "reuse_recommendations",
        "no_reuse_detected",
        "evidence_refs",
        "decision",
        "summary",
    ]:
        assert f"`{key}`" in content


def test_req_016_rejects_active_project_as_reuse_source() -> None:
    payload = _read_json(FIXTURE_PATH)
    bad_payload = dict(payload)
    existing_functionality = list(bad_payload["existing_functionality"])
    first = dict(existing_functionality[0])
    first["source_project_id"] = payload["active_project_id"]
    existing_functionality[0] = first
    bad_payload["existing_functionality"] = existing_functionality

    with pytest.raises(ValueError, match=r"other apps"):
        detect_reuse_opportunities(bad_payload, evaluated_at="2026-03-15T01:30:00Z")
