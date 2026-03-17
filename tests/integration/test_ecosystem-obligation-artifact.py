from scripts import strategy_artifacts_handoff as module


def test_req_058_processing_behavior_uses_broad_sweep_context_and_emits_only_evidence_backed_obligations() -> None:
    payload = {
        "analysis_type": "ecosystem_obligation_artifact",
        "now_utc": "2026-03-16T11:30:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "ecosystem_obligations": [
            {
                "obligation_id": "obl.consume-runtime-heartbeats",
                "peer_project_id": "earth-core-runtime",
                "responsibility": "consume",
                "artifact": "runtime_lease_heartbeat_events",
                "obligation_summary": "Consume runtime heartbeat events for stale-worker detection.",
                "dependency_prerequisites": [
                    "dep.runtime-heartbeat-contract",
                    "dep.state-artifact-cadence",
                ],
                "evidence_refs": [
                    "earth-sweep/ref-runtime",
                    "strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json#lineage_index",
                ],
            }
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "earth-sweep/ref-runtime",
                "earth-sweep/ref-health",
            ],
            "projects_considered": [
                "earth-orchestrator",
                "earth-core-runtime",
                "earth-analytics-hub",
            ],
            "cross_project_obligations": [
                {
                    "obligation_id": "obl.produce-strategy-health-summary",
                    "peer_project_id": "earth-analytics-hub",
                    "responsibility": "produce",
                    "artifact": "strategy_health_summary_v1",
                    "obligation_summary": "Produce strategy cycle health summary packets for analytics baselines.",
                    "dependency_prerequisites": [
                        "dep.analytics-schema-v2",
                        "dep.runtime-heartbeat-contract",
                    ],
                    "evidence_refs": [
                        "earth-sweep/ref-health",
                    ],
                },
                {
                    "obligation_id": "obl.produce-unverified-obligation",
                    "peer_project_id": "earth-orchestrator",
                    "responsibility": "produce",
                    "artifact": "handoff_bridge_v2",
                    "obligation_summary": "Candidate obligation without Earth-sweep evidence must remain an open risk.",
                    "dependency_prerequisites": [
                        "dep.handoff-contract-v2",
                    ],
                    "evidence_refs": [],
                },
            ],
            "unresolved_ideas": [
                {
                    "risk_id": "risk.idea-bridge-contract",
                    "summary": "Evaluate additional bridge-contract rollout after sweep evidence is refreshed.",
                    "reason_code": "needs_followup_validation",
                    "required_evidence_refs": [
                        "earth-sweep/ref-bridge-contract",
                    ],
                }
            ],
        },
    }

    output = module.build_req_058_ecosystem_obligation_artifact(payload)
    assert module.validate_req_058_ecosystem_obligation_artifact(output) == []

    obligations = output["ecosystem_obligation_artifact"]["ecosystem_obligations"]
    obligation_ids = [row["obligation_id"] for row in obligations]
    assert obligation_ids == [
        "obl.consume-runtime-heartbeats",
        "obl.produce-strategy-health-summary",
    ]

    processing = output["processing_behavior"]
    recommendation = processing["recommendation"]
    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "context_project_ids",
        "cross_project_context",
        "approved_ecosystem_obligations",
        "open_risks",
    }

    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["context_project_ids"] == [
        "earth-analytics-hub",
        "earth-core-runtime",
        "earth-orchestrator",
    ]
    assert "earth-sweep/ref-runtime" in recommendation["evidence_refs"]
    assert "earth-sweep/ref-health" in recommendation["evidence_refs"]
    assert "earth-sweep/ref-bridge-contract" in recommendation["evidence_refs"]

    approved = recommendation["approved_ecosystem_obligations"]
    assert [row["obligation_id"] for row in approved] == obligation_ids

    open_risk_ids = {row["risk_id"] for row in recommendation["open_risks"]}
    assert open_risk_ids == {
        "risk.idea-bridge-contract",
        "risk.obl.produce-unverified-obligation",
    }

    context_usage = processing["context_usage"]
    assert context_usage["broad_sweep_context_used"] is True
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["earth_sweep_context_used"] is True
    assert context_usage["projects_considered"] == recommendation["context_project_ids"]
    assert context_usage["candidate_obligations_considered"] == 3
    assert context_usage["obligations_emitted"] == 2
    assert context_usage["open_risks_count"] == 2

    cross_project_context = recommendation["cross_project_context"]
    assert cross_project_context["projects_considered"] == recommendation["context_project_ids"]
    assert cross_project_context["earth_sweep_evidence_refs"] == [
        "earth-sweep/ref-health",
        "earth-sweep/ref-runtime",
    ]
    assert cross_project_context["cross_project_obligation_ids"] == [
        "obl.produce-strategy-health-summary",
        "obl.produce-unverified-obligation",
    ]


def test_req_058_cross_project_obligation_alias_field_supports_earth_sweep_evidence_refs() -> None:
    payload = {
        "analysis_type": "ecosystem_obligation_artifact",
        "now_utc": "2026-03-16T11:30:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": ["earth-sweep/ref-runtime"],
            "projects_considered": ["earth-core-runtime"],
            "cross_project_obligations": [
                {
                    "obligation_id": "obl.consume-runtime-heartbeats",
                    "peer_project_id": "earth-core-runtime",
                    "responsibility": "consume",
                    "artifact": "runtime_lease_heartbeat_events",
                    "obligation_summary": "Consume runtime heartbeat events for stale-worker detection.",
                    "dependency_prerequisites": [
                        "dep.runtime-heartbeat-contract",
                    ],
                    "earth_sweep_evidence_refs": ["earth-sweep/ref-runtime"],
                }
            ],
            "unresolved_ideas": [],
        },
    }

    output = module.build_req_058_ecosystem_obligation_artifact(payload)
    assert module.validate_req_058_ecosystem_obligation_artifact(output) == []
    assert output["ecosystem_obligation_artifact"]["ecosystem_obligations"] == [
        {
            "artifact": "runtime_lease_heartbeat_events",
            "dependency_prerequisites": ["dep.runtime-heartbeat-contract"],
            "evidence_refs": ["earth-sweep/ref-runtime"],
            "obligation_id": "obl.consume-runtime-heartbeats",
            "obligation_summary": "Consume runtime heartbeat events for stale-worker detection.",
            "peer_project_id": "earth-core-runtime",
            "responsibility": "consume",
        }
    ]
