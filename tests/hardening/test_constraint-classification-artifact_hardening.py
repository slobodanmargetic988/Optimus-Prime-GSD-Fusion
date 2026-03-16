from __future__ import annotations

from copy import deepcopy
import json

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
                "evidence_refs": [
                    "scope.md#mandatory-planning-gate",
                    "AGENTS.md#scope-authoring-rule-high-priority",
                ],
                "source_refs": [
                    "scope.md#mandatory-planning-gate",
                ],
            },
            {
                "constraint_id": "guidance-batch-size",
                "statement": "Prefer batching packets by lane.",
                "classification": "soft",
                "rationale": "Improves throughput.",
                "evidence_refs": [
                    "reports/strategy/lane-throughput-2026-03-15.json",
                    "reports/strategy/lane-throughput-2026-03-14.json",
                ],
                "source_refs": [
                    "reports/strategy/lane-throughput-2026-03-15.json",
                ],
            },
            {
                "constraint_id": "speculative-cross-project-sync",
                "statement": "Consider Earth-wide sync if lane drift increases.",
                "classification": "speculative",
                "rationale": "Optional path if drift appears.",
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                    "reports/earth/sweeps/shared-observability/signals-2026-03-13.json",
                ],
                "source_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                ],
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


def test_req055_hardening_regeneration_is_replay_stable_on_no_change_rerun() -> None:
    first_input = _base_input()
    second_input = deepcopy(first_input)

    second_input["constraints"] = list(reversed(second_input["constraints"]))
    second_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = list(
        reversed(second_input["broad_sweep_context"]["earth_sweep_evidence_refs"])
    )
    second_input["broad_sweep_context"]["projects_considered"] = list(
        reversed(second_input["broad_sweep_context"]["projects_considered"])
    )
    second_input["broad_sweep_context"]["cross_project_obligations"] = list(
        reversed(second_input["broad_sweep_context"]["cross_project_obligations"])
    )
    second_input["broad_sweep_context"]["unresolved_ideas"] = list(
        reversed(second_input["broad_sweep_context"]["unresolved_ideas"])
    )
    for row in second_input["constraints"]:
        row["evidence_refs"] = list(reversed(row["evidence_refs"]))
        row["source_refs"] = list(reversed(row["source_refs"]))

    first = module.build_req_055_constraint_classification_artifact(first_input)
    second = module.build_req_055_constraint_classification_artifact(second_input)
    third = module.build_req_055_constraint_classification_artifact(deepcopy(first_input))

    assert module.validate_req_055_constraint_classification_artifact(first) == []
    assert module.validate_req_055_constraint_classification_artifact(second) == []
    assert module.validate_req_055_constraint_classification_artifact(third) == []
    assert first == second == third

    first_json = json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    second_json = json.dumps(second, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    third_json = json.dumps(third, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert first_json == second_json == third_json


def test_req055_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    payload = module.build_req_055_constraint_classification_artifact(_base_input())
    planner_policy = payload["constraint_classification"]["planner_policy"]
    recommendation = payload["processing_behavior"]["recommendation"]
    context_usage = payload["processing_behavior"]["context_usage"]

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
        {
            "constraint_id": "speculative-cross-project-sync",
            "action_id": "constraint-speculative-cross-project-sync",
            "classification": "speculative",
            "policy_role": "optional_guidance",
        },
    ]
    assert [row["constraint_id"] for row in context_usage["recommendation_mapping"]] == (
        planner_policy["mandatory_guardrail_ids"] + planner_policy["optional_guidance_ids"]
    )
    assert {row["action_id"] for row in context_usage["recommendation_mapping"]} == {
        row["action_id"] for row in recommendation["recommended_actions"]
    }
    assert [
        row["constraint_id"]
        for row in context_usage["recommendation_mapping"]
        if row["policy_role"] == "mandatory_guardrail"
    ] == planner_policy["mandatory_guardrail_ids"]


def test_req055_hardening_acceptance_packet_preserves_required_evidence_refs_and_open_risk_handling() -> None:
    payload = module.build_req_055_constraint_classification_artifact(_base_input())
    recommendation = payload["processing_behavior"]["recommendation"]

    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["evidence_refs"] == [
        "AGENTS.md#scope-authoring-rule-high-priority",
        "reports/earth/sweeps/2026-03-16/portfolio.json",
        "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        "reports/earth/sweeps/2026-03-16/shared-observability.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-13.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        "reports/strategy/lane-throughput-2026-03-14.json",
        "reports/strategy/lane-throughput-2026-03-15.json",
        "scope.md#mandatory-planning-gate",
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
    missing_earth_payload = module.build_req_055_constraint_classification_artifact(missing_earth_input)
    missing_earth_recommendation = missing_earth_payload["processing_behavior"]["recommendation"]

    assert missing_earth_recommendation["decision"] == "collect-earth-evidence"
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
