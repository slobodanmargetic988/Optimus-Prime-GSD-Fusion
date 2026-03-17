import json

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
                        }
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


def _risk_map(payload: dict) -> dict[str, dict]:
    return {
        str(row["risk_id"]): row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
    }


def test_req_026_hardening_flags_cross_call_contradiction_with_deterministic_evidence_refs() -> None:
    payload = module.build_req_026_call_1_situational_analysis_reasoning(
        **_base_input(),
        broad_sweep_context={
            "earth_sweep_evidence_refs": ["reports/earth/sweeps/2026-03-16/portfolio.json"],
            "cross_project_context": [],
            "candidate_recommendations": [
                {
                    "recommendation_id": "rec-call-2-follow-up",
                    "summary": "Carry explicit Call-1 unknowns into the next implementation-planning pass before scope expands.",
                    "rationale": "Call-2 must resolve the remaining planning and runtime unknowns before scope expands.",
                    "recommendation_scope": "local",
                    "project_id": "",
                    "requires_earth_evidence": False,
                    "evidence_refs": [
                        "reports/optimus-prime/planning/TASK_EXECUTION_STATE.json",
                        "reports/optimus-prime/planning/VERIFICATION.md",
                    ],
                    "next_step": "Record the unknowns in the Call-2 packet and attach updated verification evidence.",
                }
            ],
            "strategic_claims": [
                {
                    "claim_id": "claim-runtime-recovery",
                    "phase": "analysis",
                    "summary": "Analysis says degraded fallback behavior remains an active branch-head concern.",
                    "position": "active-risk",
                    "source_call_sequence": 1,
                    "evidence_refs": ["reports/optimus-prime/planning/VERIFICATION.md"],
                },
                {
                    "claim_id": "claim-runtime-recovery",
                    "phase": "synthesis",
                    "summary": "Synthesis says degraded fallback behavior is already resolved and should not drive next actions.",
                    "position": "resolved-risk",
                    "source_call_sequence": 2,
                    "evidence_refs": ["reports/optimus-prime/planning/TASK_EXECUTION_STATE.json"],
                },
            ],
        },
    )

    assert module.validate_req_026_call_1_situational_analysis_reasoning(payload) == []

    contradiction_risk = _risk_map(payload)["risk-claim-claim-runtime-recovery-contradiction"]
    assert contradiction_risk == {
        "risk_id": "risk-claim-claim-runtime-recovery-contradiction",
        "reason_code": "cross_call_contradiction",
        "summary": "Synthesis says degraded fallback behavior is already resolved and should not drive next actions.",
        "required_evidence_refs": [
            "REQ-026::call-chain::01::analysis",
            "REQ-026::call-chain::02::synthesis",
            "reports/optimus-prime/planning/VERIFICATION.md",
            "reports/optimus-prime/planning/TASK_EXECUTION_STATE.json",
        ],
    }


def test_req_026_hardening_blocks_uncited_strategic_claims_with_reason_code() -> None:
    payload = module.build_req_026_call_1_situational_analysis_reasoning(
        **_base_input(),
        broad_sweep_context={
            "earth_sweep_evidence_refs": ["reports/earth/sweeps/2026-03-16/portfolio.json"],
            "cross_project_context": [],
            "candidate_recommendations": [],
            "strategic_claims": [
                {
                    "claim_id": "claim-branch-head-evidence",
                    "phase": "analysis",
                    "summary": "Branch-head verification already proves the degraded fallback issue is closed.",
                    "position": "resolved-risk",
                    "source_call_sequence": 1,
                    "evidence_refs": ["reports/optimus-prime/planning/BRANCH_HEAD_ONLY.md"],
                }
            ],
        },
    )

    assert module.validate_req_026_call_1_situational_analysis_reasoning(payload) == []

    citation_risk = _risk_map(payload)["risk-claim-claim-branch-head-evidence-citation"]
    assert citation_risk == {
        "risk_id": "risk-claim-claim-branch-head-evidence-citation",
        "reason_code": "uncited_strategic_claim",
        "summary": "Branch-head verification already proves the degraded fallback issue is closed.",
        "required_evidence_refs": [
            "REQ-026::call-chain::01::analysis",
            "reports/optimus-prime/planning/BRANCH_HEAD_ONLY.md",
        ],
    }


