import copy

from scripts import strategy_artifacts_handoff as module


def _base_input() -> dict:
    return {
        "analysis_type": "strategy_revision_history_and_diff_workflow",
        "now_utc": "2026-03-17T08:15:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
        },
        "workflow_config": {
            "strictness": "strict",
            "deterministic_failure_mode": "fail_closed",
        },
        "revision_history": {
            "current_revision_id": "strategy-rev-20260317-081500",
            "previous_revision_id": "strategy-rev-20260316-190000",
            "revision_snapshot_refs": [
                "strategy/history/strategy-rev-20260316-190000/STRATEGY.json",
                "strategy/current/STRATEGY.json",
            ],
            "diff_artifact_refs": [
                "strategy/current/DIFF_SUMMARY.json",
                "strategy/current/STRATEGY_DIFF.md",
            ],
            "recommendation_ids": [
                "rec.harden-diff-governance",
                "rec.preserve-revision-history",
            ],
            "constraint_ids": [
                "guardrail-deterministic-diff-order",
                "guidance-cross-project-governance",
            ],
            "strategy_is_current": True,
            "semantic_drift_detected": False,
        },
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-17/portfolio.json",
                "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json",
            ],
            "projects_considered": [
                "runtime-orchestrator",
                "shared-observability",
            ],
            "cross_project_obligations": [
                {
                    "obligation_id": "obligation-align-runtime-policy",
                    "project_id": "runtime-orchestrator",
                    "summary": "Align runtime policy with deterministic diff workflow governance.",
                    "earth_sweep_evidence_refs": [
                        "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json"
                    ],
                }
            ],
            "unresolved_ideas": [
                {
                    "idea_id": "idea-review-shared-observability-handoff",
                    "summary": "Validate shared observability ownership before broadening diff-governance obligations.",
                    "earth_sweep_evidence_refs": [
                        "reports/earth/sweeps/2026-03-17/shared-observability.json"
                    ],
                }
            ],
        },
    }


def test_req_069_integration_uses_broad_sweep_context_with_deterministic_processing_fields() -> None:
    payload = module.build_req_069_strategy_revision_history_and_diff_workflow(_base_input())
    assert module.validate_req_069_strategy_revision_history_and_diff_workflow(payload) == []

    hook = payload["strategy_revision_history_and_diff_workflow"]
    assert hook["planner_readiness"]["context_ready"] is True
    assert hook["planner_readiness"]["decision"] == "allow_diff_review"

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
    assert recommendation["decision"] == "allow-diff-workflow-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert "strategy/current/STRATEGY.json" in recommendation["evidence_refs"]
    assert "strategy/current/DIFF_SUMMARY.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-17/portfolio.json" in recommendation["evidence_refs"]
    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation-align-runtime-policy",
            "project_id": "runtime-orchestrator",
            "summary": "Align runtime policy with deterministic diff workflow governance.",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-17/portfolio.json",
                "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-idea-review-shared-observability-handoff",
            "summary": "Validate shared observability ownership before broadening diff-governance obligations.",
            "reason_code": "unresolved_idea_open_risk",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-17/shared-observability.json"
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-17/shared-observability.json"
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
        "reports/earth/sweeps/2026-03-17/portfolio.json",
        "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json",
    ]
    assert usage["constraint_ids_used"] == [
        "guardrail-deterministic-diff-order",
        "guidance-cross-project-governance",
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


def test_req_069_integration_records_open_risks_when_cross_project_context_lacks_earth_refs() -> None:
    test_input = copy.deepcopy(_base_input())
    test_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = []
    test_input["broad_sweep_context"]["projects_considered"] = []

    payload = module.build_req_069_strategy_revision_history_and_diff_workflow(test_input)
    assert module.validate_req_069_strategy_revision_history_and_diff_workflow(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    usage = payload["processing_behavior"]["context_usage"]

    assert recommendation["decision"] == "allow-diff-workflow-with-open-risks"
    assert recommendation["confidence"] == "low"
    assert recommendation["cross_project_obligations"] == []
    missing_earth_risks = [
        row for row in recommendation["open_risks"] if row["reason_code"] == "missing_earth_sweep_evidence_refs"
    ]
    assert missing_earth_risks == [
        {
            "risk_id": "risk-obligation-align-runtime-policy",
            "summary": "Align runtime policy with deterministic diff workflow governance.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json"
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json"
            ],
        }
    ]
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is False
