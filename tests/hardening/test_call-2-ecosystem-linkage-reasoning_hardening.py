from __future__ import annotations

from scripts import strategy_llm_pipeline as pipeline


def test_hardening_cross_call_contradiction_between_linkage_and_recommendation_emits_reason_code() -> None:
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
    }

    out = pipeline.process_req_027_call_2_ecosystem_linkage_reasoning(payload)

    assert out["totals"]["missing_links"] == 1
    recommendation = out["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "resolve-context-gaps"
    assert any(
        row["reason_code"] == "analysis_synthesis_contradiction_missing_links"
        for row in recommendation["open_risks"]
    )


def test_hardening_uncited_strategic_claim_is_blocked_by_citation_discipline() -> None:
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
            "cross_project_context": [
                {
                    "project_id": "earth-ops",
                    "project_root": "/workspace/projects/Earth/earth-ops",
                    "evidence_refs": [],
                    "context_note": "Earth-wide coordination obligations exist but are not yet cited.",
                }
            ]
        },
    }

    out = pipeline.process_req_027_call_2_ecosystem_linkage_reasoning(payload)

    assert out["totals"]["existing_links"] == 0
    assert out["totals"]["missing_links"] == 1
    recommendation = out["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "resolve-context-gaps"
    assert any(row["reason_code"] == "uncited_strategic_claim" for row in recommendation["open_risks"])


def test_hardening_call_chain_replay_produces_stable_recommendation_ids_and_ordering() -> None:
    payload_first = {
        "analysis_type": pipeline.REQ_027_ANALYSIS_TYPE,
        "now_utc": "2026-03-16T12:00:00Z",
        "target_project": {
            "project_id": "optimus-prime-gsd-fusion",
            "project_root": "/workspace/projects/optimus-prime-gsd-fusion",
        },
        "peer_projects": [
            {"project_id": "earth-runtime", "project_root": "/workspace/projects/Earth/earth-runtime"},
            {"project_id": "earth-metrics", "project_root": "/workspace/projects/Earth/earth-metrics"},
            {"project_id": "earth-ops", "project_root": "/workspace/projects/Earth/earth-ops"},
            {"project_id": "earth-analytics", "project_root": "/workspace/projects/Earth/earth-analytics"},
        ],
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": ["reports/earth/sweeps/2026-03-14/portfolio.json"],
            "earth_sweep": {
                "projects": [
                    {
                        "project_id": "earth-runtime",
                        "obligations": [
                            "not-a-mapping-obligation",
                            {
                                "summary": "Define shared observability contract for runtime telemetry.",
                                "evidence_refs": [],
                            },
                        ],
                        "unresolved_ideas": [],
                    },
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
                    },
                ]
            },
            "cross_project_context": [
                {
                    "project_id": "earth-ops",
                    "project_root": "/workspace/projects/Earth/earth-ops",
                    "evidence_refs": ["reports/earth/sweeps/2026-03-14/earth-ops.json"],
                    "context_note": "Earth-wide context for shared release conventions.",
                }
            ],
        },
    }

    payload_second = {
        **payload_first,
        "now_utc": "2026-03-17T00:00:00Z",
        "peer_projects": list(reversed(payload_first["peer_projects"])),
        "broad_sweep_context": {
            **payload_first["broad_sweep_context"],
            "earth_sweep": {
                "projects": list(reversed(payload_first["broad_sweep_context"]["earth_sweep"]["projects"]))
            },
            "cross_project_context": list(
                reversed(payload_first["broad_sweep_context"]["cross_project_context"])
            ),
        },
    }

    out_first = pipeline.process_req_027_call_2_ecosystem_linkage_reasoning(payload_first)
    out_second = pipeline.process_req_027_call_2_ecosystem_linkage_reasoning(payload_second)

    rec_first = out_first["processing_behavior"]["recommendation"]
    rec_second = out_second["processing_behavior"]["recommendation"]

    assert rec_first["recommended_actions"] == rec_second["recommended_actions"]
    assert rec_first["open_risks"] == rec_second["open_risks"]
    assert rec_first["cross_project_obligations"] == rec_second["cross_project_obligations"]
