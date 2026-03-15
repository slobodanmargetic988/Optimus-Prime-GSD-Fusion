import json

from scripts import strategy_context_sweep as module


def test_req_022_stale_earth_sweep_source_artifact_emits_deterministic_reason_code():
    payload = module.build_req_022_context_confidence_scoring(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req022-hardening-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-071/TASK_EVIDENCE.json",
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
    )

    assert module.validate_req_022_context_confidence_scoring(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    open_risks = recommendation["open_risks"]

    stale_risks = [row for row in open_risks if row["reason_code"] == "stale_earth_sweep_source_artifact"]
    assert len(stale_risks) == 1
    assert stale_risks[0]["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-01/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-15/portfolio.json",
    ]

    low_risks = [row for row in open_risks if row["reason_code"] == "low_context_confidence"]
    required_refs = {ref for risk in low_risks for ref in risk.get("required_evidence_refs", [])}
    assert "reports/earth/sweeps/2026-03-01/runtime-orchestrator.json" in required_refs
    assert recommendation["decision"] == "resolve-context-gaps"


def test_req_022_missing_mission_scope_and_peer_project_docs_emit_explicit_reason_codes():
    payload = module.build_req_022_context_confidence_scoring(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req022-hardening-r2",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-071/TASK_EVIDENCE.json",
        ],
        required_context_documents=[
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-071/TASK_EVIDENCE.json",
                ],
            },
            {
                "doc_kind": "scope",
                "doc_ref": "scope.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-071/TASK_EVIDENCE.json",
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

    assert module.validate_req_022_context_confidence_scoring(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    open_risks = recommendation["open_risks"]

    reason_codes = sorted(row["reason_code"] for row in open_risks if row["reason_code"] != "low_context_confidence")
    assert reason_codes == [
        "missing_mission_doc",
        "missing_peer_project_doc",
        "missing_scope_doc",
    ]

    for row in open_risks:
        if row["reason_code"] == "low_context_confidence":
            continue
        assert row["required_evidence_refs"]

    assert recommendation["decision"] == "resolve-context-gaps"


def test_req_022_context_bundle_serialization_is_replay_stable_across_repeated_runs():
    first = module.build_req_022_context_confidence_scoring(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req022-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-071/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-071/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-070/TASK_EVIDENCE.json",
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

    second = module.build_req_022_context_confidence_scoring(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req022-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-070/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-071/TASK_EVIDENCE.json",
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

    assert module.validate_req_022_context_confidence_scoring(first) == []
    assert module.validate_req_022_context_confidence_scoring(second) == []
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
