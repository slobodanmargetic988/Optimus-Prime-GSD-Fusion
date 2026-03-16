import json
from copy import deepcopy

from scripts import strategy_artifacts_handoff as module


def _payload() -> dict:
    return {
        "analysis_type": "strategy_quality_report_artifact",
        "now_utc": "2026-03-16T23:20:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "citation_coverage": {
            "cited_claims": 9,
            "uncited_claims": 1,
        },
        "contradiction_status": {
            "unresolved_contradiction_ids": [],
        },
        "confidence_distribution": {
            "high": 4,
            "medium": 1,
            "low": 1,
        },
        "gate_policy": {
            "min_citation_coverage_ratio": 0.8,
            "max_unresolved_contradictions": 0,
            "min_high_confidence_ratio": 0.5,
        },
        "recommendation_mappings": [
            {
                "recommendation_id": "rec.capture-citation-gaps",
                "recommendation_summary": "Capture citation gaps in planner-ready quality signals.",
                "gate_ids": ["citation_coverage", "confidence_distribution"],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-215/TASK_EVIDENCE.json",
                    "strategy/current/samples/REQ-059_strategy-quality-report-artifact.sample.json",
                ],
                "open_risk_ids": [],
            },
            {
                "recommendation_id": "rec.track-contradiction-state",
                "recommendation_summary": "Track contradiction state with explicit planner mappings.",
                "gate_ids": ["contradiction_status"],
                "evidence_refs": [
                    "contracts/req/REQ-059_strategy-quality-report-artifact.md",
                ],
                "open_risk_ids": ["risk.follow-up-peer-review"],
            },
            {
                "recommendation_id": "rec.publish-confidence-profile",
                "recommendation_summary": "Publish confidence distribution so build automation can gate deterministically.",
                "gate_ids": ["confidence_distribution"],
                "evidence_refs": [
                    "reports/earth/sweeps/runtime-orchestrator/quality-profile-2026-03-16.json",
                ],
                "open_risk_ids": [],
            },
        ],
        "acceptance_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-215/TASK_EVIDENCE.json",
            "contracts/req/REQ-059_strategy-quality-report-artifact.md",
        ],
        "artifact_ref": "strategy/current/artifacts/REQ-059/quality-report.json",
        "open_risks": [
            {
                "risk_id": "risk.follow-up-peer-review",
                "summary": "Peer review follow-up remains open but does not block the report artifact replay path.",
                "reason_code": "peer_follow_up_pending",
                "evidence_refs": [
                    "reports/earth/sweeps/runtime-orchestrator/quality-profile-2026-03-16.json",
                ],
                "blocking": False,
            }
        ],
    }


