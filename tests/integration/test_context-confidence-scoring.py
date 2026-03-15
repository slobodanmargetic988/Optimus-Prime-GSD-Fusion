from scripts import strategy_context_sweep as module


def test_req_022_context_confidence_scoring_has_evidence_refs_and_complete_recommendation():
    payload = module.build_req_022_context_confidence_scoring(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req022-integration-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-070/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
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
                "action_id": "action-local-clarify-context",
                "summary": "Clarify context confidence semantics for downstream planning.",
                "rationale": "Downstream planning should not overfit weak inputs.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-070/TASK_EVIDENCE.json",
                ],
                "next_step": "Keep deterministic confidence scoring fields stable.",
            }
        ],
    )

    assert module.validate_req_022_context_confidence_scoring(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]
    confidence = processing["context_confidence"]

    evidence_refs = recommendation["evidence_refs"]
    assert "reports/optimus-prime/planning/evidence/TASK-070/TASK_EVIDENCE.json" in evidence_refs
    assert "reports/earth/sweeps/2026-03-15/portfolio.json" in evidence_refs
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

    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert "runtime-orchestrator" in usage["cross_project_projects_considered"]

    assert confidence["recency_anchor_date"] == "2026-03-15"
    assert isinstance(confidence["elements"], list)
    assert {row["element_kind"] for row in confidence["elements"]} >= {
        "target-project",
        "earth-sweep",
        "cross-project",
    }


def test_req_022_low_confidence_context_is_marked_and_blocks_overfitting():
    payload = module.build_req_022_context_confidence_scoring(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req022-integration-r2",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-070/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        earth_sweep_source_artifacts=[
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-01/runtime-orchestrator.json",
                "status": "stale",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/portfolio.json",
                ],
            }
        ],
        required_context_documents=[
            {
                "doc_kind": "scope",
                "doc_ref": "scope.md",
                "status": "missing",
                "evidence_refs": [],
            }
        ],
    )

    assert module.validate_req_022_context_confidence_scoring(payload) == []

    processing = payload["processing_behavior"]
    confidence = processing["context_confidence"]
    recommendation = processing["recommendation"]

    assert confidence["low_confidence_element_ids"]
    assert recommendation["decision"] == "resolve-context-gaps"

    low_risks = [row for row in recommendation["open_risks"] if row.get("reason_code") == "low_context_confidence"]
    assert low_risks
    required_refs = {ref for risk in low_risks for ref in risk.get("required_evidence_refs", [])}
    assert "reports/earth/sweeps/2026-03-01/runtime-orchestrator.json" in required_refs
    assert "scope.md" in required_refs

