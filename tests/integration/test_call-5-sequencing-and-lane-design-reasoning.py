from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req030-integration-r1",
        "strategy_goal": "Promote deterministic call-5 lane sequencing only when citation discipline holds.",
        "call_id": "call-5",
        "checked_at_utc": "2026-03-16T13:15:00Z",
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
                "output_ref": "REQ-030::call::call-2::output::execution_plan",
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
                "context_note": "Shared runtime replay envelope needs a sequenced follow-up.",
            }
        ],
        "candidate_lane_designs": [
            {
                "lane_id": "lane.runtime-sync",
                "recommendation_id": "rec.runtime-sync",
                "summary": "Place the runtime packet in lane 2 after local proof.",
                "rationale": "Cross-project movement should only start after local evidence locks.",
                "sequencing_rationale": "Lane 2 depends on lane 1 producing committed deterministic proof.",
                "lane_order": 2,
                "lane_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "next_step": "Publish the synchronized runtime packet with evidence refs attached.",
                "synthesized_from_call_sequence": 5,
            },
            {
                "lane_id": "lane.local-determinism",
                "recommendation_id": "rec.local-determinism",
                "summary": "Keep deterministic replay diagnostics in lane 1.",
                "rationale": "The branch still depends on stable failure-path artifacts for diagnosis.",
                "sequencing_rationale": "Lane 1 is the gating local proof before external follow-up.",
                "lane_order": 1,
                "lane_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
                "next_step": "Keep the check bundle in the evidence packet after every rerun.",
                "synthesized_from_call_sequence": 5,
            },
        ],
        "strategic_claims": [
            {
                "claim_id": "claim.local-determinism",
                "phase": "analysis",
                "summary": "Deterministic local artifacts remain mandatory for replay diagnosis.",
                "position": "preserve",
                "source_call_sequence": 1,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
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


def test_req_030_integration_emits_trace_rows_and_structured_lane_blueprints() -> None:
    payload = module.build_req_030_call_5_sequencing_and_lane_design_reasoning(**_base_input())

    assert module.validate_req_030_call_5_sequencing_and_lane_design_reasoning(payload) == []

    processing = payload["processing_behavior"]
    lane_design = processing["lane_design"]
    lane_blueprints = lane_design["lane_blueprints"]
    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]

    assert lane_design["decision"] == "proceed"
    assert [row["recommendation_id"] for row in lane_blueprints] == [
        "rec.local-determinism",
        "rec.runtime-sync",
    ]
    assert lane_blueprints[0]["source_output_ref"] == "REQ-030::call::call-5::output::lane_design_reasoning"
    assert lane_blueprints[1]["source_output_ref"] == "REQ-030::call::call-5::output::lane_design_reasoning"
    assert trace_rows[-1]["call_id"] == "call-5"
    assert trace_rows[-1]["handoff_summary"] == "Call 5 emits lane_blueprints for 2 recommendation(s)."
    assert len(trace_rows) == 5


def test_req_030_integration_replay_is_stable_across_input_order_changes() -> None:
    first = module.build_req_030_call_5_sequencing_and_lane_design_reasoning(**_base_input())

    second_input = _base_input()
    second_input["candidate_lane_designs"] = list(reversed(second_input["candidate_lane_designs"]))
    second_input["cross_project_context"] = list(reversed(second_input["cross_project_context"]))
    second_input["strategic_claims"] = list(reversed(second_input["strategic_claims"]))
    second = module.build_req_030_call_5_sequencing_and_lane_design_reasoning(**second_input)

    assert module.validate_req_030_call_5_sequencing_and_lane_design_reasoning(first) == []
    assert module.validate_req_030_call_5_sequencing_and_lane_design_reasoning(second) == []
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
    assert (
        [row["lane_id"] for row in first["processing_behavior"]["lane_design"]["lane_blueprints"]]
        == [row["lane_id"] for row in second["processing_behavior"]["lane_design"]["lane_blueprints"]]
        == ["lane.local-determinism", "lane.runtime-sync"]
    )
