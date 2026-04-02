import json

from scripts import strategy_context_sweep as module


def test_stale_earth_sweep_source_artifact_emits_deterministic_reason_code():
    payload = module.build_req_001_runtime_entrypoint(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req001-hardening-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-003/TASK_EVIDENCE.json",
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
                "action_id": "action-local-hardening",
                "summary": "Keep hardening flow active while stale Earth artifact is refreshed.",
                "rationale": "Local hardening can continue with explicit stale-source risk tracking.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-003/TASK_EVIDENCE.json",
                ],
                "next_step": "Run hardening checks and track stale artifact reason code.",
            }
        ],
    )

    assert module.validate_req_001_runtime_entrypoint(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    stale_risks = [row for row in recommendation["open_risks"] if row["reason_code"] == "stale_earth_sweep_source_artifact"]
    assert len(stale_risks) == 1
    stale_risk = stale_risks[0]
    assert stale_risk["risk_id"].startswith("risk-earth-source-")
    assert stale_risk["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]
    assert recommendation["decision"] == "proceed-with-open-risks"


def test_missing_mission_scope_and_peer_project_docs_emit_explicit_reason_codes():
    payload = module.build_req_001_runtime_entrypoint(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req001-hardening-r2",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-003/TASK_EVIDENCE.json",
        ],
        required_context_documents=[
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-003/TASK_EVIDENCE.json",
                ],
            },
            {
                "doc_kind": "scope",
                "doc_ref": "scope.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-003/TASK_EVIDENCE.json",
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

    assert module.validate_req_001_runtime_entrypoint(payload) == []
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


def test_context_bundle_serialization_is_replay_stable_across_repeated_runs():
    first = module.build_req_001_runtime_entrypoint(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req001-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-003/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
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
    )

    second = module.build_req_001_runtime_entrypoint(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req001-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-003/TASK_EVIDENCE.json",
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
    )

    assert module.validate_req_001_runtime_entrypoint(first) == []
    assert module.validate_req_001_runtime_entrypoint(second) == []
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
