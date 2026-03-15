import json
from pathlib import Path

from scripts import strategy_context_sweep as sweep


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "cross-project-dependency-extraction.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-011_cross-project-dependency-extraction.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-011_cross-project-dependency-extraction.md"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req011_extracts_cross_project_dependency_edges_with_confidence_and_evidence_refs() -> None:
    fixture = _load_fixture()
    payload = sweep.build_req_011_cross_project_dependency_extraction(**fixture["input"])
    anchors = fixture["expected_contract_anchors"]

    assert sweep.validate_req_011_cross_project_dependency_extraction(payload) == []
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]

    extraction = payload["cross_project_dependency_extraction"]
    assert extraction["target_project_id"] == anchors["target_project_id"]

    edges = extraction["dependency_edges"]
    assert len(edges) == anchors["summary"]["dependency_edge_count"]

    providers = sorted({row["provider_project_id"] for row in edges})
    assert providers == anchors["provider_project_ids"]

    for edge in edges:
        assert set(anchors["required_edge_fields"]).issubset(edge.keys())
        assert edge["consumer_project_id"] != edge["provider_project_id"]
        assert edge["confidence"] in {"high", "medium", "low"}
        assert isinstance(edge["evidence_refs"], list) and edge["evidence_refs"]

    by_provider = {edge["provider_project_id"]: edge for edge in edges}
    assert by_provider["prj.runtime-core"]["confidence"] == "high"
    assert by_provider["prj.runtime-core"]["hard_dependency"] is True
    assert by_provider["prj.runtime-observability"]["confidence"] == "low"
    assert by_provider["prj.runtime-observability"]["hard_dependency"] is False

    open_risk_reason_codes = sorted({row["reason_code"] for row in extraction["open_risks"]})
    assert open_risk_reason_codes == anchors["open_risk_reason_codes"]

    summary = extraction["summary"]
    for key, value in anchors["summary"].items():
        assert summary[key] == value


def test_req011_call_metadata_is_reproducible_for_identical_invocations() -> None:
    fixture = _load_fixture()
    first = sweep.build_req_011_cross_project_dependency_extraction(**fixture["input"])
    second = sweep.build_req_011_cross_project_dependency_extraction(**fixture["input"])

    assert first["call_metadata"] == second["call_metadata"]

    probe = fixture["determinism_probe"]
    changed_input = {
        **fixture["input"],
        "integration_point_signals": [
            *fixture["input"]["integration_point_signals"],
            *probe["append_integration_point_signals"],
        ],
    }
    changed = sweep.build_req_011_cross_project_dependency_extraction(**changed_input)

    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]
    assert changed["call_metadata"]["processing_input_sha256"] != first["call_metadata"]["processing_input_sha256"]

    first_edges = {
        row["provider_project_id"]: row for row in first["cross_project_dependency_extraction"]["dependency_edges"]
    }
    changed_edges = {
        row["provider_project_id"]: row for row in changed["cross_project_dependency_extraction"]["dependency_edges"]
    }
    provider_project_id = probe["expected_changed_provider_project_id"]
    assert first_edges[provider_project_id]["confidence"] == probe["baseline_confidence"]
    assert changed_edges[provider_project_id]["confidence"] == probe["changed_confidence"]


def test_req011_fixture_and_sample_validate_against_contract() -> None:
    fixture_payload = sweep.build_req_011_cross_project_dependency_extraction(**_load_fixture()["input"])
    sample_payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))

    assert sweep.validate_req_011_cross_project_dependency_extraction(fixture_payload) == []
    assert sweep.validate_req_011_cross_project_dependency_extraction(sample_payload) == []
    assert set(fixture_payload.keys()) == set(sample_payload.keys())


def test_req011_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-011_cross-project-dependency-extraction.sample.json" in contract_text
