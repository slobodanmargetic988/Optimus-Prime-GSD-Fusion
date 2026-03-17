import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req031-contract-r1",
        "strategy_goal": "Emit contract-valid call-6 KPI impact estimates from deterministic inputs.",
        "call_id": "call-6",
        "checked_at_utc": "2026-03-16T14:20:00Z",
        "call_chain": [
            {
                "sequence": 1,
                "call_id": "call-1",
                "phase": "analysis",
                "output_ref": "REQ-031::call::call-1::output::situational_analysis",
            },
            {
                "sequence": 2,
                "call_id": "call-2",
                "phase": "planning",
                "output_ref": "REQ-031::call::call-2::output::execution_plan",
            },
            {
                "sequence": 3,
                "call_id": "call-3",
                "phase": "validation",
                "output_ref": "REQ-031::call::call-3::output::evidence_validation",
            },
            {
                "sequence": 4,
                "call_id": "call-4",
                "phase": "synthesis",
                "output_ref": "REQ-031::call::call-4::output::recommendation_synthesis",
            },
            {
                "sequence": 5,
                "call_id": "call-5",
                "phase": "sequencing",
                "output_ref": "REQ-031::call::call-5::output::lane_design_reasoning",
            },
            {
                "sequence": 6,
                "call_id": "call-6",
                "phase": "kpi-impact-estimation",
                "output_ref": "REQ-031::call::call-6::output::kpi_impact_estimation",
            },
        ],
        "target_project_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-105/TASK_EVIDENCE.json",
            "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
        ],
        "recommendation_adoptions": [
            {
                "recommendation_id": "rec.runtime-sync",
                "summary": "Adopt the cross-project runtime replay sync after local proof lands.",
                "adoption_status": "conditional",
                "adoption_window": "next wave",
                "project_id": "runtime-orchestrator",
                "requires_earth_evidence": True,
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
            {
                "recommendation_id": "rec.local-determinism",
                "summary": "Keep deterministic replay diagnostics on the committed branch head.",
                "adoption_status": "planned",
                "adoption_window": "this wave",
                "project_id": "",
                "requires_earth_evidence": False,
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
            },
        ],
        "kpi_definitions": [
            {
                "kpi_id": "kpi.replay-failure-rate",
                "kpi_name": "Replay Failure Rate",
                "baseline_value": 0.12,
                "unit": "ratio",
                "desired_direction": "decrease",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
            },
            {
                "kpi_id": "kpi.mean-time-to-diagnose",
                "kpi_name": "Mean Time To Diagnose",
                "baseline_value": 75.0,
                "unit": "minutes",
                "desired_direction": "decrease",
                "evidence_refs": [
                    "reports/optimus-prime/planning/evidence/TASK-105/TASK_EVIDENCE.json",
                ],
            },
        ],
        "impact_assumptions": [
            {
                "recommendation_id": "rec.runtime-sync",
                "kpi_id": "kpi.replay-failure-rate",
                "expected_movement_lower": -0.03,
                "expected_movement_upper": -0.01,
                "reasoning_summary": "Cross-project runtime alignment should remove a smaller class of replay mismatches.",
                "confidence": "low",
                "caveats": [
                    "Runtime-orchestrator adoption remains conditional on fresh earth evidence.",
                ],
                "evidence_backed_assumptions": [
                    "Lane 2 adoption stays aligned with the latest runtime-orchestrator sweep.",
                ],
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/earth/sweeps/2026-03-16/runtime-orchestrator.json",
                ],
            },
            {
                "recommendation_id": "rec.local-determinism",
                "kpi_id": "kpi.mean-time-to-diagnose",
                "expected_movement_lower": -15.0,
                "expected_movement_upper": -8.0,
                "reasoning_summary": "Committed deterministic diagnostics should shorten branch-head failure triage.",
                "confidence": "medium",
                "caveats": [
                    "Savings depend on keeping evidence packets attached to reruns.",
                ],
                "evidence_backed_assumptions": [
                    "Investigators continue to rely on branch-head trace artifacts for diagnosis.",
                ],
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/optimus-prime/planning/evidence/TASK-105/TASK_EVIDENCE.json",
                ],
            },
            {
                "recommendation_id": "rec.local-determinism",
                "kpi_id": "kpi.replay-failure-rate",
                "expected_movement_lower": -0.04,
                "expected_movement_upper": -0.02,
                "reasoning_summary": "Local deterministic hardening should remove a larger share of replay failures.",
                "confidence": "high",
                "caveats": [
                    "The estimate assumes no new non-deterministic runtime inputs land mid-wave.",
                ],
                "evidence_backed_assumptions": [
                    "Branch-head diagnostics remain replay-stable across repeated smoke and integration runs.",
                ],
                "evidence_refs": [
                    "REQ-031::call::call-5::output::lane_design_reasoning",
                    "reports/optimus-prime/planning/evidence/TASK-102/TASK_EVIDENCE.json",
                ],
            },
        ],
    }


def test_req_031_builder_emits_contract_valid_kpi_estimates() -> None:
    payload = module.build_req_031_call_6_kpi_impact_estimation_reasoning(**_base_input())

    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(payload) == []
    assert payload["schema_version"] == module.REQ_031_SCHEMA_VERSION
    assert payload["requirement_id"] == module.REQ_031_REQUIREMENT_ID
    assert payload["analysis_type"] == module.REQ_031_ANALYSIS_TYPE
    assert payload["processing_behavior"]["strategy"] == module.REQ_031_PROCESSING_STRATEGY
    assert payload["processing_behavior"]["reasoning_mode"] == module.REQ_031_REASONING_MODE
    assert payload["call_metadata"]["llm_call_trace_schema_version"] == module.REQ_031_LLM_CALL_TRACE_SCHEMA_VERSION
    assert payload["call_metadata"]["llm_call_trace_path"] == module.LLM_CALL_TRACE_RELATIVE_PATH


def test_req_031_cli_writes_contract_valid_payload(tmp_path: Path) -> None:
    input_path = tmp_path / "req031-input.json"
    input_path.write_text(json.dumps(_base_input(), indent=2) + "\n", encoding="utf-8")

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
    assert module.validate_req_031_call_6_kpi_impact_estimation_reasoning(payload) == []
    assert payload["processing_behavior"]["kpi_impact_estimation"]["decision"] == "proceed"
