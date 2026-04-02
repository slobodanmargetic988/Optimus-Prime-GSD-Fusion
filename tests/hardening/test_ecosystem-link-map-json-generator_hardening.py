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


def _earth_backed_broad_sweep_context() -> dict:
    return {
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


def _extend_with_second_cross_project_recommendation(payload: dict) -> dict:
    extended = deepcopy(payload)
    second_recommendation = {
        "recommendation_id": "rec.align-earth-runtime-telemetry",
        "summary": "Align telemetry handoff ownership with earth-core-runtime before wider rollout.",
        "rationale": "Shared runtime telemetry ownership should stay synchronized across the canary lane.",
        "packet_kind": "cross-project",
        "peer_project_id": "earth-core-runtime",
        "lane": "telemetry",
        "sequence_hint": 3,
        "priority": "medium",
        "evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/runtime/telemetry/freshness-gap-2026-03-15.json",
        ],
        "call_trace_lineage": [],
        "contributing_call_ids": [
            "call-2",
        ],
        "contributing_requirement_ids": [
            "REQ-027",
        ],
        "supporting_call_count": 1,
        "strategy_packet_input_id": "pkt.req050.telemetry",
    }
    second_packet_input = {
        "packet_input_id": "pkt.req050.telemetry",
        "packet_kind": "cross-project",
        "target_project_id": "optimus-prime-gsd-fusion",
        "peer_project_id": "earth-core-runtime",
        "lane": "telemetry",
        "recommendation_ids": [
            "rec.align-earth-runtime-telemetry",
        ],
        "recommendation_count": 1,
        "earliest_sequence_hint": 3,
        "evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/runtime/telemetry/freshness-gap-2026-03-15.json",
        ],
    }
    extended["final_strategy_synthesis"]["final_recommendations"].append(second_recommendation)
    extended["final_strategy_synthesis"]["strategy_packet_inputs"].append(second_packet_input)
    extended["broad_sweep_context"]["earth_sweep"]["projects"][0]["obligations"].append(
        {
            "summary": "Telemetry ownership alignment stays active with earth-core-runtime.",
            "recommendation_ids": ["rec.align-earth-runtime-telemetry"],
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            ],
        }
    )
    return extended


def test_req_050_hardening_artifact_regeneration_has_no_semantic_drift_on_no_change_rerun() -> None:
    payload = _load_fixture_payload()
    payload["broad_sweep_context"] = _earth_backed_broad_sweep_context()

    first_processing = module.process_req_050_ecosystem_link_map_json_generator(payload)
    second_processing = module.process_req_050_ecosystem_link_map_json_generator(payload)
    first_artifact = module.build_req_050_ecosystem_link_map_json_generator(payload)
    second_artifact = module.build_req_050_ecosystem_link_map_json_generator(payload)

    assert first_processing == second_processing
    assert first_artifact == second_artifact
    assert first_artifact["ecosystem_link_map"]["open_risks"] == second_artifact["ecosystem_link_map"]["open_risks"]
    assert first_artifact["ecosystem_link_map"]["evidence_refs"] == second_artifact["ecosystem_link_map"]["evidence_refs"]


def test_req_050_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    payload = _load_fixture_payload()
    payload["broad_sweep_context"] = _earth_backed_broad_sweep_context()
    payload = _extend_with_second_cross_project_recommendation(payload)

    processing = module.process_req_050_ecosystem_link_map_json_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]
    proposed_links = recommendation["proposed_links"]
    completeness_rows = recommendation["recommendation_field_completeness"]["rows"]
    proposed_by_recommendation_id = {
        row["source_recommendation_id"]: row
        for row in proposed_links
    }
    planner_hook_mapping = {
        row["source_recommendation_id"]: {
            "link_id": row["link_id"],
            "fields_complete": row["fields_complete"],
            "missing_fields": row["missing_fields"],
            "obligation_status": proposed_by_recommendation_id[row["source_recommendation_id"]]["obligation_status"],
            "evidence_refs": list(proposed_by_recommendation_id[row["source_recommendation_id"]]["evidence_refs"]),
        }
        for row in completeness_rows
    }

    assert set(planner_hook_mapping) == {
        "rec.align-earth-runtime-canary",
        "rec.align-earth-runtime-telemetry",
    }
    assert recommendation["recommendation_field_completeness"]["complete_count"] == 2
    assert recommendation["recommendation_field_completeness"]["incomplete_count"] == 0
    assert {row["source_recommendation_id"] for row in recommendation["recommended_actions"]} == set(planner_hook_mapping)
    assert all(row["fields_complete"] for row in planner_hook_mapping.values())
    assert all(not row["missing_fields"] for row in planner_hook_mapping.values())


def test_req_050_hardening_acceptance_packet_includes_required_evidence_refs_and_open_risk_handling() -> None:
    payload = _load_fixture_payload()
    payload["final_strategy_synthesis"]["open_risks"] = []
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
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        ],
        "cross_project_context": [
            {
                "project_id": "earth-core-runtime",
                "evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                ],
                "context_note": "Earth context exists, but the recommendation still lacks Earth-backed evidence refs.",
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
                    "unresolved_ideas": [],
                }
            ]
        },
    }

    processing = module.process_req_050_ecosystem_link_map_json_generator(payload)
    artifact = module.build_req_050_ecosystem_link_map_json_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]
    missing_earth_rows = [
        row
        for row in recommendation["open_risks"]
        if row["reason_code"] == "missing_earth_sweep_evidence_refs"
    ]
    acceptance_packet = {
        "artifact_ref": artifact["ecosystem_link_map"]["artifact_path"],
        "evidence_refs": list(artifact["ecosystem_link_map"]["evidence_refs"]),
        "open_risk_rows": [
            {
                "open_risk_id": row["open_risk_id"],
                "reason_code": row["reason_code"],
                "required_evidence_refs": list(row["required_evidence_refs"]),
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in recommendation["open_risks"]
        ],
        "unresolved_blocker_rows": [],
    }

    assert recommendation["decision"] == "collect-earth-evidence"
    assert len(missing_earth_rows) == 1
    assert acceptance_packet["artifact_ref"] == module.REQ_050_ARTIFACT_PATH
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in acceptance_packet["evidence_refs"]
    assert "reports/local/canary-alignment-notes.json" in acceptance_packet["evidence_refs"]
    assert acceptance_packet["open_risk_rows"] == [
        {
            "open_risk_id": "open-risk.missing-earth-evidence.rec.align-earth-runtime-canary",
            "reason_code": "missing_earth_sweep_evidence_refs",
            "required_evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            ],
            "evidence_refs": [
                "reports/local/canary-alignment-notes.json",
            ],
        }
    ]
    assert acceptance_packet["unresolved_blocker_rows"] == []
