from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-md-generator.json"


def _load_fixture_payload() -> dict:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["analysis_type"] = module.REQ_051_ANALYSIS_TYPE
    payload["revision_pair"] = {
        "previous_revision_id": "strategy-2026-03-15T08:00:00Z",
        "current_revision_id": "strategy-2026-03-16T09:15:00Z",
    }
    payload["change_summary"] = {
        "total_change_count": 4,
        "changed_sections": [
            "ecosystem_signals",
            "runtime_data",
        ],
        "change_ids": [
            "chg.ecosystem_signals.runtime-window",
            "chg.ecosystem_signals.telemetry-ownership",
            "chg.runtime_data.freshness-gap",
            "chg.runtime_data.rollout-window",
        ],
    }
    payload["recommendation_deltas"] = [
        {
            "recommendation_id": "rec.align-earth-runtime-canary",
            "summary": "Align the Earth runtime canary stabilization window before widening rollout.",
            "anchors": [
                "ecosystem_signals",
            ],
            "change_ids": [
                "chg.ecosystem_signals.runtime-window",
                "chg.ecosystem_signals.telemetry-ownership",
            ],
            "delta_type": "updated",
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                "strategy/history/strategy-2026-03-15T08:00:00Z/STRATEGY.json",
            ],
            "linked_context_project_ids": [
                "earth-core-runtime",
            ],
        },
        {
            "recommendation_id": "rec.harden-telemetry-freshness",
            "summary": "Harden telemetry freshness checks before the next autonomous canary pass.",
            "anchors": [
                "runtime_data",
            ],
            "change_ids": [
                "chg.runtime_data.freshness-gap",
                "chg.runtime_data.rollout-window",
            ],
            "delta_type": "updated",
            "evidence_refs": [
                "reports/runtime/telemetry/freshness-gap-2026-03-15.json",
                "strategy/history/strategy-2026-03-15T08:00:00Z/STRATEGY.json",
            ],
            "linked_context_project_ids": [],
        },
    ]
    return payload


def test_hardening_req051_no_change_rerun_regenerates_identical_artifact() -> None:
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

    first_processing = module.process_req_051_strategy_changelog_md_generator(payload)
    first_built = module.build_req_051_strategy_changelog_md_generator(payload)

    second_payload = deepcopy(payload)
    second_processing = module.process_req_051_strategy_changelog_md_generator(second_payload)
    second_built = module.build_req_051_strategy_changelog_md_generator(second_payload)

    assert first_processing == second_processing
    assert first_built == second_built
    assert first_built["strategy_changelog_md"]["markdown"] == second_built["strategy_changelog_md"]["markdown"]


def test_hardening_req051_planner_hook_receives_complete_recommendation_mapping_set() -> None:
    payload = _load_fixture_payload()
    payload["change_summary"] = {
        "total_change_count": 2,
        "changed_sections": [
            "runtime_data",
        ],
        "change_ids": [
            "chg.runtime_data.freshness-gap",
            "chg.runtime_data.rollout-window",
        ],
    }
    payload["recommendation_deltas"] = [
        row
        for row in payload["recommendation_deltas"]
        if row["recommendation_id"] == "rec.harden-telemetry-freshness"
    ]
    payload["final_strategy_synthesis"]["final_recommendations"] = [
        row
        for row in payload["final_strategy_synthesis"]["final_recommendations"]
        if row["recommendation_id"] == "rec.harden-telemetry-freshness"
    ]
    payload["final_strategy_synthesis"]["deferred_recommendations"] = []
    payload["final_strategy_synthesis"]["open_risks"] = []
    payload["final_strategy_synthesis"]["strategy_packet_inputs"] = [
        row
        for row in payload["final_strategy_synthesis"]["strategy_packet_inputs"]
        if row["packet_kind"] == "target-project"
    ]
    payload["broad_sweep_context"] = {
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_context": [
            {
                "project_id": "earth-shared-observability",
                "evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                ],
                "context_note": "Shared-observability context feeds the follow-up investigation.",
            }
        ],
        "earth_sweep": {
            "projects": [
                {
                    "project_id": "earth-shared-observability",
                    "obligations": [],
                    "unresolved_ideas": [
                        {
                            "idea": "Validate telemetry ownership before broadening the next canary.",
                            "recommendation_ids": ["rec.harden-telemetry-freshness"],
                            "evidence_refs": [
                                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                            ],
                        }
                    ],
                }
            ]
        },
    }

    processing = module.process_req_051_strategy_changelog_md_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]
    open_risk = next(
        row
        for row in recommendation["open_risks"]
        if row["reason_code"] == "unresolved_idea_open_risk"
    )
    entry = next(
        row
        for row in recommendation["changelog_entries"]
        if row["recommendation_id"] == "rec.harden-telemetry-freshness"
    )

    assert processing["processing_behavior"]["context_usage"]["recommendation_ids_with_context"] == [
        "rec.harden-telemetry-freshness"
    ]
    assert "reports/runtime/telemetry/freshness-gap-2026-03-15.json" in open_risk["evidence_refs"]
    assert "reports/quality/req-039-rationale-quality-score.json" in open_risk["evidence_refs"]
    assert "strategy/history/strategy-2026-03-15T08:00:00Z/STRATEGY.json" in open_risk["evidence_refs"]
    assert open_risk["open_risk_id"] in entry["linked_open_risk_ids"]


