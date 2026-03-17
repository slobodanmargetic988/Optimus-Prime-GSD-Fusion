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


def test_req_070_acceptance_packet_contract_exposes_planner_hook_and_open_risk_diagnostics() -> None:
    packet = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(_read_fixture_payload())

    assert packet["requirement_id"] == "REQ-070"
    assert packet["acceptance_packet_version"] == "1.0"
    assert packet["run_identity"] == {
        "project_id": "prj.optimus-prime",
        "run_id": "run.20260317t101500z-req070",
        "event_id": "event.20260317t101900z-acceptance",
        "revision_id": "strat.20260317-r7",
    }
    assert set(packet["artifacts"]) == {
        "current",
        "history",
        "validators",
    }
    assert packet["planner_hook"]["mapping_complete"] is True
    assert sorted(packet["planner_hook"]["recommendation_mapping"]) == [
        "rec.dispatch-quality-first",
        "rec.peer-signal-reuse",
    ]
    dispatch_mapping = packet["planner_hook"]["recommendation_mapping"]["rec.dispatch-quality-first"]
    assert dispatch_mapping["status"] == "ready"
    assert dispatch_mapping["artifact_refs"] == [
        "reports/optimus-prime/planning/validator/strategy_packet_validation.json",
        "strategy/current/strategy_packet.context.v1.json",
        "strategy/current/strategy_packet.v1.json",
        "strategy/history/REVISION_HISTORY.json",
    ]
    assert dispatch_mapping["evidence_refs"] == [
        "Earth/peer-alpha/mission.md#L3",
        "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12",
        "Optimus-Prime-GSD-Fusion/strategy/current/strategy_packet.context.v1.json#L1",
    ]
    assert packet["open_risks"][0]["reason_code"] == "missing_earth_sweep_evidence_refs"
    assert packet["open_risks"][0]["required_evidence_refs"] == [
        "Earth/peer-beta/reports/planning/STATE.md#L6",
    ]


def test_req_070_acceptance_packet_artifact_refs_exist_in_repo() -> None:
    packet = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(_read_fixture_payload())

    for artifact_ref in packet["artifact_refs"]:
        assert (REPO_ROOT / artifact_ref).is_file(), artifact_ref
