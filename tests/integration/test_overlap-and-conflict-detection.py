import json
from pathlib import Path

from scripts.strategy_context_sweep import detect_overlap_and_conflicts


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "overlap-and-conflict-detection.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_017_integration_overlap_detection_uses_cross_project_context_and_evidence_partitions() -> None:
    payload = _read_json(FIXTURE_PATH)
    output = detect_overlap_and_conflicts(payload, evaluated_at="2026-03-15T03:10:00Z")

    assert output["decision"] == "conflicts_detected"
    assert output["cross_project_context"]["cross_project_context_used"] is True
    assert output["cross_project_context"]["earth_sweep_context_used"] is True
    assert output["cross_project_context"]["projects_considered"] == [
        "earth-core-runtime",
        "shared-observability",
    ]

    evidence_refs = output["evidence_refs"]
    assert evidence_refs["earth_sweep"] == [
        "reports/earth/sweeps/earth-core-runtime/roadmap-2026-q2.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]
    assert evidence_refs["recommendation"] == [
        "reports/earth/sweeps/earth-core-runtime/roadmap-2026-q2.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]
    assert evidence_refs["out_of_scope"] == [
        "contracts/req/REQ-006_runtime-telemetry-artifact-sweep-across-earth.md",
        "reports/optimus-prime/planning/evidence/TASK-052/runtime-signal-router.json",
        "strategy/current/samples/REQ-006_runtime-telemetry-artifact-sweep-across-earth.sample.json",
    ]

    recommendation = output["recommendation"]
    assert recommendation["decision"] == "planning_with_open_risks"
    assert recommendation["summary"] == (
        "2 evidence-backed conflict resolution recommendation(s); "
        "2 cross-project obligation(s); 1 open risk(s)."
    )
    assert len(recommendation["conflict_resolution_recommendations"]) == 2
    assert len(recommendation["cross_project_obligations"]) == 2
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-idea-shared-observability-budget-gate",
            "reason": "unresolved_direction_idea_open_risk",
            "reason_code": "unresolved_direction_idea_open_risk",
            "project_id": "shared-observability",
            "summary": "Confirm whether telemetry budget gating should defer dispatch-safety rollout until exporter cost controls land.",
            "related_conflict_ids": ["conflict-002"],
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "out_of_scope_evidence_refs": [],
        }
    ]

    for row in recommendation["conflict_resolution_recommendations"]:
        assert set(row.keys()) >= {
            "recommendation_id",
            "conflict_id",
            "summary",
            "project_ids",
            "shared_capability_tags",
            "overlap_window",
            "risk_level",
            "resolution_options",
            "evidence_refs",
        }
        assert row["evidence_refs"]
        for option in row["resolution_options"]:
            assert set(option.keys()) == {"option_id", "summary", "risk_tradeoff"}
