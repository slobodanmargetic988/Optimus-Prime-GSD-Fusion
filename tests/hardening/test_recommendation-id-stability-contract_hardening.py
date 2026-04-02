from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-id-stability-contract.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _missing_earth_ref_fixture() -> dict:
    fixture_payload = deepcopy(_read_json(FIXTURE_PATH))
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
    return fixture_payload


def test_req_053_hardening_artifact_regeneration_is_replay_stable_for_no_change_reruns() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    reordered_payload = deepcopy(fixture_payload)
    reordered_payload["baseline_revision"]["recommendations"] = list(
        reversed(reordered_payload["baseline_revision"]["recommendations"])
    )
    reordered_payload["rerun_scenarios"] = list(reversed(reordered_payload["rerun_scenarios"]))
    reordered_payload["broad_sweep_context"]["earth_sweep_evidence_refs"] = [
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]
    reordered_payload["broad_sweep_context"]["projects_considered"] = list(
        reversed(reordered_payload["broad_sweep_context"]["projects_considered"])
    )
    for scenario in reordered_payload["rerun_scenarios"]:
        scenario["recommendations"] = list(reversed(scenario["recommendations"]))

    first = module.run(deepcopy(fixture_payload))
    second = module.run(reordered_payload)
    third = module.run(deepcopy(fixture_payload))

    assert module.validate_req_053_recommendation_id_stability_contract(first) == []
    assert module.validate_req_053_recommendation_id_stability_contract(second) == []
    assert module.validate_req_053_recommendation_id_stability_contract(third) == []
    assert first == second == third

    first_serialized = json.dumps(first, sort_keys=True, separators=(",", ":"))
    second_serialized = json.dumps(second, sort_keys=True, separators=(",", ":"))
    third_serialized = json.dumps(third, sort_keys=True, separators=(",", ":"))
    assert first_serialized == second_serialized == third_serialized

    no_change_rows = next(
        row
        for row in first["recommendation_id_stability"]["scenario_results"]
        if row["scenario_id"] == "scenario.no-change"
    )["recommendation_results"]
    assert [row["id_status"] for row in no_change_rows] == ["stable", "stable"]


def test_req_053_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    payload = module.build_req_053_recommendation_id_stability_contract(_read_json(FIXTURE_PATH))
    mapping_set = module.build_req_053_planner_recommendation_mapping_set(payload)

    expected_pairs = {
        ("baseline", row["lineage_key"])
        for row in payload["recommendation_id_stability"]["baseline_recommendations"]
    }
    expected_pairs.update(
        (scenario["scenario_id"], row["lineage_key"])
        for scenario in payload["recommendation_id_stability"]["scenario_results"]
        for row in scenario["recommendation_results"]
    )
    actual_pairs = {
        (row["scenario_id"], row["lineage_key"]) for row in mapping_set["recommendation_mappings"]
    }

    assert actual_pairs == expected_pairs
    assert mapping_set["scenario_ids"] == ["baseline", "scenario.no-change", "scenario.substantive-change"]
    assert mapping_set["recommendation_id_inventory"] == [
        "rec.align-earth-runtime-canary",
        "rec.escalate-telemetry-freshness-guardrail",
        "rec.harden-telemetry-freshness",
    ]
    assert mapping_set["mapping_row_count"] == len(mapping_set["recommendation_mappings"])

    telemetry_evolved = next(
        row
        for row in mapping_set["recommendation_mappings"]
        if row["scenario_id"] == "scenario.substantive-change"
        and row["lineage_key"] == "lineage.telemetry-freshness"
    )
    assert telemetry_evolved["id_status"] == "evolved"
    assert telemetry_evolved["changed_fields"] == ["summary", "rationale"]
    assert telemetry_evolved["baseline_recommendation_id"] == "rec.harden-telemetry-freshness"
    assert telemetry_evolved["scenario_recommendation_id"] == "rec.escalate-telemetry-freshness-guardrail"


def test_req_053_hardening_acceptance_packet_includes_required_evidence_refs_and_open_risk_handling() -> None:
    payload = module.build_req_053_recommendation_id_stability_contract(_missing_earth_ref_fixture())
    acceptance_packet = module.build_req_053_acceptance_packet(payload)
    open_risk_id = payload["recommendation_id_stability"]["open_risks"][0]["open_risk_id"]

    assert module.validate_req_053_recommendation_id_stability_contract(payload) == []
    assert acceptance_packet == {
        "requirement_id": "REQ-053",
        "baseline_revision_id": "strategy-2026-03-15T08:00:00Z",
        "decision": "acceptance-with-open-risks",
        "mapping_row_count": 6,
        "scenario_ids": ["baseline", "scenario.no-change", "scenario.substantive-change"],
        "recommendation_id_inventory": [
            "rec.align-earth-runtime-canary",
            "rec.escalate-telemetry-freshness-guardrail",
            "rec.harden-telemetry-freshness",
        ],
        "required_evidence_refs": ["missing:earth-sweep-evidence-ref"],
        "evidence_refs": [
            "missing:earth-sweep-evidence-ref",
            "reports/quality/req-039-rationale-quality-score.json",
            "reports/runtime/telemetry/freshness-gap-2026-03-15.json",
            "reports/runtime/telemetry/freshness-gap-2026-03-16.json",
        ],
        "open_risk_ids": [open_risk_id],
        "open_risk_reason_codes": ["missing_earth_sweep_evidence_refs"],
    }
