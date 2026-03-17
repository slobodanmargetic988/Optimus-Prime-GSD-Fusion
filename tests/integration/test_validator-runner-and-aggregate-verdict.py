import copy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module
from scripts import strategy_validators as strategy_validators_module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "validator-runner-and-aggregate-verdict.json"
PACKET_SAMPLE_PATH = REPO_ROOT / "op-tools" / "strategy" / "examples" / "strategy_packet.sample.v1.json"
CURRENT_PACKET_PATH = REPO_ROOT / "strategy" / "current" / "strategy_packet.v1.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "strategy_packet.v1.schema.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_066_integration_uses_broad_sweep_context_and_emits_processing_behavior() -> None:
    payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    payload.pop("strategy_packet_path")
    payload["strategy_packet"] = _read_json(PACKET_SAMPLE_PATH)
    payload["broad_sweep_context"] = {
        "projects_considered": [
            "earth-core-runtime",
            "earth-ops-pipeline",
            "earth-shared-observability",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/earth-ops-pipeline/planner-packet-gaps-2026-03-15.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_obligations": [
            {
                "obligation_id": "obligation-runtime-canary-alignment",
                "summary": "Coordinate runtime canary windows before widening rollout.",
                "recommendation_ids": ["rec.align-earth-runtime-canary"],
                "project_ids": ["earth-core-runtime"],
                "earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
                ],
            },
            {
                "obligation_id": "obligation-missing-earth-evidence",
                "summary": "Link reuse contract updates to cross-project ownership evidence.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "earth_sweep_evidence_refs": [],
            },
        ],
        "unresolved_ideas": [
            {
                "idea_id": "idea.reuse-ownership-followup",
                "summary": "Validate shared ownership handoff before adding new cross-project packets.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "required_earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
                ],
            }
        ],
    }

    out = module.build_req_066_validator_runner_and_aggregate_verdict(payload)

    assert module.validate_req_066_validator_runner_and_aggregate_verdict(out) == []
    assert out["ok"] is True
    assert out["verdict"] == "pass"
    assert out["blocking_reason_codes"] == []
    assert out["validator_count"] == 1
    assert out["passed_validator_count"] == 1
    assert out["failed_validator_count"] == 0

    assert out["validators"] == [
        {
            "validator_id": "strategy_packet_v1_schema_validator",
            "requirement_id": "REQ-060",
            "analysis_type": "strategy_packet_v1_schema_validator",
            "ok": True,
            "verdict": "pass",
            "blocking_reason_codes": [],
            "diagnostic_count": 0,
            "summary": "Strategy packet is planner-consumable.",
        }
    ]

    processing = out["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["cross_project_context_usage"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "evidence_refs",
        "context_project_ids",
        "mapped_recommendation_ids",
        "mapped_task_intent_handles",
        "recommendation_field_completeness",
        "approved_cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "planner_ready_with_open_risks"
    assert recommendation["rationale"] == (
        "packet_recommendations=3 mapped_recommendations=3 complete_recommendations=3 "
        "recommendations_with_evidence=3 approved=1 open_risks=2 diagnostics=0"
    )
    assert "reports/runtime/telemetry/freshness-gap-2026-03-15.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in recommendation["evidence_refs"]
    assert "missing:earth-sweep-evidence-ref" in recommendation["evidence_refs"]

    completeness_by_id = {
        row["recommendation_id"]: row for row in recommendation["recommendation_field_completeness"]
    }
    assert sorted(completeness_by_id) == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
        "rec.review-reuse-contracts",
    ]
    for row in completeness_by_id.values():
        assert row["required_fields_present"] == [
            "recommendation_id",
            "priority",
            "summary",
            "rationale",
            "expected_impact",
            "risk_level",
        ]
        assert row["missing_required_fields"] == []
        assert row["has_complete_required_fields"] is True
        assert row["has_evidence_refs"] is True
        assert row["evidence_refs"]

    assert usage == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": [
            "earth-core-runtime",
            "earth-ops-pipeline",
            "earth-shared-observability",
        ],
        "earth_sweep_evidence_refs_considered": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/earth-ops-pipeline/planner-packet-gaps-2026-03-15.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_obligation_count": 2,
        "unresolved_idea_count": 1,
        "recommendation_ids_with_context": [
            "rec.align-earth-runtime-canary",
            "rec.review-reuse-contracts",
        ],
    }


