from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-md-generator.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


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
    return payload


def test_req051_builder_validates_and_matches_run_entrypoint() -> None:
    payload = _load_fixture_payload()

    built_payload = module.build_req_051_strategy_changelog_md_generator(payload)

    assert module.validate_req_051_strategy_changelog_md_generator(built_payload) == []
    assert module.run(payload) == built_payload
    assert built_payload["strategy_changelog_md"]["artifact_path"] == module.REQ_051_ARTIFACT_PATH
    assert built_payload["totals"]["changelog_entries"] == 2
    assert built_payload["totals"]["open_risks"] == 2


def test_req051_builder_rejects_incomplete_change_coverage() -> None:
    payload = _load_fixture_payload()
    payload["change_summary"]["change_ids"].append("chg.runtime_data.sequence-gap")
    payload["change_summary"]["total_change_count"] = len(payload["change_summary"]["change_ids"])

    try:
        module.build_req_051_strategy_changelog_md_generator(payload)
    except ValueError as exc:
        assert "change_summary.change_ids must be fully covered" in str(exc)
    else:
        raise AssertionError("expected build_req_051_strategy_changelog_md_generator to reject uncovered change ids")


def test_req051_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    fixture_payload = _load_fixture_payload()
    expected = module.build_req_051_strategy_changelog_md_generator(fixture_payload)
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(fixture_payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert json.loads(proc.stdout) == expected
