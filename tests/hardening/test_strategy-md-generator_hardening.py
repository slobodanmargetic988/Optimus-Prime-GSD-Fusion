from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-md-generator.json"


def _load_fixture_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req048_hardening_strategy_md_regeneration_is_semantically_stable_on_no_change_rerun() -> None:
    payload = _load_fixture_payload()
    original_payload = deepcopy(payload)

    first = module.build_req_048_strategy_md_generator(payload)
    second = module.build_req_048_strategy_md_generator(payload)

    assert payload == original_payload
    assert first == second
    assert first["strategy_md"]["content_sha256"] == second["strategy_md"]["content_sha256"]
    assert first["strategy_md"]["line_count"] == second["strategy_md"]["line_count"]
    assert first["strategy_md"]["alignment"] == second["strategy_md"]["alignment"]


def test_req048_hardening_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    processing = module.process_req_048_strategy_md_generator(_load_fixture_payload())
    planner_hook = processing["processing_behavior"]["planner_hook"]

    assert planner_hook["recommendation_ids"] == [
        "idea.review-reuse-contracts-follow-up",
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
        "rec.review-reuse-contracts",
    ]
    assert planner_hook["strategy_packet_input_ids"] == [
        "pkt.9e0c566d663e",
        "pkt.c3c7c38214ae",
    ]

    mapping_by_id = {
        row["recommendation_id"]: row
        for row in planner_hook["recommendation_mapping_set"]
    }
    assert mapping_by_id["rec.harden-telemetry-freshness"] == {
        "recommendation_id": "rec.harden-telemetry-freshness",
        "source": "final_recommendation",
        "strategy_packet_input_id": "pkt.9e0c566d663e",
        "packet_kind": "target-project",
        "lane": "execution",
        "peer_project_id": "",
        "packet_recommendation_ids": ["rec.harden-telemetry-freshness"],
        "linked_open_risk_ids": [],
    }
    assert mapping_by_id["rec.align-earth-runtime-canary"] == {
        "recommendation_id": "rec.align-earth-runtime-canary",
        "source": "final_recommendation",
        "strategy_packet_input_id": "pkt.c3c7c38214ae",
        "packet_kind": "cross-project",
        "lane": "coordination",
        "peer_project_id": "earth-core-runtime",
        "packet_recommendation_ids": ["rec.align-earth-runtime-canary"],
        "linked_open_risk_ids": [],
    }
    assert mapping_by_id["rec.review-reuse-contracts"] == {
        "recommendation_id": "rec.review-reuse-contracts",
        "source": "deferred_recommendation",
        "strategy_packet_input_id": None,
        "packet_kind": "cross-project,target-project",
        "lane": "deferred",
        "peer_project_id": "earth-shared-observability",
        "packet_recommendation_ids": [],
        "linked_open_risk_ids": ["open-risk.c6d73dbb8f81"],
    }
    assert mapping_by_id["idea.review-reuse-contracts-follow-up"] == {
        "recommendation_id": "idea.review-reuse-contracts-follow-up",
        "source": "open_risk_only",
        "strategy_packet_input_id": None,
        "packet_kind": "open-risk-only",
        "lane": "risk-follow-up",
        "peer_project_id": "",
        "packet_recommendation_ids": [],
        "linked_open_risk_ids": ["open-risk.c6d73dbb8f81"],
    }


def test_req048_hardening_acceptance_packet_includes_required_evidence_refs_and_open_risk_handling() -> None:
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
                        }
                    ],
                    "unresolved_ideas": [],
                }
            ]
        },
    }

    processing = module.process_req_048_strategy_md_generator(payload)
    acceptance_packet = processing["processing_behavior"]["acceptance_packet"]

    assert acceptance_packet["decision"] == "collect-earth-evidence"
    assert acceptance_packet["recommendation_ids"] == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
    ]
    assert acceptance_packet["cross_project_recommendation_ids"] == []
    assert acceptance_packet["required_evidence_refs"] == [
        "contracts/req/REQ-016_reuse-opportunity-detection.md",
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        "reports/local/canary-alignment-notes.json",
        "reports/quality/req-039-rationale-quality-score.json",
        "reports/runtime/telemetry/freshness-gap-2026-03-15.json",
        "strategy/current/llm_call_trace.jsonl#call-2-001",
        "strategy/current/llm_call_trace.jsonl#call-5-001",
        "strategy/current/llm_call_trace.jsonl#rationale-quality-001",
        "strategy/current/llm_call_trace_artifacts/req-027/call-2/trace-call-2-001.json",
        "strategy/current/llm_call_trace_artifacts/req-030/call-5/trace-call-5-001.json",
        "strategy/current/llm_call_trace_artifacts/req-039/rationale-quality-001.json",
    ]
    assert acceptance_packet["open_risk_handling"] == {
        "status": "open_risks_present",
        "open_risk_ids": [
            "open-risk.c6d73dbb8f81",
            "open-risk.missing-earth-evidence.rec.align-earth-runtime-canary",
        ],
        "reason_codes": [
            "missing_earth_sweep_evidence_refs",
            "unresolved_idea_open_risk",
        ],
        "requires_operator_review": True,
    }
