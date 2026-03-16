import json
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-id-uniqueness-validator.json"
SAMPLE_PATH = (
    REPO_ROOT / "strategy" / "current" / "samples" / "REQ-062_recommendation-id-uniqueness-validator.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-062_recommendation-id-uniqueness-validator.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_062_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_062_recommendation_id_uniqueness_validator(fixture_payload["input"])

    assert module.validate_req_062_recommendation_id_uniqueness_validator(built_payload) == []
    assert module.validate_req_062_recommendation_id_uniqueness_validator(sample_payload) == []
    assert built_payload == sample_payload


def test_req_062_diagnostics_capture_collision_and_drift() -> None:
    payload = _read_json(SAMPLE_PATH)

    assert payload["verdict"] == {
        "is_unique_within_revision": False,
        "ids_stable_across_revisions": False,
        "passed": False,
    }

    collisions = payload["diagnostics"]["id_collisions"]
    assert len(collisions) == 1
    assert collisions[0]["revision_id"] == "strategy-rev-042"
    assert collisions[0]["recommendation_id"] == "rec.align-earth-runtime-canary"
    assert collisions[0]["occurrence_count"] == 2
    assert collisions[0]["recommendation_keys"] == [
        "integration-latency-watch",
        "runtime-canary-alignment",
    ]

    drift = payload["diagnostics"]["id_drift"]
    assert len(drift) == 1
    assert drift[0]["recommendation_key"] == "telemetry-freshness"
    assert drift[0]["previous_recommendation_ids"] == ["rec.harden-telemetry-freshness"]
    assert drift[0]["current_recommendation_ids"] == ["rec.harden-telemetry-freshness-v2"]


def test_req_062_builder_passes_when_ids_are_unique_and_stable() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    built_payload = module.build_req_062_recommendation_id_uniqueness_validator(
        fixture_payload["stable_unique_input"]
    )

    assert module.validate_req_062_recommendation_id_uniqueness_validator(built_payload) == []
    assert built_payload["diagnostics"]["id_collisions"] == []
    assert built_payload["diagnostics"]["id_drift"] == []
    assert built_payload["verdict"] == {
        "is_unique_within_revision": True,
        "ids_stable_across_revisions": True,
        "passed": True,
    }


def test_req_062_validator_rejects_non_differing_drift_row() -> None:
    payload = _read_json(SAMPLE_PATH)
    payload["diagnostics"]["id_drift"][0]["current_recommendation_ids"] = payload["diagnostics"]["id_drift"][0][
        "previous_recommendation_ids"
    ]

    errors = module.validate_req_062_recommendation_id_uniqueness_validator(payload)

    assert "diagnostics.id_drift[0] must represent differing previous/current recommendation IDs" in errors


def test_req_062_builder_rejects_missing_previous_revision() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"previous_revision"):
        module.build_req_062_recommendation_id_uniqueness_validator(
            fixture_payload["invalid_missing_previous_revision_input"]
        )


def test_req_062_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json" in contract_text
    for key in (
        "revision_snapshots.previous.recommendation_ids",
        "revision_snapshots.current.recommendation_ids",
        "diagnostics.id_collisions",
        "diagnostics.id_drift",
        "diagnostics.added_ids",
        "diagnostics.removed_ids",
        "totals",
        "verdict",
    ):
        assert key in contract_text
