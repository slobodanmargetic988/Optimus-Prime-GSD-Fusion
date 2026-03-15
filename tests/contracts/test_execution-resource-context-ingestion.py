import json
from pathlib import Path

import pytest

from scripts import strategy_context_sweep as module

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "execution-resource-context-ingestion.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-019_execution-resource-context-ingestion.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-019_execution-resource-context-ingestion.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_019_builder_matches_fixture_expected_payload() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_019_execution_resource_context_ingestion(**fixture["input"])
    assert module.validate_req_019_execution_resource_context_ingestion(payload) == []
    assert payload == fixture["expected_payload"]


def test_req_019_call_metadata_is_reproducible_for_identical_invocations() -> None:
    fixture = _read_json(FIXTURE_PATH)
    first = module.build_req_019_execution_resource_context_ingestion(**fixture["input"])
    second = module.build_req_019_execution_resource_context_ingestion(**fixture["input"])
    assert first["call_metadata"] == second["call_metadata"]

    changed_input = dict(fixture["input"])
    changed_input["revision_identity"] = "rev-req019-fixture-r2"
    changed = module.build_req_019_execution_resource_context_ingestion(**changed_input)
    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]


def test_req_019_sample_payload_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_019_execution_resource_context_ingestion(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-019_execution-resource-context-ingestion.sample.json" in contract_text


def test_req_019_resource_context_shapes_sequencing_and_model_routing() -> None:
    sample = _read_json(SAMPLE_PATH)
    recommendation = sample["processing_behavior"]["recommendation"]
    usage = sample["processing_behavior"]["context_usage"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "sequencing_policy_suggestions",
        "model_routing_policy_suggestions",
        "cross_project_context",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "proceed-with-constraints"
    assert usage["effective_parallel_slots_used"] == 2
    assert usage["sequencing_batch_count"] == 2
    assert usage["cross_project_context_used"] is True
    assert usage["cross_project_projects_considered"] == ["runtime-orchestrator"]
    assert usage["earth_sweep_evidence_refs_used"] == [
        "reports/earth/sweeps/2026-03-15/resource-portfolio.json"
    ]

    sequencing = recommendation["sequencing_policy_suggestions"]
    assert [row["action_id"] for row in sequencing] == [
        "action-risk-scan",
        "action-contract-normalize",
        "action-summary-pass",
    ]
    assert [row["execution_batch"] for row in sequencing] == [1, 1, 2]

    model_routing = recommendation["model_routing_policy_suggestions"]
    routed_model_ids = {row["action_id"]: row["suggested_model_id"] for row in model_routing}
    assert routed_model_ids == {
        "action-risk-scan": "gpt-5-pro",
        "action-contract-normalize": "gpt-5",
        "action-summary-pass": "gpt-5-mini",
    }
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-resource-runtime-orchestrator",
            "project_id": "runtime-orchestrator",
            "summary": (
                "Coordinate execution-resource sequencing and model-routing policy with "
                "'runtime-orchestrator' before shared execution."
            ),
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/resource-portfolio.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        }
    ]


def test_req_019_rejects_invalid_parallel_task_limit() -> None:
    fixture = _read_json(FIXTURE_PATH)
    bad_input = json.loads(json.dumps(fixture["input"]))
    bad_input["execution_resource_context"]["rate_limits"]["max_parallel_tasks"] = 0

    with pytest.raises(ValueError, match="max_parallel_tasks"):
        module.build_req_019_execution_resource_context_ingestion(**bad_input)
