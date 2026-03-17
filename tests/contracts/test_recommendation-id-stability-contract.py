import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-id-stability-contract.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-053_recommendation-id-stability-contract.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-053_recommendation-id-stability-contract.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_053_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_053_recommendation_id_stability_contract(fixture_payload)

    assert module.validate_req_053_recommendation_id_stability_contract(built_payload) == []
    assert module.validate_req_053_recommendation_id_stability_contract(sample_payload) == []
    assert built_payload == sample_payload
    assert built_payload["totals"] == {
        "baseline_recommendations": 2,
        "scenario_count": 2,
        "stable_results": 3,
        "evolved_results": 1,
        "added_results": 0,
        "removed_results": 0,
        "open_risk_count": 1,
    }


def test_req_053_contract_proves_stable_and_evolved_paths() -> None:
    payload = _read_json(SAMPLE_PATH)["recommendation_id_stability"]
    scenario_results = {row["scenario_id"]: row for row in payload["scenario_results"]}

    assert payload["stability_basis_fields"] == [
        "summary",
        "rationale",
        "packet_kind",
        "peer_project_id",
        "lane",
        "priority",
    ]

    no_change = scenario_results["scenario.no-change"]
    assert no_change["stable_recommendation_ids"] == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
    ]
    assert no_change["evolved_recommendation_ids"] == []
    assert all(row["id_status"] == "stable" for row in no_change["recommendation_results"])

    substantive_change = scenario_results["scenario.substantive-change"]
    telemetry = next(
        row
        for row in substantive_change["recommendation_results"]
        if row["lineage_key"] == "lineage.telemetry-freshness"
    )
    runtime = next(
        row
        for row in substantive_change["recommendation_results"]
        if row["lineage_key"] == "lineage.runtime-canary-alignment"
    )

    assert runtime["id_status"] == "stable"
    assert telemetry["id_status"] == "evolved"
    assert telemetry["baseline_recommendation_id"] == "rec.harden-telemetry-freshness"
    assert telemetry["scenario_recommendation_id"] == "rec.escalate-telemetry-freshness-guardrail"
    assert telemetry["changed_fields"] == ["summary", "rationale"]


def test_req_053_contract_carries_evidence_refs_context_usage_and_field_completeness() -> None:
    payload = _read_json(SAMPLE_PATH)["recommendation_id_stability"]

    usage = payload["cross_project_context_usage"]
    assert usage == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": ["earth-core-runtime", "earth-shared-observability"],
        "earth_sweep_evidence_refs_considered": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_obligation_count": 1,
        "unresolved_idea_count": 1,
        "recommendation_ids_with_context": [
            "rec.align-earth-runtime-canary",
            "rec.harden-telemetry-freshness",
        ],
    }

    expected_baseline_keys = {
        "lineage_key",
        "recommendation_id",
        "stability_key",
        "stability_basis",
        "evidence_refs",
        "earth_sweep_evidence_refs",
        "recommendation_field_completeness",
    }
    for row in payload["baseline_recommendations"]:
        assert set(row.keys()) == expected_baseline_keys
        assert row["evidence_refs"]
        assert row["recommendation_field_completeness"] == {
            "required_fields": [
                "lineage_key",
                "recommendation_id",
                "summary",
                "rationale",
                "packet_kind",
                "peer_project_id",
                "lane",
                "priority",
                "evidence_refs",
            ],
            "missing_fields": [],
            "all_fields_present": True,
        }

    runtime = next(
        row for row in payload["baseline_recommendations"] if row["recommendation_id"] == "rec.align-earth-runtime-canary"
    )
    telemetry = next(
        row for row in payload["baseline_recommendations"] if row["recommendation_id"] == "rec.harden-telemetry-freshness"
    )
    assert runtime["earth_sweep_evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
    ]
    assert telemetry["earth_sweep_evidence_refs"] == []

    assert payload["open_risks"] == [
        {
            "open_risk_id": "open-risk.5054fc9d54b5",
            "recommendation_id": "idea.telemetry-shared-observability-follow-up",
            "summary": "Validate earth-shared-observability ownership before coupling freshness guardrails to shared dashboards.",
            "reason_code": "unresolved_idea_open_risk",
            "project_id": "earth-shared-observability",
            "required_evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
            ],
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json"
            ],
            "linked_recommendation_ids": ["rec.harden-telemetry-freshness"],
            "call_trace_lineage": [],
            "contributing_call_ids": [],
        }
    ]


def test_req_053_contract_doc_references_documented_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-053_recommendation-id-stability-contract.sample.json" in contract_text
    for key in (
        "recommendation_id_stability.stability_basis_fields",
        "recommendation_id_stability.baseline_recommendations",
        "recommendation_id_stability.scenario_results",
        "recommendation_id_stability.scenario_results[].recommendation_results",
        "recommendation_id_stability.cross_project_context_usage",
        "recommendation_id_stability.open_risks",
        "totals",
    ):
        assert key in contract_text


def test_req_053_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(fixture_payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stderr == ""
    assert json.loads(proc.stdout) == _read_json(SAMPLE_PATH)


def test_req_053_builder_rejects_substantive_change_that_reuses_id() -> None:
    fixture_payload = deepcopy(_read_json(FIXTURE_PATH))
    telemetry = fixture_payload["rerun_scenarios"][1]["recommendations"][1]
    telemetry["recommendation_id"] = "rec.harden-telemetry-freshness"

    with pytest.raises(ValueError, match=r"without changing recommendation_id"):
        module.build_req_053_recommendation_id_stability_contract(fixture_payload)


def test_req_053_builder_rejects_missing_evidence_refs() -> None:
    fixture_payload = deepcopy(_read_json(FIXTURE_PATH))
    fixture_payload["baseline_revision"]["recommendations"][0]["evidence_refs"] = []

    with pytest.raises(ValueError, match=r"baseline_revision\.recommendations\[0\]\.evidence_refs must be a non-empty list of strings"):
        module.build_req_053_recommendation_id_stability_contract(fixture_payload)
