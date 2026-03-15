import json

from scripts import strategy_context_sweep as module


def test_req_011_stale_earth_sweep_source_artifact_emits_deterministic_reason_code() -> None:
    payload = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-hardening-r1",
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
            "declared_integration_points": [
                {
                    "signal_id": "signal-integration-analytics-ingest",
                    "dependency_key": "analytics-ingest",
                    "summary": "Planner packet declares analytics-hub ingestion as an integration point.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "analytics-hub",
                    "target_project_root": "/workspace/projects/Earth/analytics-hub",
                    "integration_point_ref": (
                        "strategy/current/samples/REQ-015_integration-opportunity-detection.sample.json"
                    ),
                    "evidence_refs": [],
                }
            ],
            "earth_sweep_source_artifacts": [
                {
                    "artifact_ref": "reports/earth/sweeps/2026-03-15/analytics-hub.json",
                    "status": "stale",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/analytics-hub.audit.json",
                    ],
                }
            ],
        },
    )

    assert module.validate_req_011_cross_project_dependency_extraction(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    stale_risks = [row for row in recommendation["open_risks"] if row["reason_code"] == "stale_earth_sweep_source_artifact"]
    assert len(stale_risks) == 1
    assert stale_risks[0]["risk_id"].startswith("risk-earth-source-")
    assert stale_risks[0]["required_evidence_refs"] == [
        "reports/earth/sweeps/2026-03-15/analytics-hub.audit.json",
        "reports/earth/sweeps/2026-03-15/analytics-hub.json",
    ]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-dependency-edge-optimus-prime-analytics-hub-analytics-ingest",
            "project_id": "analytics-hub",
            "summary": (
                "Coordinate dependency 'analytics-ingest' between 'optimus-prime' and 'analytics-hub' "
                "before implementation."
            ),
            "confidence": "high",
            "evidence_refs": [
                "contracts/req/REQ-015_integration-opportunity-detection.md",
                "reports/contracts/analytics-hub-ingest.json",
                "reports/earth/sweeps/2026-03-15/analytics-hub.json",
                "reports/earth/sweeps/2026-03-15/portfolio.json",
                "reports/runtime/analytics-hub/dispatch-trace.jsonl",
                "strategy/current/samples/REQ-015_integration-opportunity-detection.sample.json",
            ],
        }
    ]


def test_req_011_missing_mission_scope_and_peer_project_docs_emit_explicit_reason_codes() -> None:
    payload = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-hardening-r2",
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
            "contract_dependencies": [
                {
                    "signal_id": "signal-contract-runtime-sync",
                    "dependency_key": "runtime-sync",
                    "summary": "Worker scheduling envelopes must satisfy the runtime sync contract.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "runtime-orchestrator",
                    "target_project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "contract_ref": "contracts/req/REQ-015_integration-opportunity-detection.md",
                    "evidence_refs": [
                        "reports/contracts/runtime-sync.json",
                    ],
                }
            ],
            "trace_dependencies": [
                {
                    "signal_id": "signal-trace-runtime-sync",
                    "dependency_key": "runtime-sync",
                    "summary": "Dispatch traces show a runtime-orchestrator handshake.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "runtime-orchestrator",
                    "target_project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "trace_ref": "reports/runtime/runtime-orchestrator/dispatch-sync.jsonl",
                    "evidence_refs": [],
                }
            ],
            "required_context_documents": [
                {
                    "doc_kind": "mission",
                    "doc_ref": "mission.md",
                    "status": "missing",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-035/TASK_EVIDENCE.json",
                    ],
                },
                {
                    "doc_kind": "scope",
                    "doc_ref": "scope.md",
                    "status": "missing",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-035/TASK_EVIDENCE.json",
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
        },
    )

    assert module.validate_req_011_cross_project_dependency_extraction(payload) == []
    recommendation = payload["processing_behavior"]["recommendation"]
    open_risks = recommendation["open_risks"]
    assert sorted(row["reason_code"] for row in open_risks) == [
        "missing_mission_doc",
        "missing_peer_project_doc",
        "missing_scope_doc",
    ]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-dependency-edge-optimus-prime-runtime-orchestrator-runtime-sync",
            "project_id": "runtime-orchestrator",
            "summary": (
                "Coordinate dependency 'runtime-sync' between 'optimus-prime' and 'runtime-orchestrator' "
                "before implementation."
            ),
            "confidence": "medium",
            "evidence_refs": [
                "contracts/req/REQ-015_integration-opportunity-detection.md",
                "reports/contracts/runtime-sync.json",
                "reports/earth/sweeps/2026-03-15/portfolio.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "reports/runtime/runtime-orchestrator/dispatch-sync.jsonl",
            ],
        }
    ]
    for row in open_risks:
        assert row["required_evidence_refs"]


