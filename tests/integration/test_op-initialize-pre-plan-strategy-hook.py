import copy

from scripts import strategy_artifacts_handoff as module


def _base_input() -> dict:
    return {
        "analysis_type": "op_initialize_pre_plan_strategy_hook",
        "now_utc": "2026-03-16T11:40:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "hook_config": {
            "strictness": "strict",
            "deterministic_failure_mode": "fail_closed",
        },
        "strategy_context": {
            "strategy_revision_id": "strategy-rev-20260316-113000",
            "strategy_artifact_refs": [
                "strategy/current/ECOSYSTEM_LINK_MAP.json",
                "strategy/current/STRATEGY.json",
                "strategy/current/STRATEGY_CHANGELOG.md",
            ],
            "recommendation_ids": [
                "rec.contract-enforce-quality-floor",
                "rec.pre-plan-sequence-alignment",
            ],
            "constraint_ids": [
                "guardrail-task-floor",
                "guidance-batch-size",
            ],
            "strategy_is_current": True,
        },
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


def test_req_067_integration_uses_broad_sweep_context_with_deterministic_processing_fields() -> None:
    payload = module.build_req_067_op_initialize_pre_plan_strategy_hook(_base_input())
    assert module.validate_req_067_op_initialize_pre_plan_strategy_hook(payload) == []

    hook = payload["pre_plan_strategy_hook"]
    assert hook["planner_readiness"]["context_ready"] is True
    assert hook["planner_readiness"]["decision"] == "allow_planning"

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
    assert recommendation["decision"] == "allow-op-plan-with-open-risks"
    assert "strategy/current/STRATEGY.json" in recommendation["evidence_refs"]
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
                "reports/earth/sweeps/2026-03-16/shared-observability.json"
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/shared-observability.json"
            ],
        }
    ]

    assert usage["cross_project_context_provided"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert usage["projects_considered"] == [
        "runtime-orchestrator",
        "shared-observability",
    ]
    assert usage["earth_sweep_evidence_refs_considered"] == [
        "reports/earth/sweeps/2026-03-16/portfolio.json",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
    ]
    assert usage["constraint_ids_used"] == [
        "guardrail-task-floor",
        "guidance-batch-size",
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


def test_req_067_integration_records_open_risks_when_cross_project_context_lacks_earth_refs() -> None:
    test_input = copy.deepcopy(_base_input())
    test_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = []
    test_input["broad_sweep_context"]["projects_considered"] = []

    payload = module.build_req_067_op_initialize_pre_plan_strategy_hook(test_input)
    assert module.validate_req_067_op_initialize_pre_plan_strategy_hook(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    usage = payload["processing_behavior"]["context_usage"]

    assert recommendation["decision"] == "allow-op-plan-with-open-risks"
    assert recommendation["cross_project_obligations"] == []
    missing_earth_risks = [
        row for row in recommendation["open_risks"] if row["reason_code"] == "missing_earth_sweep_evidence_refs"
    ]
    assert missing_earth_risks == [
        {
            "risk_id": "risk-obligation-align-runtime-policy",
            "summary": "Align planner policy interpretation with runtime orchestrator.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json"
            ],
        }
    ]
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is False
