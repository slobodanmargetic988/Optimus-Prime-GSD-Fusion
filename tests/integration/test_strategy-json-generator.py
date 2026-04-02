from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-json-generator.json"


def _load_fixture_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req049_processing_uses_broad_sweep_context_and_reports_complete_recommendation_fields() -> None:
    payload = _load_fixture_payload()
    payload["broad_sweep_context"] = {
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        ],
        "cross_project_context": [
            {
                "project_id": "earth-core-runtime",
                "evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                ],
                "context_note": "Earth runtime context supports cross-project sequencing.",
            }
        ],
        "earth_sweep": {
            "projects": [
                {
                    "project_id": "earth-core-runtime",
                    "obligations": [
                        {
                            "summary": "Coordinate canary stabilization with earth-core-runtime.",
                            "recommendation_ids": ["rec.align-earth-runtime-canary"],
                        }
                    ],
                    "unresolved_ideas": [
                        {
                            "idea": "Confirm shared telemetry ownership model.",
                            "recommendation_ids": ["rec.align-earth-runtime-canary"],
                        }
                    ],
                }
            ]
        },
    }

    processing = module.process_req_049_strategy_json_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]
    context_usage = processing["processing_behavior"]["context_usage"]

    assert context_usage["cross_project_context_provided"] is True
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["projects_considered"] == ["earth-core-runtime"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in context_usage[
        "earth_sweep_evidence_refs_considered"
    ]
    assert context_usage["cross_project_obligation_count"] == 1
    assert context_usage["unresolved_idea_count"] == 1
    assert context_usage["recommendation_ids_with_context"] == ["rec.align-earth-runtime-canary"]

    assert recommendation["recommendation_field_completeness"]["incomplete_count"] == 0
    assert recommendation["recommendation_field_completeness"]["complete_count"] == 2
    assert recommendation["cross_project_obligations"] == [
        {
            "project_id": "earth-core-runtime",
            "recommendation_id": "rec.align-earth-runtime-canary",
            "status": "active",
            "rationale": "Cross-project runtime canary alignment is required before widening rollout in the target project.",
            "impacts": [
                "Prevents rollout drift between target and peer runtime teams.",
                "Synchronizes runtime stabilization checkpoints across projects.",
            ],
            "risk_ids": [
                "risk.cross-project-rollout-drift",
                "risk.telemetry-freshness-regression",
            ],
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                "strategy/current/llm_call_trace_artifacts/req-027/call-2/trace-call-2-001.json",
            ],
        }
    ]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in recommendation["evidence_refs"]
    assert all(row["reason_code"] != "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])
    assert any(row["reason_code"] == "unresolved_idea_open_risk" for row in recommendation["open_risks"])

    strategy_payload = module.build_req_049_strategy_json_generator(payload)
    strategy_json = strategy_payload["strategy_json"]
    for row in strategy_json["recommendations"]:
        assert row["recommendation_id"]
        assert row["rationale"]
        assert row["impacts"]
        assert row["risk_ids"]
        assert row["evidence_refs"]


def test_req049_processing_does_not_emit_cross_project_obligations_without_earth_evidence_refs() -> None:
    payload = deepcopy(_load_fixture_payload())
    cross_project_recommendation = next(
        row
        for row in payload["recommendations"]
        if row["recommendation_id"] == "rec.align-earth-runtime-canary"
    )
    cross_project_recommendation["evidence_refs"] = [
        "reports/local/canary-alignment-notes.json",
    ]
    payload["broad_sweep_context"] = {
        "earth_sweep_evidence_refs": [],
        "cross_project_context": [
            {
                "project_id": "earth-core-runtime",
                "evidence_refs": [],
                "context_note": "Cross-project context exists, but Earth evidence refs are missing.",
            }
        ],
        "earth_sweep": {
            "projects": [
                {
                    "project_id": "earth-core-runtime",
                    "obligations": [
                        {
                            "summary": "Coordinate canary stabilization with earth-core-runtime.",
                            "recommendation_ids": ["rec.align-earth-runtime-canary"],
                            "evidence_refs": [],
                        }
                    ],
                    "unresolved_ideas": [],
                }
            ]
        },
    }

    processing = module.process_req_049_strategy_json_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]

    assert recommendation["cross_project_obligations"] == []
    assert recommendation["decision"] == "collect-earth-evidence"
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])
