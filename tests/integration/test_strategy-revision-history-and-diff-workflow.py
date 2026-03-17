import copy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-revision-history-and-diff-workflow.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_069_integration_emits_complete_recommendation_with_evidence_refs_and_context_usage() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_069_strategy_revision_history_and_diff_workflow(fixture["input"])
    assert module.validate_req_069_strategy_revision_history_and_diff_workflow(payload) == []

    processing = payload["processing_behavior"]
    usage = processing["cross_project_context_usage"]
    recommendation = processing["recommendation"]

    assert usage == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": ["ground-control-hub", "runtime-orchestrator"],
        "earth_sweep_evidence_refs_considered": [
            "reports/earth/sweeps/2026-03-16/ground-control-hub.json",
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        ],
        "diff_ids_with_cross_project_context": ["diff.runtime.r15-r16", "diff.scope.r15-r16"],
        "cross_project_obligation_count": 1,
        "open_risk_count": 1,
        "evidence_refs_used": [
            "reports/earth/sweeps/2026-03-16/ground-control-hub.json",
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            "reports/governance/reviews/GR-204-runtime-lane.md",
            "reports/runtime/runtime-status-2026-03-15.json#queue_backlog",
            "reports/runtime/runtime-status-2026-03-15.json#telemetry_staleness",
            "reports/runtime/runtime-status-2026-03-16.json#worker_parallelism",
            "strategy/current/STRATEGY.json#constraints.change_budget",
            "strategy/history/strategy-2026-03-15/STRATEGY.json#constraints.task_floor",
        ],
    }

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["confidence"] == "medium"
    assert recommendation["rationale"] == "diffs=4 review_required=2 obligations=1 open_risks=1"
    assert recommendation["evidence_refs"] == usage["evidence_refs_used"]

    for row in recommendation["recommended_actions"]:
        assert set(row.keys()) == {
            "action_id",
            "diff_id",
            "action_scope",
            "summary",
            "rationale",
            "next_step",
            "evidence_refs",
        }
        assert row["summary"]
        assert row["rationale"]
        assert row["next_step"]
        assert row["evidence_refs"]

    assert recommendation["cross_project_obligations"] == [
        {
            "obligation_id": "obligation.diff.runtime.r15-r16.ground-control-hub",
            "diff_id": "diff.runtime.r15-r16",
            "project_id": "ground-control-hub",
            "summary": (
                "Apply reviewed directional shift 'diff.runtime.r15-r16' using broad-sweep context for project "
                "'ground-control-hub'."
            ),
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-16/ground-control-hub.json",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
            ],
        }
    ]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk.diff.scope.r15-r16.governance-review",
            "diff_id": "diff.scope.r15-r16",
            "summary": (
                "Directional shift for diff 'diff.scope.r15-r16' is blocked until governance review evidence is "
                "attached."
            ),
            "reason_code": "blocked_needs_governance_review",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/ground-control-hub.json",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                "strategy/current/STRATEGY.json#constraints.change_budget",
            ],
        }
    ]


def test_req_069_integration_records_open_risk_when_earth_refs_are_missing() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload_input = copy.deepcopy(fixture["input"])
    payload_input["broad_sweep_context"]["earth_sweep_evidence_refs"] = []

    payload = module.build_req_069_strategy_revision_history_and_diff_workflow(payload_input)
    assert module.validate_req_069_strategy_revision_history_and_diff_workflow(payload) == []

    usage = payload["processing_behavior"]["cross_project_context_usage"]
    recommendation = payload["processing_behavior"]["recommendation"]

    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_evidence_refs_considered"] == []
    assert usage["cross_project_obligation_count"] == 0
    assert usage["open_risk_count"] == 2

    assert recommendation["decision"] == "collect-earth-evidence"
    assert recommendation["cross_project_obligations"] == []
    assert {row["reason_code"] for row in recommendation["open_risks"]} == {
        "blocked_needs_governance_review",
        "missing_earth_sweep_evidence_refs",
    }
