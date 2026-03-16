from scripts import strategy_llm_pipeline as module


def _contradiction_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req034-hardening-r1",
        "strategy_goal": "Harden cross-call memory replay against contradiction drift and uncited synthesis claims.",
        "call_id": "call-memory-handoff",
        "checked_at_utc": "2026-03-16T14:20:00Z",
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
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
                "context_note": "Runtime orchestrator remains the shared recovery owner.",
            }
        ],
        "prior_call_handoffs": [
            {
                "sequence": 1,
                "call_id": "call-1",
                "phase": "analysis",
                "output_ref": "REQ-034::call::call-1::output::situational_analysis",
                "memory_items": [
                    {
                        "memory_id": "memory.runtime-envelope",
                        "summary": "Analysis says runtime orchestrator still owns the shared recovery envelope.",
                        "category": "dependency",
                        "position": "preserve",
                        "project_scope": "cross-project",
                        "project_id": "runtime-orchestrator",
                        "citation_refs": [
                            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                        ],
                    }
                ],
            },
            {
                "sequence": 2,
                "call_id": "call-2",
                "phase": "synthesis",
                "output_ref": "REQ-034::call::call-2::output::recommendation_synthesis",
                "memory_items": [
                    {
                        "memory_id": "memory.runtime-envelope",
                        "summary": "Synthesis says runtime coordination should be retired from the handoff window.",
                        "category": "dependency",
                        "position": "retire",
                        "project_scope": "cross-project",
                        "project_id": "runtime-orchestrator",
                        "citation_refs": [
                            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                        ],
                    }
                ],
            },
        ],
        "candidate_recommendations": [
            {
                "recommendation_id": "rec.runtime-sync",
                "summary": "Promote the runtime-orchestrator follow-up immediately.",
                "rationale": "This synthesis recommendation must stay blocked while the handoff contract contradicts itself.",
                "recommendation_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "next_step": "Do not promote the runtime follow-up until the contradiction is resolved.",
                "synthesized_from_call_sequence": 2,
                "memory_anchor_ids": ["memory.runtime-envelope"],
            }
        ],
    }


def _stable_replay_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req034-hardening-r2",
        "strategy_goal": "Keep recommendation ids stable across replayed memory handoff runs.",
        "call_id": "call-memory-handoff",
        "checked_at_utc": "2026-03-16T14:25:00Z",
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/portfolio.json",
        ],
        "cross_project_context": [],
        "prior_call_handoffs": [
            {
                "sequence": 1,
                "call_id": "call-1",
                "phase": "analysis",
                "output_ref": "REQ-034::call::call-1::output::situational_analysis",
                "memory_items": [
                    {
                        "memory_id": "memory.beta",
                        "summary": "Beta diagnostic context remains in scope.",
                        "category": "constraint",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                        ],
                    },
                    {
                        "memory_id": "memory.alpha",
                        "summary": "Alpha diagnostic context remains in scope.",
                        "category": "constraint",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                        ],
                    },
                ],
            },
            {
                "sequence": 2,
                "call_id": "call-2",
                "phase": "validation",
                "output_ref": "REQ-034::call::call-2::output::dependency_validation",
                "memory_items": [
                    {
                        "memory_id": "memory.beta",
                        "summary": "Validation keeps beta diagnostics in scope.",
                        "category": "constraint",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                        ],
                    },
                    {
                        "memory_id": "memory.alpha",
                        "summary": "Validation keeps alpha diagnostics in scope.",
                        "category": "constraint",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                        ],
                    },
                ],
            },
        ],
        "candidate_recommendations": [
            {
                "recommendation_id": "rec.beta",
                "summary": "Keep beta diagnostics replay-stable.",
                "rationale": "Beta remains anchored in every prior handoff.",
                "recommendation_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                ],
                "next_step": "Carry beta diagnostics into the next call.",
                "synthesized_from_call_sequence": 2,
                "memory_anchor_ids": ["memory.beta"],
            },
            {
                "recommendation_id": "rec.alpha",
                "summary": "Keep alpha diagnostics replay-stable.",
                "rationale": "Alpha remains anchored in every prior handoff.",
                "recommendation_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                ],
                "next_step": "Carry alpha diagnostics into the next call.",
                "synthesized_from_call_sequence": 2,
                "memory_anchor_ids": ["memory.alpha"],
            },
        ],
    }


