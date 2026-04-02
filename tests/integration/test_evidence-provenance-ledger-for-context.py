from scripts import strategy_context_sweep as module


def test_req_021_integration_ledger_tracks_broad_sweep_context_and_recommendation_claims():
    payload = module.build_req_021_evidence_provenance_ledger_for_context(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req021-integration-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-066/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        cross_project_context=[
            {
                "project_id": "ground-control-hub",
                "project_root": "/workspace/projects/Earth/ground-control-hub",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                ],
                "context_note": "Cross-project provenance expectations for context auditing.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-local-ledger",
                "summary": "Emit provenance ledger for context claims.",
                "rationale": "Target project evidence shows the audit surface needs deterministic provenance.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-066/TASK_EVIDENCE.json",
                ],
                "next_step": "Attach the REQ-021 ledger to the context sweep output.",
            },
            {
                "action_id": "action-cross-project-audit",
                "summary": "Align provenance expectations with Ground Control Hub.",
                "rationale": "Cross-project obligations are valid only when Earth-sweep evidence refs are attached.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "ground-control-hub",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                ],
                "next_step": "Open the cross-project follow-up only with Earth evidence attached.",
            },
        ],
        earth_sweep_source_artifacts=[
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/sources/ground-control-hub.md",
                "status": "stale",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                ],
            }
        ],
    )

    assert module.validate_req_021_evidence_provenance_ledger_for_context(payload) == []

    ledger = payload["evidence_provenance_ledger_for_context"]
    claim_keys = {row["claim_key"] for row in ledger["context_claims"]}
    canonical_processing_input = payload["call_metadata"]["canonical_processing_input"]

    assert canonical_processing_input["cross_project_context"][0]["project_id"] == "ground-control-hub"
    assert canonical_processing_input["earth_sweep_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/portfolio.json",
    ]

    expected_claim_keys = {
        "processing_behavior.context_inputs.target_project.evidence_refs",
        "processing_behavior.context_inputs.earth_sweep.evidence_refs",
        "processing_behavior.context_inputs.cross_project_context[project_id=ground-control-hub]",
        "processing_behavior.context_inputs.candidate_recommendations[action_id=action-local-ledger]",
        "processing_behavior.context_inputs.candidate_recommendations[action_id=action-cross-project-audit]",
        "processing_behavior.context_inputs.earth_sweep_source_artifacts[artifact_ref=reports/earth/sweeps/2026-03-15/sources/ground-control-hub.md]",
        "processing_behavior.context_usage.target_project_context_used",
        "processing_behavior.context_usage.earth_sweep_context_used",
        "processing_behavior.context_usage.cross_project_context_used",
        "processing_behavior.context_usage.cross_project_projects_considered",
        "processing_behavior.context_usage.cross_project_refs_used",
        "processing_behavior.context_usage.evidence_refs_used",
        "processing_behavior.recommendation.decision",
        "processing_behavior.recommendation.rationale",
        "processing_behavior.recommendation.confidence",
        "processing_behavior.recommendation.evidence_refs",
        "processing_behavior.recommendation.recommended_actions[action_id=action-local-ledger]",
        "processing_behavior.recommendation.recommended_actions[action_id=action-cross-project-audit]",
        "processing_behavior.recommendation.cross_project_obligations[obligation_id=obligation-action-cross-project-audit]",
        "processing_behavior.recommendation.open_risks[risk_id=risk-earth-source-7c8910de8334]",
    }
    assert expected_claim_keys.issubset(claim_keys)

    expected_index = [
        "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
        "reports/earth/sweeps/2026-03-15/portfolio.json",
        "reports/earth/sweeps/2026-03-15/sources/ground-control-hub.md",
        "reports/optimus-prime/planning/evidence/TASK-066/TASK_EVIDENCE.json",
    ]
    assert ledger["artifact_refs_index"] == expected_index

    decision_claim = next(
        row for row in ledger["context_claims"] if row["claim_key"] == "processing_behavior.recommendation.decision"
    )
    assert decision_claim["source_artifact_refs"] == expected_index

    obligation_claim = next(
        row
        for row in ledger["context_claims"]
        if row["claim_key"]
        == "processing_behavior.recommendation.cross_project_obligations[obligation_id=obligation-action-cross-project-audit]"
    )
    assert obligation_claim["source_artifact_refs"] == [
        "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
        "reports/earth/sweeps/2026-03-15/portfolio.json",
    ]


def test_req_021_integration_cross_project_ideas_without_earth_refs_stay_open_risks():
    payload = module.build_req_021_evidence_provenance_ledger_for_context(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req021-integration-r2",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-066/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[],
        cross_project_context=[
            {
                "project_id": "ground-control-hub",
                "project_root": "/workspace/projects/Earth/ground-control-hub",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                ],
                "context_note": "Cross-project provenance expectations remain incomplete without Earth-sweep refs.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-cross-project-audit",
                "summary": "Align provenance expectations with Ground Control Hub.",
                "rationale": "Cross-project obligations require Earth-sweep evidence refs.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "ground-control-hub",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                ],
                "next_step": "Attach Earth evidence before opening the obligation.",
            }
        ],
    )

    assert module.validate_req_021_evidence_provenance_ledger_for_context(payload) == []

    ledger = payload["evidence_provenance_ledger_for_context"]
    claim_keys = {row["claim_key"] for row in ledger["context_claims"]}

    assert payload["call_metadata"]["canonical_processing_input"]["earth_sweep_evidence_refs"] == []
    assert "processing_behavior.recommendation.open_risks[risk_id=risk-action-cross-project-audit]" in claim_keys
    assert (
        "processing_behavior.recommendation.cross_project_obligations[obligation_id=obligation-action-cross-project-audit]"
        not in claim_keys
    )
    assert "processing_behavior.context_inputs.earth_sweep.evidence_refs" not in claim_keys
    assert "processing_behavior.context_usage.earth_sweep_context_used" not in claim_keys
    assert ledger["artifact_refs_index"] == [
        "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
        "reports/optimus-prime/planning/evidence/TASK-066/TASK_EVIDENCE.json",
    ]
