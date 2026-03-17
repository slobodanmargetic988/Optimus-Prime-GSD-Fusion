from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-061_recommendation-quality-validator.sample.json"
)


def _sample_payload() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def _diagnostics(errors: list[str]) -> list[dict]:
    diagnostics: list[dict] = []
    for row in errors:
        if " diagnostic " not in row:
            continue
        _, payload = row.split(" diagnostic ", 1)
        diagnostics.append(json.loads(payload))
    return diagnostics


def test_req061_hardening_invalid_strategy_packet_schema_row_rejected_with_deterministic_diagnostics() -> None:
    payload = _sample_payload()
    payload["processing_behavior"]["recommendation"]["recommended_actions"][0]["sequence_hint"] = 0

    first = module.validate_req_061_recommendation_quality_validator(payload)
    second = module.validate_req_061_recommendation_quality_validator(deepcopy(payload))

    assert first == second
    assert (
        "processing_behavior.recommendation.recommended_actions[0].sequence_hint must be a positive integer"
        in first
    )

    diagnostics = _diagnostics(first)
    schema_rows = [
        row
        for row in diagnostics
        if row["reason_code"] == module._REQ_061_REASON_CODE_STRATEGY_PACKET_SCHEMA_ROW_INVALID
    ]
    assert schema_rows == [
        {
            "reason_code": "strategy_packet_schema_row_invalid",
            "message": "strategy packet schema row rejected by deterministic validation gate",
            "evidence_refs": [
                "processing_behavior.recommendation.recommended_actions[0]"
            ],
            "diff_details": {
                "issue_types": "invalid_sequence_hint"
            },
        }
    ]


def test_req061_hardening_duplicate_recommendation_id_collision_reports_diff_details() -> None:
    payload = _sample_payload()
    payload["quality_validation"]["blocked_recommendations"][0]["recommendation_id"] = (
        payload["quality_validation"]["accepted_recommendations"][0]["recommendation_id"]
    )

    first = module.validate_req_061_recommendation_quality_validator(payload)
    second = module.validate_req_061_recommendation_quality_validator(deepcopy(payload))

    assert first == second
    assert "quality_validation recommendation_id values must be unique across accepted and blocked rows" in first

    diagnostics = _diagnostics(first)
    collision_rows = [
        row
        for row in diagnostics
        if row["reason_code"] == module._REQ_061_REASON_CODE_DUPLICATE_RECOMMENDATION_ID_COLLISION
    ]
    assert collision_rows == [
        {
            "reason_code": "duplicate_recommendation_id_collision",
            "message": "duplicate recommendation_id collision detected across quality buckets",
            "evidence_refs": [
                "quality_validation.accepted_recommendations[0]",
                "quality_validation.blocked_recommendations[0]",
            ],
            "diff_details": {
                "first_seen": "quality_validation.accepted_recommendations[0]",
                "duplicate_seen": "quality_validation.blocked_recommendations[0]",
                "recommendation_id": "rec.contract-enforce-quality-floor",
            },
        }
    ]


def test_req061_hardening_broken_evidence_reference_fails_traceability_gate() -> None:
    payload = _sample_payload()
    payload["processing_behavior"]["recommendation"]["recommended_actions"][0]["evidence_refs"][0] = (
        "reports/traceability/broken-reference.json"
    )

    first = module.validate_req_061_recommendation_quality_validator(payload)
    second = module.validate_req_061_recommendation_quality_validator(deepcopy(payload))

    assert first == second
    assert (
        "processing_behavior.recommendation.recommended_actions[0].evidence_refs[0] "
        "must exist in processing_behavior.recommendation.evidence_refs for traceability gate"
    ) in first

    diagnostics = _diagnostics(first)
    traceability_rows = [
        row
        for row in diagnostics
        if row["reason_code"] == module._REQ_061_REASON_CODE_TRACEABILITY_GATE_FAILED
    ]
    assert traceability_rows == [
        {
            "reason_code": "traceability_gate_failed",
            "message": "broken evidence reference failed traceability gate",
            "evidence_refs": [
                "reports/traceability/broken-reference.json"
            ],
            "diff_details": {
                "expected_ref_set": "processing_behavior.recommendation.evidence_refs",
                "observed_ref": "reports/traceability/broken-reference.json",
            },
        }
    ]
