import copy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as handoff


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-id-stability-contract.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_053_integration_uses_broad_sweep_context_with_deterministic_fields() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    payload = handoff.build_req_053_recommendation_id_stability_contract(fixture_payload)
    assert handoff.validate_req_053_recommendation_id_stability_contract(payload) == []
    assert set(payload.keys()) == {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "target_project",
        "recommendation_id_stability",
        "totals",
    }

    stability = payload["recommendation_id_stability"]
    assert set(stability.keys()) == {
        "baseline_revision_id",
        "stability_basis_fields",
        "baseline_recommendations",
        "scenario_results",
        "cross_project_context_usage",
        "open_risks",
    }

    usage = stability["cross_project_context_usage"]
    assert usage == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": ["earth-core-runtime", "earth-shared-observability"],
        "earth_sweep_evidence_refs_considered": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_obligation_count": 1,
        "unresolved_idea_count": 1,
        "recommendation_ids_with_context": [
            "rec.align-earth-runtime-canary",
            "rec.harden-telemetry-freshness",
        ],
    }

    expected_baseline_keys = {
        "lineage_key",
        "recommendation_id",
        "stability_key",
        "stability_basis",
        "evidence_refs",
        "earth_sweep_evidence_refs",
        "recommendation_field_completeness",
    }
    for row in stability["baseline_recommendations"]:
        assert set(row.keys()) == expected_baseline_keys
        assert row["evidence_refs"]
        assert row["recommendation_field_completeness"]["all_fields_present"] is True
        assert row["recommendation_field_completeness"]["missing_fields"] == []

    by_recommendation = {
        row["recommendation_id"]: row for row in stability["baseline_recommendations"]
    }
    assert by_recommendation["rec.align-earth-runtime-canary"]["earth_sweep_evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
    ]
    assert by_recommendation["rec.harden-telemetry-freshness"]["earth_sweep_evidence_refs"] == []

    no_change = next(row for row in stability["scenario_results"] if row["scenario_id"] == "scenario.no-change")
    runtime_result = next(
        row for row in no_change["recommendation_results"] if row["lineage_key"] == "lineage.runtime-canary-alignment"
    )
    telemetry_result = next(
        row for row in no_change["recommendation_results"] if row["lineage_key"] == "lineage.telemetry-freshness"
    )
    for row in (runtime_result, telemetry_result):
        assert row["baseline_evidence_refs"]
        assert row["scenario_evidence_refs"]
        assert row["baseline_recommendation_field_completeness"]["all_fields_present"] is True
        assert row["scenario_recommendation_field_completeness"]["all_fields_present"] is True

    assert stability["open_risks"] == [
        {
            "open_risk_id": "open-risk.5054fc9d54b5",
            "recommendation_id": "idea.telemetry-shared-observability-follow-up",
            "summary": "Validate earth-shared-observability ownership before coupling freshness guardrails to shared dashboards.",
            "reason_code": "unresolved_idea_open_risk",
            "project_id": "earth-shared-observability",
            "required_evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
            ],
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
            ],
            "linked_recommendation_ids": ["rec.harden-telemetry-freshness"],
            "call_trace_lineage": [],
            "contributing_call_ids": [],
        }
    ]
    assert payload["totals"]["open_risk_count"] == 1


def test_req_053_integration_surfaces_cross_project_without_earth_refs_as_open_risk() -> None:
    fixture_payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    fixture_payload["broad_sweep_context"]["earth_sweep_evidence_refs"] = []
    fixture_payload["broad_sweep_context"]["projects_considered"] = []
    fixture_payload["broad_sweep_context"]["cross_project_obligations"] = []
    fixture_payload["broad_sweep_context"]["unresolved_ideas"] = []

    for recommendation in fixture_payload["baseline_revision"]["recommendations"]:
        if recommendation["recommendation_id"] == "rec.align-earth-runtime-canary":
            recommendation["evidence_refs"] = ["reports/quality/req-039-rationale-quality-score.json"]
    for scenario in fixture_payload["rerun_scenarios"]:
        for recommendation in scenario["recommendations"]:
            if recommendation["recommendation_id"] == "rec.align-earth-runtime-canary":
                recommendation["evidence_refs"] = ["reports/quality/req-039-rationale-quality-score.json"]

    payload = handoff.build_req_053_recommendation_id_stability_contract(fixture_payload)
    assert handoff.validate_req_053_recommendation_id_stability_contract(payload) == []

    stability = payload["recommendation_id_stability"]
    assert stability["cross_project_context_usage"]["cross_project_context_provided"] is False
    assert stability["cross_project_context_usage"]["cross_project_context_used"] is True
    assert stability["cross_project_context_usage"]["projects_considered"] == ["earth-core-runtime"]

    risks = [
        row
        for row in stability["open_risks"]
        if row["recommendation_id"] == "rec.align-earth-runtime-canary"
        and row["reason_code"] == "missing_earth_sweep_evidence_refs"
    ]
    assert len(risks) == 1
    risk = risks[0]
    assert risk["project_id"] == "earth-core-runtime"
    assert risk["required_evidence_refs"] == ["missing:earth-sweep-evidence-ref"]
    assert risk["evidence_refs"] == ["reports/quality/req-039-rationale-quality-score.json"]
