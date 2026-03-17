import json
from pathlib import Path

import pytest

from scripts.strategy_context_sweep import detect_overlap_and_conflicts


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "overlap-and-conflict-detection.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-017_overlap-and-conflict-detection.sample.json"
CONTRACT_DOC_PATH = REPO_ROOT / "contracts" / "req" / "REQ-017_overlap-and-conflict-detection.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_017_detects_overlaps_and_conflicts_with_resolution_tradeoffs() -> None:
    payload = _read_json(FIXTURE_PATH)
    output = detect_overlap_and_conflicts(payload, evaluated_at="2026-03-15T03:10:00Z")

    assert set(output.keys()) == {
        "requirement_id",
        "surface",
        "schema_version",
        "evaluated_at",
        "active_project_id",
        "related_project_ids",
        "overlap_index",
        "overlapping_initiatives",
        "conflicting_directions",
        "cross_project_context",
        "evidence_refs",
        "recommendation",
        "decision",
        "summary",
    }
    assert output["requirement_id"] == "REQ-017"
    assert output["surface"] == "overlap_and_conflict_detection"
    assert output["schema_version"] == "req-017.overlap-and-conflict-detection.v1"
    assert output["evaluated_at"] == "2026-03-15T03:10:00Z"
    assert output["decision"] == "conflicts_detected"

    overlaps = output["overlapping_initiatives"]
    conflicts = output["conflicting_directions"]
    assert len(overlaps) == 2
    assert len(conflicts) == 2
    assert {row["risk_level"] for row in conflicts} == {"high", "medium"}
    assert output["evidence_refs"]["earth_sweep"] == [
        "reports/earth/sweeps/earth-core-runtime/roadmap-2026-q2.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]

    cross_project_context = output["cross_project_context"]
    assert cross_project_context["cross_project_context_used"] is True
    assert cross_project_context["earth_sweep_context_used"] is True
    assert cross_project_context["projects_considered"] == [
        "earth-core-runtime",
        "shared-observability",
    ]
    assert cross_project_context["related_project_context"] == [
        {
            "project_id": "earth-core-runtime",
            "context_note": "Earth sweep shows runtime-signals migration pressure during the same delivery window.",
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/roadmap-2026-q2.json",
            ],
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/roadmap-2026-q2.json",
            ],
            "out_of_scope_evidence_refs": [],
            "overlap_ids": ["overlap-001"],
            "conflict_ids": ["conflict-001"],
        },
        {
            "project_id": "shared-observability",
            "context_note": "Observability budget controls intersect dispatch-safety rollout timing.",
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "out_of_scope_evidence_refs": [],
            "overlap_ids": ["overlap-002"],
            "conflict_ids": ["conflict-002"],
        },
    ]
    assert cross_project_context["unresolved_direction_ideas"] == [
        {
            "idea_id": "idea-shared-observability-budget-gate",
            "project_id": "shared-observability",
            "summary": "Confirm whether telemetry budget gating should defer dispatch-safety rollout until exporter cost controls land.",
            "related_conflict_ids": ["conflict-002"],
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "out_of_scope_evidence_refs": [],
        }
    ]

    for overlap in overlaps:
        assert "earth_sweep_evidence_refs" in overlap
        assert "out_of_scope_evidence_refs" in overlap

    for conflict in conflicts:
        assert conflict["resolution_options"]
        assert "earth_sweep_evidence_refs" in conflict
        assert "out_of_scope_evidence_refs" in conflict
        for option in conflict["resolution_options"]:
            assert option["option_id"]
            assert option["summary"]
            assert option["risk_tradeoff"]

    recommendation = output["recommendation"]
    assert recommendation["decision"] == "planning_with_open_risks"
    assert len(recommendation["conflict_resolution_recommendations"]) == 2
    assert len(recommendation["cross_project_obligations"]) == 2
    assert len(recommendation["open_risks"]) == 1
    for row in recommendation["conflict_resolution_recommendations"]:
        assert row["recommendation_id"]
        assert row["summary"]
        assert row["risk_level"]
        assert row["resolution_options"]
        assert row["evidence_refs"]


def test_req_017_sample_matches_detection_output_for_fixture() -> None:
    payload = _read_json(FIXTURE_PATH)
    expected = detect_overlap_and_conflicts(payload, evaluated_at="2026-03-15T03:10:00Z")
    sample = _read_json(SAMPLE_PATH)
    assert sample == expected


def test_req_017_contract_doc_includes_sample_structure_reference() -> None:
    content = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-017_overlap-and-conflict-detection.sample.json" in content
    for key in [
        "requirement_id",
        "surface",
        "schema_version",
        "evaluated_at",
        "active_project_id",
        "related_project_ids",
        "overlap_index",
        "overlapping_initiatives",
        "conflicting_directions",
        "cross_project_context",
        "evidence_refs",
        "recommendation",
        "decision",
        "summary",
    ]:
        assert f"`{key}`" in content


def test_req_017_rejects_initiative_project_outside_related_scope() -> None:
    payload = _read_json(FIXTURE_PATH)
    bad_payload = dict(payload)
    initiatives = list(bad_payload["initiatives"])
    first = dict(initiatives[0])
    first["project_id"] = "unrelated-project"
    initiatives[0] = first
    bad_payload["initiatives"] = initiatives

    with pytest.raises(ValueError, match=r"active_project_id or related_project_ids"):
        detect_overlap_and_conflicts(bad_payload, evaluated_at="2026-03-15T03:10:00Z")


def test_req_017_rejects_project_context_outside_related_scope() -> None:
    payload = _read_json(FIXTURE_PATH)
    bad_payload = dict(payload)
    bad_context = dict(payload["broad_sweep_context"])
    bad_context["project_context"] = [
        {
            "project_id": "unrelated-project",
            "context_note": "Nope",
            "evidence_refs": [],
        }
    ]
    bad_payload["broad_sweep_context"] = bad_context

    with pytest.raises(ValueError, match=r"project_context\[0\]\.project_id must reference related_project_ids"):
        detect_overlap_and_conflicts(bad_payload, evaluated_at="2026-03-15T03:10:00Z")
