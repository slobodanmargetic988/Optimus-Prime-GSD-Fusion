import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-quality-validator.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-061_recommendation-quality-validator.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-061_recommendation-quality-validator.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_061_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_061_recommendation_quality_validator(fixture_payload["input"])

    assert module.validate_req_061_recommendation_quality_validator(built_payload) == []
    assert module.validate_req_061_recommendation_quality_validator(sample_payload) == []
    assert built_payload == sample_payload


def test_req_061_quality_validation_blocks_low_substance_and_incomplete_rows() -> None:
    payload = _read_json(SAMPLE_PATH)
    quality_validation = payload["quality_validation"]

    assert quality_validation["planner_readiness"] == {
        "decision": "allow_planner_packet",
        "allowed_recommendation_ids": ["rec.contract-enforce-quality-floor"],
        "blocked_recommendation_ids": [
            "rec.review-reuse-drift",
            "rec.fill-routing-gap",
        ],
        "blocking_reason_codes": [
            "incomplete_recommendation",
            "insufficient_evidence_citations",
            "low_substance_rationale",
        ],
    }

    blocked = {row["recommendation_id"]: row for row in quality_validation["blocked_recommendations"]}
    assert blocked["rec.review-reuse-drift"]["failure_reason_codes"] == [
        "low_substance_rationale",
        "insufficient_evidence_citations",
    ]
    assert blocked["rec.fill-routing-gap"]["missing_fields"] == ["lane"]
    assert payload["totals"] == {
        "candidate_recommendations": 3,
        "accepted_recommendations": 1,
        "blocked_recommendations": 2,
        "incomplete_recommendations": 1,
        "low_substance_recommendations": 1,
        "citation_failures": 1,
    }


def test_req_061_validator_rejects_planner_readiness_alignment_drift() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["quality_validation"]["planner_readiness"]["allowed_recommendation_ids"] = []

    errors = module.validate_req_061_recommendation_quality_validator(broken)

    assert (
        "quality_validation.planner_readiness.allowed_recommendation_ids must match assessed recommendation IDs"
        in errors
    )


def test_req_061_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-061_recommendation-quality-validator.sample.json" in contract_text
    for key in (
        "quality_thresholds.required_recommendation_fields",
        "quality_validation.accepted_recommendations",
        "quality_validation.blocked_recommendations",
        "quality_validation.planner_readiness",
        "totals",
    ):
        assert key in contract_text


def test_req_061_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(fixture_payload["input"]), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stderr == ""
    assert json.loads(proc.stdout) == _read_json(SAMPLE_PATH)


def test_req_061_builder_rejects_invalid_packet_kind() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"packet_kind"):
        module.build_req_061_recommendation_quality_validator(fixture_payload["invalid_packet_kind_input"])
