import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "existing-functionality-interaction-reasoning.json"
EARTH_REFS = [
    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
    "reports/earth/sweeps/2026-03-16/shared-observability.json",
]
TASK_148_EVIDENCE_REF = "reports/optimus-prime/planning/evidence/TASK-148/TASK_EVIDENCE.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_042_integration_recommendation_is_complete_and_uses_cross_project_context() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_042_existing_functionality_interaction_reasoning(**fixture["input"])

    assert module.validate_req_042_existing_functionality_interaction_reasoning(payload) == []

    usage = payload["processing_behavior"]["context_usage"]
    assert usage["target_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["candidate_ids_considered"] == [
        "call-3-gap-reasoner",
        "integration-opportunity-bridge",
        "reuse-detector-adapter",
    ]
    assert usage["cross_project_projects_considered"] == [
        "runtime-orchestrator",
        "shared-observability",
    ]
    assert usage["cross_project_refs_used"] == EARTH_REFS

    recommendation = payload["processing_behavior"]["recommendation"]
    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "selected_path",
        "reuse_candidates",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "consume_existing_functionality"
    assert recommendation["confidence"] == "high"
    assert recommendation["selected_path"] == payload["selected_path"]
    assert recommendation["open_risks"] == []
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-reuse-detector-adapter",
            "project_id": "runtime-orchestrator",
            "candidate_id": "reuse-detector-adapter",
            "summary": "Coordinate reuse of reuse-detector-adapter before promoting existing-functionality-interaction-reasoning into execution.",
            "evidence_refs": [
                "contracts/req/REQ-016_reuse-opportunity-detection.md",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                "reports/optimus-prime/planning/evidence/TASK-148/TASK_EVIDENCE.json",
                "strategy/current/samples/REQ-016_reuse-opportunity-detection.sample.json",
            ],
        }
    ]
    assert TASK_148_EVIDENCE_REF in recommendation["evidence_refs"]
    for ref in EARTH_REFS:
        assert ref in recommendation["evidence_refs"]
    assert payload["processing_behavior"]["existing_functionality_reasoning"]["selected_candidate_id"] == (
        "reuse-detector-adapter"
    )


def test_req_042_cross_project_reuse_without_earth_evidence_becomes_open_risk() -> None:
    fixture = _read_json(FIXTURE_PATH)
    mutated_input = copy.deepcopy(fixture["input"])
    mutated_input["earth_sweep_evidence_refs"] = []
    for row in mutated_input["cross_project_context"]:
        row["evidence_refs"] = []

    payload = module.build_req_042_existing_functionality_interaction_reasoning(**mutated_input)

    assert module.validate_req_042_existing_functionality_interaction_reasoning(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "investigate_existing_functionality"
    assert recommendation["confidence"] == "medium"
    assert recommendation["selected_path"] == payload["selected_path"]
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-reuse-detector-adapter",
            "summary": "Cross-project reuse candidate reuse-detector-adapter is missing Earth-sweep evidence needed for promotion.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "project_id": "runtime-orchestrator",
            "candidate_id": "reuse-detector-adapter",
            "required_evidence_refs": [
                "contracts/req/REQ-016_reuse-opportunity-detection.md",
                "reports/optimus-prime/planning/evidence/TASK-148/TASK_EVIDENCE.json",
                "strategy/current/samples/REQ-016_reuse-opportunity-detection.sample.json",
            ],
        }
    ]
    assert payload["selected_path"] == {
        "decision": "investigate_existing_functionality",
        "selected_candidate_id": None,
        "rationale": (
            "reuse-detector-adapter is technically compatible, but cross-project reuse cannot be promoted until "
            "Earth-sweep evidence is attached for runtime-orchestrator."
        ),
    }
