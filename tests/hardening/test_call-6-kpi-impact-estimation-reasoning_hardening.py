import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-6-kpi-impact-estimation-reasoning.json"


def _load_fixture_input() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return json.loads(json.dumps(fixture["input"]))


def _risk_map(payload: dict) -> dict[str, dict]:
    return {
        str(row["risk_id"]): row
        for row in payload["processing_behavior"]["diagnostics"]["open_risks"]
    }


def test_req_031_hardening_flags_cross_call_contradiction_with_deterministic_reason_code() -> None:
    payload_input = _load_fixture_input()

    payload = module.build_req_031_call_6_kpi_impact_estimation_reasoning(
        **payload_input,
        strategic_claims=[
            {
                "claim_id": "claim-replay-status",
                "phase": "analysis",
                "summary": "Analysis says replay failure exposure is still active at branch head.",
                "position": "active-risk",
                "source_call_sequence": 1,
                "evidence_refs": ["reports/optimus-prime/planning/VERIFICATION.md"],
            },
            {
                "claim_id": "claim-replay-status",
                "phase": "synthesis",
                "summary": "Synthesis says replay failure exposure is already closed before KPI estimation.",
                "position": "resolved-risk",
                "source_call_sequence": 4,
                "evidence_refs": ["REQ-029::call::call-4::output::recommendation_synthesis"],
            },
        ],
    )

    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(payload) == []

    contradiction_risk = _risk_map(payload)["risk-claim-claim-replay-status-contradiction"]
    assert contradiction_risk == {
        "risk_id": "risk-claim-claim-replay-status-contradiction",
        "reason_code": "cross_call_contradiction",
        "summary": "Synthesis says replay failure exposure is already closed before KPI estimation.",
        "required_evidence_refs": [
            "REQ-031::call-chain::01::analysis",
            "REQ-031::call-chain::04::synthesis",
            "reports/optimus-prime/planning/VERIFICATION.md",
            "REQ-029::call::call-4::output::recommendation_synthesis",
        ],
    }
    assert payload["processing_behavior"]["context_usage"]["open_risk_ids_emitted"] == [
        "risk-claim-claim-replay-status-contradiction"
    ]
    assert payload["processing_behavior"]["context_usage"]["reason_codes_emitted"] == [
        "cross_call_contradiction"
    ]


def test_req_031_hardening_blocks_uncited_strategic_claim_with_evidence_ref() -> None:
    payload_input = _load_fixture_input()

    payload = module.build_req_031_call_6_kpi_impact_estimation_reasoning(
        **payload_input,
        strategic_claims=[
            {
                "claim_id": "claim-branch-head-citation",
                "phase": "analysis",
                "summary": "Branch-head evidence already proves replay failure exposure is closed.",
                "position": "resolved-risk",
                "source_call_sequence": 1,
                "evidence_refs": ["reports/optimus-prime/planning/BRANCH_HEAD_ONLY.md"],
            }
        ],
    )

    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(payload) == []

    citation_risk = _risk_map(payload)["risk-claim-claim-branch-head-citation-citation"]
    assert citation_risk == {
        "risk_id": "risk-claim-claim-branch-head-citation-citation",
        "reason_code": "uncited_strategic_claim",
        "summary": "Branch-head evidence already proves replay failure exposure is closed.",
        "required_evidence_refs": [
            "REQ-031::call-chain::01::analysis",
            "reports/optimus-prime/planning/BRANCH_HEAD_ONLY.md",
        ],
    }
    assert payload["processing_behavior"]["context_usage"]["open_risk_ids_emitted"] == [
        "risk-claim-claim-branch-head-citation-citation"
    ]
    assert payload["processing_behavior"]["context_usage"]["reason_codes_emitted"] == [
        "uncited_strategic_claim"
    ]


def test_req_031_hardening_replay_keeps_recommendation_ids_and_risk_order_stable() -> None:
    base_input = _load_fixture_input()
    strategic_claims = [
        {
            "claim_id": "claim-replay-status",
            "phase": "analysis",
            "summary": "Analysis says replay failure exposure is still active at branch head.",
            "position": "active-risk",
            "source_call_sequence": 1,
            "evidence_refs": ["reports/optimus-prime/planning/VERIFICATION.md"],
        },
        {
            "claim_id": "claim-branch-head-citation",
            "phase": "analysis",
            "summary": "Branch-head evidence already proves replay failure exposure is closed.",
            "position": "resolved-risk",
            "source_call_sequence": 1,
            "evidence_refs": ["reports/optimus-prime/planning/BRANCH_HEAD_ONLY.md"],
        },
        {
            "claim_id": "claim-replay-status",
            "phase": "synthesis",
            "summary": "Synthesis says replay failure exposure is already closed before KPI estimation.",
            "position": "resolved-risk",
            "source_call_sequence": 4,
            "evidence_refs": ["REQ-029::call::call-4::output::recommendation_synthesis"],
        },
    ]

    replay_input = json.loads(json.dumps(base_input))
    replay_input["recommendation_adoptions"].reverse()
    replay_input["kpi_definitions"].reverse()
    replay_input["impact_assumptions"].reverse()
    replay_claims = list(reversed(strategic_claims))

    first = module.build_req_031_call_6_kpi_impact_estimation_reasoning(
        **base_input,
        strategic_claims=strategic_claims,
    )
    second = module.build_req_031_call_6_kpi_impact_estimation_reasoning(
        **replay_input,
        strategic_claims=replay_claims,
    )

    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(first) == []
    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(second) == []
    assert first == second

    usage = first["processing_behavior"]["context_usage"]
    assert usage["recommendation_ids_considered"] == [
        "rec.local-replay-hardening",
        "rec.runtime-sync",
    ]
    assert usage["open_risk_ids_emitted"] == [
        "risk-claim-claim-branch-head-citation-citation",
        "risk-claim-claim-replay-status-contradiction",
    ]
    assert usage["reason_codes_emitted"] == [
        "uncited_strategic_claim",
        "cross_call_contradiction",
    ]
    assert [
        row["recommendation_id"] for row in first["kpi_impact_estimation"]["recommendation_adoptions"]
    ] == [
        "rec.local-replay-hardening",
        "rec.runtime-sync",
    ]
