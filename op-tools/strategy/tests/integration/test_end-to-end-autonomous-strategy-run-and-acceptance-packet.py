from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_artifacts_handoff.py"
SPEC = importlib.util.spec_from_file_location("strategy_artifacts_handoff", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_acceptance_packet_is_planner_consumable_and_uses_broad_sweep_context() -> None:
    payload = {
        "identity": {
            "project_id": "prj.optimus-prime",
            "run_id": "run.20260317t101500z-req070",
            "event_id": "event.20260317t101900z-acceptance",
        },
        "strategy": {
            "revision_id": "strat.20260317-r7",
        },
        "recommendations": [
            {
                "recommendation_id": "rec.dispatch-quality-first",
                "priority": "high",
                "summary": "Keep dispatch quality first in the autonomous lane.",
                "rationale": "This preserves planner trust in each run output.",
                "expected_impact": "Lower invalid handoff churn.",
                "risk_level": "medium",
                "confidence": "high",
                "evidence_refs": [
                    "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12",
                    "Earth/peer-alpha/mission.md#L3",
                ],
            },
            {
                "recommendation_id": "rec.peer-signal-reuse",
                "priority": "medium",
                "summary": "Reuse peer planning signals during the autonomous sweep.",
                "rationale": "Broad-sweep context reduces duplicate solution hunting.",
                "expected_impact": "Faster planner-ready synthesis.",
                "risk_level": "low",
                "confidence": "medium",
            },
        ],
        "evidence_provenance": [
            {
                "recommendation_id": "rec.peer-signal-reuse",
                "evidence_refs": [
                    "Earth/peer-beta/reports/planning/ROADMAP.md#L9",
                ],
            }
        ],
        "earth_sweep": {
            "projects": [
                {"project_id": "prj.optimus-prime"},
                {
                    "project_id": "prj.peer-alpha",
                    "evidence_refs": ["Earth/peer-alpha/reports/planning/PROJECT.md#L4"],
                },
                {
                    "project_id": "prj.peer-beta",
                    "evidence_refs": ["Earth/peer-beta/reports/planning/STATE.md#L6"],
                },
            ]
        },
        "broad_sweep": {
            "projects": [
                {
                    "project_id": "prj.peer-gamma",
                    "evidence_refs": ["Earth/peer-gamma/reports/planning/ROADMAP.md#L8"],
                }
            ]
        },
        "cross_project_context": [
            {
                "project_id": "prj.peer-alpha",
                "summary": "Peer alpha exposes stable contract signals.",
                "evidence_refs": ["Earth/peer-alpha/reports/planning/RISK_REGISTER.json#L2"],
            }
        ],
        "current_artifacts": [
            {
                "artifact_id": "current.strategy-packet",
                "artifact_ref": "strategy/current/strategy_packet.v1.json",
                "evidence_refs": ["Optimus-Prime-GSD-Fusion/strategy/current/strategy_packet.v1.json#L1"],
            }
        ],
        "history_artifacts": [
            {
                "artifact_id": "history.revision-log",
                "artifact_ref": "strategy/history/REVISION_HISTORY.json",
                "evidence_refs": ["Optimus-Prime-GSD-Fusion/strategy/history/REVISION_HISTORY.json#L1"],
            }
        ],
        "validator_artifacts": [
            {
                "artifact_id": "validator.packet",
                "artifact_ref": "reports/optimus-prime/planning/validator/strategy_packet_validation.json",
                "evidence_refs": [
                    "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/validator/strategy_packet_validation.json#L1"
                ],
            }
        ],
        "obligations": [
            {
                "project_id": "prj.peer-beta",
                "summary": "Consider a shared taxonomy sync with peer beta.",
            }
        ],
    }

    packet = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(payload)

    assert packet["artifact_type"] == "end_to_end_autonomous_strategy_acceptance_packet"
    assert packet["artifact_refs"] == [
        "reports/optimus-prime/planning/validator/strategy_packet_validation.json",
        "strategy/current/strategy_packet.v1.json",
        "strategy/history/REVISION_HISTORY.json",
    ]
    assert packet["recommendation_field_completeness"]["missing_by_recommendation"] == {}
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
            "Optimus-Prime-GSD-Fusion/strategy/current/strategy_packet.v1.json#L1",
            "Optimus-Prime-GSD-Fusion/strategy/history/REVISION_HISTORY.json#L1",
        ]
    )
    assert packet["open_risks"] == [
        {
            "risk_id": "risk.unsupported-cross-project-obligation.001",
            "severity": "medium",
            "category": "open_risk",
            "summary": "Cross-project obligation for prj.peer-beta has no Earth-sweep evidence refs.",
            "project_id": "prj.peer-beta",
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
    payload = {
        "identity": {
            "project_id": "prj.optimus-prime",
            "run_id": "run.20260317t111500z-req070",
            "event_id": "event.20260317t111900z-acceptance",
        },
        "recommendations": [
            {
                "recommendation_id": "rec.dispatch-quality-first",
                "summary": "Keep dispatch quality first in the autonomous lane.",
                "rationale": "Planner trust depends on explicit outputs.",
                "expected_impact": "Lower invalid handoff churn.",
                "risk_level": "medium",
                "evidence_refs": [
                    "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12"
                ],
            }
        ],
        "earth_sweep": {
            "projects": [
                {"project_id": "prj.optimus-prime"},
            ]
        },
        "current_artifacts": [
            "strategy/current/strategy_packet.v1.json",
        ],
        "history_artifacts": [
            "strategy/history/REVISION_HISTORY.json",
        ],
        "validator_artifacts": [
            "reports/optimus-prime/planning/validator/strategy_packet_validation.json",
        ],
    }

    packet = MODULE.build_end_to_end_autonomous_strategy_acceptance_packet(payload)

    assert packet["recommendation_field_completeness"]["missing_by_recommendation"] == {
        "rec.dispatch-quality-first": ["priority"]
    }
    assert packet["cross_project_context"]["peer_project_ids"] == []
    assert packet["cross_project_context"]["used_in_acceptance_packet"] is False
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
