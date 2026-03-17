from __future__ import annotations

from scripts import strategy_artifacts_handoff as module


def _req_064_payload() -> dict:
    return {
        "analysis_type": "source_traceability_validator",
        "now_utc": "2026-03-16T18:30:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "source_references": [
            {
                "evidence_ref": "src.mission-001",
                "source_path": "mission.md#L1",
                "source_excerpt": "Strategy output must remain evidence-backed.",
            },
            {
                "evidence_ref": "src.runtime-002",
                "source_path": "reports/earth/sweeps/earth-core-runtime/runtime-lease-heartbeat.json",
                "source_excerpt": "Runtime lease heartbeat reveals stale worker risk.",
            },
            {
                "evidence_ref": "src.sweep-003",
                "source_path": "reports/earth/sweeps/earth-orchestrator/strategy-bridge-summary.json",
                "source_excerpt": "Cross-project bridge obligations require sweep evidence refs.",
            },
        ],
        "recommendations": [
            {
                "recommendation_id": "rec.enforce-citations",
                "summary": "Require citations on each recommendation and claim before handoff.",
                "evidence_refs": [
                    "src.mission-001",
                    "src.runtime-002",
                ],
                "claims": [
                    {
                        "claim_id": "claim.recommendations-cited",
                        "statement": "Recommendations without citation refs must fail validation.",
                        "evidence_refs": [
                            "src.mission-001",
                        ],
                    },
                    {
                        "claim_id": "claim.claims-cited",
                        "statement": "Claims without evidence refs must fail validation.",
                        "evidence_refs": [
                            "src.runtime-002",
                        ],
                    },
                ],
            },
            {
                "recommendation_id": "rec.cross-project-evidence-gate",
                "summary": "Do not promote cross-project obligations without Earth-sweep evidence refs.",
                "evidence_refs": [
                    "src.sweep-003",
                ],
                "claims": [
                    {
                        "claim_id": "claim.broken-ref-fails",
                        "statement": "Broken refs are a hard validator failure.",
                        "evidence_refs": [
                            "src.sweep-003",
                        ],
                    }
                ],
            },
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "src.runtime-002",
                "src.sweep-003",
            ],
            "projects_considered": [
                "earth-core-runtime",
                "earth-orchestrator",
            ],
            "cross_project_obligations": [
                {
                    "obligation_id": "obl.consume-runtime-heartbeats",
                    "peer_project_id": "earth-core-runtime",
                    "responsibility": "consume",
                    "artifact": "runtime_lease_heartbeat_events",
                    "obligation_summary": "Consume runtime lease heartbeat events.",
                    "dependency_prerequisites": [
                        "dep.runtime-heartbeat-contract",
                    ],
                    "evidence_refs": [
                        "src.runtime-002",
                    ],
                },
                {
                    "obligation_id": "obl.produce-unverified-evidence",
                    "peer_project_id": "earth-orchestrator",
                    "responsibility": "produce",
                    "artifact": "cross_project_handoff_bridge",
                    "obligation_summary": "Candidate bridge work without Earth-sweep evidence refs.",
                    "dependency_prerequisites": [
                        "dep.bridge-contract-v2",
                    ],
                    "evidence_refs": [],
                },
            ],
            "unresolved_ideas": [
                {
                    "risk_id": "risk.idea.refresh-sweep-evidence",
                    "summary": "Refresh sweep evidence before enabling additional bridge obligations.",
                    "reason_code": "needs_followup_validation",
                    "required_evidence_refs": [
                        "src.sweep-003",
                    ],
                }
            ],
        },
    }


