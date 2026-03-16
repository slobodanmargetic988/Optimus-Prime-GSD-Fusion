from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_artifacts_handoff.py"
SPEC = importlib.util.spec_from_file_location("strategy_artifacts_handoff", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_planner_consumability_validator_captures_evidence_and_context_usage() -> None:
    payload = {
        "project_id": "prj.optimus-prime",
        "required_files": [
            "strategy/current/strategy_packet.v1.json",
            "strategy/current/samples/REQ-065_planner-consumability-validator.sample.json",
        ],
        "available_files": [
            "contracts/req/REQ-065_planner-consumability-validator.md",
            "strategy/current/samples/REQ-065_planner-consumability-validator.sample.json",
            "strategy/current/strategy_packet.v1.json",
        ],
        "required_keys": [
            "identity.project_id",
            "strategy.summary",
            "recommendations[0].recommendation_id",
            "recommendation_mapping[0].op_plan_ref",
            "recommendation_mapping[0].op_initialize_ref",
        ],
        "strategy_output": {
            "identity": {"project_id": "prj.optimus-prime"},
            "strategy": {"summary": "Validate planner intake fields without manual transforms."},
            "recommendations": [
                {
                    "recommendation_id": "rec.dispatch-quality-first",
                    "priority": "high",
                    "summary": "Prioritize deterministic planner handoff mapping.",
                    "rationale": "Stable references keep op-plan and op-initialize deterministic.",
                    "expected_impact": "Removes manual transforms during planner intake.",
                    "risk_level": "low",
                    "evidence_refs": [
                        "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12"
                    ],
                },
                {
                    "recommendation_id": "rec.ecosystem-join",
                    "priority": "medium",
                    "summary": "Incorporate broad-sweep project signals.",
                    "rationale": "Peer project state influences intake sequencing.",
                    "expected_impact": "Improves planner ordering across lanes.",
                    "risk_level": "medium",
                },
            ],
            "recommendation_mapping": [
                {
                    "recommendation_id": "rec.dispatch-quality-first",
                    "op_plan_ref": "op-plan.input.recommendations[rec.dispatch-quality-first]",
                    "op_initialize_ref": "op-initialize.input.recommendations[rec.dispatch-quality-first]",
                },
                {
                    "recommendation_id": "rec.ecosystem-join",
                    "op_plan_ref": "op-plan.input.recommendations[rec.ecosystem-join]",
                    "op_initialize_ref": "op-initialize.input.recommendations[rec.ecosystem-join]",
                },
            ],
        },
        "evidence_provenance": [
            {
                "recommendation_id": "rec.ecosystem-join",
                "evidence_refs": [
                    "Earth/peer-alpha/reports/planning/PROJECT.md#L4",
                    "Earth/peer-beta/reports/planning/ROADMAP.md#L9",
                ],
            }
        ],
        "broad_sweep": {
            "projects": [
                {"project_id": "prj.optimus-prime"},
                {"project_id": "prj.peer-alpha"},
                {"project_id": "prj.peer-beta"},
            ]
        },
    }

    report = MODULE.build_planner_consumability_validator(payload)

    assert report["artifact_type"] == "planner_consumability_validator"
    assert report["requirement_id"] == "REQ-065"
    assert report["checks"]["required_files"]["pass"] is True
    assert report["checks"]["required_keys"]["pass"] is True
    assert report["checks"]["recommendation_mapping"]["pass"] is True

    assert report["evidence_refs"] == [
        "Earth/peer-alpha/reports/planning/PROJECT.md#L4",
        "Earth/peer-beta/reports/planning/ROADMAP.md#L9",
        "Optimus-Prime-GSD-Fusion/reports/optimus-prime/planning/STATE.md#L12",
    ]
    assert report["citation_coverage"] == {
        "recommendations_total": 2,
        "recommendations_with_evidence_refs": 2,
        "coverage_ratio": 1.0,
        "missing_recommendation_ids": [],
        "pass": True,
    }
    assert report["recommendation_field_completeness"] == {
        "required_fields": [
            "recommendation_id",
            "priority",
            "summary",
            "rationale",
            "expected_impact",
            "risk_level",
        ],
        "complete_recommendations": 2,
        "incomplete_recommendations": 0,
        "missing_by_recommendation": {},
        "pass": True,
    }
    assert report["cross_project_context"] == {
        "target_project_id": "prj.optimus-prime",
        "project_ids": ["prj.optimus-prime", "prj.peer-alpha", "prj.peer-beta"],
        "peer_project_ids": ["prj.peer-alpha", "prj.peer-beta"],
        "project_count": 3,
        "peer_project_count": 2,
        "used_in_validator": True,
        "pass": True,
    }
    assert report["open_risks"] == []
    assert report["gate_verdict"] == {
        "verdict": "pass",
        "ready_for_planner_consumption": True,
        "blocking_reasons": [],
        "warning_reasons": [],
    }


def test_planner_consumability_validator_records_unsupported_obligations_as_open_risks() -> None:
    payload = {
        "project_id": "prj.optimus-prime",
        "required_files": ["strategy/current/strategy_packet.v1.json"],
        "available_files": ["strategy/current/strategy_packet.v1.json"],
        "required_keys": [
            "identity.project_id",
            "recommendations[0].recommendation_id",
            "recommendation_mapping[0].op_plan_ref",
            "recommendation_mapping[0].op_initialize_ref",
        ],
        "strategy_output": {
            "identity": {"project_id": "prj.optimus-prime"},
            "recommendations": [
                {
                    "recommendation_id": "rec.single",
                    "priority": "high",
                    "summary": "Keep planner references deterministic.",
                    "rationale": "Planner contracts require stable references.",
                    "expected_impact": "Prevents manual intake transforms.",
                    "risk_level": "low",
                    "evidence_refs": ["Optimus-Prime-GSD-Fusion/contracts/strategy_packet.v1.schema.json#L1"],
                }
            ],
            "recommendation_mapping": [
                {
                    "recommendation_id": "rec.single",
                    "op_plan_ref": "op-plan.input.recommendations[rec.single]",
                    "op_initialize_ref": "op-initialize.input.recommendations[rec.single]",
                }
            ],
        },
        "earth_sweep": {
            "projects": [
                {"project_id": "prj.optimus-prime"},
                {"project_id": "prj.peer-alpha"},
            ]
        },
        "obligations": [
            {
                "project_id": "prj.peer-alpha",
                "summary": "Requires peer-side update but evidence refs are not available yet.",
            }
        ],
    }

    report = MODULE.build_planner_consumability_validator(payload)

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
    assert report["cross_project_context"]["used_in_validator"] is True
    assert report["checks"]["required_files"]["pass"] is True
    assert report["checks"]["required_keys"]["pass"] is True
    assert report["checks"]["recommendation_mapping"]["pass"] is True
    assert report["gate_verdict"]["verdict"] == "pass"
