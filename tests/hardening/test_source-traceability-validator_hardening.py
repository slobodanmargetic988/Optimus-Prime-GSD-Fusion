from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-064_source-traceability-validator.sample.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sample_payload() -> dict:
    return deepcopy(_read_json(SAMPLE_PATH))


def test_req_064_invalid_strategy_packet_schema_row_rejected_with_deterministic_diagnostics() -> None:
    broken = _sample_payload()
    recommendation = broken["source_traceability_validator"]["recommendations"][0]
    recommendation.pop("summary")
    recommendation["unexpected_row_key"] = "invalid"

    first_errors = module.validate_req_064_source_traceability_validator(broken)
    second_errors = module.validate_req_064_source_traceability_validator(deepcopy(broken))

    assert first_errors == second_errors
    assert (
        "source_traceability_validator.recommendations[0] missing keys: ['summary']"
    ) in first_errors
    assert (
        "source_traceability_validator.recommendations[0] has unexpected keys: ['unexpected_row_key']"
    ) in first_errors


def test_req_064_duplicate_recommendation_id_collision_flagged_with_diff_details() -> None:
    broken = _sample_payload()
    recommendations = broken["source_traceability_validator"]["recommendations"]
    recommendations[1]["recommendation_id"] = recommendations[0]["recommendation_id"]

    first_errors = module.validate_req_064_source_traceability_validator(broken)
    second_errors = module.validate_req_064_source_traceability_validator(deepcopy(broken))

    assert first_errors == second_errors
    assert "source_traceability_validator.recommendations[1].recommendation_id must be unique" in first_errors

    prefix = "source_traceability_validator.recommendations[1].recommendation_id duplicate collision details: "
    details_row = next(row for row in first_errors if row.startswith(prefix))
    details = json.loads(details_row[len(prefix) :])
    assert details == {
        "claim_count_delta": -1,
        "claim_ids_added": ["claim.broken-ref-blocker"],
        "claim_ids_removed": ["claim.citations-required", "claim.runtime-context-link"],
        "duplicate_index": 1,
        "evidence_refs_added": ["src.sweep-002"],
        "evidence_refs_removed": ["src.mission-001", "src.runtime-003"],
        "first_index": 0,
        "recommendation_id": "rec.harden-source-citations",
        "summary_changed": True,
    }


def test_req_064_broken_evidence_reference_causes_traceability_gate_failure() -> None:
    broken = _sample_payload()
    broken["source_traceability_validator"]["recommendations"][0]["claims"][0]["evidence_refs"] = ["src.unknown-999"]

    first_errors = module.validate_req_064_source_traceability_validator(broken)
    second_errors = module.validate_req_064_source_traceability_validator(deepcopy(broken))

    assert first_errors == second_errors
    assert first_errors
    assert (
        "source_traceability_validator.recommendations[0].claims[0].evidence_refs "
        "contains unknown evidence refs: ['src.unknown-999']"
    ) in first_errors
