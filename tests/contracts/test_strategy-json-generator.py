from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-json-generator.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req049_builder_validates_fixture_and_preserves_machine_artifact_schema() -> None:
    payload = module.build_req_049_strategy_json_generator(_read_json(FIXTURE_PATH))

    assert module.validate_req_049_strategy_json_generator(payload) == []
    assert list(payload.keys()) == [
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "artifact_kind",
        "generated_at_utc",
        "target_project",
        "strategy_json",
        "totals",
    ]
    assert payload["artifact_kind"] == "STRATEGY.json"
    assert payload["target_project"] == {
        "project_id": "optimus-prime-gsd-fusion",
        "project_root": "/Users/slobodan/projects/Earth/Optimus-Prime-GSD-Fusion",
    }

    strategy_json = payload["strategy_json"]
    assert list(strategy_json.keys()) == [
        "artifact_path",
        "strategy_id",
        "revision",
        "generated_by",
        "source_requirement_ids",
        "recommendations",
        "risks",
        "evidence_refs",
    ]
    assert strategy_json["artifact_path"] == "strategy/current/STRATEGY.json"
    assert strategy_json["source_requirement_ids"] == ["REQ-038", "REQ-041", "REQ-046"]
    assert [row["recommendation_id"] for row in strategy_json["recommendations"]] == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
    ]
    assert [row["risk_id"] for row in strategy_json["risks"]] == [
        "risk.cross-project-rollout-drift",
        "risk.telemetry-freshness-regression",
    ]
    assert strategy_json["evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
        "reports/quality/req-039-rationale-quality-score.json",
        "reports/runtime/telemetry/freshness-gap-2026-03-15.json",
        "strategy/current/llm_call_trace_artifacts/req-027/call-2/trace-call-2-001.json",
    ]
    assert payload["totals"] == {
        "recommendations": 2,
        "risks": 2,
        "impacts": 4,
        "evidence_refs": 4,
    }


def test_req049_validator_rejects_strategy_evidence_refs_outside_recommendation_and_risk_union() -> None:
    payload = module.build_req_049_strategy_json_generator(_read_json(FIXTURE_PATH))
    broken = deepcopy(payload)
    broken["strategy_json"]["evidence_refs"] = sorted(
        [
            *broken["strategy_json"]["evidence_refs"],
            "reports/runtime/telemetry/unexpected-extra-ref.json",
        ]
    )
    broken["totals"]["evidence_refs"] = len(broken["strategy_json"]["evidence_refs"])

    errors = module.validate_req_049_strategy_json_generator(broken)

    assert (
        "strategy_json.evidence_refs must match the unique sorted union of recommendation and risk evidence refs"
        in errors
    )


def test_req049_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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
    assert json.loads(proc.stdout) == module.build_req_049_strategy_json_generator(fixture_payload)


def test_req049_builder_rejects_unknown_risk_ids() -> None:
    fixture_payload = deepcopy(_read_json(FIXTURE_PATH))
    fixture_payload["recommendations"][0]["risk_ids"] = [
        "risk.cross-project-rollout-drift",
        "risk.unknown-gap",
    ]

    with pytest.raises(
        ValueError,
        match=r"recommendations\[\]\.risk_ids must reference defined risks; unknown ids",
    ):
        module.build_req_049_strategy_json_generator(fixture_payload)
