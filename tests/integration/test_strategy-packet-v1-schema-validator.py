import copy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-packet-v1-schema-validator.json"
PACKET_SAMPLE_PATH = REPO_ROOT / "op-tools" / "strategy" / "examples" / "strategy_packet.sample.v1.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_060_integration_uses_broad_sweep_context_and_tracks_recommendation_completeness() -> None:
    payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    payload.pop("strategy_packet_path")
    payload["strategy_packet"] = _read_json(PACKET_SAMPLE_PATH)
    payload["broad_sweep_context"] = {
        "projects_considered": [
            "earth-core-runtime",
            "earth-ops-pipeline",
            "earth-shared-observability",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/earth-ops-pipeline/planner-packet-gaps-2026-03-15.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_obligations": [
            {
                "obligation_id": "obligation-runtime-canary-alignment",
                "summary": "Coordinate runtime canary windows before widening rollout.",
                "recommendation_ids": ["rec.align-earth-runtime-canary"],
                "project_ids": ["earth-core-runtime"],
                "earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
                ],
            },
            {
                "obligation_id": "obligation-missing-earth-evidence",
                "summary": "Link reuse contract updates to cross-project ownership evidence.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "earth_sweep_evidence_refs": [],
            },
        ],
        "unresolved_ideas": [
            {
                "idea_id": "idea.reuse-ownership-followup",
                "summary": "Validate shared ownership handoff before adding new cross-project packets.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "required_earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
                ],
            }
        ],
    }

    out = module.build_req_060_strategy_packet_v1_schema_validator(payload)

    assert module.validate_req_060_strategy_packet_v1_schema_validator(out) == []
    assert out["ok"] is True
    assert out["verdict"] == "pass"
    assert out["planner_consumability"] == "planner_ready"

    processing = out["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["cross_project_context_usage"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "evidence_refs",
        "context_project_ids",
        "mapped_recommendation_ids",
        "mapped_task_intent_handles",
        "recommendation_field_completeness",
        "approved_cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "planner_ready_with_open_risks"
    assert recommendation["rationale"] == (
        "packet_recommendations=3 mapped_recommendations=3 complete_recommendations=3 "
        "recommendations_with_evidence=3 approved=1 open_risks=2 diagnostics=0"
    )
    assert recommendation["mapped_recommendation_ids"] == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
        "rec.review-reuse-contracts",
    ]
    assert recommendation["mapped_task_intent_handles"] == [
        "intent.cross-project-reuse-ownership-clarification",
        "intent.cross-project-runtime-canary-alignment",
        "intent.reuse-contract-review",
        "intent.telemetry-freshness-hardening",
    ]
    assert recommendation["context_project_ids"] == [
        "earth-core-runtime",
        "earth-ops-pipeline",
        "earth-shared-observability",
    ]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in recommendation["evidence_refs"]
    assert "reports/runtime/telemetry/freshness-gap-2026-03-15.json" in recommendation["evidence_refs"]
    assert "missing:earth-sweep-evidence-ref" in recommendation["evidence_refs"]

    assert recommendation["approved_cross_project_obligations"] == [
        {
            "obligation_id": "obligation-runtime-canary-alignment",
            "summary": "Coordinate runtime canary windows before widening rollout.",
            "project_ids": ["earth-core-runtime"],
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
            ],
            "linked_recommendation_ids": ["rec.align-earth-runtime-canary"],
            "linked_planner_task_intent_handles": ["intent.cross-project-runtime-canary-alignment"],
        }
    ]

    assert {row["source_id"]: row["reason_code"] for row in recommendation["open_risks"]} == {
        "idea.reuse-ownership-followup": "unresolved_idea_open_risk",
        "obligation-missing-earth-evidence": "missing_earth_sweep_evidence_refs",
    }

    completeness_by_id = {
        row["recommendation_id"]: row for row in recommendation["recommendation_field_completeness"]
    }
    assert sorted(completeness_by_id) == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
        "rec.review-reuse-contracts",
    ]
    for row in completeness_by_id.values():
        assert row["required_fields_present"] == [
            "recommendation_id",
            "priority",
            "summary",
            "rationale",
            "expected_impact",
            "risk_level",
        ]
        assert row["missing_required_fields"] == []
        assert row["has_complete_required_fields"] is True
        assert row["has_evidence_refs"] is True
        assert row["evidence_refs"]

    assert completeness_by_id["rec.align-earth-runtime-canary"]["planner_task_intent_handles"] == [
        "intent.cross-project-runtime-canary-alignment"
    ]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in completeness_by_id[
        "rec.align-earth-runtime-canary"
    ]["evidence_refs"]
    assert completeness_by_id["rec.review-reuse-contracts"]["planner_task_intent_handles"] == [
        "intent.cross-project-reuse-ownership-clarification",
        "intent.reuse-contract-review",
    ]
    assert "reports/earth/sweeps/shared-observability/signals-2026-03-14.json" in completeness_by_id[
        "rec.review-reuse-contracts"
    ]["evidence_refs"]

    assert usage == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": [
            "earth-core-runtime",
            "earth-ops-pipeline",
            "earth-shared-observability",
        ],
        "earth_sweep_evidence_refs_considered": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/earth-ops-pipeline/planner-packet-gaps-2026-03-15.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_obligation_count": 2,
        "unresolved_idea_count": 1,
        "recommendation_ids_with_context": [
            "rec.align-earth-runtime-canary",
            "rec.review-reuse-contracts",
        ],
    }


