import json

from scripts import strategy_context_sweep as module


def test_req_021_hardening_stale_source_artifact_detected_during_earth_sweep() -> None:
    payload = module.build_req_021_evidence_provenance_ledger_for_context(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req021-hardening-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
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
        required_context_documents=[
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "present",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            }
        ],
        context_claims=[
            {
                "claim_id": "claim-stale-earth-source",
                "claim_text": "Earth sweep runtime constraints are currently derived from a stale source artifact.",
                "claim_kind": "earth-sweep",
                "source_artifact_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                ],
            }
        ],
    )

    assert module.validate_req_021_evidence_provenance_ledger_for_context(payload) == []
    open_risks = payload["processing_behavior"]["recommendation"]["open_risks"]
    stale_rows = [row for row in open_risks if row["reason_code"] == "stale_earth_sweep_source_artifact"]
    assert len(stale_rows) == 1
    assert stale_rows[0]["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
    ]
    claim = payload["provenance_ledger"]["claims"][0]
    assert claim["source_artifacts"][0]["status"] == "stale"


def test_req_021_hardening_missing_mission_scope_or_peer_project_doc_with_explicit_reason_codes() -> None:
    payload = module.build_req_021_evidence_provenance_ledger_for_context(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req021-hardening-r2",
        required_context_documents=[
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            },
            {
                "doc_kind": "scope",
                "doc_ref": "scope.md",
                "status": "missing",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
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
        context_claims=[
            {
                "claim_id": "claim-mission-anchor",
                "claim_text": "Mission must anchor the replay context.",
                "claim_kind": "mission",
                "source_artifact_refs": ["mission.md"],
            },
            {
                "claim_id": "claim-scope-anchor",
                "claim_text": "Scope must bound the replay context.",
                "claim_kind": "scope",
                "source_artifact_refs": ["scope.md"],
            },
            {
                "claim_id": "claim-peer-anchor",
                "claim_text": "Peer project overview constrains replay-safe context.",
                "claim_kind": "peer-project",
                "source_artifact_refs": ["docs/runtime-orchestrator/overview.md"],
                "supporting_project_ids": ["runtime-orchestrator"],
            },
        ],
    )

    assert module.validate_req_021_evidence_provenance_ledger_for_context(payload) == []
    open_risks = payload["processing_behavior"]["recommendation"]["open_risks"]
    assert sorted(row["reason_code"] for row in open_risks) == [
        "missing_mission_doc",
        "missing_peer_project_doc",
        "missing_scope_doc",
    ]
    for row in open_risks:
        assert row["required_evidence_refs"]

    statuses = {
        claim["claim_id"]: claim["source_artifacts"][0]["status"] for claim in payload["provenance_ledger"]["claims"]
    }
    assert statuses == {
        "claim-mission-anchor": "missing",
        "claim-peer-anchor": "missing",
        "claim-scope-anchor": "missing",
    }


def test_req_021_hardening_context_bundle_serialization_replay_stable_across_repeated_runs() -> None:
    first = module.build_req_021_evidence_provenance_ledger_for_context(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req021-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
        ],
        earth_sweep_source_artifacts=[
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "status": "fresh",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                ],
            }
        ],
        required_context_documents=[
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "present",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            },
            {
                "doc_kind": "peer-project",
                "project_id": "runtime-orchestrator",
                "doc_ref": "docs/runtime-orchestrator/overview.md",
                "status": "present",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
            },
            {
                "doc_kind": "scope",
                "doc_ref": "scope.md",
                "status": "present",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            },
        ],
        context_claims=[
            {
                "claim_id": "claim-scope-anchor",
                "claim_text": "Scope bounds the replay-safe context ledger.",
                "claim_kind": "scope",
                "source_artifact_refs": ["scope.md"],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            },
            {
                "claim_id": "claim-peer-anchor",
                "claim_text": "Peer project overview constrains replay-safe context.",
                "claim_kind": "peer-project",
                "source_artifact_refs": [
                    "docs/runtime-orchestrator/overview.md",
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "supporting_project_ids": ["runtime-orchestrator"],
            },
            {
                "claim_id": "claim-mission-anchor",
                "claim_text": "Mission anchors deterministic replay and auditability.",
                "claim_kind": "mission",
                "source_artifact_refs": ["mission.md"],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            },
        ],
    )

    second = module.build_req_021_evidence_provenance_ledger_for_context(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req021-hardening-r3",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
        ],
        earth_sweep_source_artifacts=[
            {
                "artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "status": "fresh",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                ],
            }
        ],
        required_context_documents=[
            {
                "doc_kind": "peer-project",
                "project_id": "runtime-orchestrator",
                "doc_ref": "docs/runtime-orchestrator/overview.md",
                "status": "present",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
            },
            {
                "doc_kind": "scope",
                "doc_ref": "scope.md",
                "status": "present",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            },
            {
                "doc_kind": "mission",
                "doc_ref": "mission.md",
                "status": "present",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            },
        ],
        context_claims=[
            {
                "claim_id": "claim-mission-anchor",
                "claim_text": "Mission anchors deterministic replay and auditability.",
                "claim_kind": "mission",
                "source_artifact_refs": ["mission.md"],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            },
            {
                "claim_id": "claim-peer-anchor",
                "claim_text": "Peer project overview constrains replay-safe context.",
                "claim_kind": "peer-project",
                "source_artifact_refs": [
                    "docs/runtime-orchestrator/overview.md",
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "supporting_project_ids": ["runtime-orchestrator"],
            },
            {
                "claim_id": "claim-scope-anchor",
                "claim_text": "Scope bounds the replay-safe context ledger.",
                "claim_kind": "scope",
                "source_artifact_refs": ["scope.md"],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-067/TASK_EVIDENCE.json",
                ],
            },
        ],
    )

    assert module.validate_req_021_evidence_provenance_ledger_for_context(first) == []
    assert module.validate_req_021_evidence_provenance_ledger_for_context(second) == []
    assert first["call_metadata"]["canonical_processing_input"] == second["call_metadata"]["canonical_processing_input"]
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert first["provenance_ledger"] == second["provenance_ledger"]
    assert first["context_bundle"]["canonical_json"] == second["context_bundle"]["canonical_json"]
    assert first["context_bundle"]["sha256"] == second["context_bundle"]["sha256"]

    parsed = json.loads(first["context_bundle"]["canonical_json"])
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert first["context_bundle"]["canonical_json"] == canonical
