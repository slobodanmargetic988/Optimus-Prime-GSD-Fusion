from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_MODULE_PATH = ROOT / "scripts" / "strategy_artifacts_handoff.py"
VALIDATORS_MODULE_PATH = ROOT / "scripts" / "strategy_validators.py"
SCHEMA_PATH = ROOT / "contracts" / "strategy_packet.v1.schema.json"
STRATEGY_PACKET_SAMPLE_PATH = ROOT / "examples" / "strategy_packet.sample.v1.json"

ARTIFACTS_SPEC = importlib.util.spec_from_file_location("strategy_artifacts_handoff", ARTIFACTS_MODULE_PATH)
ARTIFACTS_MODULE = importlib.util.module_from_spec(ARTIFACTS_SPEC)
assert ARTIFACTS_SPEC is not None and ARTIFACTS_SPEC.loader is not None
sys.modules[ARTIFACTS_SPEC.name] = ARTIFACTS_MODULE
ARTIFACTS_SPEC.loader.exec_module(ARTIFACTS_MODULE)

VALIDATORS_SPEC = importlib.util.spec_from_file_location("strategy_validators", VALIDATORS_MODULE_PATH)
VALIDATORS_MODULE = importlib.util.module_from_spec(VALIDATORS_SPEC)
assert VALIDATORS_SPEC is not None and VALIDATORS_SPEC.loader is not None
sys.modules[VALIDATORS_SPEC.name] = VALIDATORS_MODULE
VALIDATORS_SPEC.loader.exec_module(VALIDATORS_MODULE)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_req_065_payload() -> dict[str, object]:
    return {
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
            "strategy": {"summary": "Keep planner inputs consumable without manual transforms."},
            "recommendations": [
                {
                    "recommendation_id": "rec.planner-ready",
                    "priority": "high",
                    "summary": "Preserve deterministic recommendation handoff shape.",
                    "rationale": "Stable references prevent planner-side patching.",
                    "expected_impact": "Higher replayability for op-plan and op-initialize.",
                    "risk_level": "low",
                    "evidence_refs": [
                        "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json#L1"
                    ],
                }
            ],
            "recommendation_mapping": [
                {
                    "recommendation_id": "rec.planner-ready",
                    "op_plan_ref": "op-plan.input.recommendations[rec.planner-ready]",
                    "op_initialize_ref": "op-initialize.input.recommendations[rec.planner-ready]",
                }
            ],
        },
    }


def test_req_065_hardening_invalid_strategy_packet_schema_row_rejected_with_deterministic_diagnostics() -> None:
    strategy_packet = _load_json(STRATEGY_PACKET_SAMPLE_PATH)
    strategy_packet["recommendations"][0]["priority"] = "urgent"
    schema = _load_json(SCHEMA_PATH)

    result = VALIDATORS_MODULE.validate_strategy_packet_payload(strategy_packet, schema)

    assert result["ok"] is False
    assert result["summary"] == {
        "diagnostic_count": 1,
        "error_count": 1,
        "warning_count": 0,
    }
    assert result["diagnostics"] == [
        {
            "severity": "error",
            "reason_code": "schema.enum",
            "field_path": "recommendations[0].priority",
            "message": "'urgent' is not one of ['high', 'medium', 'low']",
        }
    ]


def test_req_065_hardening_duplicate_recommendation_id_collision_flagged_with_diff_details() -> None:
    payload = copy.deepcopy(_valid_req_065_payload())
    payload["strategy_output"]["recommendations"] = [
        {
            "recommendation_id": "rec.planner-ready",
            "priority": "high",
            "summary": "Use deterministic recommendation IDs across planner ingest.",
            "rationale": "Direct op-plan/op-initialize mapping requires stable IDs.",
            "expected_impact": "No manual transforms after strategy output emission.",
            "risk_level": "low",
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json#L10"
            ],
        },
        {
            "recommendation_id": "rec.planner-ready",
            "priority": "high",
            "summary": "Use deterministic recommendation IDs across planner replay.",
            "rationale": "Direct op-plan/op-initialize mapping requires stable IDs.",
            "expected_impact": "No manual transforms after strategy output replay.",
            "risk_level": "low",
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json#L11"
            ],
        },
    ]

    report = ARTIFACTS_MODULE.build_planner_consumability_validator(payload)

    assert report["checks"]["recommendation_id_collisions"] == {
        "reason_code": "req065.duplicate_recommendation_id_collision",
        "collisions": [
            {
                "recommendation_id": "rec.planner-ready",
                "reason_code": "req065.duplicate_recommendation_id_collision",
                "duplicate_count": 2,
                "occurrence_refs": [
                    "recommendations[0]",
                    "recommendations[1]",
                ],
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json#L10",
                    "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json#L11",
                ],
                "diff_details": [
                    {
                        "left_ref": "recommendations[0]",
                        "right_ref": "recommendations[1]",
                        "field_diffs": [
                            {
                                "field": "evidence_refs",
                                "left_value": [
                                    "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json#L10"
                                ],
                                "right_value": [
                                    "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json#L11"
                                ],
                            },
                            {
                                "field": "expected_impact",
                                "left_value": "No manual transforms after strategy output emission.",
                                "right_value": "No manual transforms after strategy output replay.",
                            },
                            {
                                "field": "summary",
                                "left_value": "Use deterministic recommendation IDs across planner ingest.",
                                "right_value": "Use deterministic recommendation IDs across planner replay.",
                            },
                        ],
                    }
                ],
            }
        ],
        "pass": False,
    }
    assert report["gate_verdict"] == {
        "verdict": "fail",
        "ready_for_planner_consumption": False,
        "blocking_reasons": ["recommendation_id_collision_check_failed"],
        "warning_reasons": [],
    }


def test_req_065_hardening_broken_evidence_reference_causes_traceability_gate_failure() -> None:
    payload = copy.deepcopy(_valid_req_065_payload())
    payload["strategy_output"]["recommendations"][0]["evidence_refs"] = [
        "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json"
    ]

    report = ARTIFACTS_MODULE.build_planner_consumability_validator(payload)

    assert report["checks"]["traceability"] == {
        "reason_code": "req065.traceability.invalid_evidence_ref",
        "checked_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json"
        ],
        "invalid_evidence_refs": [
            {
                "recommendation_ref": "rec.planner-ready",
                "recommendation_id": "rec.planner-ready",
                "evidence_ref": "reports/optimus-prime/planning/evidence/TASK-239/TASK_EVIDENCE.json",
                "reason_code": "req065.traceability.invalid_evidence_ref",
            }
        ],
        "pass": False,
    }
    assert report["gate_verdict"] == {
        "verdict": "fail",
        "ready_for_planner_consumption": False,
        "blocking_reasons": ["traceability_check_failed"],
        "warning_reasons": [],
    }