def test_req_060_integration_keeps_invalid_recommendation_fields_and_missing_earth_refs_explicit() -> None:
    payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    payload.pop("strategy_packet_path")
    payload["strategy_packet"] = _read_json(PACKET_SAMPLE_PATH)
    payload["strategy_packet"]["recommendations"][2].pop("expected_impact")
    payload["broad_sweep_context"] = {
        "projects_considered": ["earth-shared-observability"],
        "earth_sweep_evidence_refs": [],
        "cross_project_obligations": [
            {
                "obligation_id": "obligation-reuse-without-evidence",
                "summary": "Promote reuse ownership work without Earth evidence.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "earth_sweep_evidence_refs": [],
            }
        ],
        "unresolved_ideas": [],
    }

    out = module.build_req_060_strategy_packet_v1_schema_validator(payload)

    assert module.validate_req_060_strategy_packet_v1_schema_validator(out) == []
    assert out["ok"] is False
    assert out["verdict"] == "fail"
    assert out["planner_consumability"] == "planner_blocked"
    assert out["reason_codes"] == ["schema_required_field_missing"]
    assert out["diagnostic_count"] == 1
    assert out["diagnostics"] == [
        {
            "severity": "error",
            "reason_code": "schema_required_field_missing",
            "field_path": "recommendations[2].expected_impact",
            "message": "'expected_impact' is a required property",
        }
    ]

    processing = out["processing_behavior"]
    recommendation = processing["recommendation"]

    assert recommendation["decision"] == "planner_blocked"
    assert recommendation["rationale"] == (
        "packet_recommendations=3 mapped_recommendations=3 complete_recommendations=2 "
        "recommendations_with_evidence=3 approved=0 open_risks=1 diagnostics=1"
    )
    assert recommendation["approved_cross_project_obligations"] == []
    assert {row["source_id"]: row["reason_code"] for row in recommendation["open_risks"]} == {
        "obligation-reuse-without-evidence": "missing_earth_sweep_evidence_refs"
    }

    review_recommendation = next(
        row
        for row in recommendation["recommendation_field_completeness"]
        if row["recommendation_id"] == "rec.review-reuse-contracts"
    )
    assert review_recommendation["required_fields_present"] == [
        "recommendation_id",
        "priority",
        "summary",
        "rationale",
        "risk_level",
    ]
    assert review_recommendation["missing_required_fields"] == ["expected_impact"]
    assert review_recommendation["has_complete_required_fields"] is False
    assert review_recommendation["has_evidence_refs"] is True
    assert "missing:earth-sweep-evidence-ref" in review_recommendation["evidence_refs"]

    assert processing["cross_project_context_usage"] == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": ["earth-shared-observability"],
        "earth_sweep_evidence_refs_considered": [],
        "cross_project_obligation_count": 1,
        "unresolved_idea_count": 0,
        "recommendation_ids_with_context": [],
    }