def test_hardening_req051_acceptance_packet_includes_required_evidence_refs_and_open_risk_handling() -> None:
    payload = _load_fixture_payload()
    cross_project_recommendation = next(
        row
        for row in payload["final_strategy_synthesis"]["final_recommendations"]
        if row["packet_kind"] == "cross-project"
    )
    cross_project_recommendation["evidence_refs"] = [
        "reports/local/canary-alignment-notes.json",
    ]
    cross_project_packet = next(
        row
        for row in payload["final_strategy_synthesis"]["strategy_packet_inputs"]
        if row["packet_kind"] == "cross-project"
    )
    cross_project_packet["evidence_refs"] = [
        "reports/local/canary-alignment-notes.json",
    ]
    delta = next(
        row
        for row in payload["recommendation_deltas"]
        if row["recommendation_id"] == "rec.align-earth-runtime-canary"
    )
    delta["evidence_refs"] = [
        "reports/local/canary-alignment-notes.json",
        "strategy/history/strategy-2026-03-15T08:00:00Z/STRATEGY.json",
    ]
    payload["final_strategy_synthesis"]["open_risks"] = []
    payload["broad_sweep_context"] = {
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-required.json",
        ],
        "cross_project_context": [
            {
                "project_id": "earth-core-runtime",
                "evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-required.json",
                ],
                "context_note": "Cross-project evidence remains required before the changelog can activate the link.",
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

    built = module.build_req_051_strategy_changelog_md_generator(payload)
    strategy_changelog = built["strategy_changelog_md"]
    open_risks = strategy_changelog["open_risks"]
    missing_evidence_risk = next(
        row
        for row in open_risks
        if row["reason_code"] == "missing_earth_sweep_evidence_refs"
    )
    unresolved_idea_risk = next(
        row
        for row in open_risks
        if row["reason_code"] == "unresolved_idea_open_risk"
    )
    entry = next(
        row
        for row in strategy_changelog["entries"]
        if row["recommendation_id"] == "rec.align-earth-runtime-canary"
    )

    assert module.validate_req_051_strategy_changelog_md_generator(built) == []
    assert missing_evidence_risk["required_evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-required.json",
    ]
    assert unresolved_idea_risk["required_evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-required.json",
    ]
    assert set(entry["linked_open_risk_ids"]) == {
        missing_evidence_risk["open_risk_id"],
        unresolved_idea_risk["open_risk_id"],
    }
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-required.json" in strategy_changelog["evidence_refs"]
    assert "reports/earth/sweeps/earth-core-runtime/open-idea-telemetry.json" in strategy_changelog["evidence_refs"]
    assert "Required evidence refs:" in strategy_changelog["markdown"]
