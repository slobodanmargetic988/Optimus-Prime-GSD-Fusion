from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req030-contract-r1",
        "strategy_goal": "Build deterministic call-5 sequencing and lane design outputs from prior call reasoning.",
        "call_id": "call-5",
        "checked_at_utc": "2026-03-16T13:00:00Z",
        "call_chain": [
            {
                "sequence": 1,
                "call_id": "call-1",
                "phase": "analysis",
                "output_ref": "REQ-030::call::call-1::output::situational_analysis",
            },
            {
                "sequence": 2,
                "call_id": "call-2",
                "phase": "planning",
                "output_ref": "REQ-030::call::call-2::output::option_set",
            },
            {
                "sequence": 3,
                "call_id": "call-3",
                "phase": "validation",
                "output_ref": "REQ-030::call::call-3::output::evidence_validation",
            },
            {
                "sequence": 4,
                "call_id": "call-4",
                "phase": "synthesis",
                "output_ref": "REQ-030::call::call-4::output::recommendation_synthesis",
            },
            {
                "sequence": 5,
                "call_id": "call-5",
                "phase": "sequencing",
                "output_ref": "REQ-030::call::call-5::output::lane_design_reasoning",
            },
        ],
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
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
                "context_note": "Shared runtime replay envelope remains in scope for lane sequencing.",
            }
        ],
        "candidate_lane_designs": [
            {
                "lane_id": "lane.runtime-sync",
                "recommendation_id": "rec.runtime-sync",
                "summary": "Stage the cross-project runtime replay sync in lane 2.",
                "rationale": "Cross-project coordination should follow local hardening proof.",
                "sequencing_rationale": "Lane 2 waits for the local deterministic checks to stay green twice.",
                "lane_order": 2,
                "lane_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "next_step": "Publish the synchronized runtime packet after local proof is committed.",
                "synthesized_from_call_sequence": 5,
            },
            {
                "lane_id": "lane.local-determinism",
                "recommendation_id": "rec.local-determinism",
                "summary": "Keep the local replay hardening checks in lane 1.",
                "rationale": "Local deterministic evidence must land before escalation.",
                "sequencing_rationale": "Lane 1 produces the branch-head evidence required for follow-up lanes.",
                "lane_order": 1,
                "lane_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
                "next_step": "Run the scoped contract, integration, and hardening checks twice.",
                "synthesized_from_call_sequence": 5,
            },
        ],
        "strategic_claims": [
            {
                "claim_id": "claim.local-determinism",
                "phase": "analysis",
                "summary": "Analysis says deterministic local evidence remains a prerequisite.",
                "position": "preserve",
                "source_call_sequence": 1,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
            },
            {
                "claim_id": "claim.runtime-sync",
                "phase": "synthesis",
                "summary": "Synthesis says the runtime handoff can proceed once local evidence is stable.",
                "position": "promote",
                "source_call_sequence": 4,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
        ],
    }


def test_req_030_builder_emits_contract_valid_lane_blueprints() -> None:
    payload = module.build_req_030_call_5_sequencing_and_lane_design_reasoning(**_base_input())

    assert module.validate_req_030_call_5_sequencing_and_lane_design_reasoning(payload) == []
    assert payload["schema_version"] == module.REQ_030_SCHEMA_VERSION
    assert payload["requirement_id"] == module.REQ_030_REQUIREMENT_ID
    assert payload["analysis_type"] == module.REQ_030_ANALYSIS_TYPE

    processing = payload["processing_behavior"]
    lane_design = processing["lane_design"]
    lane_blueprints = lane_design["lane_blueprints"]

    assert processing["strategy"] == module.REQ_030_PROCESSING_STRATEGY
    assert processing["reasoning_mode"] == module.REQ_030_REASONING_MODE
    assert lane_design["decision"] == "proceed"
    assert [row["lane_id"] for row in lane_blueprints] == [
        "lane.local-determinism",
        "lane.runtime-sync",
    ]
    assert processing["context_usage"]["emitted_recommendation_ids"] == [
        "rec.local-determinism",
        "rec.runtime-sync",
    ]
    assert all(row["rationale"] for row in lane_blueprints)
    assert all(row["sequencing_rationale"] for row in lane_blueprints)
    assert lane_design["open_risks"] == []


def test_req_030_lane_ids_must_match_schema() -> None:
    invalid_input = _base_input()
    invalid_input["candidate_lane_designs"] = [
        {
            **invalid_input["candidate_lane_designs"][0],
            "lane_id": "LANE-INVALID",
        }
    ]

    try:
        module.build_req_030_call_5_sequencing_and_lane_design_reasoning(**invalid_input)
    except module.Req030Error as exc:
        assert "candidate_lane_designs[0].lane_id" in str(exc)
    else:
        raise AssertionError("expected Req030Error for invalid lane_id schema")
