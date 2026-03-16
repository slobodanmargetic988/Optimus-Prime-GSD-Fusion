from scripts import strategy_llm_pipeline as pipeline

import json
import shutil
from pathlib import Path


def _reset_call_trace() -> None:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    if trace_path.exists():
        trace_path.unlink()
    artifacts_dir = Path("strategy/current/llm_call_trace_artifacts")
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)


def _read_last_trace_row() -> dict:
    trace_path = Path("strategy/current/llm_call_trace.jsonl")
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert lines
    return json.loads(lines[-1])


def test_req027_processing_emits_evidence_gated_links_and_complete_recommendation() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_027_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T12:00:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/workspace/projects/optimus-prime-gsd-fusion",
        },
        "peer_projects": [
            {"project_id": "earth-ops", "project_root": "/workspace/projects/Earth/earth-ops"},
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [
                "reports/earth/sweeps/2026-03-14/portfolio.json",
            ],
            "earth_sweep": {
                "projects": [
                    {
                        "project_id": "earth-ops",
                        "obligations": [
                            {
                                "summary": "Adopt shared release tag format for handoff reports.",
                                "earth_sweep_evidence_refs": [
                                    "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json",
                                ],
                            }
                        ],
                        "unresolved_ideas": [
                            {"idea": "Pilot multi-region failover runbook", "evidence_refs": []}
                        ],
                    }
                ]
            },
            "cross_project_context": [
                {
                    "project_id": "earth-ops",
                    "project_root": "/workspace/projects/Earth/earth-ops",
                    "evidence_refs": [
                        "reports/earth/sweeps/2026-03-14/earth-ops.json",
                    ],
                    "context_note": "Earth-wide context for shared release conventions.",
                }
            ],
        },
    }

    result = pipeline.process_req_027_call_2_ecosystem_linkage_reasoning(payload)

    assert result["ok"] is True
    assert result["schema_version"] == pipeline.REQ_027_PROCESSING_SCHEMA_VERSION
    assert pipeline.validate_req_027_call_2_ecosystem_linkage_reasoning(
        {
            "ok": True,
            "schema_version": pipeline.REQ_027_SCHEMA_VERSION,
            "requirement_id": pipeline.REQ_027_REQUIREMENT_ID,
            "analysis_type": pipeline.REQ_027_ANALYSIS_TYPE,
            "call_id": pipeline.REQ_027_CALL_ID,
            "checked_at_utc": result["checked_at_utc"],
            "target_project": result["target_project"],
            "peer_projects": result["peer_projects"],
            "linkage_reasoning": result["linkage_reasoning"],
            "totals": result["totals"],
        }
    ) == []

    processing = result["processing_behavior"]
    usage = processing["context_usage"]
    recommendation = processing["recommendation"]

    expected_recommendation_fields = {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "recommended_actions",
        "cross_project_obligations",
        "open_risks",
    }
    assert set(recommendation.keys()) == expected_recommendation_fields
    assert usage["cross_project_context_used"] is True
    assert usage["earth_sweep_context_used"] is True
    assert "earth-ops" in usage["cross_project_projects_considered"]

    assert "reports/earth/sweeps/2026-03-14/portfolio.json" in recommendation["evidence_refs"]
    assert recommendation["cross_project_obligations"]

    proposed = result["linkage_reasoning"]["proposed_links"]
    assert proposed
    obligation_refs = proposed[0]["interaction_obligations"][0]["evidence_refs"]
    assert "reports/earth/sweeps/2026-03-14/portfolio.json" in obligation_refs

    row = _read_last_trace_row()
    assert row["requirement_id"] == pipeline.REQ_027_REQUIREMENT_ID
    assert row["call_id"] == pipeline.REQ_027_CALL_ID
    assert row["call_objective"]
    assert row["input_refs"]
    assert row["output_refs"]
    assert row["handoff_summary"]
    assert row["artifacts"]
    for artifact in row["artifacts"]:
        assert Path(artifact["path"]).exists()


def test_req027_processing_without_earth_sweep_evidence_refs_does_not_invent_obligations() -> None:
    _reset_call_trace()
    payload = {
        "analysis_type": pipeline.REQ_027_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T12:00:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/workspace/projects/optimus-prime-gsd-fusion",
        },
        "peer_projects": [
            {"project_id": "earth-ops", "project_root": "/workspace/projects/Earth/earth-ops"},
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": [],
            "earth_sweep": {
                "projects": [
                    {
                        "project_id": "earth-ops",
                        "obligations": [
                            {
                                "summary": "Coordinate release conventions with peer.",
                                "earth_sweep_evidence_refs": [
                                    "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json",
                                ],
                            }
                        ],
                    }
                ]
            },
        },
    }

    result = pipeline.process_req_027_call_2_ecosystem_linkage_reasoning(payload)
    recommendation = result["processing_behavior"]["recommendation"]

    assert result["linkage_reasoning"]["proposed_links"] == []
    assert recommendation["decision"] == "collect-earth-evidence"
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])

    row = _read_last_trace_row()
    assert row["totals"]["proposed_links"] == 0
    assert "reports/earth-ops/planning/evidence/TASK-042/TASK_EVIDENCE.json" in row["output_refs"]