def test_req_026_hardening_replay_keeps_recommendation_ids_and_order_stable() -> None:
    base_context = {
        "earth_sweep_evidence_refs": ["reports/earth/sweeps/2026-03-16/portfolio.json"],
        "cross_project_context": [
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": ["reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"],
                "context_note": "Runtime orchestrator owns the shared recovery envelope touched by degraded fallback behavior.",
            },
            {
                "project_id": "planner-core",
                "project_root": "/workspace/projects/Earth/planner-core",
                "evidence_refs": ["reports/earth/sweeps/2026-03-16/planner-core.json"],
                "context_note": "Planner core may already reserve follow-up capacity for unknown resolution in later calls.",
            },
        ],
        "candidate_recommendations": [
            {
                "recommendation_id": "rec-z-unknown-log",
                "summary": "Persist explicit unknown tracking for the next call packet.",
                "rationale": "Later calls need a stable unknown ledger before scope expands.",
                "recommendation_scope": "local",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": ["reports/optimus-prime/planning/TASK_EXECUTION_STATE.json"],
                "next_step": "Append the current unknown set to the Call-2 packet.",
            },
            {
                "recommendation_id": "rec-b-runtime-sync",
                "summary": "Coordinate degraded fallback interpretation with runtime-orchestrator.",
                "rationale": "Runtime orchestration owns the shared recovery envelope implicated by degraded runtime evidence.",
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
                "recommendation_id": "rec-a-call-2-follow-up",
                "summary": "Carry explicit Call-1 unknowns into the next implementation-planning pass.",
                "rationale": "Call-2 still has to resolve the bounded planning and runtime unknowns.",
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
                "recommendation_id": "rec-c-analytics-routing",
                "summary": "Route unresolved unknowns into analytics-hub reporting.",
                "rationale": "The idea should stay blocked until analytics-hub participation is backed by Earth-sweep context.",
                "recommendation_scope": "cross-project",
                "project_id": "analytics-hub",
                "requires_earth_evidence": True,
                "evidence_refs": ["reports/earth/sweeps/2026-03-16/analytics-hub.json"],
                "next_step": "Confirm analytics-hub participation with Earth-sweep evidence before creating an obligation.",
            },
        ],
        "strategic_claims": [],
    }

    replay_context = json.loads(json.dumps(base_context))
    replay_context["cross_project_context"].reverse()
    replay_context["candidate_recommendations"].reverse()

    first = module.build_req_026_call_1_situational_analysis_reasoning(
        **_base_input(),
        broad_sweep_context=base_context,
    )
    second = module.build_req_026_call_1_situational_analysis_reasoning(
        **_base_input(),
        broad_sweep_context=replay_context,
    )

    assert module.validate_req_026_call_1_situational_analysis_reasoning(first) == []
    assert module.validate_req_026_call_1_situational_analysis_reasoning(second) == []
    assert first == second

    usage = first["processing_behavior"]["context_usage"]
    assert usage["candidate_recommendation_ids_considered"] == [
        "rec-a-call-2-follow-up",
        "rec-b-runtime-sync",
        "rec-c-analytics-routing",
        "rec-z-unknown-log",
    ]
    assert usage["local_recommendation_ids_emitted"] == [
        "rec-a-call-2-follow-up",
        "rec-z-unknown-log",
    ]
    assert usage["cross_project_obligation_ids_emitted"] == ["obligation-rec-b-runtime-sync"]
    assert usage["open_risk_ids_emitted"] == ["risk-rec-c-analytics-routing"]
