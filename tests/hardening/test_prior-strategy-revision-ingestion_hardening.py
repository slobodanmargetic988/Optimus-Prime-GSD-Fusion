import json

from scripts import strategy_context_sweep as module


def test_req_009_stale_earth_sweep_source_artifact_emits_deterministic_reason_code():
    payload = module.build_req_009_prior_strategy_revision_ingestion(
        current_revision_identity="rev-req009-hardening-r1",
        prior_strategy_revisions=[
            {
                "revision_identity": "rev-req009-r0",
                "summary": "Baseline prior revision for replay hardening.",
                "recommended_action_ids": ["action-replay-hardening"],
                "evidence_refs": [
                    "reports/strategy/revisions/rev-req009-r0.json",
                ],
            }
        ],
        changelog_history=[
            {
                "change_id": "chg-req009-hardening-r1",
                "revision_identity": "rev-req009-r0",
                "action_id": "action-replay-hardening",
                "change_type": "updated",
                "change_summary": "Replay hardening guardrails tightened.",
                "changed_at": "2026-03-15T08:00:00Z",
                "evidence_refs": [
                    "CHANGELOG.md#req-009-hardening-r1",
                ],
            }
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        earth_sweep_source_artifacts=[
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "status": "stale",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                ],
            }
        ],
    )

    assert module.validate_req_009_prior_strategy_revision_ingestion(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    stale_risks = [row for row in recommendation["open_risks"] if row["reason_code"] == "stale_earth_sweep_source_artifact"]

    assert len(stale_risks) == 1
    assert stale_risks[0]["risk_id"].startswith("risk-earth-source-")
    assert stale_risks[0]["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]
    assert recommendation["decision"] == "proceed-with-open-risks"


def test_req_009_missing_mission_scope_and_peer_project_docs_emit_explicit_reason_codes():
    payload = module.build_req_009_prior_strategy_revision_ingestion(
        current_revision_identity="rev-req009-hardening-r2",
        prior_strategy_revisions=[
            {
                "revision_identity": "rev-req009-r1",
                "summary": "Prior revision before missing-doc hardening check.",
                "recommended_action_ids": ["action-ingest-required-docs"],
                "evidence_refs": [
                    "reports/strategy/revisions/rev-req009-r1.json",
                ],
            }
        ],
        changelog_history=[],
        required_context_documents=[
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-028/TASK_EVIDENCE.json",
                ],
            },
            {
                "doc_kind": "scope",
                "doc_ref": "scope.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-028/TASK_EVIDENCE.json",
                ],
            },
            {
                "doc_kind": "peer-project",
                "project_id": "runtime-orchestrator",
                "doc_ref": "docs/runtime-orchestrator/overview.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
            },
        ],
    )

    assert module.validate_req_009_prior_strategy_revision_ingestion(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    assert sorted(row["reason_code"] for row in recommendation["open_risks"]) == [
        "missing_mission_doc",
        "missing_peer_project_doc",
        "missing_scope_doc",
    ]
    assert recommendation["decision"] == "proceed-with-open-risks"
    for risk in recommendation["open_risks"]:
        assert risk["required_evidence_refs"]


def test_req_009_context_bundle_serialization_is_replay_stable_across_repeated_runs():
    first = module.build_req_009_prior_strategy_revision_ingestion(
        current_revision_identity="rev-req009-hardening-r3",
        prior_strategy_revisions=[
            {
                "revision_identity": "rev-req009-r1",
                "summary": "Prior revision one.",
                "recommended_action_ids": [
                    "action-a",
                    "action-b",
                ],
                "evidence_refs": [
                    "reports/strategy/revisions/rev-req009-r1.json",
                ],
            },
            {
                "revision_identity": "rev-req009-r2",
                "summary": "Prior revision two.",
                "recommended_action_ids": [
                    "action-b",
                    "action-c",
                ],
                "evidence_refs": [
                    "reports/strategy/revisions/rev-req009-r2.json",
                ],
            },
        ],
        changelog_history=[
            {
                "change_id": "chg-202",
                "revision_identity": "rev-req009-r2",
                "action_id": "action-c",
                "change_type": "added",
                "change_summary": "Action C added to latest prior revision.",
                "changed_at": "2026-03-15T08:30:00Z",
                "evidence_refs": [
                    "CHANGELOG.md#req-009-c",
                    "CHANGELOG.md#req-009-c",
                ],
            },
            {
                "change_id": "chg-201",
                "revision_identity": "rev-req009-r2",
                "action_id": "action-b",
                "change_type": "updated",
                "change_summary": "Action B details updated.",
                "changed_at": "2026-03-15T08:10:00Z",
                "evidence_refs": [
                    "CHANGELOG.md#req-009-b",
                ],
            },
        ],
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-028/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-027/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-028/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        cross_project_context=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "context_note": "Earth-wide runtime compatibility context.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-local-followup",
                "summary": "Carry local follow-up into current strategy.",
                "rationale": "Local continuity should remain explicit.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-028/TASK_EVIDENCE.json",
                ],
                "next_step": "Validate local continuity assumptions against current goals.",
            },
            {
                "action_id": "action-cross-runtime-sync",
                "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
                "rationale": "Cross-project runtime assumptions must remain synchronized.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Open a cross-project sync task backed by Earth sweep evidence.",
            },
        ],
        earth_sweep_source_artifacts=[
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "status": "stale",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                ],
            },
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                "status": "fresh",
                "evidence_refs": [],
            },
        ],
        required_context_documents=[
            {
                "doc_kind": "peer-project",
                "project_id": "runtime-orchestrator",
                "doc_ref": "docs/runtime-orchestrator/overview.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
            },
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "present",
                "evidence_refs": [],
            },
        ],
    )

    second = module.build_req_009_prior_strategy_revision_ingestion(
        current_revision_identity="rev-req009-hardening-r3",
        prior_strategy_revisions=[
            {
                "revision_identity": "rev-req009-r1",
                "summary": "Prior revision one.",
                "recommended_action_ids": [
                    "action-a",
                    "action-b",
                ],
                "evidence_refs": [
                    "reports/strategy/revisions/rev-req009-r1.json",
                ],
            },
            {
                "revision_identity": "rev-req009-r2",
                "summary": "Prior revision two.",
                "recommended_action_ids": [
                    "action-b",
                    "action-c",
                ],
                "evidence_refs": [
                    "reports/strategy/revisions/rev-req009-r2.json",
                ],
            },
        ],
        changelog_history=[
            {
                "change_id": "chg-201",
                "revision_identity": "rev-req009-r2",
                "action_id": "action-b",
                "change_type": "updated",
                "change_summary": "Action B details updated.",
                "changed_at": "2026-03-15T08:10:00Z",
                "evidence_refs": [
                    "CHANGELOG.md#req-009-b",
                ],
            },
            {
                "change_id": "chg-202",
                "revision_identity": "rev-req009-r2",
                "action_id": "action-c",
                "change_type": "added",
                "change_summary": "Action C added to latest prior revision.",
                "changed_at": "2026-03-15T08:30:00Z",
                "evidence_refs": [
                    "CHANGELOG.md#req-009-c",
                ],
            },
        ],
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-027/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-028/TASK_EVIDENCE.json",
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
                "context_note": "Earth-wide runtime compatibility context.",
            }
        ],
        candidate_recommendations=[
            {
                "action_id": "action-cross-runtime-sync",
                "summary": "Coordinate runtime assumptions with runtime-orchestrator.",
                "rationale": "Cross-project runtime assumptions must remain synchronized.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Open a cross-project sync task backed by Earth sweep evidence.",
            },
            {
                "action_id": "action-local-followup",
                "summary": "Carry local follow-up into current strategy.",
                "rationale": "Local continuity should remain explicit.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-028/TASK_EVIDENCE.json",
                ],
                "next_step": "Validate local continuity assumptions against current goals.",
            },
        ],
        earth_sweep_source_artifacts=[
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/ground-control-hub.json",
                "status": "fresh",
                "evidence_refs": [],
            },
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "status": "stale",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                ],
            },
        ],
        required_context_documents=[
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "present",
                "evidence_refs": [],
            },
            {
                "doc_kind": "peer-project",
                "project_id": "runtime-orchestrator",
                "doc_ref": "docs/runtime-orchestrator/overview.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
            },
        ],
    )

    assert module.validate_req_009_prior_strategy_revision_ingestion(first) == []
    assert module.validate_req_009_prior_strategy_revision_ingestion(second) == []
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == second["call_metadata"]["processing_call_id"]

    first_bundle = json.dumps(
        first["call_metadata"]["canonical_processing_input"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    second_bundle = json.dumps(
        second["call_metadata"]["canonical_processing_input"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert first_bundle == second_bundle
