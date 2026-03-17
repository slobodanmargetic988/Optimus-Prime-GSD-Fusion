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


def test_multi_call_strategy_pipeline_planner_emits_replay_stable_trace_rows() -> None:
    payload = module.build_req_025_multi_call_strategy_pipeline_planner(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req025-integration-r3",
        strategy_goal="Audit per-call orchestration trace stability for REQ-025.",
        call_depth=4,
        evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-080/TASK_EVIDENCE.json",
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-080/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
    )

    assert module.validate_req_025_multi_call_strategy_pipeline_planner(payload) == []

    plan_calls = payload["processing_behavior"]["pipeline_plan"]["calls"]
    trace_rows = payload["call_metadata"]["llm_call_trace_rows"]

    assert payload["call_metadata"]["llm_call_trace_path"] == module.LLM_CALL_TRACE_RELATIVE_PATH
    assert len(trace_rows) == len(plan_calls) == 4
    assert trace_rows[0]["call_objective"] == plan_calls[0]["purpose"]
    assert trace_rows[0]["input_refs"] == payload["processing_behavior"]["pipeline_plan"]["required_evidence_refs"]
    assert trace_rows[1]["input_refs"][-1] == trace_rows[0]["output_refs"][0]
    assert trace_rows[-1]["output_refs"] == [
        module._build_call_output_ref(
            plan_id=payload["processing_behavior"]["pipeline_plan"]["plan_id"],
            call_id=plan_calls[-1]["call_id"],
            expected_output=plan_calls[-1]["expected_output"],
        )
    ]
    assert payload["processing_behavior"]["recommendation"]["decision"] in trace_rows[-1]["handoff_summary"]

    second_payload = module.build_req_025_multi_call_strategy_pipeline_planner(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req025-integration-r3",
        strategy_goal="Audit per-call orchestration trace stability for REQ-025.",
        call_depth=4,
        evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-080/TASK_EVIDENCE.json",
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-080/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
    )
    assert second_payload["call_metadata"]["llm_call_trace_rows"] == trace_rows
    assert second_payload["call_metadata"]["llm_call_trace_sha256"] == payload["call_metadata"]["llm_call_trace_sha256"]
