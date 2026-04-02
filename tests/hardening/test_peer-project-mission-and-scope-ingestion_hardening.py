import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_context_sweep.py"
SPEC = importlib.util.spec_from_file_location("strategy_context_sweep", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "examples" / "fixtures" / "peer-project-mission-and-scope-ingestion.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req004_stale_source_artifact_in_earth_sweep_emits_reason_code_and_evidence_ref():
    payload = _load_fixture()
    stale_ref = next(
        item
        for item in payload["earth_sweep_context"]["evidence_refs"]
        if item["peer_project_id"] == "op-tools-strategy"
        and item["source_path"] == "op-tools/strategy/mission.md"
        and item["line_number"] == 2
    )
    stale_ref["source_sha256"] = "f" * 64

    out = MODULE.ingest_peer_project_mission_and_scope(payload, generated_at="2026-03-14T00:00:00Z")

    assert out["summary"]["recommendation_count"] == 7
    assert out["summary"]["open_risk_count"] == 1
    stale_risk = out["open_risks"][0]
    assert stale_risk["risk_type"] == "stale_earth_sweep_source_artifact"
    assert stale_risk["reason_code"] == "stale_earth_sweep_source_artifact_detected"
    assert stale_risk["required_context_match_keys"] == [
        "op-tools-strategy:op-tools/strategy/mission.md:2"
    ]
    assert stale_risk["evidence_refs"] == ["earth-sweep/op-tools-strategy/mission#L2"]


def test_req004_missing_mission_scope_or_peer_documents_emits_explicit_reason_codes():
    payload = _load_fixture()
    for peer in payload["peer_projects"]:
        if peer["project_id"] == "op-tools-strategy":
            peer["documents"] = [
                doc for doc in peer["documents"] if doc.get("document_type") != "scope"
            ]
        if peer["project_id"] == "op-tools-research":
            peer.pop("documents", None)

    out = MODULE.ingest_peer_project_mission_and_scope(payload, generated_at="2026-03-14T00:00:00Z")

    reason_codes = {row["reason_code"] for row in out["open_risks"]}
    assert "missing_peer_project_documents" in reason_codes
    assert "missing_peer_mission_or_scope_document" in reason_codes

    missing_docs_risk = next(
        row for row in out["open_risks"] if row["reason_code"] == "missing_peer_project_documents"
    )
    assert missing_docs_risk["source_project_id"] == "op-tools-research"
    assert missing_docs_risk["evidence_refs"] == ["peer-project/op-tools-research/documents#missing"]

    missing_type_risk = next(
        row for row in out["open_risks"] if row["reason_code"] == "missing_peer_mission_or_scope_document"
    )
    assert missing_type_risk["source_project_id"] == "op-tools-strategy"
    assert missing_type_risk["missing_document_types"] == ["scope"]
    assert missing_type_risk["evidence_refs"]


def test_req004_context_bundle_serialization_is_replay_stable():
    payload = _load_fixture()
    first = MODULE.ingest_peer_project_mission_and_scope(payload, generated_at="2026-03-14T00:00:00Z")
    second = MODULE.ingest_peer_project_mission_and_scope(payload, generated_at="2026-03-15T00:00:00Z")

    first_bundle = first["context_bundle"]
    second_bundle = second["context_bundle"]
    assert first_bundle["serialization"] == second_bundle["serialization"]
    assert first_bundle["serialization_sha256"] == second_bundle["serialization_sha256"]

    parsed = json.loads(first_bundle["serialization"])
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert first_bundle["serialization"] == canonical
