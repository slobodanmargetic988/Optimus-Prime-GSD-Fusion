import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_context_sweep.py"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "fixtures"
    / "runtime-telemetry-artifact-sweep-across-earth.json"
)
SPEC = importlib.util.spec_from_file_location("strategy_context_sweep", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

ARTIFACT_AGE_SECONDS = {
    ("earth-north", "runtime_traces", "trace-main"): 120,
    ("earth-north", "runtime_traces", "trace-errors"): 601,
    ("earth-north", "cycle_summaries", "summary-current"): 200,
    ("earth-south", "cycle_summaries", "summary-current"): 301,
    ("earth-south", "cycle_summaries", "summary-history"): 1200,
}


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


def _seed_artifacts(payload: dict) -> None:
    now_utc = _parse_utc(payload["now_utc"])
    for project in payload["projects"]:
        project_id = project["project_id"]
        project_root = Path(project["root_path"])
        artifacts = project["artifacts"]
        for artifact_key, rows in artifacts.items():
            for row in rows:
                source_id = row["source_id"]
                age_seconds = ARTIFACT_AGE_SECONDS.get((project_id, artifact_key, source_id))
                if age_seconds is None:
                    continue
                _write_with_age(project_root, row["path"], now_utc=now_utc, age_seconds=age_seconds)


def _rows_by_source(rows: list[dict]) -> dict[str, dict]:
    return {row["source_id"]: row for row in rows}


def test_sweep_contract_classifies_runtime_telemetry_and_emits_citations(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_artifacts(payload)

    out = MODULE.run(payload)

    assert out["ok"] is True
    assert out["tool"] == "strategy-context-sweep"
    assert out["checked_at_utc"] == "2026-03-14T21:00:00Z"
    assert out["totals"] == {
        "projects": 2,
        "sources": 6,
        "fresh": 2,
        "stale": 3,
        "missing": 1,
        "include": 2,
        "downgrade": 3,
        "exclude": 1,
    }

    projects = {row["project_id"]: row for row in out["projects"]}
    north_traces = _rows_by_source(projects["earth-north"]["artifacts"]["runtime_traces"])
    south_traces = _rows_by_source(projects["earth-south"]["artifacts"]["runtime_traces"])
    south_summaries = _rows_by_source(projects["earth-south"]["artifacts"]["cycle_summaries"])

    assert north_traces["trace-main"]["freshness"] == "fresh"
    assert north_traces["trace-errors"]["decision"] == "downgrade"
    assert south_traces["trace-main"]["freshness"] == "missing"
    assert south_traces["trace-main"]["decision"] == "exclude"
    assert south_summaries["summary-current"]["freshness"] == "stale"

    source_refs = out["source_references"]
    assert len(source_refs) == 6
    assert source_refs[0]["citation_id"] == "SRC-0001"
    assert source_refs[-1]["citation_id"] == "SRC-0006"
    assert north_traces["trace-main"]["source_reference"]["analysis_anchors"] == [
        "throughput",
        "blockers",
        "failure_patterns",
    ]


def test_sweep_contract_allows_stale_exclusion_policy(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    payload["decision_policy"]["stale"] = "exclude"
    _seed_artifacts(payload)

    out = MODULE.run(payload)

    assert out["ok"] is True
    assert out["decision_policy"] == {"stale": "exclude", "missing": "exclude"}
    assert out["totals"]["downgrade"] == 0
    assert out["totals"]["exclude"] == 4


def test_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_artifacts(payload)
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
    assert out["totals"]["sources"] == 6
