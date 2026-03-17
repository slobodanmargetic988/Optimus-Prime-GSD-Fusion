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


def test_acceptance_packet_is_planner_consumable_and_uses_broad_sweep_context() -> None:
    packet = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(_read_fixture_payload())

    assert packet["artifact_type"] == "end_to_end_autonomous_strategy_acceptance_packet"
    assert packet["artifact_refs"] == [
        "reports/optimus-prime/planning/validator/strategy_packet_validation.json",
        "strategy/current/strategy_packet.v1.json",
        "strategy/history/REVISION_HISTORY.json",
    ]
    assert packet["recommendation_field_completeness"]["missing_by_recommendation"] == {}
    assert packet["planner_hook"] == {
        "recommendation_ids": [
            "rec.dispatch-quality-first",
            "rec.peer-signal-reuse",
        ],
        "mapped_recommendation_ids": [
            "rec.dispatch-quality-first",
            "rec.peer-signal-reuse",
        ],
        "missing_recommendation_ids": [],
        "mapping_complete": True,
        "sources_used": [
            "generated_from_recommendations",
            "planner_hook.recommendation_readiness",
        ],
        "recommendation_mapping": {
            "rec.dispatch-quality-first": {
                "recommendation_id": "rec.dispatch-quality-first",
                "recommendation_key": "dispatch-quality-first",
                "status": "ready",
                "priority": "high",
                "summary": "Keep dispatch quality first in the autonomous lane.",
                "artifact_refs": [
                    "reports/optimus-prime/planning/validator/strategy_packet_validation.json",
                    "strategy/current/strategy_packet.context.v1.json",
                    "strategy/current/strategy_packet.v1.json",
                    "strategy/history/REVISION_HISTORY.json",
                ],
                "evidence_refs": [
                    "Earth/peer-alpha/mission.md#L3",
                    "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12",
                    "Optimus-Prime-GSD-Fusion/strategy/current/strategy_packet.context.v1.json#L1",
                ],
            },
            "rec.peer-signal-reuse": {
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
            },
        },
        "evidence_refs": [
            "Earth/peer-alpha/mission.md#L3",
            "Earth/peer-beta/reports/planning/ROADMAP.md#L9",
            "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12",
            "Optimus-Prime-GSD-Fusion/strategy/current/strategy_packet.context.v1.json#L1",
        ],
    }
    assert packet["cross_project_context"] == {
        "target_project_id": "prj.optimus-prime",
        "project_ids": [
            "prj.optimus-prime",
            "prj.peer-alpha",
            "prj.peer-beta",
            "prj.peer-gamma",
        ],
        "peer_project_ids": [
            "prj.peer-alpha",
            "prj.peer-beta",
            "prj.peer-gamma",
        ],
        "project_count": 4,
        "peer_project_count": 3,
        "used_in_quality_report": True,
        "context_sources_used": [
            "broad_sweep",
            "cross_project_context",
            "earth_sweep",
        ],
        "evidence_refs": [
            "Earth/peer-alpha/reports/planning/PROJECT.md#L4",
            "Earth/peer-alpha/reports/planning/RISK_REGISTER.json#L2",
            "Earth/peer-beta/reports/planning/STATE.md#L6",
            "Earth/peer-gamma/reports/planning/ROADMAP.md#L8",
        ],
        "used_in_acceptance_packet": True,
    }
    assert packet["evidence_refs"] == sorted(
        [
            "Earth/peer-alpha/mission.md#L3",
            "Earth/peer-alpha/reports/planning/PROJECT.md#L4",
            "Earth/peer-alpha/reports/planning/RISK_REGISTER.json#L2",
            "Earth/peer-beta/reports/planning/ROADMAP.md#L9",
            "Earth/peer-beta/reports/planning/STATE.md#L6",
            "Earth/peer-gamma/reports/planning/ROADMAP.md#L8",
            "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12",
            "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/validator/strategy_packet_validation.json#L1",
            "Optimus-Prime-GSD-Fusion/strategy/current/strategy_packet.context.v1.json#L1",
            "Optimus-Prime-GSD-Fusion/strategy/current/strategy_packet.v1.json#L1",
            "Optimus-Prime-GSD-Fusion/strategy/history/REVISION_HISTORY.json#L1",
        ]
    )
    assert packet["open_risks"] == [
        {
            "risk_id": "risk.unsupported-cross-project-obligation.001",
            "severity": "medium",
            "category": "open_risk",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "summary": "Cross-project obligation for prj.peer-beta has no Earth-sweep evidence refs.",
            "project_id": "prj.peer-beta",
            "linked_recommendation_ids": [
                "rec.peer-signal-reuse",
            ],
            "evidence_refs": [
                "Earth/peer-beta/reports/planning/STATE.md#L6",
            ],
            "required_evidence_refs": [
                "Earth/peer-beta/reports/planning/STATE.md#L6",
            ],
            "recommendation": "Keep this as an open risk until Earth-sweep evidence refs exist.",
        }
    ]
    assert packet["consumability_verdict"] == {
        "verdict": "pass",
        "planner_consumable": True,
        "ecosystem_aware": True,
        "artifacts_complete": True,
        "citation_coverage_pass": True,
        "recommendation_fields_pass": True,
        "contradiction_pass": True,
        "ready_for_autonomous_planning": True,
        "missing_artifact_groups": [],
        "blocking_reasons": [],
        "warning_reasons": ["open_risks_present"],
    }


def test_acceptance_packet_fails_when_recommendations_or_cross_project_context_are_incomplete() -> None:
    payload = _read_fixture_payload()
    payload["recommendations"] = [payload["recommendations"][0]]
    payload["recommendations"][0].pop("priority")
    payload["earth_sweep"] = {"projects": [{"project_id": "prj.optimus-prime"}]}
    payload["broad_sweep"] = {"projects": []}
    payload["cross_project_context"] = []
    payload["obligations"] = []

    packet = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(payload)

    assert packet["recommendation_field_completeness"]["missing_by_recommendation"] == {
        "rec.dispatch-quality-first": ["priority"]
    }
    assert packet["planner_hook"]["recommendation_ids"] == ["rec.dispatch-quality-first"]
    assert packet["planner_hook"]["mapped_recommendation_ids"] == ["rec.dispatch-quality-first"]
    assert packet["planner_hook"]["missing_recommendation_ids"] == []
    assert packet["planner_hook"]["mapping_complete"] is True
    assert packet["cross_project_context"]["peer_project_ids"] == []
    assert packet["cross_project_context"]["used_in_acceptance_packet"] is False
    assert packet["open_risks"] == []
    assert packet["consumability_verdict"] == {
        "verdict": "fail",
        "planner_consumable": False,
        "ecosystem_aware": False,
        "artifacts_complete": True,
        "citation_coverage_pass": True,
        "recommendation_fields_pass": False,
        "contradiction_pass": True,
        "ready_for_autonomous_planning": False,
        "missing_artifact_groups": [],
        "blocking_reasons": [
            "incomplete_recommendations",
            "missing_cross_project_context",
        ],
        "warning_reasons": [],
    }
