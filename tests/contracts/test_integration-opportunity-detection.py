from pathlib import Path

import pytest

from scripts.strategy_context_sweep import detect_integration_opportunities, load_ground_graph_snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "ground-graph-snapshot-ingestion.json"


def test_req_015_detects_integration_opportunities_with_contract_and_side_effect_notes() -> None:
    snapshot = load_ground_graph_snapshot(SNAPSHOT_FIXTURE_PATH)
    broad_context = {
        "active_project_id": "optimus-prime-gsd-fusion",
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "integration_opportunity_candidates": [
            {
                "linked_project_id": "earth-core-runtime",
                "action": "Align canary rollout checkpoint with run-131 stabilization outputs.",
                "interaction_contract": {
                    "contract_ref": "contracts/req/REQ-007_ground-graph-snapshot-ingestion.md",
                    "expected_interactions": ["lineage-anchor-index", "json-canonical-v1"],
                },
                "dependency_side_effect_notes": "Requires updated stabilization timing; may shift verification window.",
                "evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                ],
            },
        ],
    }

    output = detect_integration_opportunities(
        snapshot,
        broad_sweep_context=broad_context,
        source_path="examples/fixtures/ground-graph-snapshot-ingestion.json",
        evaluated_at="2026-03-15T02:10:00Z",
    )

    assert set(output.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "evaluated_at",
        "source_artifact",
        "lineage_anchors",
        "lineage_index",
        "integration_context",
        "evidence_refs",
        "recommendation",
    }
    assert output["requirement_id"] == "REQ-015"
    assert output["surface"] == "integration_opportunity_detection"
    assert output["schema_version"] == "req-015.integration-opportunity-detection.v1"
    assert output["evaluated_at"] == "2026-03-15T02:10:00Z"

    recommendation = output["recommendation"]
    assert set(recommendation.keys()) == {
        "decision",
        "summary",
        "integration_opportunities",
        "deferred_opportunities",
        "open_risks",
        "evidence_refs",
    }

    opportunities = recommendation["integration_opportunities"]
    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity["linked_project_id"] == "earth-core-runtime"
    assert opportunity["interaction_contract"]["contract_ref"]
    assert opportunity["interaction_contract"]["expected_interactions"] == ["lineage-anchor-index", "json-canonical-v1"]
    assert opportunity["dependency_side_effect_notes"]
    assert opportunity["evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
    ]
    assert opportunity["lineage_anchor_ids"] == [
        "optimus-prime-gsd-fusion::era-2026-q1::plan-canary-001::phase-implementation::run-042::earth-core-runtime::depends_on"
    ]


def test_req_015_rejects_missing_active_project_id() -> None:
    snapshot = load_ground_graph_snapshot(SNAPSHOT_FIXTURE_PATH)
    broad_context = {"earth_sweep_evidence_refs": [], "integration_opportunity_candidates": []}

    with pytest.raises(ValueError, match=r"active_project_id"):
        detect_integration_opportunities(snapshot, broad_sweep_context=broad_context)
