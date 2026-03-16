import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-3-gap-and-opportunity-reasoning.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_input() -> dict:
    return copy.deepcopy(_read_json(FIXTURE_PATH)["input"])


def test_req_028_cross_call_contradiction_between_analysis_and_synthesis_emits_deterministic_reason_code() -> None:
    payload = module.build_req_028_call_3_gap_and_opportunity_reasoning(
        **_base_input(),
        strategic_claims=[
            {
                "claim_id": "claim-runtime-bridge",
                "phase": "analysis",
                "summary": "Analysis concludes the runtime handshake bridge must be promoted in Call-3.",
                "position": "promote-runtime-bridge",
                "source_output_ref": "REQ-027::call::call-2::output::analysis-runtime-bridge",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
            {
                "claim_id": "claim-runtime-bridge",
                "phase": "synthesis",
                "summary": "Synthesis concludes the runtime handshake bridge should be deferred until Call-4.",
                "position": "defer-runtime-bridge",
                "source_output_ref": "REQ-029::call::call-4::output::synthesis-runtime-bridge",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
        ],
    )

    assert module.validate_req_028_call_3_gap_and_opportunity_reasoning(payload) == []

    contradiction_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "cross_call_contradiction"
    )
    assert contradiction_risk == {
        "risk_id": "risk-claim-claim-runtime-bridge-contradiction",
        "summary": "Synthesis concludes the runtime handshake bridge should be deferred until Call-4.",
        "reason_code": "cross_call_contradiction",
        "required_evidence_refs": [
            "REQ-027::call::call-2::output::analysis-runtime-bridge",
            "REQ-029::call::call-4::output::synthesis-runtime-bridge",
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_028_uncited_strategic_claim_is_blocked_by_citation_discipline() -> None:
    payload = module.build_req_028_call_3_gap_and_opportunity_reasoning(
        **_base_input(),
        strategic_claims=[
            {
                "claim_id": "claim-uncited-shared-schema",
                "phase": "analysis",
                "summary": "Analysis proposes a shared schema promotion without attaching any evidence refs.",
                "position": "promote-shared-schema",
                "source_output_ref": "REQ-027::call::call-2::output::analysis-shared-schema",
                "evidence_refs": [],
            }
        ],
    )

    assert module.validate_req_028_call_3_gap_and_opportunity_reasoning(payload) == []

    uncited_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "uncited_strategic_claim"
    )
    assert uncited_risk == {
        "risk_id": "risk-claim-claim-uncited-shared-schema-citation",
        "summary": "Analysis proposes a shared schema promotion without attaching any evidence refs.",
        "reason_code": "uncited_strategic_claim",
        "required_evidence_refs": [
            "REQ-027::call::call-2::output::analysis-shared-schema",
        ],
    }
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"


def test_req_028_call_chain_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    first_input = _base_input()
    second_input = _base_input()
    second_input["cross_project_context"] = list(reversed(second_input["cross_project_context"]))
    second_input["unresolved_ideas"] = list(reversed(second_input["unresolved_ideas"]))
    second_input["gap_candidates"] = list(reversed(second_input["gap_candidates"]))
    second_input["opportunity_candidates"] = [
        second_input["opportunity_candidates"][2],
        second_input["opportunity_candidates"][0],
        second_input["opportunity_candidates"][1],
    ]

    first = module.build_req_028_call_3_gap_and_opportunity_reasoning(**first_input)
    second = module.build_req_028_call_3_gap_and_opportunity_reasoning(**second_input)

    assert module.validate_req_028_call_3_gap_and_opportunity_reasoning(first) == []
    assert module.validate_req_028_call_3_gap_and_opportunity_reasoning(second) == []
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == second["call_metadata"]["processing_call_id"]
    assert first["processing_behavior"]["recommendation"]["recommended_opportunities"] == second["processing_behavior"][
        "recommendation"
    ]["recommended_opportunities"]
    assert first["processing_behavior"]["recommendation"]["cross_project_obligations"] == second["processing_behavior"][
        "recommendation"
    ]["cross_project_obligations"]
    assert [row["opportunity_id"] for row in first["processing_behavior"]["recommendation"]["recommended_opportunities"]] == [
        "opp.runtime-handshake-bridge",
        "opp.shared-telemetry-contract",
        "opp.telemetry-runtime-link",
    ]
