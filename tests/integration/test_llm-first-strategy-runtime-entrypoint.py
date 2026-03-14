from scripts import strategy_context_sweep as module


def test_llm_first_runtime_entrypoint_has_evidence_refs_and_complete_recommendation():
    payload = module.build_req_001_runtime_entrypoint(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req001-integration-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-002/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-14/portfolio.json",
        ],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-14/runtime-orchestrator.json",
                ],
                "context_note": "Earth-wide context for shared runtime constraints.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-local-hardening",
                "summary": "Harden runtime entrypoint payload validation.",
                "rationale": "Target project evidence confirms contract requirements.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-002/TASK_EVIDENCE.json",
                ],
                "next_step": "Update builder and validator behavior.",
            },
            {
                "action_id": "action-cross-runtime-sync",
                "summary": "Coordinate runtime strategy assumptions with runtime-orchestrator.",
                "rationale": "Cross-project dependency is evidence-backed by Earth sweep refs.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-14/runtime-orchestrator.json",
                ],
                "next_step": "Open coordination task with evidence references attached.",
            },
        ],
    )

    assert module.validate_req_001_runtime_entrypoint(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]
    evidence_refs = recommendation["evidence_refs"]
    assert "reports/optimus-prime/planning/evidence/TASK-002/TASK_EVIDENCE.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-14/portfolio.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-14/runtime-orchestrator.json" in evidence_refs

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


def test_cross_project_context_without_earth_evidence_becomes_open_risk():
    payload = module.build_req_001_runtime_entrypoint(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req001-integration-r2",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-002/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-14/runtime-orchestrator.json",
                ],
                "context_note": "Potential cross-project dependency, evidence still incomplete.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-cross-runtime-sync",
                "summary": "Coordinate runtime strategy assumptions with runtime-orchestrator.",
                "rationale": "Cross-project dependency requires Earth-sweep evidence refs.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-14/runtime-orchestrator.json",
                ],
                "next_step": "Open coordination task with evidence references attached.",
            },
        ],
    )

    assert module.validate_req_001_runtime_entrypoint(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["decision"] == "collect-earth-evidence"
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-action-cross-runtime-sync",
            "summary": "Coordinate runtime strategy assumptions with runtime-orchestrator.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-14/runtime-orchestrator.json",
            ],
        }
    ]
