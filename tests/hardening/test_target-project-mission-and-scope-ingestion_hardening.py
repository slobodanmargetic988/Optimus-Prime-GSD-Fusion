from __future__ import annotations

from scripts.strategy_context_sweep import ingest_target_project_mission_scope


def test_stale_source_artifact_during_earth_sweep_is_rejected_with_reason_code() -> None:
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
                        "source_artifact": {
                            "status": "stale",
                            "evidence_refs": [
                                "./reports\\earth-ops\\planning\\evidence\\TASK-042\\TASK_EVIDENCE.json"
                            ],
                        },
                    }
                ]
            }
        },
    }

    result = ingest_target_project_mission_scope(payload)

    assert result["ok"] is False
    assert result["reason_codes"] == ["stale_source_artifact_detected"]
    assert result["errors"] == [
        {
            "reason_code": "stale_source_artifact_detected",
            "message": "earth_sweep.projects[earth-ops] contains stale source artifact metadata",
            "evidence_refs": [
                "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json"
            ],
        }
    ]


def test_missing_mission_scope_or_peer_project_doc_emits_explicit_reason_codes() -> None:
    missing_mission_scope_result = ingest_target_project_mission_scope({"target_project": {}})

    assert missing_mission_scope_result["ok"] is False
    assert missing_mission_scope_result["reason_codes"] == ["mission_missing", "scope_missing"]
    assert missing_mission_scope_result["errors"] == [
        {"reason_code": "mission_missing", "message": "target_project.mission is required"},
        {"reason_code": "scope_missing", "message": "target_project.scope is required"},
    ]

    missing_peer_doc_payload = {
        "target_project": {
            "mission": {"text": "Mission", "source": "mission.md"},
            "scope": {"text": "Scope", "source": "scope.md"},
        },
        "broad_sweep_context": {
            "earth_sweep": {
                "projects": [
                    {
                        "project_id": "earth-ops",
                        "requires_peer_project_doc": True,
                        "peer_project_doc": "   ",
                        "earth_sweep_evidence_refs": [
                            "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json"
                        ],
                    }
                ]
            }
        },
    }

    missing_peer_doc_result = ingest_target_project_mission_scope(missing_peer_doc_payload)

    assert missing_peer_doc_result["ok"] is False
    assert missing_peer_doc_result["reason_codes"] == ["peer_project_doc_missing"]
    assert missing_peer_doc_result["errors"] == [
        {
            "reason_code": "peer_project_doc_missing",
            "message": "earth_sweep.projects[earth-ops].peer_project_doc is required",
            "evidence_refs": [
                "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json"
            ],
        }
    ]


def test_context_bundle_serialization_is_stable_across_replay_runs() -> None:
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
                                    "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json"
                                ],
                            }
                        ],
                        "unresolved_ideas": [
                            {
                                "idea": "Pilot multi-region failover runbook",
                                "evidence_refs": [],
                            }
                        ],
                    }
                ]
            }
        },
    }

    first = ingest_target_project_mission_scope(payload)
    second = ingest_target_project_mission_scope(payload)
    third = ingest_target_project_mission_scope(payload)

    assert first["ok"] is True
    assert second["ok"] is True
    assert third["ok"] is True
    assert first["reason_codes"] == []
    assert second["reason_codes"] == []
    assert third["reason_codes"] == []
    assert first["context_bundle"]["canonical_json"] == second["context_bundle"]["canonical_json"]
    assert second["context_bundle"]["canonical_json"] == third["context_bundle"]["canonical_json"]
    assert first["context_bundle"]["sha256"] == second["context_bundle"]["sha256"] == third["context_bundle"]["sha256"]
