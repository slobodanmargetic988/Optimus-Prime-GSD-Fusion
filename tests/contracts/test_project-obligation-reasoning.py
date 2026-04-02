import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "project-obligation-reasoning.json"
SAMPLE_PATH = REPO_ROOT / "strategy" / "current" / "samples" / "REQ-043_project-obligation-reasoning.sample.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _load_sample() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_req_043_builder_emits_contract_valid_project_obligations() -> None:
    payload = module.build_req_043_project_obligation_reasoning(**_load_fixture())

    assert module.validate_req_043_project_obligation_reasoning(payload) == []
    assert payload == _load_sample()
    assert payload["schema_version"] == module.REQ_043_SCHEMA_VERSION
    assert payload["requirement_id"] == module.REQ_043_REQUIREMENT_ID
    assert payload["analysis_type"] == module.REQ_043_ANALYSIS_TYPE
    assert payload["processing_behavior"]["strategy"] == module.REQ_043_PROCESSING_STRATEGY
    assert payload["processing_behavior"]["reasoning_mode"] == module.REQ_043_REASONING_MODE

    recommendation = payload["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert [row["obligation_id"] for row in recommendation["project_obligations"]] == [
        "obl.analytics-feedback-consume",
        "obl.replay-manifest-expose",
    ]
    assert [row["direction"] for row in recommendation["project_obligations"]] == ["consume", "expose"]
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-obl.deploy-summary-expose",
            "reason_code": "missing_cross_project_context",
            "summary": "Expose deployment drift summaries to deployment controller.",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-16/analytics-hub.json",
                "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                "reports/optimus-prime/planning/evidence/TASK-151/TASK_EVIDENCE.json",
            ],
        }
    ]


def test_req_043_cli_writes_contract_valid_payload(tmp_path: Path) -> None:
    input_path = tmp_path / "req043-input.json"
    input_path.write_text(json.dumps(_load_fixture(), indent=2) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input-json",
            str(input_path),
            "--json-pretty",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    payload = json.loads(proc.stdout)
    assert module.validate_req_043_project_obligation_reasoning(payload) == []
    assert payload == _load_sample()


def test_req_043_rejects_direction_role_mismatch() -> None:
    invalid_payload = _load_fixture()
    invalid_payload["project_obligation_candidates"][0]["ownership_boundary"]["current_project_role"] = "consumer"

    try:
        module.build_req_043_project_obligation_reasoning(**invalid_payload)
    except module.Req043Error as exc:
        assert "current_project_role must be producer when direction is expose" in str(exc)
    else:
        raise AssertionError("expected Req043Error for direction and role mismatch")
