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

ARTIFACT_AGE_SECONDS = {
    "earth-north": {"plan_packets": 120, "state": 301, "roadmap": 86500, "requirements": 100},
    "earth-south": {"state": 10, "roadmap": 100, "requirements": 700000},
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
        ages = ARTIFACT_AGE_SECONDS.get(project_id, {})
        for artifact_key, age_seconds in ages.items():
            relative_path = project["artifacts"][artifact_key]
            _write_with_age(project_root, relative_path, now_utc=now_utc, age_seconds=age_seconds)


def test_req013_integration_capability_catalog_uses_earth_sweep_context(tmp_path: Path) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_artifacts(payload)

    north = next(project for project in payload["projects"] if project["project_id"] == "earth-north")
    south = next(project for project in payload["projects"] if project["project_id"] == "earth-south")
    north_plan_packets = str((Path(north["root_path"]) / north["artifacts"]["plan_packets"]).resolve())
    south_state = str((Path(south["root_path"]) / south["artifacts"]["state"]).resolve())
    payload["proposed_cross_project_obligations"] = [
        {
            "obligation_id": "earth-catalog-sync-001",
            "summary": "Use known Earth sweep evidence for catalog synchronization.",
            "project_ids": ["earth-north", "earth-south"],
            "evidence_refs": [north_plan_packets, south_state],
        },
        {
            "obligation_id": "earth-catalog-sync-002",
            "summary": "Proposed without Earth sweep evidence.",
            "project_ids": ["earth-north", "earth-west"],
            "evidence_refs": [],
        },
    ]

    out = MODULE.run(payload)
    out_repeat = MODULE.run(payload)

    assert out["ok"] is True
    assert out["tool"] == "strategy-context-sweep"
    assert out["tool_version"] == "1.1.0"
    assert out["earth_sweep_evidence_refs"] == out_repeat["earth_sweep_evidence_refs"]
    assert len(out["earth_sweep_evidence_refs"]) == 7
    assert all(Path(ref).is_absolute() for ref in out["earth_sweep_evidence_refs"])

    context = out["cross_project_context"]
    assert context == out_repeat["cross_project_context"]
    assert context["project_ids_considered"] == ["earth-north", "earth-south"]
    assert context["project_count"] == 2
    assert context["context_projects_used"] == ["earth-north", "earth-south"]
    assert context["projects_with_missing_context"] == ["earth-south"]
    assert sorted(context["projects_with_stale_context"]) == ["earth-north", "earth-south"]

    recommendation = out["recommendation"]
    assert recommendation == out_repeat["recommendation"]
    assert sorted(recommendation.keys()) == [
        "approved_cross_project_obligations",
        "context_project_ids",
        "decision",
        "evidence_refs",
        "open_risks",
        "rationale",
    ]
    assert recommendation["decision"] == "proceed_with_caution"
    assert recommendation["context_project_ids"] == ["earth-north", "earth-south"]
    assert recommendation["rationale"] == "projects=2 artifacts=8 fresh=4 stale=3 missing=1"
    assert recommendation["evidence_refs"]
    assert set(recommendation["evidence_refs"]).issubset(set(out["earth_sweep_evidence_refs"]))
    assert recommendation["approved_cross_project_obligations"] == [
        {
            "obligation_id": "earth-catalog-sync-001",
            "summary": "Use known Earth sweep evidence for catalog synchronization.",
            "project_ids": ["earth-north", "earth-south"],
            "evidence_refs": sorted([north_plan_packets, south_state]),
        }
    ]
    assert any(row["risk_type"] == "stale_artifact" for row in recommendation["open_risks"])
    assert any(row["risk_type"] == "missing_artifact" for row in recommendation["open_risks"])
    assert any(
        row["risk_type"] == "unresolved_cross_project_obligation"
        and row.get("obligation_id") == "earth-catalog-sync-002"
        and row["reason"] == "unknown_project_ids,missing_evidence_refs"
        for row in recommendation["open_risks"]
    )

    catalog = out["capability_catalog"]
    assert catalog == out_repeat["capability_catalog"]
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
    assert set(catalog["recommended_capability_ids"]).isdisjoint(
        set(catalog["already_completed_capability_ids"])
    )

    entries = {row["capability_id"]: row for row in catalog["catalog_entries"]}
    for capability_id in catalog["recommended_capability_ids"]:
        assert entries[capability_id]["availability"] == "missing"
        assert entries[capability_id]["provider_count"] == 0
        assert entries[capability_id]["providers"] == []

