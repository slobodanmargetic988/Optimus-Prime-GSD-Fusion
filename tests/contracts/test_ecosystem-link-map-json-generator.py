import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "ecosystem-link-map-json-generator.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-050_ecosystem-link-map-json-generator.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-050_ecosystem-link-map-json-generator.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_050_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_050_ecosystem_link_map_json_generator(fixture_payload)

    assert module.validate_req_050_ecosystem_link_map_json_generator(built_payload) == []
    assert module.validate_req_050_ecosystem_link_map_json_generator(sample_payload) == []
    assert built_payload == sample_payload
    assert built_payload["ecosystem_link_map"]["artifact_path"] == "ECOSYSTEM_LINK_MAP.json"
    assert built_payload["totals"]["current_links"] == 1
    assert built_payload["totals"]["missing_links"] == 1
    assert built_payload["totals"]["proposed_links"] == 1


def test_req_050_link_buckets_preserve_confidence_and_obligation_metadata() -> None:
    payload = _read_json(SAMPLE_PATH)
    link_map = payload["ecosystem_link_map"]

    current_link = link_map["current_links"][0]
    assert current_link["peer_project_id"] == "earth-core-runtime"
    assert current_link["confidence"] == "high"
    assert current_link["packet_input_ids"] == ["pkt.c3c7c38214ae"]
    assert current_link["obligation_metadata"]["status"] == "active"

    missing_link = link_map["missing_links"][0]
    assert missing_link["peer_project_id"] == "earth-shared-observability"
    assert missing_link["confidence"] == "low"
    assert missing_link["open_risk_ids"] == ["open-risk.c6d73dbb8f81"]
    assert missing_link["obligation_metadata"]["reason_codes"] == ["unresolved_idea_open_risk"]

    proposed_link = link_map["proposed_links"][0]
    assert proposed_link["peer_project_id"] == "earth-shared-observability"
    assert proposed_link["confidence"] == "medium"
    assert proposed_link["recommendation_ids"] == ["rec.review-reuse-contracts"]
    assert proposed_link["obligation_metadata"]["status"] == "proposed"


def test_req_050_validator_rejects_summary_count_drift() -> None:
    payload = _read_json(SAMPLE_PATH)
    broken = deepcopy(payload)
    broken["ecosystem_link_map"]["summary"]["total_link_count"] = 99

    errors = module.validate_req_050_ecosystem_link_map_json_generator(broken)

    assert "ecosystem_link_map.summary.total_link_count must match derived row counts" in errors


def test_req_050_contract_doc_references_documented_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-050_ecosystem-link-map-json-generator.sample.json" in contract_text
    for key in (
        "ecosystem_link_map.current_links",
        "ecosystem_link_map.missing_links",
        "ecosystem_link_map.proposed_links",
        "ecosystem_link_map.planning_context",
        "ecosystem_link_map.summary",
        "obligation_metadata",
        "totals",
    ):
        assert key in contract_text


def test_req_050_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(fixture_payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stderr == ""
    assert json.loads(proc.stdout) == _read_json(SAMPLE_PATH)


def test_req_050_builder_rejects_cross_project_deferred_rows_without_peer_candidates() -> None:
    fixture_payload = deepcopy(_read_json(FIXTURE_PATH))
    fixture_payload["final_strategy_synthesis"]["deferred_recommendations"][0]["peer_project_candidates"] = []

    with pytest.raises(ValueError, match=r"peer_project_candidates"):
        module.build_req_050_ecosystem_link_map_json_generator(fixture_payload)
