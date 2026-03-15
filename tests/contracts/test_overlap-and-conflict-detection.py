import json
from pathlib import Path

import pytest

from scripts.strategy_context_sweep import detect_overlap_and_conflicts


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "overlap-and-conflict-detection.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-017_overlap-and-conflict-detection.sample.json"
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-017_overlap-and-conflict-detection.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_017_detects_overlaps_and_conflicts_with_resolution_tradeoffs() -> None:
    payload = _read_json(FIXTURE_PATH)
    output = detect_overlap_and_conflicts(payload, evaluated_at="2026-03-15T03:10:00Z")

    assert set(output.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "evaluated_at",
        "active_project_id",
        "related_project_ids",
        "overlap_index",
        "overlapping_initiatives",
        "conflicting_directions",
        "evidence_refs",
        "decision",
        "summary",
    }
    assert output["requirement_id"] == "REQ-017"
    assert output["surface"] == "overlap_and_conflict_detection"
    assert output["schema_version"] == "req-017.overlap-and-conflict-detection.v1"
    assert output["evaluated_at"] == "2026-03-15T03:10:00Z"
    assert output["decision"] == "conflicts_detected"

    overlaps = output["overlapping_initiatives"]
    conflicts = output["conflicting_directions"]
    assert len(overlaps) == 2
    assert len(conflicts) == 2
    assert {row["risk_level"] for row in conflicts} == {"high", "medium"}

    for conflict in conflicts:
        assert conflict["resolution_options"]
        for option in conflict["resolution_options"]:
            assert option["option_id"]
            assert option["summary"]
            assert option["risk_tradeoff"]


def test_req_017_sample_matches_detection_output_for_fixture() -> None:
    payload = _read_json(FIXTURE_PATH)
    expected = detect_overlap_and_conflicts(payload, evaluated_at="2026-03-15T03:10:00Z")
    sample = _read_json(SAMPLE_PATH)
    assert sample == expected


def test_req_017_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-017_overlap-and-conflict-detection.sample.json" in content
    for key in [
        "requirement_id",
        "surface",
        "schema_version",
        "evaluated_at",
        "active_project_id",
        "related_project_ids",
        "overlap_index",
        "overlapping_initiatives",
        "conflicting_directions",
        "evidence_refs",
        "decision",
        "summary",
    ]:
        assert f"`{key}`" in content


def test_req_017_rejects_initiative_project_outside_related_scope() -> None:
    payload = _read_json(FIXTURE_PATH)
    bad_payload = dict(payload)
    initiatives = list(bad_payload["initiatives"])
    first = dict(initiatives[0])
    first["project_id"] = "unrelated-project"
    initiatives[0] = first
    bad_payload["initiatives"] = initiatives

    with pytest.raises(ValueError, match=r"active_project_id or related_project_ids"):
        detect_overlap_and_conflicts(bad_payload, evaluated_at="2026-03-15T03:10:00Z")
