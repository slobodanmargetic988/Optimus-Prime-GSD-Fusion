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


def test_req004_ingestion_models_mission_scope_signals_only():
    payload = _load_fixture()
    out = MODULE.ingest_peer_project_mission_and_scope(payload, generated_at="2026-03-14T00:00:00Z")

    assert out["schema_version"] == "REQ-004-peer-project-mission-and-scope-ingestion.v1"
    assert out["generated_at"] == "2026-03-14T00:00:00Z"
    assert out["current_project_id"] == "optimus-prime-gsd-fusion"
    assert out["summary"]["peer_projects_evaluated"] == 2
    assert out["summary"]["peer_projects_with_signals"] == 2

    strategy_model = next(model for model in out["peer_project_models"] if model["peer_project_id"] == "op-tools-strategy")
    document_types = {item["document_type"] for item in strategy_model["ingested_documents"]}
    assert document_types == {"mission", "scope"}
    assert len(strategy_model["interaction_obligations"]) == 2
    assert len(strategy_model["reuse_opportunities"]) == 2


def test_req004_recommendations_preserve_provenance_for_every_inference():
    payload = _load_fixture()
    out = MODULE.ingest_peer_project_mission_and_scope(payload, generated_at="2026-03-14T00:00:00Z")

    recommendations = out["cross_project_recommendations"]
    assert out["summary"]["interaction_obligation_count"] == 4
    assert out["summary"]["reuse_opportunity_count"] == 4
    assert out["summary"]["recommendation_count"] == 8
    assert len(recommendations) == 8

    for recommendation in recommendations:
        assert recommendation["recommendation_type"] in {"interaction_obligation", "reuse_opportunity"}
        assert recommendation["target_project_id"] == "optimus-prime-gsd-fusion"
        provenance = recommendation["source_provenance"]
        assert isinstance(provenance, list) and provenance
        entry = provenance[0]
        assert entry["document_type"] in {"mission", "scope"}
        assert entry["source_path"].endswith(".md")
        assert isinstance(entry["line_number"], int) and entry["line_number"] > 0
        assert isinstance(entry["source_sha256"], str) and len(entry["source_sha256"]) == 64
        assert isinstance(entry["excerpt"], str) and entry["excerpt"]


def test_req004_cli_file_ingestion_writes_expected_sample_surface(tmp_path: Path):
    output_path = tmp_path / "REQ-004.sample.json"
    out = MODULE.ingest_peer_project_mission_and_scope_file(
        input_path=FIXTURE_PATH,
        output_path=output_path,
        generated_at="2026-03-14T00:00:00Z",
    )
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == out
    assert written["schema_version"] == "REQ-004-peer-project-mission-and-scope-ingestion.v1"
    assert written["summary"]["recommendation_count"] == 8
