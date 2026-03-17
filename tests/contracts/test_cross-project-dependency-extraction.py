import json

from scripts import strategy_context_sweep as module


def test_req_011_builder_emits_valid_payload_with_hardening_inputs() -> None:
    payload = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-contract-r1",
        broad_sweep_context={
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/portfolio.json",
            ],
            "cross_project_context": [
                {
                    "project_id": "analytics-hub",
                    "project_root": "/workspace/projects/Earth/analytics-hub",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/analytics-hub.json",
                    ],
                    "context_note": "Analytics hub receives dispatch telemetry.",
                }
            ],
            "contract_dependencies": [
                {
                    "signal_id": "signal-contract-analytics-ingest",
                    "dependency_key": "analytics-ingest",
                    "summary": "Dispatch telemetry must satisfy analytics-hub ingestion contract.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "analytics-hub",
                    "target_project_root": "/workspace/projects/Earth/analytics-hub",
                    "contract_ref": "contracts/req/REQ-015_integration-opportunity-detection.md",
                    "evidence_refs": [
                        "reports/contracts/analytics-hub-ingest.json",
                    ],
                }
            ],
            "trace_dependencies": [
                {
                    "signal_id": "signal-trace-analytics-ingest",
                    "dependency_key": "analytics-ingest",
                    "summary": "Runtime traces show dispatch telemetry flowing into analytics-hub.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "analytics-hub",
                    "target_project_root": "/workspace/projects/Earth/analytics-hub",
                    "trace_ref": "reports/runtime/analytics-hub/dispatch-trace.jsonl",
                    "evidence_refs": [],
                }
            ],
            "declared_integration_points": [],
            "earth_sweep_source_artifacts": [
                {
                    "artifact_ref": "reports/earth/sweeps/2026-03-15/analytics-hub.json",
                    "status": "fresh",
                    "evidence_refs": [],
                }
            ],
            "required_context_documents": [
                {
                    "doc_kind": "mission",
                    "doc_ref": "mission.md",
                    "status": "present",
                    "evidence_refs": [],
                },
                {
                    "doc_kind": "peer-project",
                    "project_id": "analytics-hub",
                    "doc_ref": "docs/analytics-hub/overview.md",
                    "status": "present",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/analytics-hub.json",
                    ],
                },
            ],
        },
    )

    assert module.validate_req_011_cross_project_dependency_extraction(payload) == []
    assert payload["schema_version"] == module.REQ_011_SCHEMA_VERSION
    assert payload["requirement_id"] == module.REQ_011_REQUIREMENT_ID
    assert payload["processing_behavior"]["strategy"] == "cross-project-dependency-extraction"
    assert payload["processing_behavior"]["context_usage"]["earth_sweep_source_artifacts_used"] is True
    assert payload["processing_behavior"]["context_usage"]["required_context_documents_used"] is True
    assert payload["processing_behavior"]["recommendation"]["dependency_edges"][0]["confidence"] == "medium"


def test_req_011_call_metadata_is_reproducible_for_identical_invocations() -> None:
    first = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-contract-r2",
        broad_sweep_context={
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/portfolio.json",
            ],
            "cross_project_context": [
                {
                    "project_id": "runtime-orchestrator",
                    "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    ],
                    "context_note": "Runtime orchestrator owns worker scheduling envelopes.",
                }
            ],
            "trace_dependencies": [
                {
                    "signal_id": "signal-trace-runtime-sync",
                    "dependency_key": "runtime-sync",
                    "summary": "Dispatch traces hint at a runtime-orchestrator handshake.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "runtime-orchestrator",
                    "target_project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "trace_ref": "reports/runtime/runtime-orchestrator/dispatch-sync.jsonl",
                    "evidence_refs": [],
                }
            ],
            "earth_sweep_source_artifacts": [
                {
                    "artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    "status": "stale",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                    ],
                }
            ],
            "required_context_documents": [
                {
                    "doc_kind": "peer-project",
                    "project_id": "runtime-orchestrator",
                    "doc_ref": "docs/runtime-orchestrator/overview.md",
                    "status": "missing",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    ],
                }
            ],
        },
    )
    second = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-contract-r2",
        broad_sweep_context={
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/portfolio.json",
            ],
            "cross_project_context": [
                {
                    "project_id": "runtime-orchestrator",
                    "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    ],
                    "context_note": "Runtime orchestrator owns worker scheduling envelopes.",
                }
            ],
            "trace_dependencies": [
                {
                    "signal_id": "signal-trace-runtime-sync",
                    "dependency_key": "runtime-sync",
                    "summary": "Dispatch traces hint at a runtime-orchestrator handshake.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "runtime-orchestrator",
                    "target_project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "trace_ref": "reports/runtime/runtime-orchestrator/dispatch-sync.jsonl",
                    "evidence_refs": [],
                }
            ],
            "earth_sweep_source_artifacts": [
                {
                    "artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    "status": "stale",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                    ],
                }
            ],
            "required_context_documents": [
                {
                    "doc_kind": "peer-project",
                    "project_id": "runtime-orchestrator",
                    "doc_ref": "docs/runtime-orchestrator/overview.md",
                    "status": "missing",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    ],
                }
            ],
        },
    )

    assert first["call_metadata"] == second["call_metadata"]

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

    changed = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-contract-r3",
    )
    assert changed["call_metadata"]["canonical_input_sha256"] != first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] != first["call_metadata"]["reproducible_call_id"]