def test_req_059_hardening_artifact_regeneration_has_no_semantic_drift_on_no_change_rerun() -> None:
    first_payload = _payload()
    second_payload = deepcopy(_payload())
    second_payload["recommendation_mappings"] = [
        second_payload["recommendation_mappings"][2],
        {
            **second_payload["recommendation_mappings"][0],
            "evidence_refs": [
                "strategy/current/samples/REQ-059_strategy-quality-report-artifact.sample.json",
                "reports/optimus-prime/planning/evidence/TASK-215/TASK_EVIDENCE.json",
                "reports/optimus-prime/planning/evidence/TASK-215/TASK_EVIDENCE.json",
            ],
        },
        second_payload["recommendation_mappings"][1],
    ]
    second_payload["acceptance_evidence_refs"] = [
        "contracts/req/REQ-059_strategy-quality-report-artifact.md",
        "reports/optimus-prime/planning/evidence/TASK-215/TASK_EVIDENCE.json",
        "contracts/req/REQ-059_strategy-quality-report-artifact.md",
    ]

    run_one = module.build_req_059_strategy_quality_report_delivery_bundle(first_payload)
    run_two = module.build_req_059_strategy_quality_report_delivery_bundle(second_payload)

    assert json.dumps(run_one, sort_keys=True, separators=(",", ":")) == json.dumps(
        run_two,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert run_one["acceptance_packet"]["reason_codes"] == run_two["acceptance_packet"]["reason_codes"] == [
        "open_risks_present"
    ]


def test_req_059_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    bundle = module.build_req_059_strategy_quality_report_delivery_bundle(_payload())

    planner_hook = bundle["planner_hook"]
    assert planner_hook["complete_recommendation_mapping_set"] is True
    assert planner_hook["mapping_count"] == 3
    assert planner_hook["recommendation_ids"] == [
        "rec.capture-citation-gaps",
        "rec.publish-confidence-profile",
        "rec.track-contradiction-state",
    ]
    assert planner_hook["mapped_gate_ids"] == [
        "citation_coverage",
        "confidence_distribution",
        "contradiction_status",
    ]
    assert planner_hook["recommendation_mappings"] == [
        {
            "recommendation_id": "rec.capture-citation-gaps",
            "recommendation_summary": "Capture citation gaps in planner-ready quality signals.",
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
            "recommendation_id": "rec.publish-confidence-profile",
            "recommendation_summary": "Publish confidence distribution so build automation can gate deterministically.",
            "gate_ids": ["confidence_distribution"],
            "evidence_refs": [
                "reports/earth/sweeps/runtime-orchestrator/quality-profile-2026-03-16.json",
            ],
            "open_risk_ids": [],
        },
        {
            "recommendation_id": "rec.track-contradiction-state",
            "recommendation_summary": "Track contradiction state with explicit planner mappings.",
            "gate_ids": ["contradiction_status"],
            "evidence_refs": [
                "contracts/req/REQ-059_strategy-quality-report-artifact.md",
            ],
            "open_risk_ids": ["risk.follow-up-peer-review"],
        },
    ]


def test_req_059_hardening_acceptance_packet_includes_required_evidence_refs_and_open_risk_handling() -> None:
    payload = _payload()
    payload["citation_coverage"] = {
        "cited_claims": 7,
        "uncited_claims": 3,
    }
    payload["open_risks"] = [
        {
            "risk_id": "risk.blocking-review-gap",
            "summary": "Blocking review gap stays visible until citation coverage is restored.",
            "reason_code": "review_gap_open",
            "evidence_refs": [
                "reports/earth/sweeps/runtime-orchestrator/quality-profile-2026-03-16.json",
            ],
            "blocking": True,
        },
        {
            "risk_id": "risk.follow-up-peer-review",
            "summary": "Peer review follow-up remains open but is secondary to the blocking review gap.",
            "reason_code": "peer_follow_up_pending",
            "evidence_refs": [
                "contracts/req/REQ-059_strategy-quality-report-artifact.md",
            ],
            "blocking": False,
        },
    ]

    bundle = module.build_req_059_strategy_quality_report_delivery_bundle(payload)

    assert bundle["acceptance_packet"] == {
        "packet_type": "strategy_quality_report_acceptance",
        "requirement_id": "REQ-059",
        "artifact_ref": "strategy/current/artifacts/REQ-059/quality-report.json",
        "checked_at_utc": "2026-03-16T23:20:00Z",
        "target_project_id": "optimus-prime-gsd-fusion",
        "decision": "blocked",
        "failed_gate_ids": ["citation_coverage"],
        "required_evidence_refs": [
            "contracts/req/REQ-059_strategy-quality-report-artifact.md",
            "reports/earth/sweeps/runtime-orchestrator/quality-profile-2026-03-16.json",
            "reports/optimus-prime/planning/evidence/TASK-215/TASK_EVIDENCE.json",
            "strategy/current/samples/REQ-059_strategy-quality-report-artifact.sample.json",
        ],
        "reason_codes": [
            "quality_gates_failed",
            "open_risks_present",
            "blocking_open_risks_present",
        ],
        "open_risk_handling": {
            "status": "blocked",
            "open_risk_count": 2,
            "blocking_open_risk_count": 1,
            "non_blocking_open_risk_count": 1,
        },
        "open_risks": [
            {
                "risk_id": "risk.blocking-review-gap",
                "summary": "Blocking review gap stays visible until citation coverage is restored.",
                "reason_code": "review_gap_open",
                "evidence_refs": [
                    "reports/earth/sweeps/runtime-orchestrator/quality-profile-2026-03-16.json",
                ],
                "blocking": True,
            },
            {
                "risk_id": "risk.follow-up-peer-review",
                "summary": "Peer review follow-up remains open but is secondary to the blocking review gap.",
                "reason_code": "peer_follow_up_pending",
                "evidence_refs": [
                    "contracts/req/REQ-059_strategy-quality-report-artifact.md",
                ],
                "blocking": False,
            },
        ],
    }
