import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-packet-v1-generator.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-052_strategy-packet-v1-generator.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-052_strategy-packet-v1-generator.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_artifacts_handoff.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_052_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = module.build_req_052_strategy_packet_v1_generator(fixture_payload)

    assert module.validate_req_052_strategy_packet_v1_generator(built_payload) == []
    assert module.validate_req_052_strategy_packet_v1_generator(sample_payload) == []
    assert built_payload == sample_payload
    assert built_payload["strategy_packet_v1"]["artifact_path"] == "strategy_packet.v1.json"
    assert built_payload["totals"]["recommendations"] == 2
    assert built_payload["strategy_packet_context"]["recommendation_readiness"][1]["earth_sweep_evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json"
    ]


def test_req_052_packet_preserves_required_top_level_sections_and_canonical_ids() -> None:
    payload = _read_json(SAMPLE_PATH)
    packet = payload["strategy_packet_v1"]["packet"]

    assert list(packet.keys()) == [
        "schema_version",
        "identity",
        "strategy",
        "recommendations",
        "constraints",
        "kpi_targets",
        "source",
    ]
    assert packet["schema_version"] == "strategy-packet.v1"
    assert packet["identity"] == {
        "project_id": "prj.optimus-prime-gsd-fusion",
        "run_id": "run.20260316t100500z-task185",
        "event_id": "event.20260316t100500z-strategy-packet",
        "era_id": "era.2026q1-canary-stabilization",
        "plan_id": "plan.optimus-prime-gsd-fusion-canary",
    }
    assert [row["recommendation_id"] for row in packet["recommendations"]] == [
        "rec.harden-telemetry-freshness",
        "rec.align-earth-runtime-canary",
    ]
    context = payload["strategy_packet_context"]
    assert [row["recommendation_id"] for row in context["recommendation_readiness"]] == [
        "rec.harden-telemetry-freshness",
        "rec.align-earth-runtime-canary",
    ]
    assert context["cross_project_context_usage"]["cross_project_context_used"] is True
    assert context["open_risks"][0]["reason_code"] == "unresolved_idea_open_risk"


def test_req_052_validator_rejects_noncanonical_project_id() -> None:
    payload = _read_json(SAMPLE_PATH)
    broken = deepcopy(payload)
    broken["strategy_packet_v1"]["packet"]["identity"]["project_id"] = "optimus-prime-gsd-fusion"

    errors = module.validate_req_052_strategy_packet_v1_generator(broken)

    assert "strategy_packet_v1.packet.identity.project_id must match prj.<lowercase-hyphenated-id>" in errors


def test_req_052_contract_doc_references_documented_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-052_strategy-packet-v1-generator.sample.json" in contract_text
    for key in (
        "strategy_packet_v1.packet.identity",
        "strategy_packet_v1.packet.strategy",
        "strategy_packet_v1.packet.recommendations",
        "strategy_packet_v1.packet.constraints",
        "strategy_packet_v1.packet.kpi_targets",
        "strategy_packet_v1.packet.source",
        "strategy_packet_context.recommendation_readiness",
        "strategy_packet_context.cross_project_context_usage",
        "strategy_packet_context.open_risks",
        "totals",
    ):
        assert key in contract_text


def test_req_052_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_052_builder_rejects_missing_recommendation_profile_coverage() -> None:
    fixture_payload = deepcopy(_read_json(FIXTURE_PATH))
    fixture_payload["recommendation_profiles"] = fixture_payload["recommendation_profiles"][:1]

    with pytest.raises(ValueError, match=r"recommendation_profiles must cover every final_strategy_synthesis.final_recommendations id"):
        module.build_req_052_strategy_packet_v1_generator(fixture_payload)


def test_req_052_builder_rejects_cross_project_recommendation_without_earth_sweep_evidence() -> None:
    fixture_payload = deepcopy(_read_json(FIXTURE_PATH))
    for row in fixture_payload["final_strategy_synthesis"]["final_recommendations"]:
        if row["recommendation_id"] != "rec.align-earth-runtime-canary":
            continue
        row["evidence_refs"] = [
            "reports/quality/req-039-rationale-quality-score.json",
            "strategy/current/llm_call_trace_artifacts/req-027/call-2/trace-call-2-001.json",
        ]
    with pytest.raises(
        ValueError,
        match=r"cross-project final recommendations must include direct Earth-sweep evidence refs",
    ):
        module.build_req_052_strategy_packet_v1_generator(fixture_payload)
