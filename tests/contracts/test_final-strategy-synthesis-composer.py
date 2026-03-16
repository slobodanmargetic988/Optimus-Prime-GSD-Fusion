import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import strategy_llm_pipeline as pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "final-strategy-synthesis-composer.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-046_final-strategy-synthesis-composer.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-046_final-strategy-synthesis-composer.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_046_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)

    built_payload = pipeline.build_req_046_final_strategy_synthesis_composer(fixture_payload)

    assert pipeline.validate_req_046_final_strategy_synthesis_composer(built_payload) == []
    assert pipeline.validate_req_046_final_strategy_synthesis_composer(sample_payload) == []
    assert built_payload == sample_payload


def test_req_046_finalized_recommendations_preserve_multi_call_lineage() -> None:
    payload = _read_json(SAMPLE_PATH)
    synthesis = payload["final_strategy_synthesis"]
    recommendations = {row["recommendation_id"]: row for row in synthesis["final_recommendations"]}

    runtime_alignment = recommendations["rec.align-earth-runtime-canary"]
    assert runtime_alignment["contributing_call_ids"] == ["call-2", "rationale-quality-scoring"]
    assert [row["trace_id"] for row in runtime_alignment["call_trace_lineage"]] == [
        "trace-call-2-001",
        "trace-rationale-quality-001",
    ]
    assert runtime_alignment["strategy_packet_input_id"].startswith("pkt.")

    telemetry = recommendations["rec.harden-telemetry-freshness"]
    assert telemetry["contributing_requirement_ids"] == ["REQ-030", "REQ-039"]
    assert telemetry["supporting_call_count"] == 2


def test_req_046_conflicting_packet_routing_is_deferred() -> None:
    payload = _read_json(SAMPLE_PATH)
    deferred = payload["final_strategy_synthesis"]["deferred_recommendations"]

    assert deferred == [
        {
            "recommendation_id": "rec.review-reuse-contracts",
            "summary": "Review reuse-contract drift before promoting more shared interfaces.",
            "deferred_reason_code": "conflicting_packet_routing",
            "packet_kind_candidates": ["cross-project", "target-project"],
            "peer_project_candidates": ["earth-shared-observability"],
            "evidence_refs": [
                "contracts/req/REQ-016_reuse-opportunity-detection.md",
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
            "call_trace_lineage": [
                {
                    "call_id": "call-2",
                    "requirement_id": "REQ-027",
                    "trace_id": "trace-call-2-001",
                    "trace_ref": "strategy/current/llm_call_trace.jsonl#call-2-001",
                    "artifact_ref": "strategy/current/llm_call_trace_artifacts/req-027/call-2/trace-call-2-001.json",
                    "checked_at_utc": "2026-03-16T08:10:00Z",
                },
                {
                    "call_id": "call-5",
                    "requirement_id": "REQ-030",
                    "trace_id": "trace-call-5-001",
                    "trace_ref": "strategy/current/llm_call_trace.jsonl#call-5-001",
                    "artifact_ref": "strategy/current/llm_call_trace_artifacts/req-030/call-5/trace-call-5-001.json",
                    "checked_at_utc": "2026-03-16T08:20:00Z",
                },
            ],
            "contributing_call_ids": ["call-2", "call-5"],
        }
    ]


def test_req_046_contract_doc_references_documented_sample_structure() -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-046_final-strategy-synthesis-composer.sample.json" in contract_text
    for key in (
        "final_strategy_synthesis.final_recommendations",
        "final_strategy_synthesis.deferred_recommendations",
        "final_strategy_synthesis.strategy_packet_inputs",
        "call_trace_lineage",
        "totals",
    ):
        assert key in contract_text


def test_req_046_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
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


def test_req_046_builder_rejects_missing_call_trace_lineage_anchor() -> None:
    fixture_payload = deepcopy(_read_json(FIXTURE_PATH))
    del fixture_payload["validated_call_outputs"][0]["call_trace"]["trace_ref"]

    with pytest.raises(ValueError, match=r"trace_ref"):
        pipeline.build_req_046_final_strategy_synthesis_composer(fixture_payload)
