import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-omission-detector.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-044_recommendation-omission-detector.sample.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "req"
    / "REQ-044_recommendation-omission-detector.md"
)
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_044_builder_detects_required_class_omissions_and_local_only_plan_risk() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_044_recommendation_omission_detector(**fixture["input"])

    assert module.validate_req_044_recommendation_omission_detector(payload) == []

    anchors = fixture["expected_contract_anchors"]
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["analysis_type"] == anchors["analysis_type"]
    assert payload["call_id"] == anchors["call_id"]
    assert payload["checked_at_utc"] == anchors["checked_at_utc"]

    processing = payload["processing_behavior"]
    context_usage = processing["context_usage"]
    recommendation = processing["recommendation"]

    assert processing["strategy"] == anchors["processing_strategy"]
    assert processing["reasoning_mode"] == anchors["reasoning_mode"]
    assert context_usage["required_recommendation_class_ids_considered"] == anchors["required_recommendation_class_ids"]
    assert context_usage["required_cross_project_class_ids"] == anchors["required_cross_project_class_ids"]
    assert context_usage["candidate_recommendation_ids_considered"] == anchors["candidate_recommendation_ids"]
    assert context_usage["emitted_recommendation_ids"] == anchors["emitted_recommendation_ids"]
    assert context_usage["omitted_recommendation_class_ids"] == anchors["omitted_recommendation_class_ids"]
    assert (
        context_usage["missing_critical_cross_project_class_ids"]
        == anchors["missing_critical_cross_project_class_ids"]
    )
    assert context_usage["local_only_plan_detected"] == anchors["local_only_plan_detected"]
    assert context_usage["cross_project_obligation_ids_emitted"] == anchors["cross_project_obligation_ids"]
    assert context_usage["open_risk_ids_emitted"] == anchors["open_risk_ids"]

    assert recommendation["decision"] == anchors["decision"]
    assert recommendation["confidence"] == anchors["confidence"]
    assert [row["class_id"] for row in recommendation["omitted_recommendation_classes"]] == anchors[
        "omitted_recommendation_class_ids"
    ]


def test_req_044_sample_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_044_recommendation_omission_detector(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-044_recommendation-omission-detector.sample.json" in contract_text


def test_req_044_cli_writes_contract_valid_payload(tmp_path: Path) -> None:
    fixture = _read_json(FIXTURE_PATH)
    input_path = tmp_path / "req044-input.json"
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

    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    payload = json.loads(proc.stdout)
    assert module.validate_req_044_recommendation_omission_detector(payload) == []
    assert payload["processing_behavior"]["recommendation"]["decision"] == "resolve-strategy-gaps"
