import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "llm-call-trace-and-decision-ledger.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-047_llm-call-trace-and-decision-ledger.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-047_llm-call-trace-and-decision-ledger.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req047_builder_matches_sample_and_validates() -> None:
    fixture_payload = _read_json(FIXTURE_PATH)
    sample_payload = _read_json(SAMPLE_PATH)
    built_payload = pipeline.build_req_047_llm_call_trace_and_decision_ledger(fixture_payload)

    assert pipeline.validate_req_047_llm_call_trace_and_decision_ledger(built_payload) == []
    assert pipeline.validate_req_047_llm_call_trace_and_decision_ledger(sample_payload) == []
    assert built_payload == sample_payload


def test_req047_trace_rows_and_traceability_index_link_to_final_output_artifacts() -> None:
    payload = _read_json(SAMPLE_PATH)

    linked_refs_by_call = {
        row["call_ref"]: row["linked_final_output_artifact_refs"]
        for row in payload["llm_call_trace_rows"]
    }
    traceability_by_artifact = {
        row["final_output_artifact_ref"]: row
        for row in payload["llm_call_trace_and_decision_ledger"]["traceability_index"]
    }

    assert linked_refs_by_call["REQ-035::call::call-2"] == [
        "reports/optimus-prime/final/replay-analysis.json",
        "reports/optimus-prime/final/strategy-packet.json",
    ]
    assert linked_refs_by_call["REQ-039::call::score-req-039-contract-surface-evidence-a1b2c3d4e5f6"] == [
        "reports/optimus-prime/final/strategy-packet.json"
    ]
    assert traceability_by_artifact["reports/optimus-prime/final/strategy-packet.json"]["source_call_refs"] == [
        "REQ-035::call::call-2",
        "REQ-039::call::score-req-039-contract-surface-evidence-a1b2c3d4e5f6",
    ]
    assert traceability_by_artifact["reports/optimus-prime/final/replay-analysis.json"]["decision_ids"] == [
        "dec.hold-replay-analysis"
    ]


def test_req047_validator_rejects_decision_ledger_reference_to_unknown_call_ref() -> None:
    payload = _read_json(SAMPLE_PATH)
    payload["llm_call_trace_and_decision_ledger"]["decision_ledger"][0]["source_call_refs"] = [
        "REQ-035::call::call-2",
        "REQ-999::call::missing",
    ]

    errors = pipeline.validate_req_047_llm_call_trace_and_decision_ledger(payload)

    assert (
        "llm_call_trace_and_decision_ledger.decision_ledger[0].source_call_refs[1] must reference llm_call_trace_rows.call_ref"
        in errors
    )


def test_req047_contract_doc_and_cli_cover_sample_shape(tmp_path: Path) -> None:
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-047_llm-call-trace-and-decision-ledger.sample.json" in contract_text

    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(_read_json(FIXTURE_PATH)), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert json.loads(proc.stdout) == _read_json(SAMPLE_PATH)
