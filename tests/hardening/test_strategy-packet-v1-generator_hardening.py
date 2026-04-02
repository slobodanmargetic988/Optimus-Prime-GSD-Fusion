from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-packet-v1-generator.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_052_hardening_regeneration_is_replay_stable_on_no_change_rerun() -> None:
    fixture = _read_json(FIXTURE_PATH)
    first_input = deepcopy(fixture)
    second_input = deepcopy(fixture)

    second_input["recommendation_profiles"] = list(reversed(second_input["recommendation_profiles"]))
    second_input["constraints"]["hard"] = list(reversed(second_input["constraints"]["hard"]))
    second_input["constraints"]["soft"] = list(reversed(second_input["constraints"]["soft"]))
    second_input["kpi_targets"] = list(reversed(second_input["kpi_targets"]))

    synthesis = second_input["final_strategy_synthesis"]
    synthesis["final_recommendations"] = list(reversed(synthesis["final_recommendations"]))
    synthesis["deferred_recommendations"] = list(reversed(synthesis["deferred_recommendations"]))
    synthesis["open_risks"] = list(reversed(synthesis["open_risks"]))
    synthesis["strategy_packet_inputs"] = list(reversed(synthesis["strategy_packet_inputs"]))
    synthesis["cross_project_context_usage"]["projects_considered"] = list(
        reversed(synthesis["cross_project_context_usage"]["projects_considered"])
    )
    synthesis["cross_project_context_usage"]["earth_sweep_evidence_refs_considered"] = list(
        reversed(synthesis["cross_project_context_usage"]["earth_sweep_evidence_refs_considered"])
    )
    synthesis["cross_project_context_usage"]["recommendation_ids_with_context"] = list(
        reversed(synthesis["cross_project_context_usage"]["recommendation_ids_with_context"])
    )

    for row in synthesis["final_recommendations"]:
        row["evidence_refs"] = list(reversed(row["evidence_refs"]))
        row["call_trace_lineage"] = list(reversed(row["call_trace_lineage"]))
        row["contributing_call_ids"] = list(reversed(row["contributing_call_ids"]))
        row["contributing_requirement_ids"] = list(reversed(row["contributing_requirement_ids"]))
    for row in synthesis["deferred_recommendations"]:
        row["packet_kind_candidates"] = list(reversed(row["packet_kind_candidates"]))
        row["peer_project_candidates"] = list(reversed(row["peer_project_candidates"]))
        row["evidence_refs"] = list(reversed(row["evidence_refs"]))
        row["call_trace_lineage"] = list(reversed(row["call_trace_lineage"]))
        row["contributing_call_ids"] = list(reversed(row["contributing_call_ids"]))
    for row in synthesis["open_risks"]:
        row["required_evidence_refs"] = list(reversed(row["required_evidence_refs"]))
        row["evidence_refs"] = list(reversed(row["evidence_refs"]))
        row["linked_recommendation_ids"] = list(reversed(row["linked_recommendation_ids"]))
    for row in synthesis["strategy_packet_inputs"]:
        row["recommendation_ids"] = list(reversed(row["recommendation_ids"]))
        row["evidence_refs"] = list(reversed(row["evidence_refs"]))

    first = module.build_req_052_strategy_packet_v1_generator(first_input)
    second = module.build_req_052_strategy_packet_v1_generator(second_input)
    third = module.build_req_052_strategy_packet_v1_generator(deepcopy(fixture))

    assert module.validate_req_052_strategy_packet_v1_generator(first) == []
    assert module.validate_req_052_strategy_packet_v1_generator(second) == []
    assert module.validate_req_052_strategy_packet_v1_generator(third) == []
    assert first == second == third

    first_packet = json.dumps(first["strategy_packet_v1"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    second_packet = json.dumps(second["strategy_packet_v1"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    third_packet = json.dumps(third["strategy_packet_v1"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert first_packet == second_packet == third_packet


def test_req_052_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_052_strategy_packet_v1_generator(fixture)

    assert module.validate_req_052_strategy_packet_v1_generator(payload) == []

    context = payload["strategy_packet_context"]
    usage = context["cross_project_context_usage"]
    readiness_ids = {row["recommendation_id"] for row in context["recommendation_readiness"]}
    open_risk_linked_ids = {
        recommendation_id
        for row in context["open_risks"]
        for recommendation_id in row["linked_recommendation_ids"]
    }
    cross_project_packet_ids = {
        recommendation_id
        for row in fixture["final_strategy_synthesis"]["strategy_packet_inputs"]
        if row["packet_kind"] == "cross-project"
        for recommendation_id in row["recommendation_ids"]
    }
    expected_mapping_ids = sorted(cross_project_packet_ids | open_risk_linked_ids)

    assert usage["cross_project_context_provided"] is True
    assert usage["cross_project_context_used"] is True
    assert usage["recommendation_ids_with_context"] == expected_mapping_ids
    assert cross_project_packet_ids <= readiness_ids
    assert open_risk_linked_ids.isdisjoint(readiness_ids)
    assert open_risk_linked_ids == {"rec.review-reuse-contracts"}


def test_req_052_hardening_acceptance_packet_preserves_required_evidence_refs_and_open_risk_handling() -> None:
    payload = module.build_req_052_strategy_packet_v1_generator(_read_json(FIXTURE_PATH))

    assert module.validate_req_052_strategy_packet_v1_generator(payload) == []

    packet_recommendation_ids = {
        row["recommendation_id"] for row in payload["strategy_packet_v1"]["packet"]["recommendations"]
    }
    context = payload["strategy_packet_context"]
    readiness_by_id = {row["recommendation_id"]: row for row in context["recommendation_readiness"]}
    open_risks = context["open_risks"]

    assert payload["strategy_packet_v1"]["packet"]["source"] == {
        "repo": "Optimus-Prime-GSD-Fusion",
        "tool": "scripts/strategy_artifacts_handoff.py",
    }
    assert readiness_by_id["rec.align-earth-runtime-canary"]["earth_sweep_evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
    ]
    assert open_risks == [
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
    assert open_risks[0]["linked_recommendation_ids"][0] not in packet_recommendation_ids
    assert context["cross_project_context_usage"]["unresolved_idea_count"] == len(open_risks)
