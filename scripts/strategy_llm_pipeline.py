#!/usr/bin/env python3
"""REQ-026 Call-1 situational analysis reasoning contract surface."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

TOOL = "strategy-llm-pipeline"
TOOL_VERSION = "1.0.0"
REQUIREMENT_ID = "REQ-026"
SCHEMA_VERSION = "req-026.call-1-situational-analysis-reasoning.v1"
ANALYSIS_TYPE = "call_1_situational_analysis_reasoning"
ALLOWED_PLANNING_STATUSES = {"ready", "partial", "blocked"}
ALLOWED_RUNTIME_STATUSES = {"healthy", "degraded", "blocked"}

LOG_ROOT = Path("/Users/slobodan/projects/LOGS")
LOG_PATH = LOG_ROOT / "strategy_llm_pipeline.log"
LOG_BUDGET_CHECK_STAMP = LOG_ROOT / ".log_budget_check.strategy_llm_pipeline"
LOG_BUDGET_CHECK_INTERVAL_SECONDS = 15 * 60
LOG_BUDGET_MAX_BYTES = 3 * 1024 * 1024 * 1024


class Req026Error(ValueError):
    """Raised when REQ-026 input is malformed."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    text = _as_text(value)
    if not text:
        raise Req026Error(f"{field_name} must be a non-empty string")
    return text


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Req026Error(f"{field_name} must be an object")
    return value


