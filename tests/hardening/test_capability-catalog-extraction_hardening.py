import json

from scripts import strategy_context_sweep as module


def test_req_013_stale_earth_sweep_source_artifact_emits_deterministic_reason_code():
    payload = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-hardening-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
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
        candidate_recommendations=[
            {
                "action_id": "capability-replay-hardening",
                "summary": "Keep replay hardening active while stale Earth artifact is refreshed.",
                "rationale": "Local hardening can continue with explicit stale-source tracking.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                ],
                "next_step": "Track stale Earth artifact reason code in evidence.",
            }
        ],
        capability_catalog_entries=[
            {
                "project_id": "optimus-prime",
                "project_root": "/workspace/projects/optimus-prime",
                "capability_id": "capability-replay-hardening",
                "capability_summary": "Replay hardening remains missing from target project.",
                "status": "missing",
                "source_version": "optimus-prime@sha256:hardening-r1",
                "source_artifact_ref": "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                "evidence_refs": [],
            }
        ],
    )

    assert module.validate_req_013_capability_catalog_extraction(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    stale_risks = [row for row in recommendation["open_risks"] if row["reason_code"] == "stale_earth_sweep_source_artifact"]
    assert len(stale_risks) == 1
    assert stale_risks[0]["risk_id"].startswith("risk-earth-source-")
    assert stale_risks[0]["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]
    assert recommendation["decision"] == "proceed-with-open-risks"


def test_req_013_missing_mission_scope_and_peer_project_docs_emit_explicit_reason_codes():
    payload = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-hardening-r2",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
        ],
        required_context_documents=[
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                ],
            },
            {
                "doc_kind": "scope",
                "doc_ref": "scope.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
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
        capability_catalog_entries=[
            {
                "project_id": "optimus-prime",
                "project_root": "/workspace/projects/optimus-prime",
                "capability_id": "capability-required-doc-ingestion",
                "capability_summary": "Required context document ingestion is still missing.",
                "status": "missing",
                "source_version": "optimus-prime@sha256:hardening-r2",
                "source_artifact_ref": "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                "evidence_refs": [],
            }
        ],
    )

    assert module.validate_req_013_capability_catalog_extraction(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    open_risks = recommendation["open_risks"]
    assert len(open_risks) == 3
    assert sorted(row["reason_code"] for row in open_risks) == [
        "missing_mission_doc",
        "missing_peer_project_doc",
        "missing_scope_doc",
    ]
    assert recommendation["decision"] == "resolve-context-gaps"
    for row in open_risks:
        assert row["required_evidence_refs"]


def test_req_013_context_bundle_serialization_is_replay_stable_across_repeated_runs():
    first = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-003/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
            "reports/earth/sweeps/2026-03-15/portfolio.json",
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
        candidate_recommendations=[
            {
                "action_id": "capability-runtime-sync",
                "summary": "Coordinate runtime sync assumptions with runtime-orchestrator.",
                "rationale": "Runtime sync must remain compatible across projects.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Open a sync task if Earth evidence remains fresh.",
            },
            {
                "action_id": "capability-replay-hardening",
                "summary": "Harden replay diagnostics for local strategy execution.",
                "rationale": "Replay hardening remains a local missing capability.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                ],
                "next_step": "Run deterministic hardening checks.",
            },
        ],
        capability_catalog_entries=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "capability_id": "capability-runtime-sync",
                "capability_summary": "Runtime sync already provided in peer project.",
                "status": "provided",
                "source_version": "runtime-orchestrator@sha256:444",
                "source_artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                ],
            },
            {
                "project_id": "optimus-prime",
                "project_root": "/workspace/projects/optimus-prime",
                "capability_id": "capability-replay-hardening",
                "capability_summary": "Replay hardening is still missing locally.",
                "status": "missing",
                "source_version": "optimus-prime@sha256:555",
                "source_artifact_ref": "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                "evidence_refs": [],
            },
        ],
    )

    second = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-003/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
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
        candidate_recommendations=[
            {
                "action_id": "capability-replay-hardening",
                "summary": "Harden replay diagnostics for local strategy execution.",
                "rationale": "Replay hardening remains a local missing capability.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                ],
                "next_step": "Run deterministic hardening checks.",
            },
            {
                "action_id": "capability-runtime-sync",
                "summary": "Coordinate runtime sync assumptions with runtime-orchestrator.",
                "rationale": "Runtime sync must remain compatible across projects.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Open a sync task if Earth evidence remains fresh.",
            },
        ],
        capability_catalog_entries=[
            {
                "project_id": "optimus-prime",
                "project_root": "/workspace/projects/optimus-prime",
                "capability_id": "capability-replay-hardening",
                "capability_summary": "Replay hardening is still missing locally.",
                "status": "missing",
                "source_version": "optimus-prime@sha256:555",
                "source_artifact_ref": "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                "evidence_refs": [],
            },
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "capability_id": "capability-runtime-sync",
                "capability_summary": "Runtime sync already provided in peer project.",
                "status": "provided",
                "source_version": "runtime-orchestrator@sha256:444",
                "source_artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                ],
            },
        ],
    )

    assert module.validate_req_013_capability_catalog_extraction(first) == []
    assert module.validate_req_013_capability_catalog_extraction(second) == []
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
