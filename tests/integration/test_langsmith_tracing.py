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


def test_failed_op_trace_event_raises_for_langsmith_error_status(tmp_path: Path) -> None:
    stderr_path = tmp_path / "llm_stderr.log"
    stderr_path.write_text(
        'Error loading config.toml: unknown variant "default", expected "fast" or "flex"\n'
        "api_key=should-not-leak\n",
        encoding="utf-8",
    )

    payload = {
        "status": "failed",
        "exit_code": 1,
        "llm_stderr_ref": str(stderr_path),
        "errors": [{"code": "planner_bundle_missing", "message": "planner bundle missing"}],
    }

    try:
        langsmith_tracing.trace_op_planner_attempt_event("op.plan.planner_attempt.result", payload)
    except langsmith_tracing.OpTraceRecordedFailure as exc:
        message = str(exc)
    else:
        raise AssertionError("failed OP trace events must raise so LangSmith marks the run as errored")

    assert "OP trace event failed" in message
    assert "planner_bundle_missing" in message
    assert 'unknown variant "default"' in message
    assert "should-not-leak" not in message
    assert "[redacted]" in message


def test_emit_op_event_trace_catches_recorded_failure(monkeypatch) -> None:
    monkeypatch.setenv("LANGSTACK_TRACING", "true")
    monkeypatch.setattr(langsmith_tracing, "_langsmith_traceable", lambda *args, **kwargs: (lambda fn: fn))

    result = langsmith_tracing.emit_op_event_trace(
        event_name="op.command.error",
        payload={
            "status": "failed",
            "ok": False,
            "errors": [{"code": "planner_retry_exhausted", "message": "planner failed"}],
        },
    )

    assert result["enabled"] is True
    assert result["recorded_error"] is True
    assert "planner_retry_exhausted" in result["error"]


def test_op_trace_success_event_does_not_raise() -> None:
    result = langsmith_tracing.trace_op_command_event(
        "op.command.result",
        {"status": "completed", "ok": True, "errors": []},
    )

    assert result["event_name"] == "op.command.result"
    assert result["payload"]["status"] == "completed"


def test_op_trace_compact_payload_keeps_runtime_duration_context() -> None:
    result = langsmith_tracing.trace_op_command_event(
        "op.simple_build.manager.result",
        {
            "status": "ok",
            "ok": True,
            "cycle_number": 4,
            "manager": "BOSS",
            "worker_id": "worker-1",
            "profile_alias": "codex-opbuild",
            "executor_model": "gpt-5.5",
            "duration_seconds": 479.414,
            "started_at": "2026-06-21T13:52:26Z",
            "finished_at": "2026-06-21T14:00:26Z",
        },
    )

    payload = result["payload"]
    assert payload["cycle_number"] == 4
    assert payload["manager"] == "BOSS"
    assert payload["profile_alias"] == "codex-opbuild"
    assert payload["executor_model"] == "gpt-5.5"
    assert payload["duration_seconds"] == 479.414


def test_op_trace_returncode_marks_live_subprocess_failure() -> None:
    assert langsmith_tracing._op_payload_indicates_failure(
        "op.simple_build.worker_dispatch.live",
        {"returncode": 2},
    )


def test_live_span_inputs_match_langsmith_process_inputs_shape() -> None:
    inputs = langsmith_tracing._live_span_inputs(
        {
            "span_name": "op.manager.boss",
            "event_name": "op.simple_build.manager.live",
            "payload": {
                "cycle_number": 4,
                "manager": "BOSS",
                "duration_seconds": 479.414,
            },
            "operation": object(),
        }
    )

    assert inputs["event_name"] == "op.simple_build.manager.live"
    assert inputs["payload"]["cycle_number"] == 4
    assert inputs["payload"]["manager"] == "BOSS"
    assert inputs["payload"]["duration_seconds"] == 479.414
    assert "operation" not in inputs


def test_run_traced_op_operation_disabled_executes_operation_once(monkeypatch) -> None:
    monkeypatch.delenv("LANGSTACK_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    calls = {"count": 0}

    def operation() -> dict:
        calls["count"] += 1
        return {"status": "ok"}

    result = langsmith_tracing.run_traced_op_operation(
        span_name="op.manager.boss",
        event_name="op.simple_build.manager.live",
        payload={"manager": "BOSS"},
        operation=operation,
        run_type="llm",
    )

    assert result == {"status": "ok"}
    assert calls["count"] == 1
