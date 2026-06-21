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
_DEFAULT_PROJECT = "optimus-prime-gsd-fusion"


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