def test_req_011_context_bundle_serialization_is_replay_stable_across_repeated_runs() -> None:
    first = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-hardening-r3",
        broad_sweep_context={
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/portfolio.json",
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
                },
                {
                    "project_id": "analytics-hub",
                    "project_root": "/workspace/projects/Earth/analytics-hub",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/analytics-hub.json",
                    ],
                    "context_note": "Analytics hub receives dispatch telemetry.",
                },
            ],
            "contract_dependencies": [
                {
                    "signal_id": "signal-contract-runtime-sync",
                    "dependency_key": "runtime-sync",
                    "summary": "Worker scheduling envelopes must satisfy the runtime sync contract.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "runtime-orchestrator",
                    "target_project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "contract_ref": "contracts/req/REQ-015_integration-opportunity-detection.md",
                    "evidence_refs": [
                        "reports/contracts/runtime-sync.json",
                        "reports/contracts/runtime-sync.json",
                    ],
                },
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
                },
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
            "declared_integration_points": [
                {
                    "signal_id": "signal-integration-runtime-sync",
                    "dependency_key": "runtime-sync",
                    "summary": "Planner packet declares runtime-orchestrator sync as an integration point.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "runtime-orchestrator",
                    "target_project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "integration_point_ref": (
                        "strategy/current/samples/REQ-015_integration-opportunity-detection.sample.json"
                    ),
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
                },
                {
                    "artifact_ref": "reports/earth/sweeps/2026-03-15/analytics-hub.json",
                    "status": "fresh",
                    "evidence_refs": [],
                },
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
                },
                {
                    "doc_kind": "mission",
                    "doc_ref": "mission.md",
                    "status": "present",
                    "evidence_refs": [],
                },
            ],
        },
    )

    second = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-hardening-r3",
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
                },
                {
                    "project_id": "runtime-orchestrator",
                    "project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                    ],
                    "context_note": "Runtime orchestrator owns worker scheduling envelopes.",
                },
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
                },
                {
                    "signal_id": "signal-contract-runtime-sync",
                    "dependency_key": "runtime-sync",
                    "summary": "Worker scheduling envelopes must satisfy the runtime sync contract.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "runtime-orchestrator",
                    "target_project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "contract_ref": "contracts/req/REQ-015_integration-opportunity-detection.md",
                    "evidence_refs": [
                        "reports/contracts/runtime-sync.json",
                    ],
                },
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
            "declared_integration_points": [
                {
                    "signal_id": "signal-integration-runtime-sync",
                    "dependency_key": "runtime-sync",
                    "summary": "Planner packet declares runtime-orchestrator sync as an integration point.",
                    "source_project_id": "optimus-prime",
                    "source_project_root": "/workspace/projects/optimus-prime",
                    "target_project_id": "runtime-orchestrator",
                    "target_project_root": "/workspace/projects/Earth/runtime-orchestrator",
                    "integration_point_ref": (
                        "strategy/current/samples/REQ-015_integration-opportunity-detection.sample.json"
                    ),
                    "evidence_refs": [],
                }
            ],
            "earth_sweep_source_artifacts": [
                {
                    "artifact_ref": "reports/earth/sweeps/2026-03-15/analytics-hub.json",
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
            "required_context_documents": [
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
        },
    )

    assert first["call_metadata"] == second["call_metadata"]
    assert first["processing_behavior"] == second["processing_behavior"]

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
