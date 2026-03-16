from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_artifacts_handoff.py"
SPEC = importlib.util.spec_from_file_location("strategy_artifacts_handoff", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_quality_report_captures_evidence_refs_and_cross_project_context() -> None:
    payload = {
        "project_id": "prj.optimus-prime",
        "recommendations": [
            {
                "recommendation_id": "rec.dispatch-quality-first",
                "priority": "high",
                "summary": "Prioritize dispatch quality controls.",
                "rationale": "This reduces idle cycles.",
                "expected_impact": "Higher throughput.",
                "risk_level": "medium",
                "confidence": "high",
                "evidence_refs": [
                    "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12",
                    "Earth/peer-alpha/mission.md#L3",
                ],
            },
            {
                "recommendation_id": "rec.ecosystem-linkage",
                "priority": "medium",
                "summary": "Reuse peer lane signals.",
                "rationale": "Peer telemetry exposes reusable patterns.",
                "expected_impact": "Lower duplicated work.",
                "risk_level": "low",
                "confidence": "medium",
            },
        ],
        "evidence_provenance": [
            {
                "recommendation_id": "rec.ecosystem-linkage",
                "evidence_refs": [
                    "Earth/peer-beta/reports/planning/ROADMAP.md#L9",
                    "Earth/peer-gamma/reports/planning/PROJECT.md#L2",
                ],
            }
        ],
        "earth_sweep": {
            "projects": [
                {"project_id": "prj.optimus-prime"},
                {"project_id": "prj.peer-alpha"},
                {"project_id": "prj.peer-beta"},
                {"project_id": "prj.peer-gamma"},
            ]
        },
        "contradictions": [
            {
                "contradiction_id": "contradiction-001",
                "status": "resolved",
                "summary": "Peer dependency concern resolved.",
                "evidence_refs": ["Earth/peer-beta/reports/planning/RISK_REGISTER.json#L1"],
            }
        ],
    }

    report = MODULE.build_strategy_quality_report(payload)

    assert report["artifact_type"] == "strategy_quality_report"
    assert report["citation_coverage"]["coverage_ratio"] == 1.0
    assert report["evidence_refs"] == sorted(
        [
            "Earth/peer-alpha/mission.md#L3",
            "Earth/peer-beta/reports/planning/RISK_REGISTER.json#L1",
            "Earth/peer-beta/reports/planning/ROADMAP.md#L9",
            "Earth/peer-gamma/reports/planning/PROJECT.md#L2",
            "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12",
        ]
    )
    assert report["recommendation_field_completeness"]["missing_by_recommendation"] == {}
    assert report["cross_project_context"]["peer_project_ids"] == [
        "prj.peer-alpha",
        "prj.peer-beta",
        "prj.peer-gamma",
    ]
    assert report["cross_project_context"]["used_in_quality_report"] is True
    assert report["gate_verdict"] == {
        "verdict": "pass",
        "ready_for_build": True,
        "citation_coverage_pass": True,
        "contradiction_pass": True,
        "recommendation_fields_pass": True,
        "cross_project_context_pass": True,
        "blocking_reasons": [],
        "warning_reasons": [],
    }


def test_quality_report_records_unsupported_cross_project_obligations_as_open_risks() -> None:
    payload = {
        "project_id": "prj.optimus-prime",
        "recommendations": [
            {
                "recommendation_id": "rec.quality-report",
                "priority": "high",
                "summary": "Add quality gating.",
                "rationale": "Build automation needs deterministic gates.",
                "expected_impact": "Safer planner handoff.",
                "risk_level": "low",
                "evidence_refs": ["Optimus-Prime-GSD-Fusion/contracts/strategy_packet.v1.schema.json#L1"],
            }
        ],
        "earth_sweep": {
            "projects": [
                {"project_id": "prj.optimus-prime"},
                {"project_id": "prj.peer-alpha"},
            ]
        },
        "obligations": [
            {
                "project_id": "prj.peer-alpha",
                "summary": "Must add a peer-side contract change.",
            }
        ],
    }

    report = MODULE.build_strategy_quality_report(payload)

    assert report["open_risks"] == [
        {
            "risk_id": "risk.unsupported-cross-project-obligation.001",
            "severity": "medium",
            "category": "open_risk",
            "summary": "Cross-project obligation for prj.peer-alpha has no Earth-sweep evidence refs.",
            "project_id": "prj.peer-alpha",
            "recommendation": "Keep this as an open risk until Earth-sweep evidence refs exist.",
        }
    ]
    assert report["gate_verdict"]["verdict"] == "fail"
    assert report["gate_verdict"]["blocking_reasons"] == [
        "unsupported_cross_project_obligations"
    ]
