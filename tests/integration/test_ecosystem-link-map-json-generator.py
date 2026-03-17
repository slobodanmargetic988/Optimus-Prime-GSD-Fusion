from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-md-generator.json"


def _load_fixture_payload() -> dict:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["analysis_type"] = module.REQ_050_ANALYSIS_TYPE
    return payload


def test_req050_processing_uses_broad_sweep_context_and_reports_complete_recommendation_fields() -> None:
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
                            "evidence_refs": [
                                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                            ],
                        }
                    ],
                    "unresolved_ideas": [
                        {
                            "idea": "Confirm shared telemetry ownership model.",
                            "recommendation_ids": ["rec.align-earth-runtime-canary"],
                            "evidence_refs": [
                                "reports/earth/sweeps/earth-core-runtime/open-idea-telemetry.json",
                            ],
                        }
                    ],
                }
            ]
        },
    }

    processing = module.process_req_050_ecosystem_link_map_json_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]
    context_usage = processing["processing_behavior"]["context_usage"]

    assert processing["ok"] is True
    assert processing["schema_version"] == module.REQ_050_SCHEMA_VERSION
    assert processing["artifact_kind"] == module.REQ_050_ARTIFACT_KIND
    assert context_usage["cross_project_context_provided"] is True
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["projects_considered"] == ["earth-core-runtime"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in context_usage[
        "earth_sweep_evidence_refs_considered"
    ]

    assert recommendation["recommendation_field_completeness"]["incomplete_count"] == 0
    assert recommendation["recommendation_field_completeness"]["complete_count"] == 1
    assert recommendation["cross_project_obligations"]
    assert recommendation["current_links"]
    assert recommendation["proposed_links"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in recommendation["evidence_refs"]
    assert any(row["reason_code"] == "unresolved_idea_open_risk" for row in recommendation["open_risks"])

    link_map_payload = module.build_req_050_ecosystem_link_map_json_generator(payload)
    link_map = link_map_payload["ecosystem_link_map"]

    assert module.validate_req_050_ecosystem_link_map_json_generator(link_map_payload) == []
    assert link_map["artifact_path"] == "strategy/current/ECOSYSTEM_LINK_MAP.json"
    assert link_map["current_links"]
    assert link_map["proposed_links"]
    assert link_map["confidence"]["overall"] in {"high", "medium", "low"}
    assert link_map["obligation_metadata"]["cross_project_obligations"] == 1


def test_req050_processing_does_not_emit_cross_project_obligations_without_earth_evidence_refs() -> None:
    payload = deepcopy(_load_fixture_payload())
    cross_project_recommendation = next(
        row
        for row in payload["final_strategy_synthesis"]["final_recommendations"]
        if row["packet_kind"] == "cross-project"
    )
    cross_project_recommendation["evidence_refs"] = [
        "reports/local/canary-alignment-notes.json",
    ]
    packet_input = next(
        row
        for row in payload["final_strategy_synthesis"]["strategy_packet_inputs"]
        if row["packet_kind"] == "cross-project"
    )
    packet_input["evidence_refs"] = [
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

    processing = module.process_req_050_ecosystem_link_map_json_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]

    assert recommendation["cross_project_obligations"] == []
    assert recommendation["decision"] == "collect-earth-evidence"
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])
    assert recommendation["proposed_links"][0]["obligation_status"] == "withheld"

    link_map_payload = module.build_req_050_ecosystem_link_map_json_generator(payload)
    link_map = link_map_payload["ecosystem_link_map"]
    assert link_map["obligation_metadata"]["withheld_obligations"] == 1
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in link_map["missing_links"])
