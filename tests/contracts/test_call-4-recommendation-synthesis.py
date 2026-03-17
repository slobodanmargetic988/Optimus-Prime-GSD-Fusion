from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req029-contract-r1",
        "strategy_goal": "Synthesize call-4 recommendation drafts from earlier call outputs.",
        "call_id": "call-4",
        "checked_at_utc": "2026-03-16T12:00:00Z",
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
                "output_ref": "REQ-029::call::call-2::output::option_set",
            },
            {
                "sequence": 3,
                "call_id": "call-3",
                "phase": "validation",
                "output_ref": "REQ-029::call::call-3::output::validated_candidates",
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
                "context_note": "Shared runtime recovery constraints remain in scope.",
            }
        ],
        "candidate_recommendations": [
            {
                "recommendation_id": "rec.runtime-sync",
                "summary": "Coordinate replay hardening with runtime-orchestrator.",
                "rationale": "Shared runtime evidence shows the same failure-path envelope.",
                "impact": "Cross-project alignment reduces replay drift before promotion.",
                "risk": "Coordination can stall if Earth-sweep evidence goes stale.",
                "recommendation_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "next_step": "Open a cross-project packet with the synchronized replay evidence attached.",
                "synthesized_from_call_sequence": 4,
            },
            {
                "recommendation_id": "rec.local-replay-hardening",
                "summary": "Keep the local replay diagnostics deterministic.",
                "rationale": "The current branch still needs stable unhappy-path artifacts.",
                "impact": "Developers can compare repeat runs without manual triage.",
                "risk": "Overfitting tests can hide useful noisy failures.",
                "recommendation_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-098/TASK_EVIDENCE.json",
                ],
                "next_step": "Run the scoped contract, integration, and hardening checks twice.",
                "synthesized_from_call_sequence": 4,
            },
        ],
        "strategic_claims": [
            {
                "claim_id": "claim.replay-stability",
                "phase": "analysis",
                "summary": "Replay drift is still affecting failure diagnosis.",
                "position": "needs-hardening",
                "source_call_sequence": 1,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-098/TASK_EVIDENCE.json",
                ],
            },
            {
                "claim_id": "claim.runtime-shared-envelope",
                "phase": "synthesis",
                "summary": "Runtime-orchestrator shares the replay envelope touched by call-4.",
                "position": "coordinate",
                "source_call_sequence": 4,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
        ],
    }


def test_req_029_builder_emits_contract_valid_recommendation_drafts() -> None:
    payload = module.build_req_029_call_4_recommendation_synthesis(**_base_input())

    assert module.validate_req_029_call_4_recommendation_synthesis(payload) == []
    assert payload["schema_version"] == module.REQ_029_SCHEMA_VERSION
    assert payload["requirement_id"] == module.REQ_029_REQUIREMENT_ID
    assert payload["analysis_type"] == module.REQ_029_ANALYSIS_TYPE

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    drafts = recommendation["recommendation_drafts"]

    assert processing["strategy"] == module.REQ_029_PROCESSING_STRATEGY
    assert processing["reasoning_mode"] == module.REQ_029_REASONING_MODE
    assert recommendation["decision"] == "proceed"
    assert [row["recommendation_id"] for row in drafts] == [
        "rec.local-replay-hardening",
        "rec.runtime-sync",
    ]
    assert all(row["rationale"] for row in drafts)
    assert all(row["impact"] for row in drafts)
    assert all(row["risk"] for row in drafts)
    assert recommendation["open_risks"] == []


def test_req_029_recommendation_ids_must_match_schema() -> None:
    invalid_input = _base_input()
    invalid_input["candidate_recommendations"] = [
        {
            **invalid_input["candidate_recommendations"][0],
            "recommendation_id": "REC-INVALID",
        }
    ]

    try:
        module.build_req_029_call_4_recommendation_synthesis(**invalid_input)
    except module.Req029Error as exc:
        assert "candidate_recommendations[0].recommendation_id" in str(exc)
    else:
        raise AssertionError("expected Req029Error for invalid recommendation_id schema")
