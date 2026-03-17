from copy import deepcopy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "project-obligation-reasoning.json"


def _base_input() -> dict:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["call_chain"] = [
        {
            "sequence": 1,
            "call_id": "call-1",
            "phase": "analysis",
            "output_ref": "REQ-043::call::call-1::output::obligation_analysis",
        },
        {
            "sequence": 2,
            "call_id": "call-2",
            "phase": "planning",
            "output_ref": "REQ-043::call::call-2::output::obligation_planning",
        },
        {
            "sequence": 3,
            "call_id": "call-3",
            "phase": "validation",
            "output_ref": "REQ-043::call::call-3::output::obligation_validation",
        },
        {
            "sequence": 4,
            "call_id": "call-4",
            "phase": "synthesis",
            "output_ref": "REQ-043::call::call-4::output::project_obligation_reasoning",
        },
    ]
    return payload


def test_req_043_hardening_cross_call_contradiction_blocks_obligation_with_reason_code() -> None:
    input_payload = _base_input()
    input_payload["strategic_claims"] = [
        {
            "claim_id": "claim.replay-obligation-scope",
            "obligation_id": "obl.replay-manifest-expose",
            "phase": "analysis",
            "summary": "Analysis keeps replay-manifest obligation in cross-project scope.",
            "position": "cross-project",
            "source_call_sequence": 1,
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-151/TASK_EVIDENCE.json",
            ],
        },
        {
            "claim_id": "claim.replay-obligation-scope",
            "obligation_id": "obl.replay-manifest-expose",
            "phase": "synthesis",
            "summary": "Synthesis claims replay-manifest obligation should be local-only.",
            "position": "local-only",
            "source_call_sequence": 4,
            "evidence_refs": [
                "REQ-043::call::call-4::output::project_obligation_reasoning",
            ],
        },
    ]

    payload = module.build_req_043_project_obligation_reasoning(**input_payload)

    assert module.validate_req_043_project_obligation_reasoning(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    contradiction_risk = next(
        row for row in recommendation["open_risks"] if row["reason_code"] == "cross_call_contradiction"
    )
    assert contradiction_risk["risk_id"] == "risk-claim-claim.replay-obligation-scope-contradiction"
    assert contradiction_risk["required_evidence_refs"] == [
        "REQ-043::call::call-1::output::obligation_analysis",
        "REQ-043::call::call-4::output::project_obligation_reasoning",
        "reports/optimus-prime/planning/evidence/TASK-151/TASK_EVIDENCE.json",
    ]

    blocked_obligation_risk = next(
        row
        for row in recommendation["open_risks"]
        if row["risk_id"] == "risk-obl.replay-manifest-expose"
    )
    assert blocked_obligation_risk["reason_code"] == "cross_call_contradiction"
    assert "REQ-043::call::call-1::output::obligation_analysis" in blocked_obligation_risk["required_evidence_refs"]
    assert "REQ-043::call::call-4::output::project_obligation_reasoning" in blocked_obligation_risk["required_evidence_refs"]
    assert [row["obligation_id"] for row in recommendation["project_obligations"]] == [
        "obl.analytics-feedback-consume"
    ]


def test_req_043_hardening_uncited_claim_is_blocked_by_citation_discipline() -> None:
    input_payload = _base_input()
    input_payload["strategic_claims"] = [
        {
            "claim_id": "claim.replay-citation",
            "obligation_id": "obl.replay-manifest-expose",
            "phase": "synthesis",
            "summary": "Replay manifest obligation should be emitted with stable references.",
            "position": "cross-project",
            "source_call_sequence": 4,
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-151/uncited-note.md",
            ],
        }
    ]

    payload = module.build_req_043_project_obligation_reasoning(**input_payload)

    assert module.validate_req_043_project_obligation_reasoning(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    citation_risk = next(
        row for row in recommendation["open_risks"] if row["risk_id"] == "risk-claim-claim.replay-citation-citation"
    )
    assert citation_risk["reason_code"] == "uncited_strategic_claim"
    assert citation_risk["required_evidence_refs"] == [
        "REQ-043::call::call-4::output::project_obligation_reasoning",
        "reports/optimus-prime/planning/evidence/TASK-151/uncited-note.md",
    ]

    blocked_obligation_risk = next(
        row
        for row in recommendation["open_risks"]
        if row["risk_id"] == "risk-obl.replay-manifest-expose"
    )
    assert blocked_obligation_risk["reason_code"] == "uncited_strategic_claim"
    assert "REQ-043::call::call-4::output::project_obligation_reasoning" in blocked_obligation_risk["required_evidence_refs"]
    assert "reports/optimus-prime/planning/evidence/TASK-151/uncited-note.md" in blocked_obligation_risk["required_evidence_refs"]
    assert [row["obligation_id"] for row in recommendation["project_obligations"]] == [
        "obl.analytics-feedback-consume"
    ]


def test_req_043_hardening_call_chain_replay_keeps_recommendation_ids_and_order_stable() -> None:
    first = module.build_req_043_project_obligation_reasoning(**_base_input())

    second_input = deepcopy(_base_input())
    second_input["project_obligation_candidates"] = list(reversed(second_input["project_obligation_candidates"]))
    second_input["cross_project_context"] = list(reversed(second_input["cross_project_context"]))
    second_input["call_chain"] = list(reversed(second_input["call_chain"]))
    second = module.build_req_043_project_obligation_reasoning(**second_input)

    assert module.validate_req_043_project_obligation_reasoning(first) == []
    assert module.validate_req_043_project_obligation_reasoning(second) == []
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == second["call_metadata"]["processing_call_id"]
    assert first["call_metadata"]["llm_call_trace_rows"] == second["call_metadata"]["llm_call_trace_rows"]
    assert (
        [row["obligation_id"] for row in first["processing_behavior"]["recommendation"]["project_obligations"]]
        == [row["obligation_id"] for row in second["processing_behavior"]["recommendation"]["project_obligations"]]
        == ["obl.analytics-feedback-consume", "obl.replay-manifest-expose"]
    )
    assert (
        first["processing_behavior"]["context_usage"]["open_risk_ids_emitted"]
        == second["processing_behavior"]["context_usage"]["open_risk_ids_emitted"]
        == ["risk-obl.deploy-summary-expose"]
    )
