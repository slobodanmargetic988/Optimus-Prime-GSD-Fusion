import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "ecosystem-link-map-integrity-validator.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-063_ecosystem-link-map-integrity-validator.sample.json"
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-063_ecosystem-link-map-integrity-validator.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_063_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_063_ecosystem_link_map_integrity_validator(fixture_payload["input"])

    assert module.validate_req_063_ecosystem_link_map_integrity_validator(built_payload) == []
    assert module.validate_req_063_ecosystem_link_map_integrity_validator(sample_payload) == []
    assert built_payload == sample_payload


def test_req_063_flags_orphaned_and_broken_links_with_source_level_diagnostics() -> None:
    sample_payload = _read_json(SAMPLE_PATH)
    validator_payload = sample_payload["ecosystem_link_map_integrity_validator"]
    rows = {row["link_id"]: row for row in validator_payload["links"]}
    diagnostics = {row["diagnostic_id"]: row for row in validator_payload["diagnostics"]}

    assert rows["link.analytics-export.emits-to"]["integrity_status"] == "orphaned"
    assert rows["link.runtime-core.depends-on"]["integrity_status"] == "valid"
    assert rows["link.runtime-core.self-loop"]["integrity_status"] == "broken"

    orphaned = diagnostics["diag.link.analytics-export.emits-to.missing_target_project"]
    assert orphaned["category"] == "referential_integrity"
    assert orphaned["field_path"] == "strategy/current/ECOSYSTEM_LINK_MAP.json#links[1].target_project_id"
    assert orphaned["source_ref"] == "strategy/current/ECOSYSTEM_LINK_MAP.json#links[1]"
    assert orphaned["project_ids"] == ["prj.analytics-lab"]

    broken = diagnostics["diag.link.runtime-core.self-loop.self_referential_link"]
    assert broken["category"] == "schema_integrity"
    assert broken["field_path"] == "strategy/current/ECOSYSTEM_LINK_MAP.json#links[2].target_project_id"
    assert broken["project_ids"] == ["prj.runtime-core"]

    assert validator_payload["summary"] == {
        "integrity_status": "failed",
        "valid_link_ids": ["link.runtime-core.depends-on"],
        "orphaned_link_ids": ["link.analytics-export.emits-to"],
        "broken_link_ids": ["link.runtime-core.self-loop"],
        "diagnostic_codes": ["missing_target_project", "self_referential_link"],
        "missing_project_ids": ["prj.analytics-lab"],
    }


def test_req_063_validator_rejects_mismatched_totals() -> None:
    broken = deepcopy(_read_json(SAMPLE_PATH))
    broken["totals"]["orphaned_links"] = 0

    errors = module.validate_req_063_ecosystem_link_map_integrity_validator(broken)

    assert (
        "totals.orphaned_links must equal ecosystem_link_map_integrity_validator.links orphaned count"
        in errors
    )


def test_req_063_contract_doc_references_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-063_ecosystem-link-map-integrity-validator.sample.json" in contract_text
    for key in (
        "ecosystem_link_map_integrity_validator.link_map_ref",
        "ecosystem_link_map_integrity_validator.discovered_projects",
        "ecosystem_link_map_integrity_validator.links",
        "ecosystem_link_map_integrity_validator.links[].integrity_status",
        "ecosystem_link_map_integrity_validator.diagnostics",
        "ecosystem_link_map_integrity_validator.diagnostics[].field_path",
        "ecosystem_link_map_integrity_validator.diagnostics[].source_ref",
        "ecosystem_link_map_integrity_validator.summary",
        "totals",
    ):
        assert key in contract_text


def test_req_063_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_063_builder_rejects_missing_source_refs() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)

    with pytest.raises(ValueError, match=r"source_refs"):
        module.build_req_063_ecosystem_link_map_integrity_validator(
            fixture_payload["invalid_missing_source_refs_input"]
        )
