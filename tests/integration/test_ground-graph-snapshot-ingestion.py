import json
from pathlib import Path

import pytest

from scripts.strategy_context_sweep import (
    load_ground_graph_snapshot,
    load_json_object,
    process_ground_graph_snapshot,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "ground-graph-snapshot-ingestion.json"
BROAD_CONTEXT_FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "ground-graph-snapshot-broad-context.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-007_ground-graph-snapshot-processing.sample.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_007_processing_uses_ground_graph_lineage_and_broad_context() -> None:
    snapshot = load_ground_graph_snapshot(SNAPSHOT_FIXTURE_PATH)
    broad_context = load_json_object(BROAD_CONTEXT_FIXTURE_PATH)

    output = process_ground_graph_snapshot(
        snapshot,
        broad_sweep_context=broad_context,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        ingested_at="2026-03-14T22:00:00Z",
    )

    assert set(output.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "ingested_at",
        "source_artifact",
        "lineage_anchors",
        "lineage_index",
        "cross_project_context",
        "evidence_refs",
        "recommendation",
    }

    assert output["cross_project_context"]["linked_projects"] == output["lineage_index"]["linked_project_ids"]

    # Explicit evidence-ref checks: Earth sweep refs are retained and recommendation refs
    # are a deterministic subset that actually backs supported actions.
    assert output["evidence_refs"]["earth_sweep"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]
    assert output["evidence_refs"]["recommendation"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
    ]

    recommendation = output["recommendation"]
    assert set(recommendation.keys()) == {
        "decision",
        "summary",
        "supported_actions",
        "deferred_actions",
        "open_risks",
        "evidence_refs",
    }
    assert recommendation["decision"] == "planning_with_open_risks"
    assert recommendation["evidence_refs"] == output["evidence_refs"]["recommendation"]

    supported = recommendation["supported_actions"]
    assert len(supported) == 1
    assert supported[0]["linked_project_id"] == "earth-core-runtime"
    assert supported[0]["evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
    ]
    assert supported[0]["lineage_anchor_ids"] == [
        "optimus-prime-gsd-fusion::era-2026-q1::plan-canary-001::phase-implementation::run-042::earth-core-runtime::depends_on"
    ]

    open_risks = recommendation["open_risks"]
    assert len(open_risks) == 2
    assert [risk["reason"] for risk in open_risks] == [
        "candidate_linked_project_missing_from_ground_graph",
        "candidate_action_missing_earth_sweep_evidence_refs",
    ]

    # Missing-evidence ideas must remain open risks and cannot be silently promoted.
    assert not any(item["linked_project_id"] == "shared-observability" for item in supported)
    assert any(
        risk["linked_project_id"] == "shared-observability"
        and risk["reason"] == "candidate_action_missing_earth_sweep_evidence_refs"
        for risk in open_risks
    )


def test_req_007_processing_sample_matches_fixture_processing_output() -> None:
    snapshot = load_ground_graph_snapshot(SNAPSHOT_FIXTURE_PATH)
    broad_context = load_json_object(BROAD_CONTEXT_FIXTURE_PATH)
    expected = process_ground_graph_snapshot(
        snapshot,
        broad_sweep_context=broad_context,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        ingested_at="2026-03-14T22:00:00Z",
    )
    sample = _read_json(SAMPLE_PATH)
    assert sample == expected


def test_req_007_processing_requires_active_project_id() -> None:
    snapshot = load_ground_graph_snapshot(SNAPSHOT_FIXTURE_PATH)
    broad_context = load_json_object(BROAD_CONTEXT_FIXTURE_PATH)
    broad_context.pop("active_project_id")

    with pytest.raises(ValueError, match=r"active_project_id"):
        process_ground_graph_snapshot(snapshot, broad_sweep_context=broad_context)
