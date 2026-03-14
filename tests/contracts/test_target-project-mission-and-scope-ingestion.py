import json
from pathlib import Path

from scripts.strategy_context_sweep import ingest_target_project_mission_scope


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "fixtures"
    / "target-project-mission-and-scope-ingestion.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_valid_case_ingests_authoritative_mission_scope() -> None:
    fixture = _load_fixture()
    payload = fixture["valid_case"]["input"]

    result = ingest_target_project_mission_scope(payload)

    assert result["ok"] is True
    assert result["reason_codes"] == []
    assert result["target_project_constraints"]["mission"]["authoritative"] is True
    assert result["target_project_constraints"]["scope"]["authoritative"] is True
    assert result["recommendation_generation"]["authoritative_fields"] == ["mission", "scope"]


def test_rejection_cases_emit_explicit_reason_codes() -> None:
    fixture = _load_fixture()
    rejection_cases = fixture["rejection_cases"]

    for case in rejection_cases:
        result = ingest_target_project_mission_scope(case["input"])
        assert result["ok"] is False, case["name"]
        for expected_code in case["expected_reason_codes"]:
            assert expected_code in result["reason_codes"], case["name"]
        assert isinstance(result["errors"], list) and result["errors"], case["name"]
