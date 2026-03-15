import json
from pathlib import Path

from scripts import strategy_context_sweep as sweep


def _previous_revision_payload() -> dict:
    return {
        "revision_id": "strategy-2026-03-14T08:00:00Z",
        "mission_scope": {
            "primary_objective": "Stabilize planner reliability",
            "focus_areas": ["contract coverage", "runtime readiness"],
            "constraints": {"task_floor": 400, "change_budget": "medium"},
        },
        "runtime_data": {
            "runtime_mode": "shared",
            "queue_backlog": 3,
            "blocked_cycles": 0,
            "active_incidents": [],
        },
        "ecosystem_signals": {
            "upstream_projects": [{"project_id": "prj.tetris", "signal": "stable"}],
            "risk_flags": ["none"],
        },
        "recommendations": [
            {
                "recommendation_id": "rec.scope-refresh",
                "summary": "Refresh mission/scope alignment with ecosystem evidence.",
                "anchors": ["mission_scope"],
            },
            {
                "recommendation_id": "rec.runtime-hardening",
                "summary": "Keep runtime lane stable for planner throughput.",
                "anchors": ["runtime_data"],
            },
            {
                "recommendation_id": "rec.ecosystem-signal-response",
                "summary": "Adjust integration priorities based on upstream signals.",
                "anchors": ["ecosystem_signals"],
            },
        ],
        "evidence_refs": [
            "strategy/history/strategy-2026-03-14T08:00:00Z/STRATEGY.json",
            "reports/runtime/runtime-status-2026-03-14.json",
        ],
    }


def _current_revision_payload() -> dict:
    return {
        "revision_id": "strategy-2026-03-15T08:00:00Z",
        "mission_scope": {
            "primary_objective": "Stabilize planner reliability",
            "focus_areas": ["contract coverage", "runtime readiness", "delta traceability"],
            "constraints": {"task_floor": 400, "change_budget": "tight"},
        },
        "runtime_data": {
            "runtime_mode": "isolated",
            "queue_backlog": 5,
            "blocked_cycles": 2,
            "active_incidents": ["runtime_contention"],
        },
        "ecosystem_signals": {
            "upstream_projects": [{"project_id": "prj.tetris", "signal": "degraded"}],
            "risk_flags": ["none", "integration_latency"],
        },
        "recommendations": [
            {
                "recommendation_id": "rec.scope-refresh",
                "summary": "Refresh mission/scope alignment with ecosystem evidence.",
                "anchors": ["mission_scope"],
            },
            {
                "recommendation_id": "rec.runtime-hardening",
                "summary": "Increase isolation to recover planner throughput.",
                "anchors": ["runtime_data"],
            },
            {
                "recommendation_id": "rec.ecosystem-signal-response",
                "summary": "Adjust integration priorities based on upstream signals.",
                "anchors": ["ecosystem_signals"],
            },
        ],
        "evidence_refs": [
            "strategy/current/STRATEGY.json",
            "reports/runtime/runtime-status-2026-03-15.json",
            "reports/ecosystem/signals-2026-03-15.json",
        ],
    }


def test_req010_change_detection_build_and_contract_validation():
    payload = sweep.build_change_detection_since_previous_strategy_revision(
        _previous_revision_payload(),
        _current_revision_payload(),
    )

    assert sweep.validate_change_detection_since_previous_strategy_revision(payload) == []
    assert payload["schema_version"] == "req-010.change-detection-since-previous-strategy-revision.v1"
    assert payload["change_summary"]["total_change_count"] > 0
    assert payload["change_summary"]["changed_sections"] == [
        "mission_scope",
        "runtime_data",
        "ecosystem_signals",
    ]

    detected_change_ids = set(payload["change_summary"]["change_ids"])
    referenced_change_ids = {
        change_id
        for row in payload["recommendation_deltas"]
        for change_id in row["change_ids"]
    }
    assert referenced_change_ids == detected_change_ids


def test_req010_fixture_and_sample_validate_against_contract():
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "change-detection-since-previous-strategy-revision.json"
    sample_path = (
        repo_root
        / "strategy"
        / "current"
        / "samples"
        / "REQ-010_change-detection-since-previous-strategy-revision.sample.json"
    )

    fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    sample_payload = json.loads(sample_path.read_text(encoding="utf-8"))

    assert sweep.validate_change_detection_since_previous_strategy_revision(fixture_payload) == []
    assert sweep.validate_change_detection_since_previous_strategy_revision(sample_payload) == []
    assert set(fixture_payload.keys()) == set(sample_payload.keys())


def test_req010_contract_doc_references_sample_structure():
    repo_root = Path(__file__).resolve().parents[2]
    contract_path = repo_root / "contracts" / "req" / "REQ-010_change-detection-since-previous-strategy-revision.md"
    contract_text = contract_path.read_text(encoding="utf-8")

    assert (
        "strategy/current/samples/REQ-010_change-detection-since-previous-strategy-revision.sample.json"
        in contract_text
    )
