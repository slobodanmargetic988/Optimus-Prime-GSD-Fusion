import copy
import json
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "final-strategy-synthesis-composer.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_046_integration_uses_broad_sweep_context_with_deterministic_fields() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    payload = pipeline.build_req_046_final_strategy_synthesis_composer(fixture_payload)
    assert pipeline.validate_req_046_final_strategy_synthesis_composer(payload) == []

    synthesis = payload["final_strategy_synthesis"]
    assert set(synthesis.keys()) == {
        "final_recommendations",
        "deferred_recommendations",
        "open_risks",
        "strategy_packet_inputs",
        "cross_project_context_usage",
    }

    usage = synthesis["cross_project_context_usage"]
    assert usage == {
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

    expected_recommendation_keys = {
        "recommendation_id",
        "summary",
        "rationale",
        "packet_kind",
        "peer_project_id",
        "lane",
        "sequence_hint",
        "priority",
        "evidence_refs",
        "call_trace_lineage",
        "contributing_call_ids",
        "contributing_requirement_ids",
        "supporting_call_count",
        "strategy_packet_input_id",
    }
    for row in synthesis["final_recommendations"]:
        assert set(row.keys()) == expected_recommendation_keys
        assert row["summary"]
        assert row["rationale"]
        assert row["evidence_refs"]
        assert row["call_trace_lineage"]
        assert row["strategy_packet_input_id"].startswith("pkt.")

    recommendations = {row["recommendation_id"]: row for row in synthesis["final_recommendations"]}
    cross_project_recommendation = recommendations["rec.align-earth-runtime-canary"]
    assert cross_project_recommendation["packet_kind"] == "cross-project"
    assert cross_project_recommendation["peer_project_id"] == "earth-core-runtime"
    assert any(ref.startswith("reports/earth/sweeps/") for ref in cross_project_recommendation["evidence_refs"])

    assert synthesis["open_risks"] == [
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


def test_req_046_integration_keeps_cross_project_without_earth_refs_as_open_risk() -> None:
    fixture_payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    fixture_payload["broad_sweep_context"]["earth_sweep_evidence_refs"] = []
    fixture_payload["broad_sweep_context"]["projects_considered"] = []
    fixture_payload["broad_sweep_context"]["cross_project_obligations"] = []
    fixture_payload["broad_sweep_context"]["unresolved_ideas"] = []

    for call in fixture_payload["validated_call_outputs"]:
        for recommendation in call["recommendations"]:
            if recommendation["recommendation_id"] != "rec.align-earth-runtime-canary":
                continue
            recommendation["evidence_refs"] = ["reports/quality/req-039-rationale-quality-score.json"]

    payload = pipeline.build_req_046_final_strategy_synthesis_composer(fixture_payload)
    assert pipeline.validate_req_046_final_strategy_synthesis_composer(payload) == []

    synthesis = payload["final_strategy_synthesis"]
    final_recommendation_ids = {row["recommendation_id"] for row in synthesis["final_recommendations"]}
    assert "rec.align-earth-runtime-canary" not in final_recommendation_ids

    risks = [
        row
        for row in synthesis["open_risks"]
        if row["recommendation_id"] == "rec.align-earth-runtime-canary"
        and row["reason_code"] == "missing_earth_sweep_evidence_refs"
    ]
    assert len(risks) == 1
    risk = risks[0]
    assert risk["project_id"] == "earth-core-runtime"
    assert risk["required_evidence_refs"] == ["missing:earth-sweep-evidence-ref"]
    assert [row["trace_id"] for row in risk["call_trace_lineage"]] == [
        "trace-call-2-001",
        "trace-rationale-quality-001",
    ]

    assert [row["packet_kind"] for row in synthesis["strategy_packet_inputs"]] == ["target-project"]
    assert synthesis["cross_project_context_usage"]["cross_project_context_provided"] is False
    assert synthesis["cross_project_context_usage"]["cross_project_context_used"] is True
    assert synthesis["cross_project_context_usage"]["projects_considered"] == ["earth-core-runtime"]
