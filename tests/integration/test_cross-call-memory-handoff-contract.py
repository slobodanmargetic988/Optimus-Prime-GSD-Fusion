from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req034-integration-r1",
        "strategy_goal": (
            "Carry bounded, cited memory across prior calls without contradiction drift or cross-project leakage."
        ),
        "call_id": "call-memory-handoff",
        "checked_at_utc": "2026-03-16T13:20:00Z",
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-116/TASK_EVIDENCE.json",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/portfolio.json",
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            "reports/earth/sweeps/2026-03-16/planner-core.json",
        ],
        "cross_project_context": [
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "context_note": "Runtime orchestrator owns the shared recovery envelope touched by fallback behavior.",
            },
            {
                "project_id": "planner-core",
                "project_root": "/workspace/projects/Earth/planner-core",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/planner-core.json",
                ],
                "context_note": "Planner core still shares execution capacity assumptions with the target project.",
            },
        ],
        "prior_call_handoffs": [
            {
                "sequence": 1,
                "call_id": "call-1",
                "phase": "analysis",
                "output_ref": "REQ-034::call::call-1::output::situational_analysis",
                "memory_items": [
                    {
                        "memory_id": "memory.scope-guard",
                        "summary": "Keep the reasoning scope locked to the target project unless Earth evidence says otherwise.",
                        "category": "guardrail",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-116/TASK_EVIDENCE.json",
                        ],
                    },
                    {
                        "memory_id": "memory.runtime-envelope",
                        "summary": "The shared runtime envelope still depends on runtime-orchestrator coordination.",
                        "category": "dependency",
                        "position": "preserve",
                        "project_scope": "cross-project",
                        "project_id": "runtime-orchestrator",
                        "citation_refs": [
                            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                        ],
                    },
                    {
                        "memory_id": "memory.local-diagnostics",
                        "summary": "Local diagnostics must stay replay-stable across later calls.",
                        "category": "constraint",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-116/TASK_EVIDENCE.json",
                        ],
                    },
                    {
                        "memory_id": "memory.zzz-extra",
                        "summary": "This extra item proves the handoff contract trims memory to a bounded window.",
                        "category": "note",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-116/TASK_EVIDENCE.json",
                        ],
                    },
                ],
            },
            {
                "sequence": 2,
                "call_id": "call-2",
                "phase": "planning",
                "output_ref": "REQ-034::call::call-2::output::execution_plan",
                "memory_items": [
                    {
                        "memory_id": "memory.runtime-envelope",
                        "summary": "Planning still treats runtime-orchestrator as the shared recovery owner.",
                        "category": "dependency",
                        "position": "preserve",
                        "project_scope": "cross-project",
                        "project_id": "runtime-orchestrator",
                        "citation_refs": [
                            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                        ],
                    },
                    {
                        "memory_id": "memory.planner-capacity",
                        "summary": "Planner core still controls the shared execution capacity boundary.",
                        "category": "dependency",
                        "position": "preserve",
                        "project_scope": "cross-project",
                        "project_id": "planner-core",
                        "citation_refs": [
                            "reports/earth/sweeps/2026-03-16/planner-core.json",
                        ],
                    },
                    {
                        "memory_id": "memory.local-diagnostics",
                        "summary": "Later calls still need replay-stable diagnostics for regressions.",
                        "category": "constraint",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-116/TASK_EVIDENCE.json",
                        ],
                    },
                ],
            },
            {
                "sequence": 3,
                "call_id": "call-3",
                "phase": "validation",
                "output_ref": "REQ-034::call::call-3::output::dependency_validation",
                "memory_items": [
                    {
                        "memory_id": "memory.runtime-envelope",
                        "summary": "Validation now disputes the earlier runtime-orchestrator assumption.",
                        "category": "dependency",
                        "position": "retire",
                        "project_scope": "cross-project",
                        "project_id": "runtime-orchestrator",
                        "citation_refs": [
                            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                        ],
                    },
                    {
                        "memory_id": "memory.planner-capacity",
                        "summary": "Planner core coordination remains evidence-backed.",
                        "category": "dependency",
                        "position": "preserve",
                        "project_scope": "cross-project",
                        "project_id": "planner-core",
                        "citation_refs": [
                            "reports/earth/sweeps/2026-03-16/planner-core.json",
                        ],
                    },
                    {
                        "memory_id": "memory.local-diagnostics",
                        "summary": "Validation still needs replay-stable local diagnostics.",
                        "category": "constraint",
                        "position": "preserve",
                        "project_scope": "local",
                        "project_id": "",
                        "citation_refs": [
                            "reports/optimus-prime/planning/evidence/TASK-116/TASK_EVIDENCE.json",
                        ],
                    },
                ],
            },
        ],
        "candidate_recommendations": [
            {
                "recommendation_id": "rec.local-diagnostics",
                "summary": "Keep local diagnostics replay-stable across the remaining calls.",
                "rationale": "The same local diagnostic constraint survives analysis, planning, and validation handoffs.",
                "recommendation_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-116/TASK_EVIDENCE.json",
                ],
                "next_step": "Keep the replay-stable diagnostics packet attached to every later call.",
                "synthesized_from_call_sequence": 3,
                "memory_anchor_ids": [
                    "memory.local-diagnostics",
                ],
            },
            {
                "recommendation_id": "rec.planner-core-sync",
                "summary": "Coordinate shared execution capacity assumptions with planner-core.",
                "rationale": "Planner-core evidence stays consistent across the bounded handoff window.",
                "recommendation_scope": "cross-project",
                "project_id": "planner-core",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/planner-core.json",
                ],
                "next_step": "Open the planner-core follow-up with Earth-sweep refs attached.",
                "synthesized_from_call_sequence": 3,
                "memory_anchor_ids": [
                    "memory.planner-capacity",
                ],
            },
            {
                "recommendation_id": "rec.runtime-orchestrator-sync",
                "summary": "Promote the runtime-orchestrator follow-up immediately.",
                "rationale": "This should be blocked because the memory handoff contract detected contradiction drift.",
                "recommendation_scope": "cross-project",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
                "next_step": "Do not emit this obligation while the memory contradiction remains unresolved.",
                "synthesized_from_call_sequence": 3,
                "memory_anchor_ids": [
                    "memory.runtime-envelope",
                ],
            },
        ],
    }


