import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_context_sweep.py"
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "examples" / "fixtures" / "capability-catalog-extraction.json"
SPEC = importlib.util.spec_from_file_location("strategy_context_sweep", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _load_fixture_payload(tmp_path: Path) -> dict:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for project in payload["projects"]:
        project["root_path"] = str(Path(project["root_path"].replace("__TMP__", str(tmp_path))))
    return payload


def _parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def _write_with_age(project_root: Path, relative_path: str, *, now_utc: datetime, age_seconds: int) -> None:
    target = (project_root / relative_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{target.name}\n", encoding="utf-8")
    ts = (now_utc.timestamp() - age_seconds, now_utc.timestamp() - age_seconds)
    os.utime(target, ts)


def _seed_all_fresh_artifacts(payload: dict) -> None:
    now_utc = _parse_utc(payload["now_utc"])
    for project in payload["projects"]:
        project_root = Path(project["root_path"])
        for artifact_key, relative_path in project["artifacts"].items():
            max_age = int(payload["stale_after_seconds"][artifact_key])
            _write_with_age(project_root, relative_path, now_utc=now_utc, age_seconds=max(0, min(10, max_age)))


def test_req013_capability_catalog_extracts_project_coverage_and_versions(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_all_fresh_artifacts(payload)

    out = MODULE.run(payload)

    assert out["ok"] is True
    assert out["tool"] == "strategy-context-sweep"
    catalog = out["capability_catalog"]

    assert catalog["required_capability_ids"] == [
        "capability-catalog-extraction",
        "cross-project-obligation-validation",
        "planning-artifact-sweep",
        "source-version-guard",
    ]
    assert catalog["already_completed_capability_ids"] == [
        "capability-catalog-extraction",
        "cross-project-obligation-validation",
        "planning-artifact-sweep",
    ]
    assert catalog["missing_capability_ids"] == ["source-version-guard"]
    assert catalog["recommended_capability_ids"] == ["source-version-guard"]

    projects = {row["project_id"]: row for row in catalog["projects"]}
    assert projects["earth-north"]["missing_capability_ids"] == [
        "cross-project-obligation-validation",
        "source-version-guard",
    ]
    assert projects["earth-south"]["missing_capability_ids"] == [
        "capability-catalog-extraction",
        "source-version-guard",
    ]

    entries = {row["capability_id"]: row for row in catalog["catalog_entries"]}
    assert entries["planning-artifact-sweep"]["availability"] == "provided"
    assert entries["planning-artifact-sweep"]["source_versions"] == ["1.1.0"]
    assert entries["planning-artifact-sweep"]["provider_count"] == 2

    assert entries["capability-catalog-extraction"]["providers"] == [
        {
            "project_id": "earth-north",
            "source_version": "1.0.0",
            "source_ref": "contracts/req/REQ-013_capability-catalog-extraction.md",
        }
    ]
    assert entries["source-version-guard"]["availability"] == "missing"
    assert entries["source-version-guard"]["providers"] == []
    assert entries["source-version-guard"]["project_ids_missing"] == ["earth-north", "earth-south"]


def test_req013_cli_contract_returns_capability_catalog_surface(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_all_fresh_artifacts(payload)
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert "capability_catalog" in out
    assert out["capability_catalog"]["recommended_capability_ids"] == ["source-version-guard"]
