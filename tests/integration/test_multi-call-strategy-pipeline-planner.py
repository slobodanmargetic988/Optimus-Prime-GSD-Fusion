from scripts import strategy_llm_pipeline as module


def test_multi_call_strategy_pipeline_planner_has_evidence_refs_and_complete_recommendation() -> None:
    payload = module.build_req_025_multi_call_strategy_pipeline_planner(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req025-integration-r1",
        strategy_goal="Plan a multi-call reasoning chain for REQ-025 with broad-sweep context.",
        call_depth=4,
        evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-079/TASK_EVIDENCE.json",
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-079/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        ],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "context_note": "Shared runtime coordination context for planner dependencies.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-local-pipeline-hardening",
                "summary": "Keep deterministic planner outputs replayable across reruns.",
                "rationale": "Metadata fingerprints require stable deterministic fields.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-079/TASK_EVIDENCE.json",
                ],
                "next_step": "Maintain canonical processing coverage in integration checks.",
            },
            {
                "action_id": "action-cross-project-runtime-sync",
                "summary": "Coordinate planner dependencies with runtime-orchestrator.",
                "rationale": "Cross-project call sequencing depends on Earth-sweep runtime evidence.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Publish obligation details with Earth-sweep evidence refs attached.",
            },
        ],
    )

    assert module.validate_req_025_multi_call_strategy_pipeline_planner(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]

    evidence_refs = recommendation["evidence_refs"]
    assert "reports/optimus-prime/planning/evidence/TASK-079/TASK_EVIDENCE.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-15/portfolio.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json" in evidence_refs

    expected_recommendation_fields = {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert set(recommendation.keys()) == expected_recommendation_fields
    assert recommendation["decision"] == "proceed"
    assert recommendation["cross_project_obligations"]

    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert "runtime-orchestrator" in usage["cross_project_projects_considered"]


def test_multi_call_strategy_pipeline_planner_records_open_risk_when_cross_project_evidence_is_missing() -> None:
    payload = module.build_req_025_multi_call_strategy_pipeline_planner(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req025-integration-r2",
        strategy_goal="Validate cross-project scope lock for REQ-025 planning.",
        call_depth=3,
        evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-079/TASK_EVIDENCE.json",
        ],
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-079/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [],
                "context_note": "Potential dependency that still lacks Earth-sweep evidence.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-cross-project-runtime-sync",
                "summary": "Coordinate planner dependencies with runtime-orchestrator.",
                "rationale": "Cross-project sequencing cannot be committed without Earth evidence refs.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-079/TASK_EVIDENCE.json",
                ],
                "next_step": "Collect Earth-sweep evidence before promoting obligations.",
            },
        ],
    )

    assert module.validate_req_025_multi_call_strategy_pipeline_planner(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["decision"] == "collect-earth-evidence"
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-action-cross-project-runtime-sync",
            "summary": "Coordinate planner dependencies with runtime-orchestrator.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-079/TASK_EVIDENCE.json",
            ],
        }
    ]
