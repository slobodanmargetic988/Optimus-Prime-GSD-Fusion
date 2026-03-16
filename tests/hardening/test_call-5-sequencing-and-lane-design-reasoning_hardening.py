from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req030-hardening-r1",
        "strategy_goal": "Harden replay and failure-path lane design reasoning.",
        "call_id": "call-5",
        "checked_at_utc": "2026-03-16T13:30:00Z",
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
                "context_note": "Shared runtime replay envelope remains in scope.",
            }
        ],
        "candidate_lane_designs": [
            {
                "lane_id": "lane.local-determinism",
                "recommendation_id": "rec.local-determinism",
                "summary": "Keep local failure-path diagnostics replay-stable.",
                "rationale": "Deterministic evidence is required for actionable reruns.",
                "sequencing_rationale": "Lane 1 must produce committed proof before any external follow-up.",
                "lane_order": 1,
                "lane_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
                "next_step": "Keep replay evidence in the committed task packet.",
                "synthesized_from_call_sequence": 5,
            },
            {
                "lane_id": "lane.runtime-sync",
                "recommendation_id": "rec.runtime-sync",
                "summary": "Coordinate replay hardening with runtime-orchestrator in lane 2.",
                "rationale": "Validated cross-project evidence still points at the shared recovery envelope.",
                "sequencing_rationale": "Lane 2 starts only after lane 1 establishes deterministic proof.",
                "lane_order": 2,
                "lane_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "next_step": "Publish the runtime coordination packet with evidence refs attached.",
                "synthesized_from_call_sequence": 5,
            },
        ],
        "strategic_claims": [],
    }


def test_req_030_hardening_cross_call_contradiction_emits_actionable_reason_code() -> None:
    input_payload = _base_input()
    input_payload["strategic_claims"] = [
        {
            "claim_id": "claim.recovery-envelope",
            "phase": "analysis",
            "summary": "Analysis says recovery handling still needs cross-project coordination.",
            "position": "coordinate",
            "source_call_sequence": 1,
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
            ],
        },
        {
            "claim_id": "claim.recovery-envelope",
            "phase": "synthesis",
            "summary": "Synthesis says recovery handling is purely local.",
            "position": "local-only",
            "source_call_sequence": 4,
            "evidence_refs": [
                "REQ-030::call::call-4::output::recommendation_synthesis",
            ],
        },
    ]
    payload = module.build_req_030_call_5_sequencing_and_lane_design_reasoning(**input_payload)

    assert module.validate_req_030_call_5_sequencing_and_lane_design_reasoning(payload) == []
    lane_design = payload["processing_behavior"]["lane_design"]
    contradiction_risk = next(
        row for row in lane_design["open_risks"] if row["reason_code"] == "cross_call_contradiction"
    )
    assert contradiction_risk["risk_id"] == "risk-claim-claim.recovery-envelope-contradiction"
    assert contradiction_risk["required_evidence_refs"] == [
        "REQ-030::call::call-1::output::situational_analysis",
        "REQ-030::call::call-4::output::recommendation_synthesis",
        "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
    ]


def test_req_030_hardening_uncited_claim_is_blocked_by_citation_discipline() -> None:
    input_payload = _base_input()
    input_payload["candidate_lane_designs"] = [
        {
            **input_payload["candidate_lane_designs"][0],
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                "reports/optimus-prime/planning/evidence/TASK-102/uncited-note.md",
            ],
        }
    ]
    payload = module.build_req_030_call_5_sequencing_and_lane_design_reasoning(**input_payload)

    assert module.validate_req_030_call_5_sequencing_and_lane_design_reasoning(payload) == []
    lane_design = payload["processing_behavior"]["lane_design"]
    citation_risk = next(row for row in lane_design["open_risks"] if row["reason_code"] == "uncited_strategic_claim")
    assert lane_design["decision"] == "blocked"
    assert lane_design["lane_blueprints"] == []
    assert payload["processing_behavior"]["context_usage"]["blocked_recommendation_ids"] == [
        "rec.local-determinism"
    ]
    assert citation_risk["risk_id"] == "risk-rec.local-determinism-citation"
    assert citation_risk["required_evidence_refs"] == [
        "REQ-030::call::call-5::output::lane_design_reasoning",
        "reports/optimus-prime/planning/evidence/TASK-102/uncited-note.md",
    ]


def test_req_030_hardening_replay_keeps_recommendation_ids_and_order_stable() -> None:
    first = module.build_req_030_call_5_sequencing_and_lane_design_reasoning(**_base_input())

    second_input = _base_input()
    second_input["candidate_lane_designs"] = list(reversed(second_input["candidate_lane_designs"]))
    second_input["cross_project_context"] = list(reversed(second_input["cross_project_context"]))
    second = module.build_req_030_call_5_sequencing_and_lane_design_reasoning(**second_input)

    assert module.validate_req_030_call_5_sequencing_and_lane_design_reasoning(first) == []
    assert module.validate_req_030_call_5_sequencing_and_lane_design_reasoning(second) == []
    assert (
        first["processing_behavior"]["context_usage"]["emitted_recommendation_ids"]
        == second["processing_behavior"]["context_usage"]["emitted_recommendation_ids"]
        == ["rec.local-determinism", "rec.runtime-sync"]
    )
    assert (
        first["processing_behavior"]["context_usage"]["emitted_lane_ids"]
        == second["processing_behavior"]["context_usage"]["emitted_lane_ids"]
        == ["lane.local-determinism", "lane.runtime-sync"]
    )
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
