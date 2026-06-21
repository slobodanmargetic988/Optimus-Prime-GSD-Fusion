import json
import subprocess
import sys
from pathlib import Path

from scripts import langsmith_tracing

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "multi-call-strategy-pipeline-planner.json"


def _sample_payloads() -> tuple[dict, dict]:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    input_payload = fixture["input"]
    output_payload = {
        "schema_version": "req-025.multi-call-strategy-pipeline-planner.v1",
        "requirement_id": "REQ-025",
        "processing_behavior": {
            "recommendation": {
                "decision": "promote",
                "recommended_actions": [{"action_id": "action-1"}],
                "open_risks": [],
            }
        },
        "call_metadata": {
            "processing_call_id": "req025-processing-test",
            "reproducible_call_id": "req025-test",
            "llm_call_trace_rows": [
                {
                    "call_id": "call-1",
                    "sequence": 1,
                    "depends_on": [],
                    "call_objective": "Format a strategy prompt.",
                    "expected_output": "strategy_scope_frame",
                    "input_refs": ["scope.md#mission"],
                    "output_refs": ["trace#call-1"],
                    "handoff_summary": "Call 1 hands off strategy_scope_frame to call-2.",
                },
                {
                    "call_id": "call-2",
                    "sequence": 2,
                    "depends_on": ["call-1"],
                    "call_objective": "Parse the model output.",
                    "expected_output": "final_pipeline_plan",
                    "input_refs": ["trace#call-1"],
                    "output_refs": ["trace#call-2"],
                    "handoff_summary": "Call 2 hands off final_pipeline_plan as the terminal planner output.",
                },
            ],
        },
    }
    return input_payload, output_payload


def test_langsmith_tracing_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("LANGSTACK_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    input_payload, output_payload = _sample_payloads()

    result = langsmith_tracing.emit_langsmith_trace(
        input_payload=input_payload,
        output_payload=output_payload,
    )

    assert result == {"enabled": False, "reason": "tracing_disabled"}


def test_langsmith_trace_strategy_pipeline_uses_compact_nested_shape(monkeypatch) -> None:
    monkeypatch.delenv("LANGSTACK_TRACE_INCLUDE_PAYLOADS", raising=False)
    input_payload, output_payload = _sample_payloads()

    result = langsmith_tracing.trace_strategy_pipeline(
        input_payload=input_payload,
        output_payload=output_payload,
        project_name="test-project",
        environment="test",
        agent_version="test-agent",
    )

    assert result["project_name"] == "test-project"
    assert result["environment"] == "test"
    assert result["output"]["trace_row_count"] == 2
    assert "top_level_keys" in result["input"]
    assert "candidate_recommendations" not in result["input"]
    assert [row["stop_or_continue"] for row in result["iterations"]] == ["continue", "stop"]
    assert result["iterations"][0]["llm_result"]["model"] == "deterministic-replay"


def test_strategy_llm_pipeline_cli_accepts_langsmith_tracing_without_package(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(fixture["input"], indent=2), encoding="utf-8")

    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input-json",
            str(input_path),
            "--output-json",
            str(output_path),
            "--json-pretty",
            "--langsmith-tracing",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, f"stdout={run.stdout}\nstderr={run.stderr}"
    assert json.loads(output_path.read_text(encoding="utf-8"))["requirement_id"] == "REQ-025"
    if langsmith_tracing._langsmith_traceable is None:
        assert "LangSmith tracing requested but the optional 'langsmith' package is not installed." in run.stderr
