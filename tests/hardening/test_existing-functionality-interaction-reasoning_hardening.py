import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "existing-functionality-interaction-reasoning.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_input() -> dict:
    return copy.deepcopy(_read_json(FIXTURE_PATH)["input"])


def test_req_042_cross_call_contradiction_between_analysis_and_synthesis_outputs_emits_deterministic_reason_code() -> None:
    payload = module.build_req_042_existing_functionality_interaction_reasoning(
        **_base_input(),
        strategic_claims=[
            {
                "claim_id": "claim-reuse-promotion-order",
                "phase": "analysis",
                "summary": "Analysis says compatible reuse should be promoted before fallback investigation.",
                "position": "promote-reuse-first",
                "source_output_ref": "REQ-040::call::call-2::output::analysis-reuse-promotion-order",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
            {
                "claim_id": "claim-reuse-promotion-order",
                "phase": "synthesis",
                "summary": "Synthesis says fallback investigation should run before reuse promotion.",
                "position": "investigate-before-reuse",
                "source_output_ref": "REQ-041::call::call-3::output::synthesis-reuse-promotion-order",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
        ],
    )

    assert module.validate_req_042_existing_functionality_interaction_reasoning(payload) == []

    contradiction_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "cross_call_contradiction"
    )
    assert contradiction_risk == {
        "risk_id": "risk-claim-claim-reuse-promotion-order-contradiction",
        "summary": "Synthesis says fallback investigation should run before reuse promotion.",
        "reason_code": "cross_call_contradiction",
        "required_evidence_refs": [
            "REQ-040::call::call-2::output::analysis-reuse-promotion-order",
            "REQ-041::call::call-3::output::synthesis-reuse-promotion-order",
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "investigate_existing_functionality"
    assert payload["selected_path"]["decision"] == "investigate_existing_functionality"


def test_req_042_uncited_strategic_claim_is_blocked_by_citation_discipline() -> None:
    payload = module.build_req_042_existing_functionality_interaction_reasoning(
        **_base_input(),
        strategic_claims=[
            {
                "claim_id": "claim-uncited-reuse-shortcut",
                "phase": "analysis",
                "summary": "Analysis proposes a reuse shortcut without attaching evidence refs.",
                "position": "promote-uncited-reuse-shortcut",
                "source_output_ref": "REQ-040::call::call-2::output::analysis-uncited-reuse-shortcut",
                "evidence_refs": [],
            }
        ],
    )

    assert module.validate_req_042_existing_functionality_interaction_reasoning(payload) == []

    uncited_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "uncited_strategic_claim"
    )
    assert uncited_risk == {
        "risk_id": "risk-claim-claim-uncited-reuse-shortcut-citation",
        "summary": "Analysis proposes a reuse shortcut without attaching evidence refs.",
        "reason_code": "uncited_strategic_claim",
        "required_evidence_refs": [
            "REQ-040::call::call-2::output::analysis-uncited-reuse-shortcut",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "investigate_existing_functionality"
    assert payload["selected_path"] == {
        "decision": "investigate_existing_functionality",
        "selected_candidate_id": None,
        "rationale": (
            "Strategic claim contradictions or citation gaps must be resolved before consume-vs-build "
            "promotion can proceed."
        ),
    }


def test_req_042_call_chain_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    first = module.build_req_042_existing_functionality_interaction_reasoning(**_base_input())

    replay_input = _base_input()
    replay_input["target_project_evidence_refs"] = list(reversed(replay_input["target_project_evidence_refs"]))
    replay_input["earth_sweep_evidence_refs"] = list(reversed(replay_input["earth_sweep_evidence_refs"]))
    replay_input["cross_project_context"] = list(reversed(replay_input["cross_project_context"]))
    replay_input["existing_functionality_candidates"] = list(reversed(replay_input["existing_functionality_candidates"]))
    for candidate in replay_input["existing_functionality_candidates"]:
        candidate["provided_interfaces"] = list(reversed(candidate["provided_interfaces"]))
        candidate["compatibility_checks"] = list(reversed(candidate["compatibility_checks"]))
        candidate["evidence_refs"] = list(reversed(candidate["evidence_refs"]))
        candidate["integration_burden"]["drivers"] = list(reversed(candidate["integration_burden"]["drivers"]))

    replay = module.build_req_042_existing_functionality_interaction_reasoning(**replay_input)

    assert module.validate_req_042_existing_functionality_interaction_reasoning(first) == []
    assert module.validate_req_042_existing_functionality_interaction_reasoning(replay) == []
    assert first["call_metadata"]["canonical_processing_input"] == replay["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == replay["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == replay["call_metadata"]["processing_call_id"]
    assert first["call_metadata"]["llm_call_trace_rows"] == replay["call_metadata"]["llm_call_trace_rows"]
    assert first["processing_behavior"]["recommendation"] == replay["processing_behavior"]["recommendation"]

    recommendation_ids = [
        row["candidate_id"]
        for row in first["processing_behavior"]["recommendation"]["reuse_candidates"]
    ]
    replay_recommendation_ids = [
        row["candidate_id"]
        for row in replay["processing_behavior"]["recommendation"]["reuse_candidates"]
    ]
    assert recommendation_ids == replay_recommendation_ids == [
        "call-3-gap-reasoner",
        "integration-opportunity-bridge",
        "reuse-detector-adapter",
    ]