def test_req_034_emits_bounded_memory_handoff_with_complete_recommendation() -> None:
    payload = module.build_req_034_cross_call_memory_handoff_contract(**_base_input())

    assert module.validate_req_034_cross_call_memory_handoff_contract(payload) == []

    processing = payload["processing_behavior"]
    usage = processing["context_usage"]
    recommendation = processing["recommendation"]
    memory_handoffs = recommendation["memory_handoffs"]
    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "memory_handoffs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["rationale"] == "handoffs=3 active_memory=3 local=1 obligations=1 open_risks=2"
    assert "reports/optimus-prime/planning/evidence/TASK-116/TASK_EVIDENCE.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-16/portfolio.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-16/planner-core.json" in recommendation["evidence_refs"]

    assert usage["prior_call_handoffs_used"] is True
    assert usage["bounded_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["prior_call_ids_considered"] == ["call-1", "call-2", "call-3"]
    assert usage["cross_project_projects_considered"] == ["planner-core", "runtime-orchestrator"]
    assert usage["active_memory_ids"] == [
        "memory.local-diagnostics",
        "memory.planner-capacity",
        "memory.scope-guard",
    ]
    assert usage["suppressed_memory_ids"] == ["memory.runtime-envelope"]
    assert usage["recommended_action_ids_emitted"] == ["rec.local-diagnostics"]
    assert usage["cross_project_obligation_ids_emitted"] == ["obligation-rec.planner-core-sync"]

    assert len(memory_handoffs) == 3
    assert memory_handoffs[0]["handoff_ref"] == (
        "REQ-034::call::call-1::output::situational_analysis::memory_handoff"
    )
    assert memory_handoffs[0]["bounded_item_count"] == 3
    assert memory_handoffs[0]["truncated_item_count"] == 1

    assert recommendation["recommended_actions"] == [
        {
            "recommendation_id": "rec.local-diagnostics",
            "summary": "Keep local diagnostics replay-stable across the remaining calls.",
            "rationale": (
                "The same local diagnostic constraint survives analysis, planning, and validation handoffs."
            ),
            "next_step": "Keep the replay-stable diagnostics packet attached to every later call.",
            "memory_anchor_ids": ["memory.local-diagnostics"],
            "source_output_refs": ["REQ-034::call::call-3::output::dependency_validation"],
            "evidence_refs": [
                "REQ-034::call::call-3::output::dependency_validation",
                "reports/optimus-prime/planning/evidence/TASK-116/TASK_EVIDENCE.json",
            ],
        }
    ]
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-rec.planner-core-sync",
            "project_id": "planner-core",
            "recommendation_id": "rec.planner-core-sync",
            "summary": "Coordinate shared execution capacity assumptions with planner-core.",
            "rationale": "Planner-core evidence stays consistent across the bounded handoff window.",
            "next_step": "Open the planner-core follow-up with Earth-sweep refs attached.",
            "memory_anchor_ids": ["memory.planner-capacity"],
            "source_output_refs": ["REQ-034::call::call-3::output::dependency_validation"],
            "evidence_refs": [
                "REQ-034::call::call-3::output::dependency_validation",
                "reports/earth/sweeps/2026-03-16/planner-core.json",
                "reports/earth/sweeps/2026-03-16/portfolio.json",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-memory.runtime-envelope-contradiction",
            "reason_code": "cross_call_contradiction",
            "summary": "Validation now disputes the earlier runtime-orchestrator assumption.",
            "required_evidence_refs": [
                "REQ-034::call::call-1::output::situational_analysis",
                "REQ-034::call::call-2::output::execution_plan",
                "REQ-034::call::call-3::output::dependency_validation",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
        },
        {
            "risk_id": "risk-rec.runtime-orchestrator-sync",
            "reason_code": "cross_call_contradiction",
            "summary": "Promote the runtime-orchestrator follow-up immediately.",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
        },
    ]

    assert len(trace_rows) == 4
    assert trace_rows[-1]["call_id"] == "call-memory-handoff"
    assert trace_rows[-1]["handoff_summary"] == (
        "Call 4 emits memory_handoff_contract with 3 prior handoff(s) and 3 active memory item(s)."
    )


def test_req_034_replay_stays_deterministic_when_input_order_changes() -> None:
    first = module.build_req_034_cross_call_memory_handoff_contract(**_base_input())

    second_input = _base_input()
    second_input["cross_project_context"] = list(reversed(second_input["cross_project_context"]))
    second_input["candidate_recommendations"] = list(reversed(second_input["candidate_recommendations"]))
    second_input["prior_call_handoffs"] = [
        {
            **row,
            "memory_items": list(reversed(row["memory_items"])),
        }
        for row in second_input["prior_call_handoffs"]
    ]
    second = module.build_req_034_cross_call_memory_handoff_contract(**second_input)

    assert module.validate_req_034_cross_call_memory_handoff_contract(first) == []
    assert module.validate_req_034_cross_call_memory_handoff_contract(second) == []
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["processing_behavior"]["recommendation"] == second["processing_behavior"]["recommendation"]
