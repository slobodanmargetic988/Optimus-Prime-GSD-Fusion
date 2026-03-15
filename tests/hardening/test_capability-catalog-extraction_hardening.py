import importlib.util
import json
import os
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

FRESH_AGE_SECONDS = 10


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


def _seed_artifact(
    payload: dict,
    *,
    project_id: str,
    artifact_key: str,
    age_seconds: int,
) -> str:
    now_utc = _parse_utc(payload["now_utc"])
    project = next(row for row in payload["projects"] if row["project_id"] == project_id)
    project_root = Path(project["root_path"])
    relative_path = project["artifacts"][artifact_key]
    _write_with_age(project_root, relative_path, now_utc=now_utc, age_seconds=age_seconds)
    return str((project_root / relative_path).resolve())


def _seed_all_fresh(payload: dict) -> None:
    for project in payload["projects"]:
        for artifact_key in ("plan_packets", "state", "roadmap", "requirements"):
            _seed_artifact(
                payload,
                project_id=project["project_id"],
                artifact_key=artifact_key,
                age_seconds=FRESH_AGE_SECONDS,
            )


def _risk_by_id(out: dict) -> dict[str, dict]:
    return {str(row["risk_id"]): row for row in out["recommendation"]["open_risks"]}


def test_hardening_req013_detects_stale_source_artifact_during_earth_sweep(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_all_fresh(payload)
    stale_ref = _seed_artifact(
        payload,
        project_id="earth-north",
        artifact_key="plan_packets",
        age_seconds=payload["stale_after_seconds"]["plan_packets"] + 1,
    )

    out = MODULE.run(payload)

    stale_risk = _risk_by_id(out)["earth-north:plan_packets:stale"]
    assert stale_risk["risk_type"] == "stale_artifact"
    assert stale_risk["reason_code"] == "stale_source_artifact_detected"
    assert stale_risk["evidence_refs"] == [stale_ref]
    assert (
        next(row for row in out["projects"] if row["project_id"] == "earth-north")["artifacts"]["plan_packets"]["freshness"]
        == "stale"
    )


def test_hardening_req013_emits_reason_codes_for_missing_mission_scope_and_peer_docs(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_all_fresh(payload)

    south = next(row for row in payload["projects"] if row["project_id"] == "earth-south")
    (Path(south["root_path"]) / south["artifacts"]["requirements"]).unlink(missing_ok=True)
    (Path(south["root_path"]) / south["artifacts"]["roadmap"]).unlink(missing_ok=True)

    out = MODULE.run(payload)
    risk_map = _risk_by_id(out)

    missing_requirements = risk_map["earth-south:requirements:missing"]
    missing_roadmap = risk_map["earth-south:roadmap:missing"]
    assert missing_requirements["risk_type"] == "missing_artifact"
    assert missing_requirements["reason_code"] == "missing_mission_scope_doc"
    assert missing_roadmap["risk_type"] == "missing_artifact"
    assert missing_roadmap["reason_code"] == "missing_peer_project_doc"


def test_hardening_req013_replay_stable_context_bundle_serialization(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_all_fresh(payload)
    _seed_artifact(
        payload,
        project_id="earth-north",
        artifact_key="state",
        age_seconds=payload["stale_after_seconds"]["state"] + 1,
    )
    south = next(row for row in payload["projects"] if row["project_id"] == "earth-south")
    (Path(south["root_path"]) / south["artifacts"]["roadmap"]).unlink(missing_ok=True)

    run_one = MODULE.run(json.loads(json.dumps(payload)))
    run_two = MODULE.run(json.loads(json.dumps(payload)))

    context_bundle_one = {
        "cross_project_context": run_one["cross_project_context"],
        "recommendation": run_one["recommendation"],
        "capability_catalog": run_one["capability_catalog"],
        "earth_sweep_evidence_refs": run_one["earth_sweep_evidence_refs"],
    }
    context_bundle_two = {
        "cross_project_context": run_two["cross_project_context"],
        "recommendation": run_two["recommendation"],
        "capability_catalog": run_two["capability_catalog"],
        "earth_sweep_evidence_refs": run_two["earth_sweep_evidence_refs"],
    }
    assert json.dumps(context_bundle_one, sort_keys=True, separators=(",", ":")) == json.dumps(
        context_bundle_two, sort_keys=True, separators=(",", ":")
    )
    assert [
        (row.get("risk_id"), row.get("reason_code"))
        for row in run_one["recommendation"]["open_risks"]
        if row.get("risk_type") in {"stale_artifact", "missing_artifact"}
    ] == [
        (row.get("risk_id"), row.get("reason_code"))
        for row in run_two["recommendation"]["open_risks"]
        if row.get("risk_type") in {"stale_artifact", "missing_artifact"}
    ]
