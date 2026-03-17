import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-id-uniqueness-validator.json"


def _read_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req_062_hardening_rejects_invalid_strategy_packet_schema_row_with_deterministic_diagnostics() -> None:
    fixture = _read_fixture()
    payload = deepcopy(fixture["input"])
    payload["current_revision"]["recommendations"][0]["strategy_packet_input_id"] = "pkt.invalid-schema-row"

    with pytest.raises(
        ValueError,
        match=r"current_revision\.recommendations\[0\] has unexpected keys: \['strategy_packet_input_id'\]",
    ):
        module.build_req_062_recommendation_id_uniqueness_validator(payload)


def test_req_062_hardening_flags_duplicate_recommendation_id_collision_with_diff_details() -> None:
    fixture = _read_fixture()
    payload = module.build_req_062_recommendation_id_uniqueness_validator(fixture["integration_input"])

    assert module.validate_req_062_recommendation_id_uniqueness_validator(payload) == []

    collision_rows = payload["diagnostics"]["id_collisions"]
    assert len(collision_rows) == 1
    collision = collision_rows[0]

    assert collision["diagnostic_id"].startswith("collision.")
    assert collision["revision_id"] == "strategy-rev-042"
    assert collision["recommendation_id"] == "rec.align-earth-runtime-canary"
    assert collision["occurrence_count"] == 2
    assert collision["recommendation_keys"] == [
        "integration-latency-watch",
        "runtime-canary-alignment",
    ]

    collision_risk = next(
        row
        for row in payload["processing_behavior"]["recommendation"]["open_risks"]
        if row["reason_code"] == "recommendation_id_collision"
    )
    assert collision_risk["linked_recommendation_ids"] == ["rec.align-earth-runtime-canary"]
    assert "collides within revision 'strategy-rev-042'" in collision_risk["summary"]
    assert (
        "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json#diagnostics.id_collisions"
        in collision_risk["required_evidence_refs"]
    )


def test_req_062_hardening_broken_evidence_reference_fails_traceability_gate() -> None:
    fixture = _read_fixture()
    payload = module.build_req_062_recommendation_id_uniqueness_validator(fixture["integration_input"])

    payload["processing_behavior"]["recommendation"]["evidence_refs"][0] = "broken-traceability-reference"
    payload["processing_behavior"]["context_usage"]["evidence_refs_used"] = list(
        payload["processing_behavior"]["recommendation"]["evidence_refs"]
    )
    payload["processing_behavior"]["recommendation_generation"]["evidence_refs_used"] = list(
        payload["processing_behavior"]["recommendation"]["evidence_refs"]
    )

    errors = module.validate_req_062_recommendation_id_uniqueness_validator(payload)

    assert (
        "processing_behavior.recommendation.evidence_refs[0] must be a traceability ref with '#<anchor>' or start "
        "with 'reports/earth/sweeps/'"
    ) in errors
