from __future__ import annotations

import copy
import shutil
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


def _reset_call_trace() -> None:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    if trace_path.exists():
        trace_path.unlink()
    artifacts_dir = Path("strategy/current/llm_call_trace_artifacts")
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir, ignore_errors=True)


def test_hardening_cross_call_contradiction_between_analysis_and_synthesis_outputs() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_035_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T14:10:00Z",
        "context_provenance_ledger": {
            "ledger_requirement_id": "REQ-021",
            "ledger_scope": "strategy_context_sweep.processing_behavior",
            "evidence_ids": [
                "claim-111111111111",
                "claim-222222222222",
            ],
        },
        "reasoning_calls": [
            {
                "call_id": "call-2",
                "strategic_claims": [
                    {
                        "strategic_claim_id": "sc.shared-citation-status",
                        "summary": "Shared strategic claim is cited in analysis output.",
                        "evidence_ids": ["claim-111111111111"],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.shared-cited",
                            "summary": "Promote cited recommendation from call-2.",
                            "rationale": "Cited call-2 output is promotable.",
                            "confidence_tag": "high",
                        },
                    }
                ],
            },
            {
                "call_id": "call-5",
                "strategic_claims": [
                    {
                        "strategic_claim_id": "sc.shared-citation-status",
                        "summary": "Shared strategic claim is uncited in synthesis output.",
                        "evidence_ids": [],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.shared-uncited",
                            "summary": "Do not promote uncited recommendation from call-5.",
                            "rationale": "Uncited output must be blocked.",
                            "confidence_tag": "low",
                        },
                    }
                ],
            },
        ],
    }

    result = pipeline.process_req_035_evidence_citation_discipline_in_reasoning_calls(payload)
    recommendation = result["processing_behavior"]["recommendation"]
    contradiction_rows = [
        row
        for row in recommendation["open_risks"]
        if row["reason_code"] == "analysis_synthesis_contradiction_cross_call_citation_status"
    ]
    assert len(contradiction_rows) == 1
    assert "claim-111111111111" in contradiction_rows[0]["required_evidence_refs"]
    assert recommendation["decision"] == "proceed-with-open-risks"


def test_hardening_uncited_strategic_claim_blocked_by_citation_discipline() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_035_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T14:20:00Z",
        "context_provenance_ledger": {
            "ledger_requirement_id": "REQ-021",
            "ledger_scope": "strategy_context_sweep.processing_behavior",
            "evidence_ids": [
                "claim-333333333333",
            ],
        },
        "reasoning_calls": [
            {
                "call_id": "call-2",
                "strategic_claims": [
                    {
                        "strategic_claim_id": "sc.req035.cited",
                        "summary": "Cited strategic claim stays promotable.",
                        "evidence_ids": ["claim-333333333333"],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.cited",
                            "summary": "Promote cited recommendation.",
                            "rationale": "Recommendation remains ledger-cited.",
                            "confidence_tag": "high",
                        },
                    },
                    {
                        "strategic_claim_id": "sc.req035.uncited",
                        "summary": "Uncited strategic claim must be blocked.",
                        "evidence_ids": [],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.uncited",
                            "summary": "Block uncited recommendation.",
                            "rationale": "Missing evidence IDs violate citation discipline.",
                            "confidence_tag": "low",
                        },
                    },
                ],
            }
        ],
    }

    result = pipeline.process_req_035_evidence_citation_discipline_in_reasoning_calls(payload)
    discipline = result["evidence_citation_discipline"]
    recommendation = result["processing_behavior"]["recommendation"]

    flagged_ids = {row["recommendation_id"] for row in discipline["flagged_claims"]}
    final_ids = {row["recommendation_id"] for row in discipline["final_recommendations"]}
    promoted_ids = {row["recommendation_id"] for row in recommendation["recommended_actions"]}

    assert "rec.req-035.uncited" in flagged_ids
    assert "rec.req-035.uncited" not in final_ids
    assert "rec.req-035.uncited" not in promoted_ids
    assert any(row["reason_code"] == "uncited_strategic_claim" for row in recommendation["open_risks"])


def test_hardening_call_chain_replay_produces_stable_recommendation_ids_and_ordering() -> None:
    _reset_call_trace()
    payload_first = {
        "analysis_type": pipeline.REQ_035_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T14:30:00Z",
        "context_provenance_ledger": {
            "ledger_requirement_id": "REQ-021",
            "ledger_scope": "strategy_context_sweep.processing_behavior",
            "evidence_ids": [
                "claim-111111111111",
                "claim-222222222222",
                "claim-333333333333",
            ],
        },
        "reasoning_calls": [
            {
                "call_id": "call-5",
                "strategic_claims": [
                    {
                        "strategic_claim_id": "sc.zeta",
                        "summary": "Late-stage implementation claim remains cited.",
                        "evidence_ids": ["claim-333333333333"],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.zeta",
                            "summary": "Promote zeta recommendation.",
                            "rationale": "Evidence-backed local recommendation.",
                            "confidence_tag": "medium",
                        },
                    },
                    {
                        "strategic_claim_id": "sc.alpha",
                        "summary": "Early implementation claim remains cited.",
                        "evidence_ids": ["claim-111111111111"],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.alpha",
                            "summary": "Promote alpha recommendation.",
                            "rationale": "Evidence-backed local recommendation.",
                            "confidence_tag": "high",
                        },
                    },
                ],
            },
            {
                "call_id": "call-2",
                "strategic_claims": [
                    {
                        "strategic_claim_id": "sc.beta",
                        "summary": "Middle implementation claim remains cited.",
                        "evidence_ids": ["claim-222222222222"],
                        "recommendation": {
                            "recommendation_id": "rec.req-035.beta",
                            "summary": "Promote beta recommendation.",
                            "rationale": "Evidence-backed local recommendation.",
                            "confidence_tag": "high",
                        },
                    }
                ],
            },
        ],
    }

    payload_second = copy.deepcopy(payload_first)
    payload_second["reasoning_calls"] = list(reversed(payload_second["reasoning_calls"]))
    payload_second["reasoning_calls"][0]["strategic_claims"] = list(
        reversed(payload_second["reasoning_calls"][0]["strategic_claims"])
    )
    payload_second["reasoning_calls"][1]["strategic_claims"] = list(
        reversed(payload_second["reasoning_calls"][1]["strategic_claims"])
    )

    first = pipeline.process_req_035_evidence_citation_discipline_in_reasoning_calls(payload_first)
    second = pipeline.process_req_035_evidence_citation_discipline_in_reasoning_calls(payload_second)

    first_final = first["evidence_citation_discipline"]["final_recommendations"]
    second_final = second["evidence_citation_discipline"]["final_recommendations"]
    assert first_final == second_final

    first_actions = first["processing_behavior"]["recommendation"]["recommended_actions"]
    second_actions = second["processing_behavior"]["recommendation"]["recommended_actions"]
    assert first_actions == second_actions
    assert [row["recommendation_id"] for row in first_actions] == sorted(
        row["recommendation_id"] for row in first_actions
    )

    first_meta = first["call_metadata"]
    second_meta = second["call_metadata"]
    assert first_meta["reproducible_call_id"] == second_meta["reproducible_call_id"]
    assert first_meta["processing_call_id"] == second_meta["processing_call_id"]
    assert [row["call_id"] for row in first_meta["llm_call_trace_rows"]] == ["call-2", "call-5"]
    assert [row["call_id"] for row in second_meta["llm_call_trace_rows"]] == ["call-2", "call-5"]
