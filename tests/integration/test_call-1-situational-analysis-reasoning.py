from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "mission": {
                "text": "Keep autonomous delivery loops deterministic, observable, and grounded in verifiable evidence.",
                "source": "mission.md",
            },
            "scope": {
                "text": (
                    "Limit this wave to contract and data-model surfaces backed by planning and runtime evidence, "
                    "with later-call follow-up for unresolved gaps."
                ),
                "source": "scope.md",
            },
        },
        "planning_evidence": {
            "artifacts": [
                {
                    "artifact_id": "PLAN-001",
                    "summary": "Plan packets already cover the contract and testing work for the current wave.",
                    "status": "ready",
                    "source_ref": "reports/optimus-prime/planning/PLAN_PACKETS.json",
                    "signals": [
                        "Planner output satisfies the mandatory planning gate.",
                        "Contract, fixture, sample, and test work are all explicitly scoped.",
                    ],
                    "unknowns": [],
                },
                {
                    "artifact_id": "PLAN-002",
                    "summary": "Task execution state still marks Call-1 contract/data-model implementation as pending verification.",
                    "status": "partial",
                    "source_ref": "reports/optimus-prime/planning/TASK_EXECUTION_STATE.json",
                    "signals": [
                        "Implementation intent is stable.",
                        "Verification evidence is not yet attached to the task state.",
                    ],
                    "unknowns": [
                        {
                            "question": "Has task-state drift been reconciled against the latest implementation packet?",
                            "why_it_matters": (
                                "Call-2 needs a stable implementation target before expanding execution actions."
                            ),
                        },
                        {
                            "question": "Do current task packets already reserve follow-up work for unresolved Call-1 unknowns?",
                            "why_it_matters": "Call-2 must avoid duplicating work that is already planned elsewhere.",
                        },
                    ],
                },
            ]
        },
        "runtime_evidence": {
            "artifacts": [
                {
                    "artifact_id": "RUN-001",
                    "summary": "Latest canary execution completed but recovery behavior remained degraded during fallback.",
                    "status": "degraded",
                    "source_ref": "reports/optimus-prime/planning/VERIFICATION.md",
                    "signals": [
                        "Primary canary lane completed successfully.",
                        "Fallback recovery still needs tighter evidence on current branch behavior.",
                    ],
                    "unknowns": [
                        {
                            "question": "Is the degraded fallback behavior still reproducible on the current branch head?",
                            "why_it_matters": (
                                "Call-2 must know whether the runtime concern is active or stale before prescribing next actions."
                            ),
                        }
                    ],
                },
                {
                    "artifact_id": "RUN-002",
                    "summary": "Runtime state artifacts confirm the system is still producing usable execution evidence.",
                    "status": "healthy",
                    "source_ref": "reports/optimus-prime/planning/STATE.json",
                    "signals": [
                        "Runtime evidence is still being emitted deterministically.",
                        "No total runtime blackout is present.",
                    ],
                    "unknowns": [],
                },
            ]
        },
        "analysis_type": "call_1_situational_analysis_reasoning",
        "call_id": "call-1",
        "checked_at_utc": "2026-03-16T09:30:00Z",
    }


