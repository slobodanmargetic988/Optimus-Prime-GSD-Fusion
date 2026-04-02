from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_artifacts_handoff.py"
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "examples" / "fixtures" / "planner-consumability-validator.json"
SPEC = importlib.util.spec_from_file_location("strategy_artifacts_handoff", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_065_planner_consumability_validator_passes_fixture() -> None:
    payload = _load_fixture()

    report = MODULE.build_planner_consumability_validator(payload)

    assert report["artifact_type"] == "planner_consumability_validator"
    assert report["requirement_id"] == "REQ-065"
    assert report["planner_targets"] == ["op-plan", "op-initialize"]

    assert report["checks"]["required_files"] == {
        "required_files": [
            "strategy/current/samples/REQ-065_planner-consumability-validator.sample.json",
            "strategy/current/strategy_packet.v1.json",
        ],
        "available_files": [
            "contracts/req/REQ-065_planner-consumability-validator.md",
            "strategy/current/samples/REQ-065_planner-consumability-validator.sample.json",
            "strategy/current/strategy_packet.v1.json",
        ],
        "missing_required_files": [],
        "pass": True,
    }
    assert report["checks"]["required_keys"] == {
        "required_keys": [
            "identity.project_id",
            "recommendation_mapping[0].op_initialize_ref",
            "recommendation_mapping[0].op_plan_ref",
            "recommendations[0].recommendation_id",
            "strategy.summary",
        ],
        "missing_required_keys": [],
        "empty_required_keys": [],
        "pass": True,
    }
    assert report["checks"]["recommendation_mapping"] == {
        "recommendation_ids": ["rec.dispatch-quality-first"],
        "recommendations_missing_id": [],
        "mapped_recommendation_ids": ["rec.dispatch-quality-first"],
        "missing_mapping_ids": [],
        "incomplete_mappings": [],
        "required_mapping_fields": ["op_plan_ref", "op_initialize_ref"],
        "pass": True,
    }
    assert report["gate_verdict"] == {
        "verdict": "pass",
        "ready_for_planner_consumption": True,
        "blocking_reasons": [],
        "warning_reasons": [],
    }


def test_req_065_planner_consumability_validator_fails_when_checks_are_incomplete() -> None:
    payload = copy.deepcopy(_load_fixture())

    payload["available_files"] = ["strategy/current/strategy_packet.v1.json"]
    payload["required_keys"] = [
        "identity.project_id",
        "strategy.summary",
        "strategy.revision_id",
    ]
    payload["strategy_output"]["recommendations"].append(
        {
            "recommendation_id": "rec.needs-mapping",
            "summary": "Second recommendation must be mapped.",
        }
    )
    payload["strategy_output"]["recommendation_mapping"][0]["op_initialize_ref"] = ""

    report = MODULE.build_planner_consumability_validator(payload)

    assert report["checks"]["required_files"] == {
        "required_files": [
            "strategy/current/samples/REQ-065_planner-consumability-validator.sample.json",
            "strategy/current/strategy_packet.v1.json",
        ],
        "available_files": ["strategy/current/strategy_packet.v1.json"],
        "missing_required_files": [
            "strategy/current/samples/REQ-065_planner-consumability-validator.sample.json"
        ],
        "pass": False,
    }
    assert report["checks"]["required_keys"] == {
        "required_keys": [
            "identity.project_id",
            "strategy.revision_id",
            "strategy.summary",
        ],
        "missing_required_keys": ["strategy.revision_id"],
        "empty_required_keys": [],
        "pass": False,
    }
    assert report["checks"]["recommendation_mapping"] == {
        "recommendation_ids": [
            "rec.dispatch-quality-first",
            "rec.needs-mapping",
        ],
        "recommendations_missing_id": [],
        "mapped_recommendation_ids": ["rec.dispatch-quality-first"],
        "missing_mapping_ids": ["rec.needs-mapping"],
        "incomplete_mappings": [
            {
                "recommendation_id": "rec.dispatch-quality-first",
                "missing_fields": ["op_initialize_ref"],
            }
        ],
        "required_mapping_fields": ["op_plan_ref", "op_initialize_ref"],
        "pass": False,
    }
    assert report["gate_verdict"] == {
        "verdict": "fail",
        "ready_for_planner_consumption": False,
        "blocking_reasons": [
            "required_files_check_failed",
            "required_keys_check_failed",
            "recommendation_mapping_check_failed",
        ],
        "warning_reasons": [],
    }
