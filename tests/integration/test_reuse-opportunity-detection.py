import json
from pathlib import Path

from scripts.strategy_context_sweep import detect_reuse_opportunities


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "reuse-opportunity-detection.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_016_integration_reuse_detection_emits_evidence_and_complete_recommendations() -> None:
    payload = _read_json(FIXTURE_PATH)
    output = detect_reuse_opportunities(payload, evaluated_at="2026-03-15T01:30:00Z")

    assert set(output.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "evaluated_at",
        "active_project_id",
        "reuse_index",
        "reuse_recommendations",
        "no_reuse_detected",
        "evidence_refs",
        "decision",
        "summary",
    }

    # Cross-project context usage: source projects are harvested from the broad-sweep payload,
    # and recommended candidates must never point back at the active project.
    assert output["reuse_index"]["source_project_ids"] == [
        "earth-core-runtime",
        "shared-observability",
    ]

    assert output["decision"] == "partial_reuse_recommended"
    assert output["evidence_refs"] == [
        "contracts/req/REQ-007_ground-graph-snapshot-ingestion.md",
        "strategy/current/samples/REQ-007_ground-graph-snapshot-ingestion.sample.json",
    ]

    recommendations = output["reuse_recommendations"]
    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation["capability_id"] == "ground-graph-snapshot-ingestion"
    assert recommendation["required_interfaces"] == ["json-canonical-v1", "lineage-anchor-index"]

    candidates = recommendation["reuse_candidates"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["source_project_id"] != output["active_project_id"]
    assert candidate["adoption_path"]
    assert candidate["compatibility_constraints"]

