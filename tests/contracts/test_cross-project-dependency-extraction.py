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
TASK_EVIDENCE_PATH = (
    REPO_ROOT
    / "reports"
    / "optimus-prime"
    / "planning"
    / "evidence"
    / "TASK-033"
    / "TASK_EVIDENCE.json"
)


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

    changed_input = dict(fixture["input"])
    changed_input["target_project_id"] = "prj.optimus-prime-gsd-fusion-variant"
    changed = sweep.build_req_011_cross_project_dependency_extraction(**changed_input)

    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]


def test_req011_fixture_and_sample_validate_against_contract() -> None:
    fixture_payload = sweep.build_req_011_cross_project_dependency_extraction(**_load_fixture()["input"])
    sample_payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))

    assert sweep.validate_req_011_cross_project_dependency_extraction(fixture_payload) == []
    assert sweep.validate_req_011_cross_project_dependency_extraction(sample_payload) == []
    assert set(fixture_payload.keys()) == set(sample_payload.keys())


def test_req011_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-011_cross-project-dependency-extraction.sample.json" in contract_text


def test_req011_task_evidence_machine_readable_blockers_shape() -> None:
    payload = json.loads(TASK_EVIDENCE_PATH.read_text(encoding="utf-8"))

    assert payload["task_id"] == "TASK-033"
    assert payload["requirement_ids"] == ["REQ-011"]
    assert payload["summary"]["result"] == "pass"
    assert payload["summary"]["expectation_met"] is True
    assert payload["gate"]["ready_for_test"] is True
    assert payload["dev"]["blockers"] == []
    assert payload["test"]["blockers"] == []
    assert payload["review"]["blockers"] == []

    checks = payload["dev"]["checks"]
    assert checks and all(isinstance(row, dict) and isinstance(row.get("passed"), bool) for row in checks)

    edge_case_blockers = payload["dev"]["edge_case_blockers"]
    assert isinstance(edge_case_blockers, list) and edge_case_blockers
    assert all(isinstance(row, dict) and row.get("unresolved_blockers") == [] for row in edge_case_blockers)
