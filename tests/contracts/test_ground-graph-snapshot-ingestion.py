import json
from pathlib import Path

import pytest

from scripts.strategy_context_sweep import ingest_ground_graph_snapshot, load_ground_graph_snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "ground-graph-snapshot-ingestion.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-007_ground-graph-snapshot-ingestion.sample.json"
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-007_ground-graph-snapshot-ingestion.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_007_ingestion_produces_canonical_lineage_surface() -> None:
    snapshot = load_ground_graph_snapshot(FIXTURE_PATH)
    output = ingest_ground_graph_snapshot(
        snapshot,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        ingested_at="2026-03-14T21:50:00Z",
    )

    assert set(output.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "ingested_at",
        "source_artifact",
        "lineage_anchors",
        "lineage_index",
    }
    assert output["requirement_id"] == "REQ-007"
    assert output["surface"] == "ground_graph_snapshot_ingestion"
    assert output["schema_version"] == "req-007.ground-graph-snapshot-ingestion.v1"
    assert output["ingested_at"] == "2026-03-14T21:50:00Z"

    anchors = output["lineage_anchors"]
    assert len(anchors) == 3
    assert [row["anchor_id"] for row in anchors] == sorted(row["anchor_id"] for row in anchors)
    assert all(
        set(row.keys())
        == {
            "anchor_id",
            "project_id",
            "era_id",
            "plan_id",
            "phase_id",
            "run_id",
            "linked_project_id",
            "relationship",
        }
        for row in anchors
    )

    assert output["lineage_index"] == {
        "project_ids": ["earth-core-runtime", "optimus-prime-gsd-fusion"],
        "era_ids": ["era-2026-q1"],
        "plan_ids": ["plan-canary-001", "plan-runtime-014"],
        "phase_ids": ["phase-implementation", "phase-stabilization", "phase-verification"],
        "run_ids": ["run-042", "run-043", "run-131"],
        "linked_project_ids": ["earth-core-runtime", "shared-observability"],
    }


def test_req_007_sample_matches_ingestion_output_for_fixture() -> None:
    fixture = load_ground_graph_snapshot(FIXTURE_PATH)
    expected = ingest_ground_graph_snapshot(
        fixture,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        ingested_at="2026-03-14T21:50:00Z",
    )
    sample = _read_json(SAMPLE_PATH)
    assert sample == expected


def test_req_007_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json" in content
    for key in [
        "requirement_id",
        "surface",
        "schema_version",
        "ingested_at",
        "source_artifact",
        "lineage_anchors",
        "lineage_index",
    ]:
        assert f"`{key}`" in content


def test_req_007_rejects_missing_run_id_anchor_field() -> None:
    fixture = load_ground_graph_snapshot(FIXTURE_PATH)
    bad_payload = dict(fixture)
    lineage_links = list(bad_payload["lineage_links"])
    first = dict(lineage_links[0])
    first.pop("run_id")
    lineage_links[0] = first
    bad_payload["lineage_links"] = lineage_links

    with pytest.raises(ValueError, match=r"run_id"):
        ingest_ground_graph_snapshot(bad_payload, source_path="broken.json", ingested_at="2026-03-14T21:50:00Z")
