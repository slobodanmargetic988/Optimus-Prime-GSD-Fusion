import importlib.util
import json
import os
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


def test_integration_runtime_sweep_populates_recommendation_with_evidence_and_cross_project_context(
    tmp_path: Path,
) -> None:
    payload = _load_fixture_payload(tmp_path)
    _seed_artifacts(payload)

    out = MODULE.run(payload)
    recommendation = out["recommendation"]
    source_references = out["source_references"]
    source_ref_map = {row["citation_id"]: row for row in source_references}

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "evidence_refs",
        "cross_project_context",
        "obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "proceed_with_caution"
    assert recommendation["rationale"]
    assert recommendation["open_risks"] == []

    evidence_refs = recommendation["evidence_refs"]
    assert evidence_refs
    assert all(citation_id in source_ref_map for citation_id in evidence_refs)

    evidence_projects = {source_ref_map[citation_id]["project_id"] for citation_id in evidence_refs}
    assert evidence_projects == {"earth-north", "earth-south"}

    context = recommendation["cross_project_context"]
    assert context["cross_project"] is True
    assert context["projects_considered"] == ["earth-north", "earth-south"]
    assert context["projects_with_missing_sources"] == ["earth-south"]
    assert context["projects_with_stale_sources"] == ["earth-north", "earth-south"]
    assert set(context["evidence_refs_by_project"].keys()) == {"earth-north", "earth-south"}
    assert context["artifact_coverage_by_project"]["earth-north"]["runtime_traces"] == 2
    assert context["artifact_coverage_by_project"]["earth-south"]["cycle_summaries"] == 2

    obligations = recommendation["obligations"]
    assert obligations
    for row in obligations:
        assert row["obligation_id"]
        assert row["summary"]
        assert row["evidence_refs"]
        assert all(citation_id in source_ref_map for citation_id in row["evidence_refs"])


def test_integration_runtime_sweep_records_open_risk_when_cross_project_context_is_unavailable(
    tmp_path: Path,
) -> None:
    payload = _load_fixture_payload(tmp_path)
    payload["projects"] = [payload["projects"][0]]
    _seed_artifacts(payload)

    out = MODULE.run(payload)
    recommendation = out["recommendation"]

    assert recommendation["cross_project_context"]["cross_project"] is False
    assert recommendation["cross_project_context"]["projects_considered"] == ["earth-north"]
    assert any(row["risk_id"] == "RISK-0004" for row in recommendation["open_risks"])
