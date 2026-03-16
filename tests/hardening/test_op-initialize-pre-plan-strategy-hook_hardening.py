from __future__ import annotations

from copy import deepcopy
import json

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
                        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                    ],
                }
            ],
            "unresolved_ideas": [
                {
                    "idea_id": "idea-review-shared-observability-handoff",
                    "summary": "Validate ownership handoff details before adding additional sync obligations.",
                    "earth_sweep_evidence_refs": [
                        "reports/earth/sweeps/2026-03-16/shared-observability.json",
                    ],
                }
            ],
        },
    }


def test_req067_hardening_regeneration_is_replay_stable_on_no_change_rerun() -> None:
    first_input = _base_input()
    second_input = deepcopy(first_input)

    second_input["strategy_context"]["strategy_artifact_refs"] = list(
        reversed(second_input["strategy_context"]["strategy_artifact_refs"])
    )
    second_input["strategy_context"]["recommendation_ids"] = list(
        reversed(second_input["strategy_context"]["recommendation_ids"])
    )
    second_input["strategy_context"]["constraint_ids"] = list(
        reversed(second_input["strategy_context"]["constraint_ids"])
    )
    second_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = list(
        reversed(second_input["broad_sweep_context"]["earth_sweep_evidence_refs"])
    )
    second_input["broad_sweep_context"]["projects_considered"] = list(
        reversed(second_input["broad_sweep_context"]["projects_considered"])
    )

    first = module.build_req_067_op_initialize_pre_plan_strategy_hook(first_input)
    second = module.build_req_067_op_initialize_pre_plan_strategy_hook(second_input)
    third = module.build_req_067_op_initialize_pre_plan_strategy_hook(deepcopy(first_input))

    assert module.validate_req_067_op_initialize_pre_plan_strategy_hook(first) == []
    assert module.validate_req_067_op_initialize_pre_plan_strategy_hook(second) == []
    assert module.validate_req_067_op_initialize_pre_plan_strategy_hook(third) == []
    assert first == second == third

    first_json = json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    second_json = json.dumps(second, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    third_json = json.dumps(third, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert first_json == second_json == third_json


def test_req067_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    payload = module.build_req_067_op_initialize_pre_plan_strategy_hook(_base_input())
    hook = payload["pre_plan_strategy_hook"]
    recommendation = payload["processing_behavior"]["recommendation"]
    context_usage = payload["processing_behavior"]["context_usage"]

    assert hook["planner_readiness"]["context_ready"] is True
    assert hook["planner_readiness"]["decision"] == "allow_planning"
    assert context_usage["recommendation_mapping"] == [
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
    ]
    assert [row["constraint_id"] for row in context_usage["recommendation_mapping"]] == hook["strategy_context"][
        "constraint_ids"
    ]
    assert {row["action_id"] for row in context_usage["recommendation_mapping"]} == {
        row["action_id"] for row in recommendation["recommended_actions"]
    }
    assert set(context_usage["required_recommendation_fields"]) == set(recommendation.keys())
    assert context_usage["recommendation_fields_complete"] is True


def test_req067_hardening_acceptance_packet_preserves_required_evidence_refs_and_open_risk_handling() -> None:
    payload = module.build_req_067_op_initialize_pre_plan_strategy_hook(_base_input())
    recommendation = payload["processing_behavior"]["recommendation"]

    assert recommendation["decision"] == "allow-op-plan-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["evidence_refs"] == [
        "reports/earth/sweeps/2026-03-16/portfolio.json",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-16/shared-observability.json",
        "strategy/current/ECOSYSTEM_LINK_MAP.json",
        "strategy/current/STRATEGY.json",
        "strategy/current/STRATEGY_CHANGELOG.md",
    ]
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

    missing_earth_input = deepcopy(_base_input())
    missing_earth_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = []
    missing_earth_input["broad_sweep_context"]["projects_considered"] = []
    missing_earth_payload = module.build_req_067_op_initialize_pre_plan_strategy_hook(missing_earth_input)
    missing_earth_recommendation = missing_earth_payload["processing_behavior"]["recommendation"]

    assert missing_earth_recommendation["decision"] == "allow-op-plan-with-open-risks"
    assert missing_earth_recommendation["confidence"] == "low"
    assert missing_earth_recommendation["cross_project_obligations"] == []
    assert missing_earth_recommendation["open_risks"] == [
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
