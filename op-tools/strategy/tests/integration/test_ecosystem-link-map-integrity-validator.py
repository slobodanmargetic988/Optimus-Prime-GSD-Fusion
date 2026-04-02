from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


VALIDATOR_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_packet_validate.py"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "strategy_packet.v1.schema.json"
CURRENT_PACKET_PATH = Path(__file__).resolve().parents[2] / "strategy" / "current" / "strategy_packet.v1.json"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _run_validator(packet_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_SCRIPT_PATH),
            "--input",
            str(packet_path),
            "--schema",
            str(SCHEMA_PATH),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_strategy_packet_validator_passes_valid_req_063_packet() -> None:
    proc = _run_validator(CURRENT_PACKET_PATH)

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload == {
        "ok": True,
        "verdict": "pass",
        "ready_for_consumption": True,
        "diagnostics": [],
        "summary": {
            "diagnostic_count": 0,
            "error_count": 0,
            "warning_count": 0,
        },
    }


def test_strategy_packet_validator_reports_req_063_referential_diagnostics() -> None:
    proc = _run_validator(FIXTURES_DIR / "strategy_packet.req063.invalid-link-map.json")

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)

    assert payload["ok"] is False
    assert payload["verdict"] == "fail"
    assert payload["ready_for_consumption"] is False
    assert payload["summary"] == {
        "diagnostic_count": 3,
        "error_count": 3,
        "warning_count": 0,
    }
    assert payload["diagnostics"] == [
        {
            "field_path": "strategy.link_map.discovered_projects[2].project_id",
            "message": "REQ-063 discovered_projects contains duplicate project_id prj.peer-alpha.",
            "reason_code": "req063.duplicate_discovered_project",
            "severity": "error",
        },
        {
            "field_path": "strategy.link_map.links[0].target_project_id",
            "message": (
                "REQ-063 link target_project_id must reference a discovered project; "
                "prj.peer-beta is missing from discovered_projects."
            ),
            "reason_code": "req063.orphaned_link_target",
            "severity": "error",
        },
        {
            "field_path": "strategy.link_map.links[1].source_project_id",
            "message": (
                "REQ-063 link source_project_id must reference a discovered project; "
                "prj.orphan-source is missing from discovered_projects."
            ),
            "reason_code": "req063.orphaned_link_source",
            "severity": "error",
        },
    ]


def test_strategy_packet_validator_reports_req_063_schema_diagnostics() -> None:
    proc = _run_validator(FIXTURES_DIR / "strategy_packet.req063.invalid-link-map-schema.json")

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)

    assert payload["ok"] is False
    assert payload["verdict"] == "fail"
    assert payload["ready_for_consumption"] is False
    assert payload["summary"] == {
        "diagnostic_count": 3,
        "error_count": 3,
        "warning_count": 0,
    }
    assert payload["diagnostics"] == [
        {
            "field_path": "strategy.link_map.artifact_type",
            "message": "'ecosystem-link-map.v1' was expected",
            "reason_code": "req063.link_map_schema.const",
            "severity": "error",
        },
        {
            "field_path": "strategy.link_map.discovered_projects[0].note",
            "message": "Additional properties are not allowed ('note' was unexpected)",
            "reason_code": "req063.link_map_schema.additional_properties",
            "severity": "error",
        },
        {
            "field_path": "strategy.link_map.links[0].status",
            "message": "'status' is a required property",
            "reason_code": "req063.link_map_schema.required",
            "severity": "error",
        },
    ]
