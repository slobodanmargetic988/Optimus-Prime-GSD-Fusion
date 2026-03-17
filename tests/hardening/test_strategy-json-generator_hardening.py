from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-json-generator.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rich_broad_sweep_context() -> dict:
    return {
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_context": [
            {
                "project_id": "earth-core-runtime",
                "evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                ],
                "context_note": "Earth runtime context supports cross-project sequencing.",
            },
            {
                "project_id": "earth-shared-observability",
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                ],
                "context_note": "Shared observability ownership remains unresolved.",
            },
        ],
        "earth_sweep": {
            "projects": [
                {
                    "project_id": "earth-core-runtime",
                    "obligations": [
                        {
                            "summary": "Coordinate canary stabilization with earth-core-runtime.",
                            "recommendation_ids": ["rec.align-earth-runtime-canary"],
                        }
                    ],
                    "unresolved_ideas": [],
                },
                {
                    "project_id": "earth-shared-observability",
                    "obligations": [],
                    "unresolved_ideas": [
                        {
                            "idea": (
                                "Validate earth-shared-observability ownership handoff before scheduling "
                                "additional integration obligations."
                            ),
                            "recommendation_ids": ["rec.review-reuse-contracts"],
                            "evidence_refs": [
                                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                            ],
                        }
                    ],
                },
            ]
        },
    }


def test_req049_hardening_regeneration_is_replay_stable_on_no_change_rerun() -> None:
    fixture = _read_json(FIXTURE_PATH)
    first_input = deepcopy(fixture)
    second_input = deepcopy(fixture)

    second_input["strategy_revision"]["source_requirement_ids"] = list(
        reversed(second_input["strategy_revision"]["source_requirement_ids"])
    )
    second_input["strategy_revision"]["evidence_refs"] = list(reversed(second_input["strategy_revision"]["evidence_refs"]))
    second_input["recommendations"] = list(reversed(second_input["recommendations"]))
    second_input["risks"] = list(reversed(second_input["risks"]))

    for row in second_input["recommendations"]:
        row["impacts"] = list(reversed(row["impacts"]))
        row["risk_ids"] = list(reversed(row["risk_ids"]))
        row["evidence_refs"] = list(reversed(row["evidence_refs"]))
    for row in second_input["risks"]:
        row["evidence_refs"] = list(reversed(row["evidence_refs"]))

    first = module.build_req_049_strategy_json_generator(first_input)
    second = module.build_req_049_strategy_json_generator(second_input)
    third = module.build_req_049_strategy_json_generator(deepcopy(fixture))

    assert module.validate_req_049_strategy_json_generator(first) == []
    assert module.validate_req_049_strategy_json_generator(second) == []
    assert module.validate_req_049_strategy_json_generator(third) == []
    assert first == second == third

    first_json = json.dumps(first["strategy_json"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    second_json = json.dumps(second["strategy_json"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    third_json = json.dumps(third["strategy_json"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert first_json == second_json == third_json


def test_req049_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    payload = _read_json(FIXTURE_PATH)
    payload["broad_sweep_context"] = _rich_broad_sweep_context()

    processing = module.process_req_049_strategy_json_generator(payload)
    context_usage = processing["processing_behavior"]["context_usage"]
    recommendation = processing["processing_behavior"]["recommendation"]

    recommended_action_ids = {row["recommendation_id"] for row in recommendation["recommended_actions"]}
    cross_project_obligation_ids = {row["recommendation_id"] for row in recommendation["cross_project_obligations"]}
    open_risk_linked_ids = {
        recommendation_id
        for row in recommendation["open_risks"]
        for recommendation_id in row["linked_recommendation_ids"]
    }
    expected_mapping_ids = sorted(cross_project_obligation_ids | open_risk_linked_ids)

    assert context_usage["cross_project_context_provided"] is True
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["recommendation_ids_with_context"] == expected_mapping_ids
    assert cross_project_obligation_ids <= recommended_action_ids
    assert open_risk_linked_ids - recommended_action_ids == {"rec.review-reuse-contracts"}


def test_req049_hardening_acceptance_packet_preserves_required_evidence_refs_and_open_risk_handling() -> None:
    payload = _read_json(FIXTURE_PATH)
    payload["broad_sweep_context"] = _rich_broad_sweep_context()

    processing = module.process_req_049_strategy_json_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]

    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        "reports/quality/req-039-rationale-quality-score.json",
        "reports/runtime/telemetry/freshness-gap-2026-03-15.json",
        "strategy/current/llm_call_trace_artifacts/req-027/call-2/trace-call-2-001.json",
        "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json",
    ]
    assert recommendation["cross_project_obligations"] == [
        {
            "project_id": "earth-core-runtime",
            "recommendation_id": "rec.align-earth-runtime-canary",
            "status": "active",
            "rationale": "Cross-project runtime canary alignment is required before widening rollout in the target project.",
            "impacts": [
                "Prevents rollout drift between target and peer runtime teams.",
                "Synchronizes runtime stabilization checkpoints across projects.",
            ],
            "risk_ids": [
                "risk.cross-project-rollout-drift",
                "risk.telemetry-freshness-regression",
            ],
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                "strategy/current/llm_call_trace_artifacts/req-027/call-2/trace-call-2-001.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "open_risk_id": "open-risk.unresolved-idea.earth-shared-observability.001",
            "project_id": "earth-shared-observability",
            "recommendation_id": "rec.review-reuse-contracts",
            "reason_code": "unresolved_idea_open_risk",
            "summary": "Validate earth-shared-observability ownership handoff before scheduling additional integration obligations.",
            "required_evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "linked_recommendation_ids": ["rec.review-reuse-contracts"],
        }
    ]
    assert all(row["reason_code"] != "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])
