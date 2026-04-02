import json
from copy import deepcopy
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "kpi-target-artifact.json"


def _read_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _recommendation_to_target_mapping(payload: dict) -> dict[str, list[str]]:
    mapping: dict[str, set[str]] = {}
    for row in payload["kpi_target_artifact"]["kpi_targets"]:
        for recommendation_id in row["originating_recommendation_ids"]:
            mapping.setdefault(recommendation_id, set()).add(row["target_id"])
    return {key: sorted(value) for key, value in sorted(mapping.items())}


def test_hardening_req056_no_change_rerun_regenerates_identical_artifact() -> None:
    fixture = _read_fixture()
    payload = fixture["integration_input"]

    run_one = module.build_req_056_kpi_target_artifact(deepcopy(payload))
    run_two = module.build_req_056_kpi_target_artifact(deepcopy(payload))

    assert json.dumps(run_one, sort_keys=True, separators=(",", ":")) == json.dumps(
        run_two, sort_keys=True, separators=(",", ":")
    )
    assert [row["reason_code"] for row in run_one["processing_behavior"]["recommendation"]["open_risks"]] == [
        row["reason_code"] for row in run_two["processing_behavior"]["recommendation"]["open_risks"]
    ]


def test_hardening_req056_planner_hook_mapping_set_is_complete() -> None:
    fixture = _read_fixture()
    out = module.build_req_056_kpi_target_artifact(fixture["integration_input"])
    assert module.validate_req_056_kpi_target_artifact(out) == []

    recommendation = out["processing_behavior"]["recommendation"]
    context_usage = out["processing_behavior"]["context_usage"]
    planner_hook_mapping = _recommendation_to_target_mapping(out)

    assert sorted(planner_hook_mapping.keys()) == context_usage["linked_recommendation_ids_used"]
    assert sorted({target_id for rows in planner_hook_mapping.values() for target_id in rows}) == recommendation[
        "linked_kpi_target_ids"
    ]
    assert planner_hook_mapping == {
        "rec.align-earth-runtime-canary": ["kpi.cross-project-integration-latency"],
        "rec.harden-telemetry-freshness": [
            "kpi.cross-project-integration-latency",
            "kpi.telemetry-freshness-slo",
        ],
    }


def test_hardening_req056_acceptance_packet_includes_evidence_refs_and_open_risk_handling() -> None:
    fixture = _read_fixture()
    out = module.build_req_056_kpi_target_artifact(fixture["integration_input"])
    recommendation = out["processing_behavior"]["recommendation"]

    acceptance_packet = {
        "req_id": "REQ-056",
        "summary": recommendation["rationale"],
        "consumability_verdict": recommendation["decision"],
        "evidence_refs": recommendation["evidence_refs"],
        "open_risks": recommendation["open_risks"],
    }

    assert acceptance_packet["evidence_refs"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in acceptance_packet[
        "evidence_refs"
    ]
    assert "reports/earth/sweeps/shared-observability/signals-2026-03-14.json" in acceptance_packet["evidence_refs"]
    assert acceptance_packet["consumability_verdict"] == "proceed-with-open-risks"

    assert len(acceptance_packet["open_risks"]) == 1
    open_risk = acceptance_packet["open_risks"][0]
    assert open_risk["reason_code"] == "unresolved_cross_project_idea"
    assert open_risk["evidence_refs"] == [
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]
    assert "reports/earth/sweeps/shared-observability/signals-2026-03-14.json" in open_risk["required_evidence_refs"]
    assert all(ref.startswith("reports/earth/sweeps/") for ref in open_risk["required_evidence_refs"])
