from __future__ import annotations

from copy import deepcopy
import json

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
                        "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json",
                    ],
                }
            ],
            "unresolved_ideas": [
                {
                    "idea_id": "idea-review-shared-observability-handoff",
                    "summary": "Validate shared observability ownership before broadening diff-governance obligations.",
                    "earth_sweep_evidence_refs": [
                        "reports/earth/sweeps/2026-03-17/shared-observability.json",
                    ],
                }
            ],
        },
    }


def test_req069_hardening_regeneration_is_replay_stable_on_no_change_rerun() -> None:
    first_input = _base_input()
    second_input = deepcopy(first_input)

    second_input["revision_history"]["revision_snapshot_refs"] = list(
        reversed(second_input["revision_history"]["revision_snapshot_refs"])
    )
    second_input["revision_history"]["diff_artifact_refs"] = list(
        reversed(second_input["revision_history"]["diff_artifact_refs"])
    )
    second_input["revision_history"]["recommendation_ids"] = list(
        reversed(second_input["revision_history"]["recommendation_ids"])
    )
    second_input["revision_history"]["constraint_ids"] = list(
        reversed(second_input["revision_history"]["constraint_ids"])
    )
    second_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = list(
        reversed(second_input["broad_sweep_context"]["earth_sweep_evidence_refs"])
    )
    second_input["broad_sweep_context"]["projects_considered"] = list(
        reversed(second_input["broad_sweep_context"]["projects_considered"])
    )

    first = module.build_req_069_strategy_revision_history_and_diff_workflow(first_input)
    second = module.build_req_069_strategy_revision_history_and_diff_workflow(second_input)
    third = module.build_req_069_strategy_revision_history_and_diff_workflow(deepcopy(first_input))

    assert module.validate_req_069_strategy_revision_history_and_diff_workflow(first) == []
    assert module.validate_req_069_strategy_revision_history_and_diff_workflow(second) == []
    assert module.validate_req_069_strategy_revision_history_and_diff_workflow(third) == []
    assert first == second == third

    first_json = json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    second_json = json.dumps(second, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    third_json = json.dumps(third, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert first_json == second_json == third_json


def test_req069_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    payload = module.build_req_069_strategy_revision_history_and_diff_workflow(_base_input())
    hook = payload["strategy_revision_history_and_diff_workflow"]
    recommendation = payload["processing_behavior"]["recommendation"]
    context_usage = payload["processing_behavior"]["context_usage"]

    assert hook["planner_readiness"]["context_ready"] is True
    assert hook["planner_readiness"]["decision"] == "allow_diff_review"
    assert context_usage["recommendation_mapping"] == [
        {
            "constraint_id": "guardrail-deterministic-diff-order",
            "action_id": "constraint-guardrail-deterministic-diff-order",
            "classification": "hard",
            "policy_role": "mandatory_guardrail",
        },
        {
            "constraint_id": "guidance-cross-project-governance",
            "action_id": "constraint-guidance-cross-project-governance",
            "classification": "soft",
            "policy_role": "optional_guidance",
        },
    ]
    assert [row["constraint_id"] for row in context_usage["recommendation_mapping"]] == hook["revision_history"][
        "constraint_ids"
    ]
    assert {row["action_id"] for row in context_usage["recommendation_mapping"]} == {
        row["action_id"] for row in recommendation["recommended_actions"]
    }
    assert set(context_usage["required_recommendation_fields"]) == set(recommendation.keys())
    assert context_usage["recommendation_fields_complete"] is True


def test_req069_hardening_acceptance_packet_preserves_required_evidence_refs_and_open_risk_handling() -> None:
    payload = module.build_req_069_strategy_revision_history_and_diff_workflow(_base_input())
    recommendation = payload["processing_behavior"]["recommendation"]

    assert recommendation["decision"] == "allow-diff-workflow-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["evidence_refs"] == [
        "reports/earth/sweeps/2026-03-17/portfolio.json",
        "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-17/shared-observability.json",
        "strategy/current/DIFF_SUMMARY.json",
        "strategy/current/STRATEGY.json",
        "strategy/current/STRATEGY_DIFF.md",
        "strategy/history/strategy-rev-20260316-190000/STRATEGY.json",
    ]
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
                "reports/earth/sweeps/2026-03-17/shared-observability.json",
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-17/shared-observability.json",
            ],
        }
    ]

    missing_earth_input = deepcopy(_base_input())
    missing_earth_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = []
    missing_earth_input["broad_sweep_context"]["projects_considered"] = []
    missing_earth_payload = module.build_req_069_strategy_revision_history_and_diff_workflow(missing_earth_input)
    missing_earth_recommendation = missing_earth_payload["processing_behavior"]["recommendation"]

    assert missing_earth_recommendation["decision"] == "allow-diff-workflow-with-open-risks"
    assert missing_earth_recommendation["confidence"] == "low"
    assert missing_earth_recommendation["cross_project_obligations"] == []
    assert missing_earth_recommendation["open_risks"] == [
        {
            "risk_id": "risk-obligation-align-runtime-policy",
            "summary": "Align runtime policy with deterministic diff workflow governance.",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json",
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-17/runtime-orchestrator.json",
            ],
        },
        {
            "risk_id": "risk-idea-review-shared-observability-handoff",
            "summary": "Validate shared observability ownership before broadening diff-governance obligations.",
            "reason_code": "unresolved_idea_open_risk",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-17/shared-observability.json",
            ],
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-17/shared-observability.json",
            ],
        },
    ]