def test_req_064_processing_behavior_uses_broad_sweep_context_and_emits_traceability_fields() -> None:
    output = module.build_req_064_source_traceability_validator(_req_064_payload())
    assert module.validate_req_064_source_traceability_validator(output) == []

    processing = output["processing_behavior"]
    assert processing["strategy"] == module.REQ_064_PROCESSING_STRATEGY
    assert processing["reasoning_mode"] == module.REQ_064_REASONING_MODE
    assert processing["heuristic_summarization_only"] is False

    usage = processing["context_usage"]
    assert usage["broad_sweep_context_used"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["source_references_considered"] == 3
    assert usage["recommendations_considered"] == 2
    assert usage["claims_considered"] == 3
    assert usage["cross_project_obligations_considered"] == 2
    assert usage["cross_project_obligations_accepted"] == 1
    assert usage["open_risks_count"] == 2
    assert usage["citation_traceability_pass"] is True
    assert usage["recommendation_field_completeness_pass"] is True
    assert usage["projects_considered"] == [
        "earth-core-runtime",
        "earth-orchestrator",
    ]

    recommendation = processing["recommendation"]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["context_project_ids"] == usage["projects_considered"]
    assert "src.mission-001" in recommendation["evidence_refs"]
    assert "src.runtime-002" in recommendation["evidence_refs"]
    assert "src.sweep-003" in recommendation["evidence_refs"]

    citation_traceability = recommendation["citation_traceability"]
    assert citation_traceability == {
        "recommendations_total": 2,
        "recommendations_with_evidence_refs": 2,
        "claims_total": 3,
        "claims_with_evidence_refs": 3,
        "missing_recommendation_ids": [],
        "missing_claim_ids": [],
    }

    completeness = recommendation["recommendation_field_completeness"]
    assert completeness == {
        "required_fields": [
            "recommendation_id",
            "summary",
            "evidence_refs",
            "claims",
        ],
        "recommendations_total": 2,
        "complete_recommendations": 2,
        "incomplete_recommendations": 0,
        "missing_by_recommendation": {},
    }

    cross_project_context = recommendation["cross_project_context"]
    assert cross_project_context["projects_considered"] == usage["projects_considered"]
    assert cross_project_context["earth_sweep_evidence_refs"] == [
        "src.runtime-002",
        "src.sweep-003",
    ]
    assert cross_project_context["cross_project_obligation_ids"] == [
        "obl.consume-runtime-heartbeats",
        "obl.produce-unverified-evidence",
    ]
    assert cross_project_context["accepted_cross_project_obligation_ids"] == [
        "obl.consume-runtime-heartbeats",
    ]
    assert cross_project_context["withheld_cross_project_obligation_ids"] == [
        "obl.produce-unverified-evidence",
    ]
    assert cross_project_context["unresolved_idea_ids"] == [
        "risk.idea.refresh-sweep-evidence",
    ]

    assert recommendation["accepted_cross_project_obligations"] == [
        {
            "obligation_id": "obl.consume-runtime-heartbeats",
            "peer_project_id": "earth-core-runtime",
            "responsibility": "consume",
            "artifact": "runtime_lease_heartbeat_events",
            "evidence_refs": ["src.runtime-002"],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk.idea.refresh-sweep-evidence",
            "summary": "Refresh sweep evidence before enabling additional bridge obligations.",
            "reason_code": "needs_followup_validation",
            "required_evidence_refs": ["src.sweep-003"],
        },
        {
            "risk_id": "risk.obl.produce-unverified-evidence",
            "summary": (
                "Cross-project obligation withheld until Earth-sweep evidence refs are attached: "
                "Candidate bridge work without Earth-sweep evidence refs."
            ),
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [],
        },
    ]


def test_req_064_processing_behavior_keeps_uncorroborated_cross_project_obligations_as_open_risks() -> None:
    payload = _req_064_payload()
    payload["broad_sweep_context"]["earth_sweep_evidence_refs"] = []
    output = module.build_req_064_source_traceability_validator(payload)
    assert module.validate_req_064_source_traceability_validator(output) == []

    recommendation = output["processing_behavior"]["recommendation"]
    assert recommendation["accepted_cross_project_obligations"] == []
    assert recommendation["cross_project_context"]["accepted_cross_project_obligation_ids"] == []
    assert recommendation["cross_project_context"]["withheld_cross_project_obligation_ids"] == [
        "obl.consume-runtime-heartbeats",
        "obl.produce-unverified-evidence",
    ]

    risk_by_id = {row["risk_id"]: row for row in recommendation["open_risks"]}
    assert risk_by_id["risk.idea.refresh-sweep-evidence"]["reason_code"] == "needs_followup_validation"
    assert risk_by_id["risk.obl.consume-runtime-heartbeats"]["reason_code"] == "missing_earth_sweep_evidence_refs"
    assert risk_by_id["risk.obl.produce-unverified-evidence"]["reason_code"] == "missing_earth_sweep_evidence_refs"

    completeness = recommendation["recommendation_field_completeness"]
    assert completeness["incomplete_recommendations"] == 0
    assert completeness["missing_by_recommendation"] == {}

    usage = output["processing_behavior"]["context_usage"]
    assert usage["cross_project_context_used"] is True
    assert usage["recommendation_field_completeness_pass"] is True
    assert usage["citation_traceability_pass"] is True
