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


def test_req051_processing_uses_broad_sweep_context_and_reports_complete_recommendation_fields() -> None:
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

    processing = module.process_req_051_strategy_changelog_md_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]
    context_usage = processing["processing_behavior"]["context_usage"]

    assert processing["ok"] is True
    assert processing["schema_version"] == module.REQ_051_SCHEMA_VERSION
    assert processing["artifact_kind"] == module.REQ_051_ARTIFACT_KIND
    assert context_usage["cross_project_context_provided"] is True
    assert context_usage["cross_project_context_used"] is True
    assert context_usage["projects_considered"] == ["earth-core-runtime"]
    assert context_usage["cross_project_obligation_count"] == 1
    assert context_usage["unresolved_idea_count"] == 1
    assert context_usage["recommendation_ids_with_context"] == ["rec.align-earth-runtime-canary"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in context_usage[
        "earth_sweep_evidence_refs_considered"
    ]

    assert recommendation["recommendation_field_completeness"]["incomplete_count"] == 0
    assert recommendation["recommendation_field_completeness"]["complete_count"] == 2
    assert recommendation["cross_project_obligations"]
    assert recommendation["strategic_direction_changes"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in recommendation["evidence_refs"]
    assert "strategy/history/strategy-2026-03-15T08:00:00Z/STRATEGY.json" in recommendation["evidence_refs"]
    assert any(row["reason_code"] == "unresolved_idea_open_risk" for row in recommendation["open_risks"])

    entry = next(
        row
        for row in recommendation["changelog_entries"]
        if row["recommendation_id"] == "rec.align-earth-runtime-canary"
    )
    assert entry["direction_status"] == "active"
    assert entry["linked_context_project_ids"] == ["earth-core-runtime"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in entry["evidence_refs"]

    changelog_payload = module.build_req_051_strategy_changelog_md_generator(payload)
    strategy_changelog = changelog_payload["strategy_changelog_md"]

    assert module.validate_req_051_strategy_changelog_md_generator(changelog_payload) == []
    assert strategy_changelog["artifact_path"] == "strategy/current/STRATEGY_CHANGELOG.md"
    assert strategy_changelog["entries"]
    assert strategy_changelog["strategic_direction_changes"]
    assert strategy_changelog["cross_project_context_usage"]["projects_considered"] == ["earth-core-runtime"]
    assert "## Changed Recommendations" in strategy_changelog["markdown"]
    assert "rec.align-earth-runtime-canary" in strategy_changelog["markdown"]


def test_req051_processing_does_not_emit_cross_project_obligations_without_earth_evidence_refs() -> None:
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
    delta = next(
        row
        for row in payload["recommendation_deltas"]
        if row["recommendation_id"] == "rec.align-earth-runtime-canary"
    )
    delta["evidence_refs"] = [
        "reports/local/canary-alignment-notes.json",
        "strategy/history/strategy-2026-03-15T08:00:00Z/STRATEGY.json",
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

    processing = module.process_req_051_strategy_changelog_md_generator(payload)
    recommendation = processing["processing_behavior"]["recommendation"]

    assert recommendation["cross_project_obligations"] == []
    assert recommendation["decision"] == "collect-earth-evidence"
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in recommendation["open_risks"])

    entry = next(
        row
        for row in recommendation["changelog_entries"]
        if row["recommendation_id"] == "rec.align-earth-runtime-canary"
    )
    assert entry["direction_status"] == "withheld"

    changelog_payload = module.build_req_051_strategy_changelog_md_generator(payload)
    strategy_changelog = changelog_payload["strategy_changelog_md"]
    assert strategy_changelog["cross_project_context_usage"]["cross_project_context_used"] is True
    assert any(row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in strategy_changelog["open_risks"])
    assert "withheld" in strategy_changelog["markdown"]