def test_req_034_hardening_cross_call_contradiction_between_analysis_and_synthesis_is_blocked() -> None:
    payload = module.build_req_034_cross_call_memory_handoff_contract(**_contradiction_input())

    assert module.validate_req_034_cross_call_memory_handoff_contract(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    contradiction_risk = next(
        row for row in recommendation["open_risks"] if row["risk_id"] == "risk-rec.runtime-sync"
    )

    assert recommendation["decision"] == "resolve-strategy-gaps"
    assert recommendation["recommended_actions"] == []
    assert recommendation["cross_project_obligations"] == []
    assert payload["processing_behavior"]["context_usage"]["suppressed_memory_ids"] == [
        "memory.runtime-envelope"
    ]
    assert contradiction_risk["reason_code"] == "cross_call_contradiction"
    assert contradiction_risk["required_evidence_refs"] == [
        "REQ-034::call::call-1::output::situational_analysis",
        "REQ-034::call::call-2::output::recommendation_synthesis",
        "REQ-034::call::call-memory-handoff::output::memory_handoff_contract",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
    ]


def test_req_034_hardening_uncited_strategic_claim_is_blocked_by_citation_discipline() -> None:
    input_payload = _stable_replay_input()
    input_payload["candidate_recommendations"] = [
        {
            **input_payload["candidate_recommendations"][0],
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-118/TASK_EVIDENCE.json",
                "reports/optimus-prime/planning/evidence/TASK-118/uncited-note.md",
            ],
        }
    ]

    payload = module.build_req_034_cross_call_memory_handoff_contract(**input_payload)

    assert module.validate_req_034_cross_call_memory_handoff_contract(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    citation_risk = next(row for row in recommendation["open_risks"] if row["risk_id"] == "risk-rec.beta")

    assert recommendation["decision"] == "resolve-strategy-gaps"
    assert recommendation["recommended_actions"] == []
    assert citation_risk["reason_code"] == "uncited_strategic_claim"
    assert citation_risk["required_evidence_refs"] == [
        "REQ-034::call::call-1::output::situational_analysis",
        "REQ-034::call::call-2::output::dependency_validation",
        "REQ-034::call::call-memory-handoff::output::memory_handoff_contract",
        "reports/optimus-prime/planning/evidence/TASK-118/uncited-note.md",
    ]


def test_req_034_hardening_replay_keeps_recommendation_ids_and_order_stable() -> None:
    first = module.build_req_034_cross_call_memory_handoff_contract(**_stable_replay_input())

    second_input = _stable_replay_input()
    second_input["prior_call_handoffs"] = [
        {
            **row,
            "memory_items": list(reversed(row["memory_items"])),
        }
        for row in reversed(second_input["prior_call_handoffs"])
    ]
    second_input["candidate_recommendations"] = list(reversed(second_input["candidate_recommendations"]))
    second = module.build_req_034_cross_call_memory_handoff_contract(**second_input)

    assert module.validate_req_034_cross_call_memory_handoff_contract(first) == []
    assert module.validate_req_034_cross_call_memory_handoff_contract(second) == []
    assert [row["recommendation_id"] for row in first["processing_behavior"]["recommendation"]["recommended_actions"]] == [
        "rec.alpha",
        "rec.beta",
    ]
    assert first["processing_behavior"]["recommendation"]["recommended_actions"] == second["processing_behavior"][
        "recommendation"
    ]["recommended_actions"]
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
