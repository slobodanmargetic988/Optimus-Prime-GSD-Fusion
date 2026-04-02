from scripts import strategy_artifacts_handoff as module


def _base_payload() -> dict:
    return {
        "analysis_type": "strategy_quality_report_artifact",
        "now_utc": "2026-03-16T23:10:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "citation_coverage": {
            "cited_claims": 12,
            "uncited_claims": 2,
        },
        "contradiction_status": {
            "unresolved_contradiction_ids": [],
        },
        "confidence_distribution": {
            "high": 5,
            "medium": 2,
            "low": 1,
        },
        "gate_policy": {
            "min_citation_coverage_ratio": 0.8,
            "max_unresolved_contradictions": 0,
            "min_high_confidence_ratio": 0.5,
        },
        "recommendation_mappings": [
            {
                "recommendation_id": "rec.align-runtime-automation",
                "recommendation_summary": "Align runtime automation with quality report evidence coverage.",
                "gate_ids": ["citation_coverage", "confidence_distribution"],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-215/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-059_strategy-quality-report-artifact.sample.json",
                ],
                "open_risk_ids": [],
            },
            {
                "recommendation_id": "rec.resolve-peer-follow-up",
                "recommendation_summary": "Track peer follow-up as a non-blocking open risk with evidence refs.",
                "gate_ids": ["contradiction_status"],
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-16.json",
                ],
                "open_risk_ids": ["risk.peer-follow-up"],
            },
        ],
        "acceptance_evidence_refs": [
            "contracts/req/REQ-059_strategy-quality-report-artifact.md",
        ],
        "artifact_ref": "strategy/current/artifacts/REQ-059/quality-report.json",
        "open_risks": [
            {
                "risk_id": "risk.peer-follow-up",
                "summary": "Peer review remains open while evidence is complete enough to proceed.",
                "reason_code": "peer_follow_up_pending",
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-16.json",
                ],
                "blocking": False,
            }
        ],
    }


def test_req_059_integration_builds_delivery_bundle_with_planner_hook_and_acceptance_packet() -> None:
    payload = _base_payload()

    bundle = module.build_req_059_strategy_quality_report_delivery_bundle(payload)

    artifact = bundle["quality_report_artifact"]
    planner_hook = bundle["planner_hook"]
    acceptance_packet = bundle["acceptance_packet"]

    assert module.validate_req_059_strategy_quality_report_artifact(artifact) == []
    assert planner_hook == {
        "hook_id": "planner.strategy-quality-report",
        "requirement_id": "REQ-059",
        "target_project_id": "optimus-prime-gsd-fusion",
        "target_project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        "checked_at_utc": "2026-03-16T23:10:00Z",
        "ready_for_build": True,
        "failed_gate_ids": [],
        "mapped_gate_ids": [
            "citation_coverage",
            "confidence_distribution",
            "contradiction_status",
        ],
        "recommendation_ids": [
            "rec.align-runtime-automation",
            "rec.resolve-peer-follow-up",
        ],
        "recommendation_mappings": [
            {
                "recommendation_id": "rec.align-runtime-automation",
                "recommendation_summary": "Align runtime automation with quality report evidence coverage.",
                "gate_ids": [
                    "citation_coverage",
                    "confidence_distribution",
                ],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-215/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-059_strategy-quality-report-artifact.sample.json",
                ],
                "open_risk_ids": [],
            },
            {
                "recommendation_id": "rec.resolve-peer-follow-up",
                "recommendation_summary": "Track peer follow-up as a non-blocking open risk with evidence refs.",
                "gate_ids": ["contradiction_status"],
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-16.json",
                ],
                "open_risk_ids": ["risk.peer-follow-up"],
            },
        ],
        "mapping_count": 2,
        "complete_recommendation_mapping_set": True,
    }
    assert acceptance_packet == {
        "packet_type": "strategy_quality_report_acceptance",
        "requirement_id": "REQ-059",
        "artifact_ref": "strategy/current/artifacts/REQ-059/quality-report.json",
        "checked_at_utc": "2026-03-16T23:10:00Z",
        "target_project_id": "optimus-prime-gsd-fusion",
        "decision": "accepted-with-open-risks",
        "failed_gate_ids": [],
        "required_evidence_refs": [
            "contracts/req/REQ-059_strategy-quality-report-artifact.md",
            "reports/earth/sweeps/shared-observability/signals-2026-03-16.json",
            "reports/optimus-prime/planning/evidence/TASK-215/TASK_EVIDENCE.json",
            "strategy/current/samples/REQ-059_strategy-quality-report-artifact.sample.json",
        ],
        "reason_codes": ["open_risks_present"],
        "open_risk_handling": {
            "status": "accepted-with-open-risks",
            "open_risk_count": 1,
            "blocking_open_risk_count": 0,
            "non_blocking_open_risk_count": 1,
        },
        "open_risks": [
            {
                "risk_id": "risk.peer-follow-up",
                "summary": "Peer review remains open while evidence is complete enough to proceed.",
                "reason_code": "peer_follow_up_pending",
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-16.json",
                ],
                "blocking": False,
            }
        ],
    }


def test_req_059_integration_acceptance_packet_blocks_on_failed_gates_and_blocking_open_risks() -> None:
    payload = _base_payload()
    payload["citation_coverage"] = {
        "cited_claims": 4,
        "uncited_claims": 6,
    }
    payload["contradiction_status"] = {
        "unresolved_contradiction_ids": [
            "contradiction.runtime-vs-evidence",
        ],
    }
    payload["confidence_distribution"] = {
        "high": 1,
        "medium": 2,
        "low": 5,
    }
    payload["open_risks"] = [
        {
            "risk_id": "risk.peer-follow-up",
            "summary": "Peer review remains open and now blocks acceptance until contradictory evidence is resolved.",
            "reason_code": "peer_follow_up_pending",
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-16.json",
            ],
            "blocking": True,
        }
    ]

    bundle = module.build_req_059_strategy_quality_report_delivery_bundle(payload)

    assert bundle["planner_hook"]["failed_gate_ids"] == [
        "citation_coverage",
        "contradiction_status",
        "confidence_distribution",
    ]
    assert bundle["acceptance_packet"]["decision"] == "blocked"
    assert bundle["acceptance_packet"]["reason_codes"] == [
        "quality_gates_failed",
        "open_risks_present",
        "blocking_open_risks_present",
    ]
    assert bundle["acceptance_packet"]["open_risk_handling"] == {
        "status": "blocked",
        "open_risk_count": 1,
        "blocking_open_risk_count": 1,
        "non_blocking_open_risk_count": 0,
    }
