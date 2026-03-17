import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "existing-functionality-interaction-reasoning.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-042_existing-functionality-interaction-reasoning.sample.json"
)
CONTRACT_DOC_PATH = (
    REPO_ROOT / "contracts" / "req" / "REQ-042_existing-functionality-interaction-reasoning.md"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_042_builder_matches_fixture_expected_payload() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_042_existing_functionality_interaction_reasoning(**fixture["input"])
    assert module.validate_req_042_existing_functionality_interaction_reasoning(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_042_sample_matches_fixture_payload_and_is_valid() -> None:
    fixture = _read_json(FIXTURE_PATH)
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_042_existing_functionality_interaction_reasoning(sample) == []
    assert sample == fixture["expected_payload"]
    assert sample["selected_path"]["decision"] == "consume_existing_functionality"
    assert sample["selected_path"]["selected_candidate_id"] == "reuse-detector-adapter"


def test_req_042_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-042_existing-functionality-interaction-reasoning.sample.json" in content
    for key in [
        "requirement_id",
        "surface",
        "schema_version",
        "evaluated_at",
        "active_project_id",
        "capability_need",
        "build_new_assessment",
        "interaction_reasoning",
        "required_interfaces",
        "provided_interfaces",
        "missing_interfaces",
        "compatibility_state",
        "compatibility_checks",
        "integration_burden",
        "candidate_decision",
        "decision_rationale",
        "selected_path",
        "selected_candidate_id",
        "processing_behavior",
        "context_inputs",
        "context_usage",
        "existing_functionality_reasoning",
        "candidate_assessments",
        "recommendation",
        "reuse_candidates",
        "cross_project_obligations",
        "open_risks",
        "evidence_refs",
        "summary",
    ]:
        assert f"`{key}`" in content


def test_req_042_prefers_build_new_when_new_work_is_lower_burden() -> None:
    fixture = _read_json(FIXTURE_PATH)
    mutated_input = dict(fixture["input"])
    mutated_build_new = dict(mutated_input["build_new_assessment"])
    mutated_build_new["estimated_burden"] = "low"
    mutated_input["build_new_assessment"] = mutated_build_new

    payload = module.build_req_042_existing_functionality_interaction_reasoning(**mutated_input)

    assert payload["selected_path"]["decision"] == "build_new_capability"
    assert payload["selected_path"]["selected_candidate_id"] is None
    compatible_row = next(row for row in payload["interaction_reasoning"] if row["candidate_id"] == "reuse-detector-adapter")
    assert compatible_row["compatibility_state"] == "compatible"
    assert compatible_row["candidate_decision"] == "build_new_capability"


def test_req_042_uses_followup_when_no_candidate_is_fully_compatible() -> None:
    fixture = _read_json(FIXTURE_PATH)
    mutated_input = dict(fixture["input"])
    candidates = [dict(row) for row in mutated_input["existing_functionality_candidates"]]
    compatible_candidate = dict(candidates[0])
    compatible_checks = [dict(row) for row in compatible_candidate["compatibility_checks"]]
    compatible_checks[0]["status"] = "unknown"
    compatible_candidate["compatibility_checks"] = compatible_checks
    candidates[0] = compatible_candidate
    mutated_input["existing_functionality_candidates"] = candidates

    payload = module.build_req_042_existing_functionality_interaction_reasoning(**mutated_input)

    assert payload["selected_path"]["decision"] == "investigate_existing_functionality"
    assert payload["selected_path"]["selected_candidate_id"] is None
    assert all(row["compatibility_state"] != "compatible" for row in payload["interaction_reasoning"])
