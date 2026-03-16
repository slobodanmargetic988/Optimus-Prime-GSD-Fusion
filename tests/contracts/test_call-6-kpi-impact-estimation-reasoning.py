import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-6-kpi-impact-estimation-reasoning.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-031_call-6-kpi-impact-estimation-reasoning.sample.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "req"
    / "REQ-031_call-6-kpi-impact-estimation-reasoning.md"
)
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_031_builder_emits_bounded_kpi_impact_estimates() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_031_call_6_kpi_impact_estimation_reasoning(**fixture["input"])

    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(payload) == []

    anchors = fixture["expected_contract_anchors"]
    estimation = payload["kpi_impact_estimation"]
    usage = payload["processing_behavior"]["context_usage"]

    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["checked_at_utc"] == anchors["checked_at_utc"]
    assert estimation["target_project"]["project_id"] == anchors["project_id"]
    assert payload["processing_behavior"]["strategy"] == anchors["processing_strategy"]
    assert payload["processing_behavior"]["reasoning_mode"] == anchors["reasoning_mode"]
    assert [row["recommendation_id"] for row in estimation["recommendation_adoptions"]] == anchors["recommendation_ids"]
    assert [row["kpi_id"] for row in estimation["kpi_estimates"]] == [
        "kpi.mean-time-to-diagnose",
        "kpi.replay-failure-rate",
        "kpi.replay-failure-rate",
    ]
    assert usage["kpi_ids_considered"] == anchors["kpi_ids"]
    assert [row["estimate_id"] for row in estimation["kpi_estimates"]] == anchors["estimate_ids"]
    assert usage["estimate_ids_emitted"] == anchors["estimate_ids"]
    assert usage["low_confidence_estimate_ids"] == anchors["low_confidence_estimate_ids"]
    assert estimation["summary"] == anchors["summary"]
    assert usage["earth_sweep_context_used"] is True
    assert usage["source_call_ids_used"] == ["call-1", "call-2", "call-3", "call-4", "call-5", "call-6"]
    assert usage["caveat_count"] == 5
    assert all(row["confidence"] in {"high", "medium", "low"} for row in estimation["kpi_estimates"])
    assert all(row["caveats"] for row in estimation["kpi_estimates"])
    assert all(row["evidence_backed_assumptions"] for row in estimation["kpi_estimates"])


def test_req_031_sample_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-031_call-6-kpi-impact-estimation-reasoning.sample.json" in contract_text


def test_req_031_cli_writes_contract_valid_payload(tmp_path: Path) -> None:
    fixture = _read_json(FIXTURE_PATH)
    input_path = tmp_path / "req031-input.json"
    input_path.write_text(json.dumps(fixture["input"], indent=2) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input-json",
            str(input_path),
            "--json-pretty",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(payload) == []
    assert payload["kpi_impact_estimation"]["summary"]["estimate_count"] == 3
