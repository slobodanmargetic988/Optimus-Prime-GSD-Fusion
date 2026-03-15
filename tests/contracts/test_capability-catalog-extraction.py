import json

from scripts import strategy_context_sweep as module


def test_req_013_builder_emits_valid_payload_with_source_versioned_catalog():
    payload = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-contract-r1",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
        ],
        earth_sweep_evidence_refs=[
            "reports/earth/sweeps/2026-03-15/portfolio.json",
        ],
        candidate_recommendations=[
            {
                "action_id": "capability-runtime-sync",
                "summary": "Keep runtime sync coverage aligned across projects.",
                "rationale": "Cross-project runtime compatibility requires explicit tracking.",
                "action_scope": "cross-project",
                "requires_earth_evidence": True,
                "project_id": "runtime-orchestrator",
                "evidence_refs": [
                    "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                ],
                "next_step": "Coordinate runtime sync assumptions before merge.",
            },
            {
                "action_id": "capability-replay-hardening",
                "summary": "Harden replay diagnostics for strategy bundle execution.",
                "rationale": "Local project still has replay hardening gaps.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                ],
                "next_step": "Close replay hardening gap with deterministic checks.",
            },
        ],
        capability_catalog_entries=[
            {
                "project_id": "runtime-orchestrator",
                "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                "capability_id": "capability-runtime-sync",
                "capability_summary": "Runtime sync pipeline already present in peer project.",
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
                "capability_summary": "Replay hardening still missing from local strategy flow.",
                "status": "missing",
                "source_version": "optimus-prime@sha256:222",
                "source_artifact_ref": "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                "evidence_refs": [],
            },
        ],
    )

    assert module.validate_req_013_capability_catalog_extraction(payload) == []
    assert payload["schema_version"] == module.REQ_013_SCHEMA_VERSION
    assert payload["requirement_id"] == module.REQ_013_REQUIREMENT_ID
    assert payload["processing_behavior"]["strategy"] == "capability-catalog-broad-sweep"

    catalog = payload["processing_behavior"]["capability_catalog"]
    assert catalog["provided_capability_ids"] == ["capability-runtime-sync"]
    assert catalog["missing_capability_ids"] == ["capability-replay-hardening"]
    assert "runtime-orchestrator@sha256:111" in catalog["source_versions"]


def test_req_013_call_metadata_is_reproducible_for_identical_invocations():
    first = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-contract-r2",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
        ],
        candidate_recommendations=[
            {
                "action_id": "capability-replay-hardening",
                "summary": "Harden replay diagnostics for strategy bundle execution.",
                "rationale": "Replay bundle diagnostics should remain deterministic.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                ],
                "next_step": "Keep deterministic replay checks enabled.",
            },
        ],
        capability_catalog_entries=[
            {
                "project_id": "optimus-prime",
                "project_root": "/workspace/projects/optimus-prime",
                "capability_id": "capability-replay-hardening",
                "capability_summary": "Replay hardening still missing from local strategy flow.",
                "status": "missing",
                "source_version": "optimus-prime@sha256:222",
                "source_artifact_ref": "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                "evidence_refs": [],
            },
        ],
    )
    second = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-contract-r2",
        target_project_evidence_refs=[
            "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
        ],
        candidate_recommendations=[
            {
                "action_id": "capability-replay-hardening",
                "summary": "Harden replay diagnostics for strategy bundle execution.",
                "rationale": "Replay bundle diagnostics should remain deterministic.",
                "action_scope": "local",
                "requires_earth_evidence": False,
                "project_id": "",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                ],
                "next_step": "Keep deterministic replay checks enabled.",
            },
        ],
        capability_catalog_entries=[
            {
                "project_id": "optimus-prime",
                "project_root": "/workspace/projects/optimus-prime",
                "capability_id": "capability-replay-hardening",
                "capability_summary": "Replay hardening still missing from local strategy flow.",
                "status": "missing",
                "source_version": "optimus-prime@sha256:222",
                "source_artifact_ref": "reports/optimus-prime/planning/evidence/TASK-041/TASK_EVIDENCE.json",
                "evidence_refs": [],
            },
        ],
    )

    assert first["call_metadata"] == second["call_metadata"]

    changed = module.build_req_013_capability_catalog_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req013-contract-r3",
    )
    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]

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
