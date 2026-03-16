import copy

from scripts import strategy_artifacts_handoff as module


def _base_input() -> dict:
    return {
        "analysis_type": "constraint_classification_artifact",
        "now_utc": "2026-03-16T09:05:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "constraints": [
            {
                "constraint_id": "guardrail-task-floor",
                "statement": "Before build starts, planner must output at least 400 tasks.",
                "classification": "hard",
                "rationale": "Mandatory planning gate.",
                "evidence_refs": ["scope.md#mandatory-planning-gate"],
                "source_refs": ["scope.md#mandatory-planning-gate"],
            },
            {
                "constraint_id": "guidance-batch-size",
                "statement": "Prefer batching packets by lane.",
                "classification": "soft",
                "rationale": "Improves throughput.",
                "evidence_refs": ["reports/strategy/lane-throughput-2026-03-15.json"],
                "source_refs": ["reports/strategy/lane-throughput-2026-03-15.json"],
            },
            {
                "constraint_id": "speculative-cross-project-sync",
                "statement": "Consider Earth-wide sync if lane drift increases.",
                "classification": "speculative",
                "rationale": "Optional path if drift appears.",
                "evidence_refs": ["reports/earth/sweeps/shared-observability/signals-2026-03-14.json"],
                "source_refs": ["reports/earth/sweeps/shared-observability/signals-2026-03-14.json"],
            },
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/portfolio.json",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
            "projects_considered": [
                "runtime-orchestrator",
                "shared-observability",
            ],
            "cross_project_obligations": [
                {
                    "obligation_id": "obligation-align-runtime-policy",
                    "project_id": "runtime-orchestrator",
                    "summary": "Align planner policy interpretation with runtime orchestrator.",
                    "earth_sweep_evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
                    ],
                }
            ],
            "unresolved_ideas": [
                {
                    "idea_id": "idea-review-shared-observability-handoff",
                    "summary": "Validate ownership handoff details before adding additional sync obligations.",
                    "earth_sweep_evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/shared-observability.json"
                    ],
                }
            ],
        },
    }


def test_req_055_integration_uses_broad_sweep_context_with_deterministic_recommendation_fields() -> None:
    payload = module.build_req_055_constraint_classification_artifact(_base_input())
    assert module.validate_req_055_constraint_classification_artifact(payload) == []

    processing = payload["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["context_usage"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert "scope.md#mandatory-planning-gate" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-16/portfolio.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json" in recommendation["evidence_refs"]

    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-align-runtime-policy",
            "project_id": "runtime-orchestrator",
            "summary": "Align planner policy interpretation with runtime orchestrator.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/portfolio.json",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-idea-review-shared-observability-handoff",
            "summary": "Validate ownership handoff details before adding additional sync obligations.",
            "reason_code": "unresolved_idea_open_risk",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/shared-observability.json",
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/shared-observability.json",
            ],
        }
    ]

    assert usage["cross_project_context_provided"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["projects_considered"] == ["runtime-orchestrator", "shared-observability"]
    assert usage["earth_sweep_evidence_refs_considered"] == [
        "reports/earth/sweeps/2026-03-16/portfolio.json",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
    ]
    assert usage["constraint_ids_used"] == [
        "guardrail-task-floor",
        "guidance-batch-size",
        "speculative-cross-project-sync",
    ]
    assert usage["recommendation_mapping"] == [
        {
            "constraint_id": "guardrail-task-floor",
            "action_id": "constraint-guardrail-task-floor",
            "classification": "hard",
            "policy_role": "mandatory_guardrail",
        },
        {
            "constraint_id": "guidance-batch-size",
            "action_id": "constraint-guidance-batch-size",
            "classification": "soft",
            "policy_role": "optional_guidance",
        },
        {
            "constraint_id": "speculative-cross-project-sync",
            "action_id": "constraint-speculative-cross-project-sync",
            "classification": "speculative",
            "policy_role": "optional_guidance",
        },
    ]
    assert usage["recommendation_fields_complete"] is True
    assert usage["required_recommendation_fields"] == [
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    ]


def test_req_055_integration_missing_earth_refs_moves_cross_project_obligation_to_open_risk() -> None:
    test_input = copy.deepcopy(_base_input())
    test_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = []

    payload = module.build_req_055_constraint_classification_artifact(test_input)
    assert module.validate_req_055_constraint_classification_artifact(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    usage = payload["processing_behavior"]["context_usage"]

    assert recommendation["decision"] == "collect-earth-evidence"
    assert recommendation["cross_project_obligations"] == []
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-obligation-align-runtime-policy",
            "summary": "Align planner policy interpretation with runtime orchestrator.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
        },
        {
            "risk_id": "risk-idea-review-shared-observability-handoff",
            "summary": "Validate ownership handoff details before adding additional sync obligations.",
            "reason_code": "unresolved_idea_open_risk",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/shared-observability.json",
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/shared-observability.json",
            ],
        },
    ]
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is False