def test_req_026_recommendation_is_complete_and_uses_cross_project_context() -> None:
    payload = module.build_req_026_call_1_situational_analysis_reasoning(
        **_base_input(),
        broad_sweep_context={
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/portfolio.json",
            ],
            "cross_project_context": [
                {
                    "project_id": "runtime-orchestrator",
                    "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                    ],
                    "context_note": "Runtime orchestrator owns the shared recovery envelope touched by degraded fallback behavior.",
                },
                {
                    "project_id": "planner-core",
                    "project_root": "/workspace/projects/Earth/planner-core",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/planner-core.json",
                    ],
                    "context_note": "Planner core may already reserve follow-up capacity for unknown resolution in later calls.",
                },
            ],
            "candidate_recommendations": [
                {
                    "recommendation_id": "rec-call-2-follow-up",
                    "summary": "Carry explicit Call-1 unknowns into the next implementation-planning pass before scope expands.",
                    "rationale": (
                        "Planning and runtime evidence both show follow-up work is still required before later calls "
                        "can safely commit to execution."
                    ),
                    "recommendation_scope": "local",
                    "project_id": "",
                    "requires_earth_evidence": False,
                    "evidence_refs": [
                        "reports/optimus-prime/planning/TASK_EXECUTION_STATE.json",
                        "reports/optimus-prime/planning/VERIFICATION.md",
                    ],
                    "next_step": "Record the unknowns in the Call-2 packet and attach updated verification evidence.",
                },
                {
                    "recommendation_id": "rec-runtime-orchestrator-sync",
                    "summary": "Coordinate degraded fallback interpretation with runtime-orchestrator before shared runtime assumptions change.",
                    "rationale": (
                        "Earth-sweep context confirms runtime-orchestrator owns the shared recovery envelope "
                        "implicated by degraded runtime evidence."
                    ),
                    "recommendation_scope": "cross-project",
                    "project_id": "runtime-orchestrator",
                    "requires_earth_evidence": True,
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                        "reports/optimus-prime/planning/VERIFICATION.md",
                    ],
                    "next_step": "Open a cross-project follow-up with Earth-sweep and runtime verification refs attached.",
                },
                {
                    "recommendation_id": "rec-analytics-unknown-routing",
                    "summary": "Route situational-analysis unknowns into analytics-hub reporting.",
                    "rationale": (
                        "The idea is plausible, but Call-1 must not create a cross-project obligation without matched "
                        "Earth-sweep context."
                    ),
                    "recommendation_scope": "cross-project",
                    "project_id": "analytics-hub",
                    "requires_earth_evidence": True,
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/analytics-hub.json",
                    ],
                    "next_step": "Confirm analytics-hub participation with Earth-sweep evidence before adding any cross-project obligation.",
                },
            ],
        },
    )

    assert module.validate_req_026_call_1_situational_analysis_reasoning(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]
    evidence_refs = recommendation["evidence_refs"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_next_actions",
        "cross_project_context",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["confidence"] == "low"
    assert recommendation["rationale"] == "assessment=needs-follow-up unknowns=3 local=1 obligations=1 open_risks=1"
    assert evidence_refs == [
        "reports/optimus-prime/planning/PLAN_PACKETS.json",
        "reports/optimus-prime/planning/TASK_EXECUTION_STATE.json",
        "reports/optimus-prime/planning/VERIFICATION.md",
        "reports/optimus-prime/planning/STATE.json",
        "reports/earth/sweeps/2026-03-16/portfolio.json",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-16/analytics-hub.json",
    ]

    assert usage["broad_sweep_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_evidence_refs_used"] == ["reports/earth/sweeps/2026-03-16/portfolio.json"]
    assert usage["cross_project_projects_considered"] == ["runtime-orchestrator", "planner-core"]
    assert usage["cross_project_projects_with_evidence_refs"] == ["runtime-orchestrator", "planner-core"]
    assert usage["cross_project_projects_without_evidence_refs"] == []
    assert usage["candidate_recommendation_ids_considered"] == [
        "rec-call-2-follow-up",
        "rec-runtime-orchestrator-sync",
        "rec-analytics-unknown-routing",
    ]
    assert usage["unknown_ids_for_later_calls"] == ["unknown.001", "unknown.002", "unknown.003"]

    assert recommendation["cross_project_context"] == {
        "cross_project": True,
        "projects_considered": ["runtime-orchestrator", "planner-core"],
        "projects_with_evidence_refs": ["runtime-orchestrator", "planner-core"],
        "projects_without_evidence_refs": [],
        "earth_sweep_evidence_refs": ["reports/earth/sweeps/2026-03-16/portfolio.json"],
        "evidence_refs_by_project": {
            "runtime-orchestrator": ["reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"],
            "planner-core": ["reports/earth/sweeps/2026-03-16/planner-core.json"],
        },
    }
    assert recommendation["recommended_next_actions"] == [
        {
            "recommendation_id": "rec-call-2-follow-up",
            "summary": "Carry explicit Call-1 unknowns into the next implementation-planning pass before scope expands.",
            "rationale": (
                "Planning and runtime evidence both show follow-up work is still required before later calls can "
                "safely commit to execution."
            ),
            "next_step": "Record the unknowns in the Call-2 packet and attach updated verification evidence.",
            "evidence_refs": [
                "reports/optimus-prime/planning/TASK_EXECUTION_STATE.json",
                "reports/optimus-prime/planning/VERIFICATION.md",
            ],
        }
    ]
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-rec-runtime-orchestrator-sync",
            "project_id": "runtime-orchestrator",
            "summary": "Coordinate degraded fallback interpretation with runtime-orchestrator before shared runtime assumptions change.",
            "rationale": (
                "Earth-sweep context confirms runtime-orchestrator owns the shared recovery envelope implicated by "
                "degraded runtime evidence."
            ),
            "next_step": "Open a cross-project follow-up with Earth-sweep and runtime verification refs attached.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/portfolio.json",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                "reports/optimus-prime/planning/VERIFICATION.md",
            ],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-rec-analytics-unknown-routing",
            "reason_code": "missing_cross_project_context",
            "summary": "Route situational-analysis unknowns into analytics-hub reporting.",
            "required_evidence_refs": ["reports/earth/sweeps/2026-03-16/analytics-hub.json"],
        }
    ]


def test_req_026_cross_project_idea_without_earth_evidence_becomes_open_risk() -> None:
    payload = module.build_req_026_call_1_situational_analysis_reasoning(
        **_base_input(),
        broad_sweep_context={
            "earth_sweep_evidence_refs": [],
            "cross_project_context": [
                {
                    "project_id": "runtime-orchestrator",
                    "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                    ],
                    "context_note": "Runtime orchestrator owns the shared recovery envelope touched by degraded fallback behavior.",
                }
            ],
            "candidate_recommendations": [
                {
                    "recommendation_id": "rec-runtime-orchestrator-sync",
                    "summary": "Coordinate degraded fallback interpretation with runtime-orchestrator before shared runtime assumptions change.",
                    "rationale": (
                        "Cross-project recovery coordination remains plausible, but Earth-sweep evidence is missing for this call."
                    ),
                    "recommendation_scope": "cross-project",
                    "project_id": "runtime-orchestrator",
                    "requires_earth_evidence": True,
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                    ],
                    "next_step": "Attach Earth-sweep evidence before creating any cross-project obligation.",
                }
            ],
        },
    )

    assert module.validate_req_026_call_1_situational_analysis_reasoning(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-rec-runtime-orchestrator-sync",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "summary": "Coordinate degraded fallback interpretation with runtime-orchestrator before shared runtime assumptions change.",
            "required_evidence_refs": ["reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"],
        }
    ]
