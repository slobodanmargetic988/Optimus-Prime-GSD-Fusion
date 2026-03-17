import copy
import json
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as handoff


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-packet-v1-generator.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_052_integration_uses_broad_sweep_context_with_deterministic_fields() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    payload = handoff.build_req_052_strategy_packet_v1_generator(fixture_payload)
    assert handoff.validate_req_052_strategy_packet_v1_generator(payload) == []
    assert set(payload.keys()) == {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "target_project",
        "strategy_packet_v1",
        "strategy_packet_context",
        "totals",
    }

    packet = payload["strategy_packet_v1"]["packet"]
    assert [row["recommendation_id"] for row in packet["recommendations"]] == [
        "rec.harden-telemetry-freshness",
        "rec.align-earth-runtime-canary",
    ]

    context = payload["strategy_packet_context"]
    assert set(context.keys()) == {
        "recommendation_readiness",
        "cross_project_context_usage",
        "open_risks",
    }
    assert [row["recommendation_id"] for row in context["recommendation_readiness"]] == [
        "rec.harden-telemetry-freshness",
        "rec.align-earth-runtime-canary",
    ]

    expected_readiness_keys = {
        "recommendation_id",
        "strategy_packet_input_id",
        "packet_kind",
        "peer_project_id",
        "lane",
        "evidence_refs",
        "earth_sweep_evidence_refs",
        "recommendation_field_completeness",
    }
    for row in context["recommendation_readiness"]:
        assert set(row.keys()) == expected_readiness_keys
        assert row["evidence_refs"]
        assert row["recommendation_field_completeness"]["all_fields_present"] is True
        assert row["recommendation_field_completeness"]["missing_fields"] == []

    cross_project_row = next(
        row for row in context["recommendation_readiness"] if row["recommendation_id"] == "rec.align-earth-runtime-canary"
    )
    assert cross_project_row["packet_kind"] == "cross-project"
    assert cross_project_row["peer_project_id"] == "earth-core-runtime"
    assert cross_project_row["earth_sweep_evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
    ]

    assert context["cross_project_context_usage"] == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": ["earth-core-runtime", "earth-shared-observability"],
        "earth_sweep_evidence_refs_considered": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_obligation_count": 2,
        "unresolved_idea_count": 1,
        "recommendation_ids_with_context": [
            "rec.align-earth-runtime-canary",
            "rec.review-reuse-contracts",
        ],
    }
    assert context["open_risks"] == [
        {
            "open_risk_id": "open-risk.c6d73dbb8f81",
            "recommendation_id": "idea.review-reuse-contracts-follow-up",
            "summary": "Validate earth-shared-observability ownership handoff before scheduling additional integration obligations.",
            "reason_code": "unresolved_idea_open_risk",
            "project_id": "earth-shared-observability",
            "required_evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "linked_recommendation_ids": ["rec.review-reuse-contracts"],
            "call_trace_lineage": [],
            "contributing_call_ids": [],
        }
    ]
    assert "rec.review-reuse-contracts" not in {
        row["recommendation_id"] for row in packet["recommendations"]
    }


def test_req_052_integration_rejects_cross_project_recommendations_without_earth_sweep_evidence() -> None:
    fixture_payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    for row in fixture_payload["final_strategy_synthesis"]["final_recommendations"]:
        if row["recommendation_id"] != "rec.align-earth-runtime-canary":
            continue
        row["evidence_refs"] = [
            "reports/quality/req-039-rationale-quality-score.json",
            "strategy/current/llm_call_trace_artifacts/req-027/call-2/trace-call-2-001.json",
        ]

    with pytest.raises(
        ValueError,
        match=r"cross-project final recommendations must include direct Earth-sweep evidence refs",
    ):
        handoff.build_req_052_strategy_packet_v1_generator(fixture_payload)
