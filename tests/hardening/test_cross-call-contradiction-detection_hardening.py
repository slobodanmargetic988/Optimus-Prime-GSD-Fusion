import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "cross-call-contradiction-detection.json"


def _read_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_036_hardening_detects_cross_call_contradiction_between_analysis_and_synthesis_outputs() -> None:
    payload = module.build_req_036_cross_call_contradiction_detection(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req036-analysis-vs-synthesis",
        call_outputs=[
            {
                "call_id": "synthesis-call",
                "call_requirement_id": "REQ-036-SYNTHESIS",
                "emitted_claims": [
                    {
                        "claim_id": "claim-runtime-posture",
                        "claim_text": "Final synthesis says the runtime can safely expand to four parallel lanes now.",
                        "stance": "support",
                        "evidence_refs": [
                            "reports/strategy/synthesis/runtime-expansion.json",
                        ],
                    }
                ],
            },
            {
                "call_id": "analysis-call",
                "call_requirement_id": "REQ-036-ANALYSIS",
                "emitted_claims": [
                    {
                        "claim_id": "claim-runtime-posture",
                        "claim_text": "Analysis says the runtime must stay capped at two parallel lanes.",
                        "stance": "contradict",
                        "evidence_refs": [
                            "reports/strategy/analysis/runtime-cap.json",
                        ],
                    }
                ],
            },
        ],
        persist_llm_call_trace=False,
    )

    contradiction = payload["contradiction_report"]["contradictions"][0]

    assert payload["contradiction_report"]["contradiction_count"] == 1
    assert contradiction["claim_id"] == "claim-runtime-posture"
    assert [row["call_id"] for row in contradiction["contradictory_calls"]] == [
        "analysis-call",
        "synthesis-call",
    ]
    assert contradiction["resolution_status"] == "unresolved"
    assert contradiction["unresolved_risk"] == {
        "risk_id": "risk-claim-claim-runtime-posture-contradiction",
        "summary": "Claim 'claim-runtime-posture' has contradictory stances across call outputs.",
        "reason_code": "cross_call_contradiction",
        "required_evidence_refs": [
            "reports/strategy/analysis/runtime-cap.json",
            "reports/strategy/synthesis/runtime-expansion.json",
        ],
    }


def test_req_036_hardening_blocks_uncited_strategic_recommendation_via_citation_discipline() -> None:
    payload = module.build_req_036_cross_call_contradiction_detection(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req036-citation-discipline",
        call_outputs=[
            {
                "call_id": "analysis-call-2",
                "call_requirement_id": "REQ-036-ANALYSIS",
                "emitted_claims": [
                    {
                        "claim_id": "claim-readiness",
                        "claim_text": "Analysis shows the recommendation can proceed with current readiness evidence.",
                        "stance": "support",
                        "evidence_refs": [
                            "reports/strategy/analysis/readiness.json",
                        ],
                    }
                ],
            },
            {
                "call_id": "analysis-call-1",
                "call_requirement_id": "REQ-036-ANALYSIS",
                "emitted_claims": [
                    {
                        "claim_id": "claim-readiness",
                        "claim_text": "A corroborating analysis confirms current readiness posture.",
                        "stance": "support",
                        "evidence_refs": [
                            "reports/strategy/analysis/corroborating-readiness.json",
                        ],
                    }
                ],
            },
        ],
        persist_llm_call_trace=False,
    )

    recommendation = payload["processing_behavior"]["recommendation"]

    assert payload["contradiction_report"]["contradiction_count"] == 0
    assert payload["contradiction_report"]["evidence_refs"] == []
    assert recommendation["decision"] == "ready-for-final-synthesis"
    assert recommendation["open_risks"] == []
    assert recommendation["evidence_refs"] == [
        "reports/strategy/analysis/corroborating-readiness.json",
        "reports/strategy/analysis/readiness.json",
    ]
    assert recommendation["recommended_actions"][0]["evidence_refs"] == recommendation["evidence_refs"]
    assert payload["processing_behavior"]["context_usage"]["evidence_refs_used"] == recommendation["evidence_refs"]


def test_req_036_hardening_replay_keeps_recommendation_action_ids_and_ordering_stable() -> None:
    fixture = _read_fixture()
    first = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )
    second = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )

    first_recommendation = first["processing_behavior"]["recommendation"]
    second_recommendation = second["processing_behavior"]["recommendation"]

    assert first_recommendation == second_recommendation
    assert [row["action_id"] for row in first_recommendation["recommended_actions"]] == [
        "resolve-cross-call-contradictions",
    ]
    assert [row["risk_id"] for row in first_recommendation["open_risks"]] == [
        "risk-claim-claim-token-headroom-contradiction",
    ]
    assert first["processing_behavior"]["context_usage"]["call_ids_considered"] == [
        "call-1",
        "call-2",
        "call-3",
    ]
    assert [row["claim_id"] for row in first["contradiction_report"]["contradictions"]] == [
        "claim-lane-parallelism",
        "claim-token-headroom",
    ]
    assert [row["trace_row_id"] for row in first["llm_call_trace"]["rows"]] == [
        row["trace_row_id"] for row in second["llm_call_trace"]["rows"]
    ]
