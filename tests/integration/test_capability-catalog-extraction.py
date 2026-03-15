from scripts import strategy_context_sweep as module


def test_req_013_processing_behavior_uses_capability_catalog_to_suppress_completed_work():
    payload = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-integration-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
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
                "context_note": "Earth runtime constraints for catalog extraction.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "capability-runtime-sync",
                "summary": "Coordinate runtime sync assumptions with runtime-orchestrator.",
                "rationale": "Cross-project runtime alignment remains mandatory.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Keep runtime sync assumptions aligned before rollout.",
            },
            {
                "action_id": "capability-replay-hardening",
                "summary": "Close replay hardening gap in local strategy pipeline.",
                "rationale": "Replay diagnostics are still missing in the local project.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                ],
                "next_step": "Implement deterministic replay checks and evidence wiring.",
            },
        ],
        capability_catalog_entries=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "capability_id": "capability-runtime-sync",
                "capability_summary": "Runtime sync capability already shipped in peer project.",
                "status": "provided",
                "source_version": "runtime-orchestrator@sha256:111",
                "source_artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                ],
            },
            {
                "project_id": "optimus-prime",
                "project_root": "/workspace/projects/optimus-prime",
                "capability_id": "capability-replay-hardening",
                "capability_summary": "Replay hardening remains missing locally.",
                "status": "missing",
                "source_version": "optimus-prime@sha256:222",
                "source_artifact_ref": "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                "evidence_refs": [],
            },
        ],
    )

    assert module.validate_req_013_capability_catalog_extraction(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]
    catalog = processing["capability_catalog"]

    assert recommendation["decision"] == "proceed"
    assert recommendation["open_risks"] == []
    assert [row["action_id"] for row in recommendation["recommended_actions"]] == ["capability-replay-hardening"]
    assert recommendation["suppressed_actions"] == [
        {
            "action_id": "capability-runtime-sync",
            "reason_code": "capability_already_provided",
            "summary": "Suppressed 'capability-runtime-sync' because capability catalog marks it as already provided.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        }
    ]
    assert recommendation["cross_project_obligations"] == []

    assert usage["capability_catalog_used"] is True
    assert usage["capabilities_provided_ids"] == ["capability-runtime-sync"]
    assert usage["capabilities_missing_ids"] == ["capability-replay-hardening"]
    assert usage["suppressed_completed_action_ids"] == ["capability-runtime-sync"]
    assert "runtime-orchestrator@sha256:111" in usage["capability_catalog_source_versions_used"]

    assert catalog["provided_capability_ids"] == ["capability-runtime-sync"]
    assert catalog["missing_capability_ids"] == ["capability-replay-hardening"]
    assert catalog["projects_considered"] == ["optimus-prime", "runtime-orchestrator"]


def test_req_013_cross_project_candidate_without_earth_refs_emits_missing_earth_reason_code():
    payload = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-integration-r2",
        earth_sweep_evidence_refs=[],
        candidate_recommendations=[
            {
                "action_id": "capability-cross-runtime-sync",
                "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
                "rationale": "Cross-project changes require Earth-sweep evidence refs.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Attach Earth evidence refs before opening obligations.",
            }
        ],
        capability_catalog_entries=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "capability_id": "capability-cross-runtime-sync",
                "capability_summary": "Cross-runtime sync capability still missing.",
                "status": "missing",
                "source_version": "runtime-orchestrator@sha256:333",
                "source_artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "evidence_refs": [],
            },
        ],
    )

    assert module.validate_req_013_capability_catalog_extraction(payload) == []
    assert payload["processing_behavior"]["recommendation"]["decision"] == "collect-earth-evidence"
    assert payload["processing_behavior"]["recommendation"]["open_risks"] == [
        {
            "risk_id": "risk-capability-cross-runtime-sync",
            "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        }
    ]
