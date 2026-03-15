import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-1-situational-analysis-reasoning.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-026_call-1-situational-analysis-reasoning.sample.json"
)
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "req"
    / "REQ-026_call-1-situational-analysis-reasoning.md"
)
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_026_builder_emits_bounded_call_1_assessment() -> None:
    fixture = _read_json(FIXTURE_PATH)

    payload = module.build_req_026_call_1_situational_analysis_reasoning(**fixture["input"])

    assert module.validate_req_026_call_1_situational_analysis_reasoning(payload) == []

    anchors = fixture["expected_contract_anchors"]
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["checked_at_utc"] == anchors["checked_at_utc"]
    assert payload["situational_analysis"]["target_project"]["project_id"] == anchors["project_id"]
    assert payload["situational_analysis"]["planning_state"]["status"] == anchors["planning_status"]
    assert payload["situational_analysis"]["runtime_state"]["status"] == anchors["runtime_status"]
    assert payload["situational_analysis"]["reasoning"]["assessment_status"] == anchors["assessment_status"]
    assert payload["situational_analysis"]["planning_state"]["artifact_ids"] == anchors["planning_artifact_ids"]
    assert payload["situational_analysis"]["runtime_state"]["artifact_ids"] == anchors["runtime_artifact_ids"]
    assert payload["situational_analysis"]["reasoning"]["evidence_basis"] == anchors["evidence_basis"]
    assert [row["unknown_id"] for row in payload["unknowns"]] == anchors["unknown_ids"]
    assert [row["category"] for row in payload["unknowns"]] == anchors["unknown_categories"]
    assert all(row["must_be_resolved_by"] == "call-2" for row in payload["unknowns"])


def test_req_026_sample_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_026_call_1_situational_analysis_reasoning(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-026_call-1-situational-analysis-reasoning.sample.json" in contract_text


def test_req_026_cli_writes_contract_valid_payload(tmp_path: Path) -> None:
    fixture = _read_json(FIXTURE_PATH)
    input_path = tmp_path / "req026-input.json"
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
    assert module.validate_req_026_call_1_situational_analysis_reasoning(payload) == []
    assert payload["situational_analysis"]["reasoning"]["assessment_status"] == "needs-follow-up"