def _require_sequence(value: Any, *, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise Req026Error(f"{field_name} must be an array")
    return value


def _json_dumps(payload: Mapping[str, Any], pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, indent=2, sort_keys=False) + "\n"
    return json.dumps(payload, separators=(",", ":"), sort_keys=False) + "\n"


def _enforce_log_budget(log_root: Path) -> None:
    log_root.mkdir(parents=True, exist_ok=True)
    now_epoch = time.time()
    if LOG_BUDGET_CHECK_STAMP.exists():
        last_checked = LOG_BUDGET_CHECK_STAMP.stat().st_mtime
        if (now_epoch - last_checked) < LOG_BUDGET_CHECK_INTERVAL_SECONDS:
            return

    log_files = [path for path in log_root.rglob("*") if path.is_file() and path != LOG_BUDGET_CHECK_STAMP]
    total_bytes = sum(path.stat().st_size for path in log_files)
    if total_bytes > LOG_BUDGET_MAX_BYTES:
        for path in sorted(log_files, key=lambda item: item.stat().st_mtime):
            original_size = path.stat().st_size
            if original_size <= 0:
                continue
            path.write_text("", encoding="utf-8")
            total_bytes -= original_size
            if total_bytes <= LOG_BUDGET_MAX_BYTES:
                break
    LOG_BUDGET_CHECK_STAMP.touch()


def _timestamped_print(message: str) -> None:
    line = f"[{TOOL} {utc_now_iso()}] {message}"
    print(line, file=sys.stderr, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _normalize_anchor(value: Any, *, field_name: str) -> dict[str, Any]:
    if isinstance(value, str):
        text = _require_nonempty_text(value, field_name=field_name)
        return {"text": text, "source": "inline", "authoritative": True}

    anchor = _require_mapping(value, field_name=field_name)
    source = _as_text(anchor.get("source")) or "inline"
    return {
        "text": _require_nonempty_text(anchor.get("text"), field_name=f"{field_name}.text"),
        "source": source,
        "authoritative": True,
    }


def _normalize_string_list(value: Any, *, field_name: str, min_items: int = 0) -> list[str]:
    rows = _require_sequence(value, field_name=field_name)
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(rows):
        text = _require_nonempty_text(item, field_name=f"{field_name}[{index}]")
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    if len(normalized) < min_items:
        raise Req026Error(f"{field_name} must contain at least {min_items} item(s)")
    return normalized


def _normalize_unknown_item(
    value: Any,
    *,
    field_name: str,
    category: str,
) -> dict[str, str]:
    if isinstance(value, str):
        question = _require_nonempty_text(value, field_name=field_name)
        why_it_matters = (
            "Call-2 needs a stable planning baseline before turning this assessment into implementation work."
            if category == "planning"
            else "Call-2 needs current runtime certainty before promoting execution assumptions."
        )
        return {"question": question, "why_it_matters": why_it_matters}

    row = _require_mapping(value, field_name=field_name)
    return {
        "question": _require_nonempty_text(row.get("question"), field_name=f"{field_name}.question"),
        "why_it_matters": _require_nonempty_text(row.get("why_it_matters"), field_name=f"{field_name}.why_it_matters"),
    }


def _normalize_evidence_artifacts(
    payload: Any,
    *,
    field_name: str,
    category: str,
    allowed_statuses: set[str],
) -> list[dict[str, Any]]:
    container = _require_mapping(payload, field_name=field_name)
    rows = _require_sequence(container.get("artifacts"), field_name=f"{field_name}.artifacts")
    if not rows:
        raise Req026Error(f"{field_name}.artifacts must contain at least one artifact")

    artifacts: list[dict[str, Any]] = []
    seen_artifact_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}.artifacts[{index}]")
        artifact_id = _require_nonempty_text(row.get("artifact_id"), field_name=f"{field_name}.artifacts[{index}].artifact_id")
        if artifact_id in seen_artifact_ids:
            raise Req026Error(f"{field_name}.artifacts[{index}].artifact_id duplicates {artifact_id}")
        seen_artifact_ids.add(artifact_id)

        status = _require_nonempty_text(row.get("status"), field_name=f"{field_name}.artifacts[{index}].status").lower()
        if status not in allowed_statuses:
            raise Req026Error(
                f"{field_name}.artifacts[{index}].status must be one of {sorted(allowed_statuses)}"
            )

        artifacts.append(
            {
                "artifact_id": artifact_id,
                "summary": _require_nonempty_text(row.get("summary"), field_name=f"{field_name}.artifacts[{index}].summary"),
                "status": status,
                "source_ref": _require_nonempty_text(
                    row.get("source_ref"),
                    field_name=f"{field_name}.artifacts[{index}].source_ref",
                ),
                "signals": _normalize_string_list(
                    row.get("signals"),
                    field_name=f"{field_name}.artifacts[{index}].signals",
                    min_items=1,
                ),
                "unknowns": [
                    _normalize_unknown_item(
                        item,
                        field_name=f"{field_name}.artifacts[{index}].unknowns[{unknown_index}]",
                        category=category,
                    )
                    for unknown_index, item in enumerate(
                        _require_sequence(
                            row.get("unknowns", []),
                            field_name=f"{field_name}.artifacts[{index}].unknowns",
                        )
                    )
                ],
            }
        )
    return artifacts


def _evidence_status(artifacts: Sequence[Mapping[str, Any]], *, category: str) -> str:
    statuses = {str(row["status"]) for row in artifacts}
    if "blocked" in statuses:
        return "blocked"
    if category == "planning":
        if "partial" in statuses:
            return "partial"
        return "ready"
    if "degraded" in statuses:
        return "degraded"
    return "healthy"


def _collect_state_details(artifacts: Sequence[Mapping[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    artifact_ids: list[str] = []
    source_refs: list[str] = []
    key_signals: list[str] = []
    seen_source_refs: set[str] = set()
    seen_signals: set[str] = set()

    for row in artifacts:
        artifact_ids.append(str(row["artifact_id"]))
        source_ref = str(row["source_ref"])
        if source_ref not in seen_source_refs:
            seen_source_refs.add(source_ref)
            source_refs.append(source_ref)
        for signal in row["signals"]:
            if signal not in seen_signals:
                seen_signals.add(signal)
                key_signals.append(signal)
    return artifact_ids, source_refs, key_signals


def _assessment_status(*, planning_status: str, runtime_status: str) -> str:
    if planning_status == "blocked" or runtime_status == "blocked":
        return "blocked"
    if planning_status == "partial" or runtime_status == "degraded":
        return "needs-follow-up"
    return "grounded"


def _build_state_summary(
    *,
    project_id: str,
    planning_status: str,
    runtime_status: str,
    unknown_count: int,
) -> str:
    return (
        f"{project_id} remains anchored to mission and scope, planning evidence is {planning_status}, "
        f"runtime evidence is {runtime_status}, and {unknown_count} explicit unknown(s) must be resolved in later calls."
    )


def _build_unknowns(
    *,
    planning_artifacts: Sequence[Mapping[str, Any]],
    runtime_artifacts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    unknowns: list[dict[str, Any]] = []
    ordinal = 1
    for category, artifacts in (("planning", planning_artifacts), ("runtime", runtime_artifacts)):
        for artifact in artifacts:
            for unknown in artifact["unknowns"]:
                unknowns.append(
                    {
                        "unknown_id": f"unknown.{ordinal:03d}",
                        "category": category,
                        "question": unknown["question"],
                        "why_it_matters": unknown["why_it_matters"],
                        "must_be_resolved_by": "call-2",
                        "provenance": {
                            "evidence_type": category,
                            "artifact_id": artifact["artifact_id"],
                            "source_ref": artifact["source_ref"],
                        },
                    }
                )
                ordinal += 1
    if not unknowns:
        raise Req026Error("at least one explicit unknown is required for Call-1 situational analysis")
    return unknowns


def build_req_026_call_1_situational_analysis_reasoning(
    *,
    target_project: Mapping[str, Any],
    planning_evidence: Mapping[str, Any],
    runtime_evidence: Mapping[str, Any],
    analysis_type: str = ANALYSIS_TYPE,
    call_id: str = "call-1",
    checked_at_utc: str | None = None,
) -> dict[str, Any]:
    if analysis_type != ANALYSIS_TYPE:
        raise Req026Error(f"analysis_type must be {ANALYSIS_TYPE}")

    project = _require_mapping(target_project, field_name="target_project")
    project_id = _require_nonempty_text(project.get("project_id"), field_name="target_project.project_id")
    mission = _normalize_anchor(project.get("mission"), field_name="target_project.mission")
    scope = _normalize_anchor(project.get("scope"), field_name="target_project.scope")

    planning_artifacts = _normalize_evidence_artifacts(
        planning_evidence,
        field_name="planning_evidence",
        category="planning",
        allowed_statuses=ALLOWED_PLANNING_STATUSES,
    )
    runtime_artifacts = _normalize_evidence_artifacts(
        runtime_evidence,
        field_name="runtime_evidence",
        category="runtime",
        allowed_statuses=ALLOWED_RUNTIME_STATUSES,
    )

    planning_status = _evidence_status(planning_artifacts, category="planning")
    runtime_status = _evidence_status(runtime_artifacts, category="runtime")
    unknowns = _build_unknowns(planning_artifacts=planning_artifacts, runtime_artifacts=runtime_artifacts)
    overall_status = _assessment_status(planning_status=planning_status, runtime_status=runtime_status)

    planning_artifact_ids, planning_refs, planning_signals = _collect_state_details(planning_artifacts)
    runtime_artifact_ids, runtime_refs, runtime_signals = _collect_state_details(runtime_artifacts)
    evidence_basis = planning_artifact_ids + runtime_artifact_ids

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "requirement_id": REQUIREMENT_ID,
        "analysis_type": ANALYSIS_TYPE,
        "call_id": call_id,
        "checked_at_utc": _require_nonempty_text(checked_at_utc or utc_now_iso(), field_name="checked_at_utc"),
        "situational_analysis": {
            "target_project": {
                "project_id": project_id,
                "mission": mission,
                "scope": scope,
                "anchor_summary": f"Mission: {mission['text']} Scope: {scope['text']}",
            },
            "planning_state": {
                "status": planning_status,
                "artifact_ids": planning_artifact_ids,
                "evidence_refs": planning_refs,
                "key_signals": planning_signals,
            },
            "runtime_state": {
                "status": runtime_status,
                "artifact_ids": runtime_artifact_ids,
                "evidence_refs": runtime_refs,
                "key_signals": runtime_signals,
            },
            "reasoning": {
                "assessment_status": overall_status,
                "anchor_set": ["mission", "scope", "planning_evidence", "runtime_evidence"],
                "state_summary": _build_state_summary(
                    project_id=project_id,
                    planning_status=planning_status,
                    runtime_status=runtime_status,
                    unknown_count=len(unknowns),
                ),
                "evidence_basis": evidence_basis,
                "follow_up_required": True,
            },
        },
        "unknowns": unknowns,
        "source": {
            "planning_artifact_count": len(planning_artifacts),
            "runtime_artifact_count": len(runtime_artifacts),
            "mission_source": mission["source"],
            "scope_source": scope["source"],
        },
    }


def validate_req_026_call_1_situational_analysis_reasoning(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("tool") != TOOL:
        errors.append(f"tool must be {TOOL}")
    if payload.get("tool_version") != TOOL_VERSION:
        errors.append(f"tool_version must be {TOOL_VERSION}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQUIREMENT_ID}")
    if payload.get("analysis_type") != ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {ANALYSIS_TYPE}")
    if payload.get("call_id") != "call-1":
        errors.append("call_id must be call-1")
    if not _as_text(payload.get("checked_at_utc")):
        errors.append("checked_at_utc is required")

    situational_analysis = payload.get("situational_analysis")
    if not isinstance(situational_analysis, Mapping):
        errors.append("situational_analysis must be an object")
        situational_analysis = {}

    target_project = situational_analysis.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("situational_analysis.target_project must be an object")
        target_project = {}
    if not _as_text(target_project.get("project_id")):
        errors.append("situational_analysis.target_project.project_id is required")
    for anchor_name in ("mission", "scope"):
        anchor = target_project.get(anchor_name)
        if not isinstance(anchor, Mapping):
            errors.append(f"situational_analysis.target_project.{anchor_name} must be an object")
            continue
        if not _as_text(anchor.get("text")):
            errors.append(f"situational_analysis.target_project.{anchor_name}.text is required")
        if not _as_text(anchor.get("source")):
            errors.append(f"situational_analysis.target_project.{anchor_name}.source is required")
        if anchor.get("authoritative") is not True:
            errors.append(f"situational_analysis.target_project.{anchor_name}.authoritative must be true")
    if not _as_text(target_project.get("anchor_summary")):
        errors.append("situational_analysis.target_project.anchor_summary is required")

    for section_name, allowed_statuses in (
        ("planning_state", ALLOWED_PLANNING_STATUSES),
        ("runtime_state", ALLOWED_RUNTIME_STATUSES),
    ):
        section = situational_analysis.get(section_name)
        if not isinstance(section, Mapping):
            errors.append(f"situational_analysis.{section_name} must be an object")
            continue
        status = _as_text(section.get("status"))
        if status not in allowed_statuses:
            errors.append(f"situational_analysis.{section_name}.status must be one of {sorted(allowed_statuses)}")
        for key in ("artifact_ids", "evidence_refs", "key_signals"):
            value = section.get(key)
            if not isinstance(value, list) or not value or any(not _as_text(item) for item in value):
                errors.append(f"situational_analysis.{section_name}.{key} must be a non-empty string array")

    reasoning = situational_analysis.get("reasoning")
    if not isinstance(reasoning, Mapping):
        errors.append("situational_analysis.reasoning must be an object")
        reasoning = {}
    if _as_text(reasoning.get("assessment_status")) not in {"grounded", "needs-follow-up", "blocked"}:
        errors.append("situational_analysis.reasoning.assessment_status must be grounded, needs-follow-up, or blocked")
    anchor_set = reasoning.get("anchor_set")
    if anchor_set != ["mission", "scope", "planning_evidence", "runtime_evidence"]:
        errors.append("situational_analysis.reasoning.anchor_set must match the canonical anchor set")
    if not _as_text(reasoning.get("state_summary")):
        errors.append("situational_analysis.reasoning.state_summary is required")
    evidence_basis = reasoning.get("evidence_basis")
    if not isinstance(evidence_basis, list) or not evidence_basis or any(not _as_text(item) for item in evidence_basis):
        errors.append("situational_analysis.reasoning.evidence_basis must be a non-empty string array")
    if reasoning.get("follow_up_required") is not True:
        errors.append("situational_analysis.reasoning.follow_up_required must be true")

    unknowns = payload.get("unknowns")
    if not isinstance(unknowns, list) or not unknowns:
        errors.append("unknowns must be a non-empty array")
        unknowns = []
    seen_unknown_ids: set[str] = set()
    for index, row in enumerate(unknowns):
        if not isinstance(row, Mapping):
            errors.append(f"unknowns[{index}] must be an object")
            continue
        unknown_id = _as_text(row.get("unknown_id"))
        if not unknown_id:
            errors.append(f"unknowns[{index}].unknown_id is required")
        elif unknown_id in seen_unknown_ids:
            errors.append(f"unknowns[{index}].unknown_id duplicates {unknown_id}")
        else:
            seen_unknown_ids.add(unknown_id)
        if _as_text(row.get("category")) not in {"planning", "runtime"}:
            errors.append(f"unknowns[{index}].category must be planning or runtime")
        if not _as_text(row.get("question")):
            errors.append(f"unknowns[{index}].question is required")
        if not _as_text(row.get("why_it_matters")):
            errors.append(f"unknowns[{index}].why_it_matters is required")
        if row.get("must_be_resolved_by") != "call-2":
            errors.append(f"unknowns[{index}].must_be_resolved_by must be call-2")
        provenance = row.get("provenance")
        if not isinstance(provenance, Mapping):
            errors.append(f"unknowns[{index}].provenance must be an object")
            continue
        if _as_text(provenance.get("evidence_type")) not in {"planning", "runtime"}:
            errors.append(f"unknowns[{index}].provenance.evidence_type must be planning or runtime")
        if not _as_text(provenance.get("artifact_id")):
            errors.append(f"unknowns[{index}].provenance.artifact_id is required")
        if not _as_text(provenance.get("source_ref")):
            errors.append(f"unknowns[{index}].provenance.source_ref is required")

    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
        source = {}
    for key in ("planning_artifact_count", "runtime_artifact_count"):
        if not isinstance(source.get(key), int) or source[key] <= 0:
            errors.append(f"source.{key} must be a positive integer")
    if not _as_text(source.get("mission_source")):
        errors.append("source.mission_source is required")
    if not _as_text(source.get("scope_source")):
        errors.append("source.scope_source is required")

    return errors


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_req_026_call_1_situational_analysis_reasoning(
        target_project=_require_mapping(payload.get("target_project"), field_name="input.target_project"),
        planning_evidence=_require_mapping(payload.get("planning_evidence"), field_name="input.planning_evidence"),
        runtime_evidence=_require_mapping(payload.get("runtime_evidence"), field_name="input.runtime_evidence"),
        analysis_type=_as_text(payload.get("analysis_type")) or ANALYSIS_TYPE,
        call_id=_as_text(payload.get("call_id")) or "call-1",
        checked_at_utc=_as_text(payload.get("checked_at_utc")) or None,
    )


def _parse_cli_input(input_path: str) -> Mapping[str, Any]:
    raw = sys.stdin.read() if input_path == "-" else Path(input_path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise Req026Error("input payload must be an object")
    return payload


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit REQ-026 Call-1 situational analysis reasoning payload.")
    parser.add_argument("--input-json", required=True, help="Input JSON path or '-' for stdin.")
    parser.add_argument("--output-json", default="", help="Optional output JSON path.")
    parser.add_argument("--json-pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _enforce_log_budget(LOG_ROOT)
    _timestamped_print(f"Starting REQ-026 Call-1 situational analysis from input source: {args.input_json}")

    try:
        input_payload = _parse_cli_input(args.input_json)
        output_payload = run(input_payload)
    except (Req026Error, json.JSONDecodeError) as exc:
        _timestamped_print(f"REQ-026 input processing failed: {exc}")
        error_payload = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "requirement_id": REQUIREMENT_ID,
            "reason_code": "input_error",
            "error": _as_text(exc),
        }
        sys.stdout.write(_json_dumps(error_payload, args.json_pretty))
        return 1

    validation_errors = validate_req_026_call_1_situational_analysis_reasoning(output_payload)
    if validation_errors:
        _timestamped_print(
            f"REQ-026 contract validation failed with {len(validation_errors)} issue(s)."
        )
        error_payload = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "requirement_id": REQUIREMENT_ID,
            "reason_code": "contract_validation_failed",
            "errors": validation_errors,
        }
        sys.stdout.write(_json_dumps(error_payload, args.json_pretty))
        return 1

    if _as_text(args.output_json):
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_json_dumps(output_payload, True), encoding="utf-8")
        _timestamped_print(f"Wrote REQ-026 sample payload to {output_path.as_posix()}.")

    _timestamped_print(
        f"Completed REQ-026 Call-1 situational analysis with {len(output_payload['unknowns'])} explicit unknown(s)."
    )
    sys.stdout.write(_json_dumps(output_payload, args.json_pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
