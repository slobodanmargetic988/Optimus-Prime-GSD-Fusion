from scripts import strategy_context_sweep as module


def test_req_009_processing_behavior_has_evidence_refs_and_complete_recommendation():
    payload = module.build_req_009_prior_strategy_revision_ingestion(
        current_revision_identity="rev-req009-integration-r4",
        prior_strategy_revisions=[
            {
                "revision_identity": "rev-req009-r2",
                "summary": "Prior revision baseline.",
                "recommended_action_ids": [
                    "action-audit-prior-revisions",
                    "action-track-drift-signals",
                ],
                "evidence_refs": [
                    "reports/strategy/revisions/rev-req009-r2.json",
                ],
            },
            {
                "revision_identity": "rev-req009-r3",
                "summary": "Latest prior revision before current composition.",
                "recommended_action_ids": [
                    "action-audit-prior-revisions",
                    "action-ingest-changelog-history",
                ],
                "evidence_refs": [
                    "reports/strategy/revisions/rev-req009-r3.json",
                ],
            },
        ],
        changelog_history=[
            {
                "change_id": "chg-200",
                "revision_identity": "rev-req009-r3",
                "action_id": "action-ingest-changelog-history",
                "change_type": "added",
                "change_summary": "Changelog ingestion is now explicit.",
                "changed_at": "2026-03-15T07:15:00Z",
                "evidence_refs": [
                    "CHANGELOG.md#req-009-r3",
                ],
            }
        ],
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-027/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "context_note": "Earth-wide context for runtime compatibility.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-audit-prior-revisions",
                "summary": "Keep revision-ingestion analysis active before composition.",
                "rationale": "Continuity must stay explicit for each new recommendation cycle.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-027/TASK_EVIDENCE.json",
                ],
                "next_step": "Keep ingestion checks in the recommendation loop.",
            },
            {
                "action_id": "action-cross-runtime-sync",
                "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
                "rationale": "Cross-project runtime constraints are Earth-sweep scoped.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Open a cross-project sync task with evidence refs.",
            },
        ],
    )

    assert module.validate_req_009_prior_strategy_revision_ingestion(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]

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

    evidence_refs = recommendation["evidence_refs"]
    assert "reports/optimus-prime/planning/evidence/TASK-027/TASK_EVIDENCE.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-15/portfolio.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json" in evidence_refs
    assert "reports/strategy/revisions/rev-req009-r3.json" in evidence_refs
    assert "CHANGELOG.md#req-009-r3" in evidence_refs

    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["prior_strategy_revisions_used"] is True
    assert usage["changelog_history_used"] is True
    assert "runtime-orchestrator" in usage["cross_project_projects_considered"]


def test_req_009_cross_project_candidate_without_earth_evidence_becomes_open_risk():
    payload = module.build_req_009_prior_strategy_revision_ingestion(
        current_revision_identity="rev-req009-integration-r5",
        prior_strategy_revisions=[
            {
                "revision_identity": "rev-req009-r3",
                "summary": "Latest prior revision before current composition.",
                "recommended_action_ids": [
                    "action-ingest-changelog-history",
                ],
                "evidence_refs": [
                    "reports/strategy/revisions/rev-req009-r3.json",
                ],
            }
        ],
        changelog_history=[
            {
                "change_id": "chg-201",
                "revision_identity": "rev-req009-r3",
                "action_id": "action-ingest-changelog-history",
                "change_type": "updated",
                "change_summary": "Tightened ingestion sequencing.",
                "changed_at": "2026-03-15T07:30:00Z",
                "evidence_refs": [
                    "CHANGELOG.md#req-009-r3",
                ],
            }
        ],
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-027/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "context_note": "Cross-project context exists but Earth evidence refs are not finalized.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-cross-runtime-sync",
                "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
                "rationale": "Cross-project runtime constraints require Earth evidence refs.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Gather Earth-sweep evidence refs before committing obligations.",
            },
        ],
    )

    assert module.validate_req_009_prior_strategy_revision_ingestion(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["decision"] == "collect-earth-evidence"
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-action-cross-runtime-sync",
            "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        }
    ]
