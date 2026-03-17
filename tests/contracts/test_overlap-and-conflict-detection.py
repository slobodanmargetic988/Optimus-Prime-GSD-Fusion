import json
from pathlib import Path

import pytest

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "overlap-and-conflict-detection.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-017_overlap-and-conflict-detection.sample.json"
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-017_overlap-and-conflict-detection.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_017_builder_emits_overlap_and_conflict_rows_with_resolution_options() -> None:
    fixture = _read_json(FIXTURE_PATH)
    output = module.build_req_017_overlap_and_conflict_detection(**fixture["input"])

    assert module.validate_req_017_overlap_and_conflict_detection(output) == []

    anchors = fixture["expected_contract_anchors"]
    assert output["schema_version"] == anchors["schema_version"]
    assert output["requirement_id"] == anchors["requirement_id"]
    assert output["target_project"]["project_id"] == anchors["target_project_id"]
    assert output["source"]["normalized_at_utc"] == anchors["normalized_at_utc"]
    assert output["decision"] == anchors["expected_decision"]
    assert output["source"]["context_bundle_sha256"] == anchors["context_bundle_sha256"]

    assert [row["overlap_id"] for row in output["overlaps"]] == anchors["overlap_ids"]
    assert [row["conflict_id"] for row in output["conflicts"]] == anchors["conflict_ids"]
    assert [row["topic"] for row in output["conflicts"]] == anchors["conflict_topics"]

    conflict = output["conflicts"][0]
    options = conflict["resolution_options"]
    assert options
    assert options[0]["recommended"] is True
    for option in options:
        assert set(option.keys()) == set(anchors["required_resolution_option_fields"])
        assert option["risk_level"] in {"low", "medium", "high"}
        assert option["tradeoffs"]


def test_req_017_sample_matches_builder_output_for_fixture() -> None:
    fixture = _read_json(FIXTURE_PATH)
    expected = module.build_req_017_overlap_and_conflict_detection(**fixture["input"])
    sample = _read_json(SAMPLE_PATH)
    assert sample == expected


def test_req_017_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-017_overlap-and-conflict-detection.sample.json" in content
    for key in [
        "schema_version",
        "requirement_id",
        "target_project",
        "projects_considered",
        "overlaps",
        "conflicts",
        "evidence_refs",
        "decision",
        "summary",
        "source",
    ]:
        assert f"`{key}`" in content


def test_req_017_rejects_invalid_initiative_date_format() -> None:
    fixture = _read_json(FIXTURE_PATH)
    bad_input = dict(fixture["input"])
    initiatives = list(bad_input["initiatives"])
    first = dict(initiatives[0])
    first["start_date"] = "2026/03/01"
    initiatives[0] = first
    bad_input["initiatives"] = initiatives

    with pytest.raises(ValueError, match=r"YYYY-MM-DD"):
        module.build_req_017_overlap_and_conflict_detection(**bad_input)

