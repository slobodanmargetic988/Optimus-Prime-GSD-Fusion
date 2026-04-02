from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "req070_end_to_end_autonomous_strategy_acceptance_packet.json"
SPEC = importlib.util.spec_from_file_location("strategy_artifacts_handoff", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _read_fixture_payload() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return deepcopy(fixture["payload"])


def test_req_070_hardening_artifact_regeneration_has_no_semantic_drift_on_no_change_rerun() -> None:
    payload = _read_fixture_payload()

    run_one = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(deepcopy(payload))
    run_two = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(deepcopy(payload))

    assert json.dumps(run_one, sort_keys=True, separators=(",", ":")) == json.dumps(
        run_two, sort_keys=True, separators=(",", ":")
    )
    assert [row["reason_code"] for row in run_one["open_risks"]] == [
        row["reason_code"] for row in run_two["open_risks"]
    ]


def test_req_070_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    packet = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(_read_fixture_payload())

    planner_hook = packet["planner_hook"]

    assert planner_hook["recommendation_ids"] == [
        "rec.dispatch-quality-first",
        "rec.peer-signal-reuse",
    ]
    assert planner_hook["mapped_recommendation_ids"] == planner_hook["recommendation_ids"]
    assert planner_hook["missing_recommendation_ids"] == []
    assert planner_hook["mapping_complete"] is True
    assert planner_hook["sources_used"] == [
        "generated_from_recommendations",
        "planner_hook.recommendation_readiness",
    ]
    assert planner_hook["recommendation_mapping"]["rec.peer-signal-reuse"] == {
        "recommendation_id": "rec.peer-signal-reuse",
        "recommendation_key": "rec.peer-signal-reuse",
        "status": "ready",
        "priority": "medium",
        "summary": "Reuse peer planning signals during the autonomous sweep.",
        "artifact_refs": [
            "reports/optimus-prime/planning/validator/strategy_packet_validation.json",
            "strategy/current/strategy_packet.v1.json",
            "strategy/history/REVISION_HISTORY.json",
        ],
        "evidence_refs": [
            "Earth/peer-beta/reports/planning/ROADMAP.md#L9",
        ],
    }


def test_req_070_hardening_acceptance_packet_includes_required_evidence_refs_and_open_risk_handling() -> None:
    packet = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(_read_fixture_payload())

    assert "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/validator/strategy_packet_validation.json#L1" in packet[
        "evidence_refs"
    ]
    assert "Optimus-Prime-GSD-Fusion/strategy/current/strategy_packet.v1.json#L1" in packet["evidence_refs"]
    assert "Optimus-Prime-GSD-Fusion/strategy/history/REVISION_HISTORY.json#L1" in packet["evidence_refs"]

    assert len(packet["open_risks"]) == 1
    open_risk = packet["open_risks"][0]
    assert open_risk["reason_code"] == "missing_earth_sweep_evidence_refs"
    assert open_risk["linked_recommendation_ids"] == ["rec.peer-signal-reuse"]
    assert open_risk["evidence_refs"] == [
        "Earth/peer-beta/reports/planning/STATE.md#L6",
    ]
    assert open_risk["required_evidence_refs"] == [
        "Earth/peer-beta/reports/planning/STATE.md#L6",
    ]
    assert packet["consumability_verdict"]["warning_reasons"] == ["open_risks_present"]
