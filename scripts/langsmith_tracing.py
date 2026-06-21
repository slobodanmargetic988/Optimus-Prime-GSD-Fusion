#!/usr/bin/env python3
"""Optional LangSmith tracing bridge for deterministic strategy pipeline payloads."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

EmitFn = Callable[[str], None]

_TRUE_VALUES = {"1", "true", "yes", "on"}
_SECRET_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password|authorization|credential)", re.IGNORECASE)
_SECRET_TEXT_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|credential)(\s*[:=]\s*)([^\s,;]+)"
)
_DEFAULT_PROJECT = "optimus-prime-gsd-fusion"
_DEFAULT_FAILURE_EXCERPT_LIMIT = 2000


class OpTraceRecordedFailure(RuntimeError):
    """Raised inside traceable OP runs so LangSmith marks failed OP events as errors."""


try:
    from langsmith import traceable as _langsmith_traceable
except Exception:  # pragma: no cover - depends on optional local package state.
    _langsmith_traceable = None


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(emit: EmitFn | None, message: str) -> None:
    if emit is not None:
        emit(message)


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in _TRUE_VALUES


def _traceable(*decorator_args: Any, **decorator_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    if _langsmith_traceable is None:
        return lambda fn: fn
    return _langsmith_traceable(*decorator_args, **decorator_kwargs)


def is_langsmith_tracing_enabled(*, force: bool = False) -> bool:
    return force or _env_truthy("LANGSTACK_TRACING") or _env_truthy("LANGSMITH_TRACING") or _env_truthy("LANGCHAIN_TRACING_V2")


def is_full_payload_tracing_enabled() -> bool:
    return _env_truthy("LANGSTACK_TRACE_INCLUDE_PAYLOADS")


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if _SECRET_KEY_RE.search(key_text):
                redacted[key_text] = "[redacted]"
            else:
                redacted[key_text] = _redact(nested)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _compact_payload_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    entrypoint_keys = [
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "strategy_goal",
        "call_depth",
        "runtime_mode",
        "execution_mode",
    ]
    summary: dict[str, Any] = {
        "top_level_keys": sorted(str(key) for key in payload.keys()),
    }
    for key in entrypoint_keys:
        if key in payload:
            summary[key] = _redact(payload.get(key))
    evidence_refs = payload.get("evidence_refs")
    if isinstance(evidence_refs, Sequence) and not isinstance(evidence_refs, (str, bytes, bytearray)):
        summary["evidence_ref_count"] = len(evidence_refs)
    return summary


def _pipeline_summary(output_payload: Mapping[str, Any]) -> dict[str, Any]:
    call_metadata = output_payload.get("call_metadata")
    call_metadata = call_metadata if isinstance(call_metadata, Mapping) else {}
    trace_rows = call_metadata.get("llm_call_trace_rows")
    trace_rows = trace_rows if isinstance(trace_rows, list) else []
    processing_behavior = output_payload.get("processing_behavior")
    processing_behavior = processing_behavior if isinstance(processing_behavior, Mapping) else {}
    recommendation = processing_behavior.get("recommendation")
    recommendation = recommendation if isinstance(recommendation, Mapping) else {}
    return {
        "requirement_id": _as_text(output_payload.get("requirement_id")),
        "schema_version": _as_text(output_payload.get("schema_version")),
        "trace_row_count": len(trace_rows),
        "processing_call_id": _as_text(call_metadata.get("processing_call_id")),
        "reproducible_call_id": _as_text(call_metadata.get("reproducible_call_id")),
        "recommendation_decision": _as_text(recommendation.get("decision")),
        "recommended_action_count": len(recommendation.get("recommended_actions") or []),
        "open_risk_count": len(recommendation.get("open_risks") or []),
    }


def _trace_payload_input(input_payload: Mapping[str, Any]) -> dict[str, Any]:
    if is_full_payload_tracing_enabled():
        return _redact(input_payload)
    return _compact_payload_summary(input_payload)


def _trace_payload_output(output_payload: Mapping[str, Any]) -> dict[str, Any]:
    if is_full_payload_tracing_enabled():
        return _redact(output_payload)
    return _pipeline_summary(output_payload)


def _row_input(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "call_id": _as_text(row.get("call_id")),
        "sequence": row.get("sequence"),
        "depends_on": list(row.get("depends_on") or []),
        "input_ref_count": len(row.get("input_refs") or []),
        "expected_output": _as_text(row.get("expected_output")),
    }


def _row_output(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "call_id": _as_text(row.get("call_id")),
        "output_refs": list(row.get("output_refs") or []),
        "handoff_summary": _as_text(row.get("handoff_summary")),
        "totals": _redact(row.get("totals") or {}),
    }


@_traceable(name="strategy_pipeline.tool_artifact_refs", run_type="tool")
def trace_tool_artifacts(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "call_id": _as_text(row.get("call_id")),
        "input_refs": list(row.get("input_refs") or []),
        "output_refs": list(row.get("output_refs") or []),
        "artifacts": _redact(row.get("artifacts") or []),
    }


@_traceable(name="strategy_pipeline.invoke_llm_placeholder", run_type="llm")
def trace_llm_call(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "messages": [
            {
                "role": "system",
                "content": "Deterministic replay placeholder for one strategy pipeline LLM reasoning call.",
            },
            {
                "role": "user",
                "content": _as_text(row.get("call_objective")),
            },
        ],
        "model": os.getenv("LANGSTACK_TRACE_MODEL", "deterministic-replay"),
        "output": _row_output(row),
    }


@_traceable(name="strategy_pipeline.loop_iteration", run_type="chain")
def trace_loop_iteration(row: Mapping[str, Any]) -> dict[str, Any]:
    tool_refs = trace_tool_artifacts(row)
    llm_result = trace_llm_call(row)
    handoff_summary = _as_text(row.get("handoff_summary")).lower()
    return {
        "iteration": row.get("sequence"),
        "selected_next_action": _as_text(row.get("expected_output")),
        "stop_or_continue": "stop" if "terminal" in handoff_summary else "continue",
        "input": _row_input(row),
        "tool_refs": tool_refs,
        "llm_result": llm_result,
    }


@_traceable(name="strategy_pipeline.run_pipeline", run_type="chain")
def trace_strategy_pipeline(
    *,
    input_payload: Mapping[str, Any],
    output_payload: Mapping[str, Any],
    project_name: str,
    environment: str,
    agent_version: str,
) -> dict[str, Any]:
    call_metadata = output_payload.get("call_metadata")
    call_metadata = call_metadata if isinstance(call_metadata, Mapping) else {}
    trace_rows = call_metadata.get("llm_call_trace_rows")
    trace_rows = trace_rows if isinstance(trace_rows, list) else []
    iterations = [trace_loop_iteration(row) for row in trace_rows if isinstance(row, Mapping)]
    return {
        "project_name": project_name,
        "environment": environment,
        "agent_version": agent_version,
        "input": _trace_payload_input(input_payload),
        "output": _trace_payload_output(output_payload),
        "iterations": iterations,
    }


def emit_langsmith_trace(
    *,
    input_payload: Mapping[str, Any],
    output_payload: Mapping[str, Any],
    force: bool = False,
    emit: EmitFn | None = None,
) -> dict[str, Any]:
    if not is_langsmith_tracing_enabled(force=force):
        return {"enabled": False, "reason": "tracing_disabled"}
    if _langsmith_traceable is None:
        _emit(emit, "LangSmith tracing requested but the optional 'langsmith' package is not installed.")
        return {"enabled": False, "reason": "langsmith_package_missing"}
    os.environ.setdefault("LANGSMITH_TRACING", "true")

    project_name = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or _DEFAULT_PROJECT
    environment = os.getenv("LANGSTACK_ENVIRONMENT", "dev")
    agent_version = os.getenv("LANGSTACK_AGENT_VERSION", "langstack-experiment-v1")
    try:
        result = trace_strategy_pipeline(
            input_payload=input_payload,
            output_payload=output_payload,
            project_name=project_name,
            environment=environment,
            agent_version=agent_version,
        )
    except Exception as exc:  # pragma: no cover - defensive around optional SaaS/client behavior.
        _emit(emit, f"LangSmith tracing failed without changing pipeline output: {exc}")
        return {"enabled": False, "reason": "trace_failed", "error": str(exc)}

    _emit(
        emit,
        (
            "LangSmith trace emitted "
            f"project={project_name} environment={environment} "
            f"iterations={len(result.get('iterations') or [])}."
        ),
    )
    return {
        "enabled": True,
        "project_name": project_name,
        "environment": environment,
        "iteration_count": len(result.get("iterations") or []),
    }


def _truncate_text(value: Any, *, limit: int = 2000) -> str:
    text = _as_text(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"...[truncated {len(text) - limit} chars]"


def _redact_text(value: Any) -> str:
    return _SECRET_TEXT_RE.sub(r"\1\2[redacted]", _as_text(value))


def _failure_excerpt_from_path(path_value: Any, *, limit: int = _DEFAULT_FAILURE_EXCERPT_LIMIT) -> str:
    path_text = _as_text(path_value)
    if not path_text:
        return ""
    try:
        with open(path_text, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read(limit + 1)
    except OSError:
        return ""
    return _truncate_text(_redact_text(text), limit=limit)


def _op_payload_indicates_failure(event_name: str, payload: Mapping[str, Any]) -> bool:
    status = _as_text(payload.get("status")).lower()
    if event_name.endswith(".error") or status in {"failed", "error"}:
        return True
    if payload.get("ok") is False:
        return True
    exit_code = payload.get("exit_code")
    if exit_code not in (None, "", 0, "0"):
        return True
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        return True
    return False


def _compact_op_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    interesting_keys = {
        "command",
        "repo_root",
        "mission",
        "mission_file",
        "scope",
        "scope_file",
        "skip_strategy",
        "start_policy",
        "executor_provider",
        "executor_model",
        "selected_aliases",
        "max_build_cycles",
        "max_parallel_workers",
        "dry_run",
        "override_old_plan",
        "status",
        "reason",
        "ok",
        "task_id",
        "stage",
        "plan_id",
        "attempt",
        "bundle_path",
        "exit_code",
        "last_message_ref",
        "llm_stderr_ref",
        "llm_stdout_ref",
        "parse_ok",
        "prompt_path",
        "schema_ok",
        "plan_check_ok",
        "control_number",
        "control_run_id",
    }
    compact: dict[str, Any] = {
        "top_level_keys": sorted(str(key) for key in payload.keys()),
    }
    for key in sorted(interesting_keys):
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, str):
            compact[key] = _truncate_text(value)
        else:
            compact[key] = _redact(value)
    for list_key in ("warnings", "errors", "artifacts", "dispatch_results", "assignment_observations"):
        value = payload.get(list_key)
        if isinstance(value, list):
            compact[f"{list_key}_count"] = len(value)
            if list_key == "errors":
                compact["errors"] = _redact(value[:5])
    data = payload.get("data")
    if isinstance(data, Mapping):
        compact["data"] = _compact_op_payload(data)
    return compact


def _enrich_failed_op_payload(event_name: str, raw_payload: Mapping[str, Any], compact_payload: dict[str, Any]) -> None:
    if not _op_payload_indicates_failure(event_name, raw_payload):
        return
    stderr_excerpt = _failure_excerpt_from_path(raw_payload.get("llm_stderr_ref"))
    if stderr_excerpt:
        compact_payload["llm_stderr_excerpt"] = stderr_excerpt


def _failed_event_message(event_name: str, compact_payload: Mapping[str, Any]) -> str:
    parts = [f"OP trace event failed: {event_name}"]
    status = _as_text(compact_payload.get("status"))
    if status:
        parts.append(f"status={status}")
    exit_code = compact_payload.get("exit_code")
    if exit_code not in (None, ""):
        parts.append(f"exit_code={exit_code}")
    errors = compact_payload.get("errors")
    if isinstance(errors, list) and errors:
        summaries: list[str] = []
        for item in errors[:3]:
            if isinstance(item, Mapping):
                code = _as_text(item.get("code")) or "error"
                message = _truncate_text(item.get("message"), limit=300)
                summaries.append(f"{code}: {message}" if message else code)
        if summaries:
            parts.append("errors=" + " | ".join(summaries))
    stderr_excerpt = _as_text(compact_payload.get("llm_stderr_excerpt"))
    if stderr_excerpt:
        parts.append("stderr=" + _truncate_text(stderr_excerpt, limit=800))
    return "; ".join(parts)


def _op_trace_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if is_full_payload_tracing_enabled():
        return _redact(payload)
    return _compact_op_payload(payload)


def _op_event_base(event_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    compact_payload = _op_trace_payload(payload)
    _enrich_failed_op_payload(event_name, payload, compact_payload)
    return {
        "event_name": event_name,
        "project_name": os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or _DEFAULT_PROJECT,
        "environment": os.getenv("LANGSTACK_ENVIRONMENT", "dev"),
        "agent_version": os.getenv("LANGSTACK_AGENT_VERSION", "langstack-experiment-v1"),
        "payload": compact_payload,
    }


@_traceable(name="op_runtime.command", run_type="chain")
def trace_op_command_event(event_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    compact = _op_event_base(event_name, payload)
    if _op_payload_indicates_failure(event_name, payload):
        raise OpTraceRecordedFailure(_failed_event_message(event_name, compact["payload"]))
    return compact


@_traceable(name="op_runtime.planner_attempt", run_type="llm")
def trace_op_planner_attempt_event(event_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    compact = _op_event_base(event_name, payload)
    prompt_preview = payload.get("prompt_preview")
    if prompt_preview is not None:
        compact["messages"] = [
            {
                "role": "user",
                "content": _truncate_text(prompt_preview, limit=4000),
            }
        ]
    compact["model"] = _as_text(payload.get("model")) or os.getenv("LANGSTACK_TRACE_MODEL", "codex-planner")
    if _op_payload_indicates_failure(event_name, payload):
        raise OpTraceRecordedFailure(_failed_event_message(event_name, compact["payload"]))
    return compact


@_traceable(name="op_runtime.orchestration_tool", run_type="tool")
def trace_op_tool_event(event_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    compact = _op_event_base(event_name, payload)
    if _op_payload_indicates_failure(event_name, payload):
        raise OpTraceRecordedFailure(_failed_event_message(event_name, compact["payload"]))
    return compact


def emit_op_event_trace(
    *,
    event_name: str,
    payload: Mapping[str, Any],
    run_type: str = "chain",
    force: bool = False,
    emit: EmitFn | None = None,
) -> dict[str, Any]:
    if not is_langsmith_tracing_enabled(force=force):
        return {"enabled": False, "reason": "tracing_disabled"}
    if _langsmith_traceable is None:
        _emit(emit, "LangSmith tracing requested but the optional 'langsmith' package is not installed.")
        return {"enabled": False, "reason": "langsmith_package_missing"}
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    try:
        if run_type == "llm":
            trace_op_planner_attempt_event(event_name, payload)
        elif run_type == "tool":
            trace_op_tool_event(event_name, payload)
        else:
            trace_op_command_event(event_name, payload)
    except OpTraceRecordedFailure as exc:
        return {
            "enabled": True,
            "event_name": event_name,
            "run_type": run_type,
            "recorded_error": True,
            "error": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive around optional SaaS/client behavior.
        _emit(emit, f"LangSmith OP trace failed without changing OP output: {exc}")
        return {"enabled": False, "reason": "trace_failed", "error": str(exc)}
    return {"enabled": True, "event_name": event_name, "run_type": run_type}