def test_req_066_integration_keeps_recommendation_field_gaps_and_open_risks_explicit() -> None:
    payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    payload.pop("strategy_packet_path")
    payload["strategy_packet"] = _read_json(PACKET_SAMPLE_PATH)
    payload["strategy_packet"]["recommendations"][2].pop("expected_impact")
    payload["broad_sweep_context"] = {
        "projects_considered": ["earth-shared-observability"],
        "earth_sweep_evidence_refs": [],
        "cross_project_obligations": [
            {
                "obligation_id": "obligation-reuse-without-evidence",
                "summary": "Promote reuse ownership work without Earth evidence.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "earth_sweep_evidence_refs": [],
            }
        ],
        "unresolved_ideas": [],
    }

    out = module.build_req_066_validator_runner_and_aggregate_verdict(payload)

    assert module.validate_req_066_validator_runner_and_aggregate_verdict(out) == []
    assert out["ok"] is False
    assert out["verdict"] == "fail"
    assert out["blocking_reason_codes"] == ["schema_required_field_missing"]
    assert out["validator_count"] == 1
    assert out["passed_validator_count"] == 0
    assert out["failed_validator_count"] == 1

    validator_row = out["validators"][0]
    assert validator_row["ok"] is False
    assert validator_row["verdict"] == "fail"
    assert validator_row["blocking_reason_codes"] == ["schema_required_field_missing"]
    assert validator_row["diagnostic_count"] == 1

    recommendation = out["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "planner_blocked"
    assert {row["source_id"]: row["reason_code"] for row in recommendation["open_risks"]} == {
        "obligation-reuse-without-evidence": "missing_earth_sweep_evidence_refs"
    }

    review_recommendation = next(
        row
        for row in recommendation["recommendation_field_completeness"]
        if row["recommendation_id"] == "rec.review-reuse-contracts"
    )
    assert review_recommendation["required_fields_present"] == [
        "recommendation_id",
        "priority",
        "summary",
        "rationale",
        "risk_level",
    ]
    assert review_recommendation["missing_required_fields"] == ["expected_impact"]
    assert review_recommendation["has_complete_required_fields"] is False
    assert review_recommendation["has_evidence_refs"] is True
    assert "missing:earth-sweep-evidence-ref" in review_recommendation["evidence_refs"]


def test_req_066_integration_keeps_packet_payload_not_object_deterministic() -> None:
    payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    payload.pop("strategy_packet_path")
    payload["strategy_packet"] = ["not", "an", "object"]

    out = module.build_req_066_validator_runner_and_aggregate_verdict(payload)

    assert module.validate_req_066_validator_runner_and_aggregate_verdict(out) == []
    assert out == {
        "requirement_id": "REQ-066",
        "analysis_type": "validator_runner_and_aggregate_verdict",
        "checked_at_utc": "2026-03-16T11:00:00Z",
        "ok": False,
        "verdict": "fail",
        "blocking_reason_codes": ["packet_payload_not_object"],
        "validator_count": 1,
        "passed_validator_count": 0,
        "failed_validator_count": 1,
        "summary": "1 of 1 validators reported blocking failures.",
        "validators": [
            {
                "validator_id": "strategy_packet_v1_schema_validator",
                "requirement_id": "REQ-060",
                "analysis_type": "strategy_packet_v1_schema_validator",
                "ok": False,
                "verdict": "fail",
                "blocking_reason_codes": ["packet_payload_not_object"],
                "diagnostic_count": 1,
                "summary": "Strategy packet is not planner-consumable; packet JSON root must be an object.",
            }
        ],
    }


def test_strategy_validators_runner_emits_req_066_aggregate_verdict_for_current_packet() -> None:
    out = strategy_validators_module.run_strategy_packet_validator_runner_files(
        input_path=CURRENT_PACKET_PATH,
        schema_path=SCHEMA_PATH,
    )

    assert out["requirement_id"] == "REQ-066"
    assert out["analysis_type"] == "validator_runner_and_aggregate_verdict"
    assert out["ok"] is True
    assert out["verdict"] == "pass"
    assert out["planner_consumability"] == "planner_ready"
    assert out["blocking_reason_codes"] == []
    assert out["validator_count"] == 1
    assert out["passed_validator_count"] == 1
    assert out["failed_validator_count"] == 0
    assert out["diagnostic_count"] == 0
    assert out["diagnostics"] == []

    assert out["validators"] == [
        {
            "validator_id": "strategy_packet_v1_schema_validator",
            "requirement_id": "REQ-060",
            "analysis_type": "strategy_packet_v1_schema_validator",
            "ok": True,
            "verdict": "pass",
            "blocking_reason_codes": [],
            "diagnostic_count": 0,
            "summary": "Strategy packet is planner-consumable.",
            "diagnostics": [],
        }
    ]


def test_strategy_validators_runner_surfaces_deterministic_field_paths_and_severity_for_invalid_packets(
    tmp_path: Path,
) -> None:
    broken_packet = _read_json(PACKET_SAMPLE_PATH)
    broken_packet["recommendation_to_planner_mapping_artifact"]["recommendation_to_task_intent_mappings"] = [
        row
        for row in broken_packet["recommendation_to_planner_mapping_artifact"]["recommendation_to_task_intent_mappings"]
        if row["recommendation_id"] != "rec.review-reuse-contracts"
    ]
    broken_packet["recommendation_to_planner_mapping_artifact"]["recommendation_ids"] = [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
    ]

    packet_path = tmp_path / "broken.packet.json"
    packet_path.write_text(json.dumps(broken_packet), encoding="utf-8")

    out = strategy_validators_module.run_strategy_packet_validator_runner_files(
        input_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert out["ok"] is False
    assert out["verdict"] == "fail"
    assert out["planner_consumability"] == "planner_blocked"
    assert out["blocking_reason_codes"] == [
        "mapping_artifact_recommendation_ids_mismatch",
        "packet_recommendation_missing_mapping",
        "req_054_contract_violation",
    ]
    assert out["validator_count"] == 1
    assert out["passed_validator_count"] == 0
    assert out["failed_validator_count"] == 1
    assert out["diagnostic_count"] == 3
    assert len(out["diagnostics"]) == 3

    validator_row = out["validators"][0]
    assert validator_row["ok"] is False
    assert validator_row["verdict"] == "fail"
    assert validator_row["blocking_reason_codes"] == [
        "mapping_artifact_recommendation_ids_mismatch",
        "packet_recommendation_missing_mapping",
        "req_054_contract_violation",
    ]
    assert validator_row["diagnostic_count"] == 3

    diagnostics_by_reason = {row["reason_code"]: row for row in validator_row["diagnostics"]}
    assert diagnostics_by_reason["mapping_artifact_recommendation_ids_mismatch"]["severity"] == "error"
    assert diagnostics_by_reason["mapping_artifact_recommendation_ids_mismatch"]["field_path"] == (
        "recommendation_to_planner_mapping_artifact.recommendation_ids"
    )
    assert diagnostics_by_reason["packet_recommendation_missing_mapping"]["severity"] == "error"
    assert diagnostics_by_reason["packet_recommendation_missing_mapping"]["field_path"] == (
        "recommendations[2].recommendation_id"
    )
    assert diagnostics_by_reason["req_054_contract_violation"]["severity"] == "error"
    assert diagnostics_by_reason["req_054_contract_violation"]["field_path"] == (
        "recommendation_to_planner_mapping_artifact.planner_task_intent_handles"
    )
