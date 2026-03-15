import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_context_sweep.py"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "fixtures"
    / "deficit-and-need-signal-extraction.json"
)
SPEC = importlib.util.spec_from_file_location("strategy_context_sweep", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _load_fixture_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _with_earth_sweep_stale_unhappy_path(payload: dict) -> None:
    payload["broad_sweep_context"] = {
        "projects_considered": ["earth-north", "earth-south"],
        "evidence_refs_by_project": {
            "earth-north": ["SRC-1001"],
            "earth-south": ["SRC-2001"],
        },
        "unhappy_paths": [
            {
                "reason_code": "stale_source_artifact_detected",
                "project_id": "earth-south",
                "artifact_type": "cycle_summaries",
                "source_id": "summary-history",
                "evidence_refs": ["SRC-2001"],
            }
        ],
    }


def test_hardening_stale_source_detected_during_earth_sweep_emits_reason_code_with_evidence_refs() -> None:
    payload = _load_fixture_payload()
    _with_earth_sweep_stale_unhappy_path(payload)

    out = MODULE.run(payload)

    assert out["ok"] is True
    assert out["analysis_type"] == "deficit_and_need_signal_extraction"
    assert out["unhappy_paths"] == [
        {
            "reason_code": "stale_source_artifact_detected",
            "project_id": "earth-south",
            "artifact_type": "cycle_summaries",
            "source_id": "summary-history",
            "evidence_refs": ["SRC-2001"],
        }
    ]
    assert "SRC-2001" in out["recommendation"]["evidence_refs"]
    assert out["context_bundle"]["unhappy_paths"] == out["unhappy_paths"]


def test_hardening_missing_context_docs_emit_explicit_reason_codes(tmp_path: Path) -> None:
    payload = _load_fixture_payload()
    scope_path = tmp_path / "scope.md"
    scope_path.write_text("scope\n", encoding="utf-8")
    missing_mission = tmp_path / "missing-mission.md"
    payload["context_bundle_docs"] = {
        "base_dir": str(tmp_path),
        "mission_path": missing_mission.name,
        "scope_path": scope_path.name,
        "peer_project_docs": [],
    }

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", "-"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert out["reason_code"] == "mission_scope_doc_missing"
    assert out["evidence_refs"] == [f"DOCREF:mission:{missing_mission.resolve()}"]

    payload = _load_fixture_payload()
    mission_path = tmp_path / "mission.md"
    mission_path.write_text("mission\n", encoding="utf-8")
    missing_peer_doc = tmp_path / "missing-peer-earth-south.md"
    payload["context_bundle_docs"] = {
        "base_dir": str(tmp_path),
        "mission_path": mission_path.name,
        "scope_path": scope_path.name,
        "peer_project_docs": [
            {
                "project_id": "earth-south",
                "path": missing_peer_doc.name,
            }
        ],
    }

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", "-"],
        input=json.dumps(payload),
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
    payload = _load_fixture_payload()
    _with_earth_sweep_stale_unhappy_path(payload)

    mission_path = tmp_path / "mission.md"
    scope_path = tmp_path / "scope.md"
    peer_path = tmp_path / "earth-south-peer.md"
    mission_path.write_text("mission\n", encoding="utf-8")
    scope_path.write_text("scope\n", encoding="utf-8")
    peer_path.write_text("peer\n", encoding="utf-8")
    payload["context_bundle_docs"] = {
        "base_dir": str(tmp_path),
        "mission_path": mission_path.name,
        "scope_path": scope_path.name,
        "peer_project_docs": [
            {
                "project_id": "earth-south",
                "path": peer_path.name,
            }
        ],
    }

    out_first = MODULE.run(payload)
    out_second = MODULE.run(payload)

    assert out_first["context_bundle_serialized"] == out_second["context_bundle_serialized"]
    assert json.loads(out_first["context_bundle_serialized"]) == out_first["context_bundle"]
    assert out_first["context_bundle"]["analysis_anchors"] == [
        "unmet_ecosystem_needs",
        "high_leverage_fit",
        "impact",
        "urgency",
    ]
    assert out_first["context_bundle"]["context_docs"]["mission"]["evidence_ref"] == (
        f"DOCREF:mission:{mission_path.resolve()}"
    )
