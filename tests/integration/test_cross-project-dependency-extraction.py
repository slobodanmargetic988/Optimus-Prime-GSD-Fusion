from scripts import strategy_context_sweep as module


def test_req_011_recommendation_is_complete_and_uses_cross_project_context() -> None:
    payload = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-integration-r1",
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
                },
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
                },
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
        },
    )

    assert module.validate_req_011_cross_project_dependency_extraction(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "dependency_edges",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "proceed-with-open-risks"

    edges_by_key = {row["dependency_key"]: row for row in recommendation["dependency_edges"]}
    assert sorted(edges_by_key.keys()) == ["analytics-ingest", "runtime-sync"]

    analytics_edge = edges_by_key["analytics-ingest"]
    assert analytics_edge["signal_types"] == ["contract", "declared-integration-point", "trace"]
    assert analytics_edge["confidence"] == "high"
    assert analytics_edge["supporting_context_project_ids"] == ["analytics-hub"]
    assert "contracts/req/REQ-015_integration-opportunity-detection.md" in analytics_edge["evidence_refs"]
    assert "reports/runtime/analytics-hub/dispatch-trace.jsonl" in analytics_edge["evidence_refs"]
    assert (
        "strategy/current/samples/REQ-015_integration-opportunity-detection.sample.json"
        in analytics_edge["evidence_refs"]
    )

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

    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-dependency-confidence-dependency-edge-optimus-prime-runtime-orchestrator-runtime-sync",
            "reason_code": "dependency_confidence_below_commit_threshold",
            "summary": (
                "Dependency edge 'runtime-sync' between 'optimus-prime' and 'runtime-orchestrator' "
                "remains an open risk because corroboration is weak."
            ),
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "reports/runtime/runtime-orchestrator/dispatch-sync.jsonl",
            ],
        }
    ]

    assert usage["broad_sweep_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["cross_project_projects_considered"] == ["analytics-hub", "runtime-orchestrator"]
    assert usage["cross_project_context_projects_matched"] == ["analytics-hub", "runtime-orchestrator"]
    assert usage["contract_dependency_signal_ids_used"] == ["signal-contract-analytics-ingest"]
    assert usage["trace_dependency_signal_ids_used"] == [
        "signal-trace-analytics-ingest",
        "signal-trace-runtime-sync",
    ]
    assert usage["declared_integration_point_signal_ids_used"] == ["signal-integration-analytics-ingest"]
    assert usage["high_confidence_dependency_edge_ids"] == [
        "dependency-edge-optimus-prime-analytics-hub-analytics-ingest"
    ]
    assert usage["low_confidence_dependency_edge_ids"] == [
        "dependency-edge-optimus-prime-runtime-orchestrator-runtime-sync"
    ]
    assert "reports/earth/sweeps/2026-03-15/portfolio.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-15/analytics-hub.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json" in recommendation["evidence_refs"]


def test_req_011_missing_earth_evidence_records_open_risk_instead_of_obligation() -> None:
    payload = module.build_req_011_cross_project_dependency_extraction(
        target_project_root="/workspace/projects/optimus-prime",
        earth_root="/workspace/projects/Earth",
        output_root="/workspace/projects/optimus-prime/strategy/out",
        revision_identity="rev-req011-integration-r2",
        broad_sweep_context={
            "earth_sweep_evidence_refs": [],
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
                    "evidence_refs": [],
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
        },
    )

    assert module.validate_req_011_cross_project_dependency_extraction(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "record-open-risks"
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["dependency_edges"] == [
        {
            "dependency_edge_id": "dependency-edge-optimus-prime-analytics-hub-analytics-ingest",
            "dependency_key": "analytics-ingest",
            "source_project_id": "optimus-prime",
            "source_project_root": "/workspace/projects/optimus-prime",
            "target_project_id": "analytics-hub",
            "target_project_root": "/workspace/projects/Earth/analytics-hub",
            "summary": "Dispatch telemetry must satisfy analytics-hub ingestion contract.",
            "signal_types": ["contract", "trace"],
            "supporting_signal_ids": [
                "signal-contract-analytics-ingest",
                "signal-trace-analytics-ingest",
            ],
            "supporting_signal_count": 2,
            "contract_refs": ["contracts/req/REQ-015_integration-opportunity-detection.md"],
            "trace_refs": ["reports/runtime/analytics-hub/dispatch-trace.jsonl"],
            "integration_point_refs": [],
            "confidence": "medium",
            "confidence_reason": "Multiple broad-sweep signal types corroborate the edge.",
            "evidence_refs": [
                "contracts/req/REQ-015_integration-opportunity-detection.md",
                "reports/runtime/analytics-hub/dispatch-trace.jsonl",
            ],
            "supporting_context_project_ids": ["analytics-hub"],
            "supporting_context_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/analytics-hub.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-dependency-earth-evidence-dependency-edge-optimus-prime-analytics-hub-analytics-ingest",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "summary": (
                "Dependency edge 'analytics-ingest' between 'optimus-prime' and 'analytics-hub' cannot "
                "become a cross-project obligation until Earth-sweep evidence refs are attached."
            ),
            "required_evidence_refs": [
                "contracts/req/REQ-015_integration-opportunity-detection.md",
                "reports/earth/sweeps/2026-03-15/analytics-hub.json",
                "reports/runtime/analytics-hub/dispatch-trace.jsonl",
            ],
        }
    ]
