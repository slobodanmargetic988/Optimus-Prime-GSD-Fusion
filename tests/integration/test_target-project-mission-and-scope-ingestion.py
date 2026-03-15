from __future__ import annotations

from scripts.strategy_context_sweep import ingest_target_project_mission_scope


def test_broad_sweep_context_produces_evidence_gated_recommendations() -> None:
    payload = {
        "target_project": {
            "mission": {"text": "Deliver deterministic strategy recommendations.", "source": "mission.md"},
            "scope": {"text": "Constrain recommendations to verified planning inputs.", "source": "scope.md"},
        },
        "broad_sweep_context": {
            "earth_sweep": {
                "projects": [
                    {
                        "project_id": "earth-ops",
                        "obligations": [
                            {
                                "summary": "Adopt shared release tag format for handoff reports.",
                                "earth_sweep_evidence_refs": [
                                    "./reports\\earth-ops\\planning\\evidence\\TASK-042\\TASK_EVIDENCE.json",
                                    "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json",
                                ],
                            },
                            {"summary": "Mirror dashboards to analytics cluster", "evidence_refs": []},
                        ],
                        "unresolved_ideas": [
                            {"idea": "Pilot multi-region failover runbook", "evidence_refs": []}
                        ],
                    }
                ]
            }
        },
    }

    result = ingest_target_project_mission_scope(payload)

    assert result["ok"] is True
    assert result["reason_codes"] == []
    assert result["context_ingestion"]["cross_project_context_used"] is True
    assert result["context_ingestion"]["cross_project_inputs_considered"] == 1
    assert result["context_ingestion"]["earth_sweep_evidence_refs"] == [
        "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json"
    ]

    recommendation_generation = result["recommendation_generation"]
    assert recommendation_generation["recommendation_fields_complete"] is True
    assert recommendation_generation["required_recommendation_fields"] == [
        "target_project_constraints",
        "context_ingestion",
        "recommendations",
    ]
    assert recommendation_generation["cross_project_context_used"] is True

    recommendations = result["recommendations"]
    assert recommendations["action_items"] == [
        {
            "source_project": "earth-ops",
            "recommendation": "Adopt shared release tag format for handoff reports.",
            "earth_sweep_evidence_refs": [
                "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json"
            ],
        }
    ]
    assert recommendations["open_risks"] == [
        {
            "risk_code": "missing_earth_sweep_evidence_refs",
            "source_project": "earth-ops",
            "item": "Mirror dashboards to analytics cluster",
            "resolution_hint": "attach Earth-sweep evidence refs before promotion",
        },
        {
            "risk_code": "unresolved_cross_project_idea",
            "source_project": "earth-ops",
            "item": "Pilot multi-region failover runbook",
            "earth_sweep_evidence_refs": [],
            "resolution_hint": "triage idea before implementation",
        },
    ]


def test_missing_scope_is_rejected_with_explicit_reason_code() -> None:
    result = ingest_target_project_mission_scope(
        {
            "target_project": {
                "mission": "Mission exists",
            }
        }
    )

    assert result["ok"] is False
    assert "scope_missing" in result["reason_codes"]
    assert result["errors"] == [
        {
            "reason_code": "scope_missing",
            "message": "target_project.scope is required",
        }
    ]
