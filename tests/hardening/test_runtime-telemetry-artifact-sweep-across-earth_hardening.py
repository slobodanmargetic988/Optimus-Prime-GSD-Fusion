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


def test_hardening_stale_source_detected_emits_reason_code_with_evidence_refs(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_artifacts(payload)

    out = MODULE.run(payload)

    stale_rows = [
        row for row in out["unhappy_paths"] if row["reason_code"] == "stale_source_artifact_detected"
    ]
    assert [row["evidence_refs"] for row in stale_rows] == [["SRC-0002"], ["SRC-0005"], ["SRC-0006"]]

    source_refs = {row["citation_id"]: row for row in out["source_references"]}
    for evidence_refs in (row["evidence_refs"] for row in stale_rows):
        citation_id = evidence_refs[0]
        assert source_refs[citation_id]["freshness"] == "stale"
        assert source_refs[citation_id]["reason_code"] == "stale_source_artifact_detected"


def test_hardening_missing_context_docs_emit_explicit_reason_codes(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_artifacts(payload)
    scope_path = tmp_path / "scope.md"
    scope_path.write_text("scope\n", encoding="utf-8")
    missing_mission = tmp_path / "missing-mission.md"
    payload["context_bundle_docs"] = {
        "mission_path": str(missing_mission),
        "scope_path": str(scope_path),
        "peer_project_docs": [],
    }
    input_json = tmp_path / "input-missing-mission.json"
    input_json.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert out["reason_code"] == "mission_scope_doc_missing"
    assert out["evidence_refs"] == [f"DOCREF:mission:{missing_mission.resolve()}"]

    mission_path = tmp_path / "mission.md"
    mission_path.write_text("mission\n", encoding="utf-8")
    missing_peer_doc = tmp_path / "missing-peer-earth-south.md"
    payload["context_bundle_docs"] = {
        "mission_path": str(mission_path),
        "scope_path": str(scope_path),
        "peer_project_docs": [
            {
                "project_id": "earth-south",
                "path": str(missing_peer_doc),
            }
        ],
    }
    input_json.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert out["reason_code"] == "peer_project_doc_missing"
    assert out["evidence_refs"] == [f"DOCREF:peer:earth-south:{missing_peer_doc.resolve()}"]


def test_hardening_context_bundle_serialization_is_replay_stable(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_artifacts(payload)

    mission_path = tmp_path / "mission.md"
    scope_path = tmp_path / "scope.md"
    peer_path = tmp_path / "earth-south-peer.md"
    mission_path.write_text("mission\n", encoding="utf-8")
    scope_path.write_text("scope\n", encoding="utf-8")
    peer_path.write_text("peer\n", encoding="utf-8")
    payload["context_bundle_docs"] = {
        "mission_path": str(mission_path),
        "scope_path": str(scope_path),
        "peer_project_docs": [
            {
                "project_id": "earth-south",
                "path": str(peer_path),
            }
        ],
    }

    out_first = MODULE.run(payload)
    out_second = MODULE.run(payload)

    assert out_first["context_bundle_serialized"] == out_second["context_bundle_serialized"]
    assert json.loads(out_first["context_bundle_serialized"]) == out_first["context_bundle"]
    assert out_first["context_bundle"]["context_docs"]["mission"]["evidence_ref"] == (
        f"DOCREF:mission:{mission_path.resolve()}"
    )
