import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from scripts.strategy_validators import validate_strategy_packet


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKET_PATH = REPO_ROOT / "strategy" / "current" / "strategy_packet.v1.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "strategy_packet.v1.schema.json"
CLI_PATH = REPO_ROOT / "scripts" / "strategy_packet_validate.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_056_validator_passes_valid_packet() -> None:
    verdict = validate_strategy_packet(packet_path=PACKET_PATH, schema_path=SCHEMA_PATH)

    assert verdict["ok"] is True
    assert verdict["verdict"] == "pass"
    assert verdict["blocking"] is False
    assert verdict["diagnostics"] == []
    assert verdict["reason_codes"] == []
    assert verdict["gate"]["status"] == "pass"
    assert verdict["gate"]["decision"] == "allow_consume"


def test_req_056_validator_fails_with_deterministic_machine_readable_diagnostics(tmp_path: Path) -> None:
    broken = deepcopy(_read_json(PACKET_PATH))
    row = broken["kpi_target_artifact"]["kpi_targets"][0]
    row["expected_direction"] = "up"
    row["baseline_reference"] = ""
    row["confidence_level"] = "certain"
    row["originating_recommendation_ids"] = ["rec.unknown-recommendation"]
    row["assumption_ids"] = ["assumption.unknown-assumption"]
    broken["kpi_target_artifact"]["totals"]["kpi_targets"] = 99
    broken["kpi_target_artifact"]["totals"]["unique_recommendations_linked"] = 98
    broken["kpi_target_artifact"]["totals"]["unique_assumptions_linked"] = 97

    invalid_packet = tmp_path / "invalid_packet.json"
    invalid_packet.write_text(json.dumps(broken), encoding="utf-8")

    first = validate_strategy_packet(packet_path=invalid_packet, schema_path=SCHEMA_PATH)
    second = validate_strategy_packet(packet_path=invalid_packet, schema_path=SCHEMA_PATH)

    assert first["verdict"] == "fail"
    assert first["ok"] is False
    assert first["blocking"] is True
    assert first["reason_codes"] == second["reason_codes"]
    assert first["diagnostics"] == second["diagnostics"]

    reason_codes = set(first["reason_codes"])
    assert "schema_contract_violation" in reason_codes
    assert "kpi_target_expected_direction_invalid" in reason_codes
    assert "kpi_target_baseline_reference_missing" in reason_codes
    assert "kpi_target_confidence_level_invalid" in reason_codes
    assert "kpi_target_unknown_originating_recommendation_id" in reason_codes
    assert "kpi_target_unknown_assumption_id" in reason_codes
    assert "kpi_target_totals_mismatch" in reason_codes

    field_paths = {row["field_path"] for row in first["diagnostics"]}
    assert "kpi_target_artifact.kpi_targets[0].expected_direction" in field_paths
    assert "kpi_target_artifact.kpi_targets[0].baseline_reference" in field_paths
    assert "kpi_target_artifact.kpi_targets[0].confidence_level" in field_paths
    assert "kpi_target_artifact.kpi_targets[0].originating_recommendation_ids[0]" in field_paths
    assert "kpi_target_artifact.kpi_targets[0].assumption_ids[0]" in field_paths

    assert all("reason_code" in row and row["reason_code"] for row in first["diagnostics"])
    assert all("field_path" in row and row["field_path"] for row in first["diagnostics"])
    assert all(row.get("severity") in {"error", "warning", "info"} for row in first["diagnostics"])

    proc = subprocess.run(
        [sys.executable, str(CLI_PATH), "--input", str(invalid_packet), "--schema", str(SCHEMA_PATH)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    assert proc.stderr == ""
    cli_payload = json.loads(proc.stdout)
    assert cli_payload["ok"] is False
    assert cli_payload["verdict"] == "fail"
    assert cli_payload["gate"]["status"] == "fail"

