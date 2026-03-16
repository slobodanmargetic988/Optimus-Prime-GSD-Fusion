from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req029-integration-r1",
        "strategy_goal": "Promote deterministic recommendation drafts only when evidence remains citable.",
        "call_id": "call-4",
        "checked_at_utc": "2026-03-16T12:15:00Z",
        "call_chain": [
            {
                "sequence": 1,
                "call_id": "call-1",
                "phase": "analysis",
                "output_ref": "REQ-029::call::call-1::output::situational_analysis",
            },
            {
                "sequence": 2,
                "call_id": "call-2",
                "phase": "planning",
                "output_ref": "REQ-029::call::call-2::output::execution_plan",
            },
            {
                "sequence": 3,
                "call_id": "call-3",
                "phase": "validation",
                "output_ref": "REQ-029::call::call-3::output::evidence_validation",
            },
            {
                "sequence": 4,
                "call_id": "call-4",
                "phase": "synthesis",
                "output_ref": "REQ-029::call::call-4::output::recommendation_synthesis",
            },
        ],
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-098/TASK_EVIDENCE.json",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/portfolio.json",
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        ],
        "cross_project_context": [
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "context_note": "Shared runtime replay envelope needs coordinated follow-up.",
            }
        ],
        "candidate_recommendations": [
            {
                "recommendation_id": "rec.runtime-sync",
                "summary": "Coordinate replay hardening with runtime-orchestrator.",
                "rationale": "The validated cross-project evidence still points at the shared recovery envelope.",
                "impact": "Joint follow-up reduces contradictory replay assumptions.",
                "risk": "A stale earth sweep could block obligation promotion.",
                "recommendation_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "next_step": "Publish the synchronized runtime packet with evidence refs attached.",
                "synthesized_from_call_sequence": 4,
            },
            {
                "recommendation_id": "rec.local-determinism",
                "summary": "Keep local failure-path diagnostics replay-stable.",
                "rationale": "The branch still depends on deterministic artifacts for regression diagnosis.",
                "impact": "Stable artifacts make repeat verification cheaper.",
                "risk": "Weak evidence discipline would hide invalid promotions.",
                "recommendation_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-098/TASK_EVIDENCE.json",
                ],
                "next_step": "Keep the check bundle in the evidence packet after every rerun.",
                "synthesized_from_call_sequence": 4,
            },
        ],
        "strategic_claims": [
            {
                "claim_id": "claim.local-determinism",
                "phase": "analysis",
                "summary": "Deterministic artifacts remain mandatory for replay diagnosis.",
                "position": "preserve",
                "source_call_sequence": 1,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-098/TASK_EVIDENCE.json",
                ],
            },
            {
                "claim_id": "claim.runtime-sync",
                "phase": "synthesis",
                "summary": "Cross-project runtime follow-up is justified by validated evidence.",
                "position": "promote",
                "source_call_sequence": 4,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
        ],
    }


def test_req_029_integration_emits_trace_rows_and_structured_drafts() -> None:
    payload = module.build_req_029_call_4_recommendation_synthesis(**_base_input())

    assert module.validate_req_029_call_4_recommendation_synthesis(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    drafts = recommendation["recommendation_drafts"]
    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]

    assert recommendation["decision"] == "proceed"
    assert [row["recommendation_id"] for row in drafts] == [
        "rec.local-determinism",
        "rec.runtime-sync",
    ]
    assert drafts[0]["source_output_ref"] == "REQ-029::call::call-4::output::recommendation_synthesis"
    assert drafts[1]["source_output_ref"] == "REQ-029::call::call-4::output::recommendation_synthesis"
    assert trace_rows[-1]["call_id"] == "call-4"
    assert trace_rows[-1]["handoff_summary"] == "Call 4 synthesizes recommendation_drafts for 2 recommendation(s)."
    assert len(trace_rows) == 4


def test_req_029_integration_replay_is_stable_across_input_order_changes() -> None:
    first = module.build_req_029_call_4_recommendation_synthesis(**_base_input())

    second_input = _base_input()
    second_input["candidate_recommendations"] = list(reversed(second_input["candidate_recommendations"]))
    second_input["cross_project_context"] = list(reversed(second_input["cross_project_context"]))
    second_input["strategic_claims"] = list(reversed(second_input["strategic_claims"]))
    second = module.build_req_029_call_4_recommendation_synthesis(**second_input)

    assert module.validate_req_029_call_4_recommendation_synthesis(first) == []
    assert module.validate_req_029_call_4_recommendation_synthesis(second) == []
    assert (
        first["call_metadata"]["canonical_processing_input"]
        == second["call_metadata"]["canonical_processing_input"]
    )
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert (
        first["processing_behavior"]["context_usage"]["emitted_recommendation_ids"]
        == second["processing_behavior"]["context_usage"]["emitted_recommendation_ids"]
        == ["rec.local-determinism", "rec.runtime-sync"]
    )
