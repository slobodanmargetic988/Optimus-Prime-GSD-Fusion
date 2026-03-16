#!/usr/bin/env python3
"""Contract/data-model surfaces for strategy LLM pipeline calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REQ_046_SCHEMA_VERSION = "req-046.final-strategy-synthesis-composer.v1"
REQ_046_REQUIREMENT_ID = "REQ-046"
REQ_046_ANALYSIS_TYPE = "final_strategy_synthesis_composer"
REQ_046_CALL_ID = "final-strategy-synthesis"
_PACKET_KINDS = ("target-project", "cross-project")
_PRIORITY_LEVELS = ("high", "medium", "low")
_ROUTING_CONFLICT_REASON = "conflicting_packet_routing"
_LOG_BUDGET_MAX_BYTES = 3 * 1024 * 1024 * 1024
_LOG_BUDGET_CHECK_INTERVAL_SECONDS = 15 * 60


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_ts_line(message: str, *, now_utc: str | None = None) -> str:
    stamp = now_utc.strip() if isinstance(now_utc, str) and now_utc.strip() else _utc_timestamp()
    return f"[{stamp}] {message}"


def _default_log_dir() -> Path:
    return Path.home() / "projects" / "LOGS"


def _log_path() -> Path:
    return _default_log_dir() / "strategy_llm_pipeline.log"


def _log_budget_check_stamp() -> Path:
    return _default_log_dir() / ".log_budget_check.strategy_llm_pipeline"


def _maintain_log_budget() -> None:
    log_dir = _default_log_dir()
    stamp = _log_budget_check_stamp()
    now = time.time()
    try:
        if stamp.exists() and now - stamp.stat().st_mtime < _LOG_BUDGET_CHECK_INTERVAL_SECONDS:
            return
        log_dir.mkdir(parents=True, exist_ok=True)
        for candidate in log_dir.glob("*.log"):
            if candidate.stat().st_size <= _LOG_BUDGET_MAX_BYTES:
                continue
            candidate.write_text("", encoding="utf-8")
        stamp.touch()
    except OSError:
        return


def _emit_debug(message: str, *, now_utc: str | None = None) -> None:
    line = _format_ts_line(message, now_utc=now_utc)
    print(line, file=sys.stderr)
    try:
        _maintain_log_budget()
        log_file = _log_path()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _normalize_root(raw_path: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_nonempty_text(raw_path, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


def _normalize_string_list(raw_value: Any, *, field_name: str, allow_empty: bool = True) -> list[str]:
    if raw_value is None:
        if allow_empty:
            return []
        raise ValueError(f"{field_name} must be a non-empty list of strings")
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: set[str] = set()
    for index, item in enumerate(raw_value):
        normalized.add(_require_nonempty_text(item, field_name=f"{field_name}[{index}]"))
    values = sorted(normalized)
    if not allow_empty and not values:
        raise ValueError(f"{field_name} must be a non-empty list of strings")
    return values


def _normalize_positive_int(raw_value: Any, *, field_name: str) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError(f"{field_name} must be a positive integer")
    if raw_value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return raw_value


def _stable_id_fragment(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _collect_unique_refs(*ref_groups: list[str]) -> list[str]:
    refs: set[str] = set()
    for group in ref_groups:
        refs.update(group)
    return sorted(refs)


def _priority_rank(priority: str) -> int:
    return {level: index for index, level in enumerate(_PRIORITY_LEVELS)}[priority]


def _normalize_target_project(raw_value: Any) -> dict[str, str]:
    target_project = _require_mapping(raw_value, field_name="target_project")
    expected_keys = {"project_id", "project_root"}
    unexpected = sorted(set(target_project.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"target_project has unexpected keys: {unexpected}")
    return {
        "project_id": _require_nonempty_text(target_project.get("project_id"), field_name="target_project.project_id"),
        "project_root": _normalize_root(target_project.get("project_root"), field_name="target_project.project_root"),
    }


def _normalize_call_trace(raw_value: Any, *, field_name: str) -> dict[str, str]:
    call_trace = _require_mapping(raw_value, field_name=field_name)
    expected_keys = {"trace_id", "trace_ref", "artifact_ref", "checked_at_utc"}
    unexpected = sorted(set(call_trace.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    return {
        "trace_id": _require_nonempty_text(call_trace.get("trace_id"), field_name=f"{field_name}.trace_id"),
        "trace_ref": _require_nonempty_text(call_trace.get("trace_ref"), field_name=f"{field_name}.trace_ref"),
        "artifact_ref": _require_nonempty_text(call_trace.get("artifact_ref"), field_name=f"{field_name}.artifact_ref"),
        "checked_at_utc": _require_nonempty_text(
            call_trace.get("checked_at_utc"),
            field_name=f"{field_name}.checked_at_utc",
        ),
    }


def _normalize_input_recommendation(raw_value: Any, *, field_name: str) -> dict[str, Any]:
    recommendation = _require_mapping(raw_value, field_name=field_name)
    expected_keys = {
        "recommendation_id",
        "summary",
        "rationale",
        "packet_kind",
        "peer_project_id",
        "lane",
        "sequence_hint",
        "priority",
        "evidence_refs",
    }
    unexpected = sorted(set(recommendation.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    packet_kind = _require_nonempty_text(recommendation.get("packet_kind"), field_name=f"{field_name}.packet_kind").lower()
    if packet_kind not in _PACKET_KINDS:
        raise ValueError(f"{field_name}.packet_kind must be one of: {list(_PACKET_KINDS)}")

    peer_project_id = ""
    if recommendation.get("peer_project_id") is not None:
        peer_project_id = _require_nonempty_text(
            recommendation.get("peer_project_id"),
            field_name=f"{field_name}.peer_project_id",
        )
    if packet_kind == "cross-project" and not peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be set when packet_kind is cross-project")
    if packet_kind == "target-project" and peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be empty when packet_kind is target-project")

    priority = _require_nonempty_text(
        recommendation.get("priority") if recommendation.get("priority") is not None else "medium",
        field_name=f"{field_name}.priority",
    ).lower()
    if priority not in _PRIORITY_LEVELS:
        raise ValueError(f"{field_name}.priority must be one of: {list(_PRIORITY_LEVELS)}")

    return {
        "recommendation_id": _require_nonempty_text(
            recommendation.get("recommendation_id"),
            field_name=f"{field_name}.recommendation_id",
        ),
        "summary": _require_nonempty_text(recommendation.get("summary"), field_name=f"{field_name}.summary"),
        "rationale": _require_nonempty_text(recommendation.get("rationale"), field_name=f"{field_name}.rationale"),
        "packet_kind": packet_kind,
        "peer_project_id": peer_project_id,
        "lane": _require_nonempty_text(recommendation.get("lane"), field_name=f"{field_name}.lane"),
        "sequence_hint": _normalize_positive_int(
            recommendation.get("sequence_hint"),
            field_name=f"{field_name}.sequence_hint",
        ),
        "priority": priority,
        "evidence_refs": _normalize_string_list(
            recommendation.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
            allow_empty=False,
        ),
    }


def _normalize_validated_call_outputs(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("validated_call_outputs must be a non-empty list")

    normalized_calls: list[dict[str, Any]] = []
    seen_trace_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        field_name = f"validated_call_outputs[{index}]"
        call_output = _require_mapping(item, field_name=field_name)
        expected_keys = {"requirement_id", "call_id", "call_status", "call_trace", "recommendations"}
        unexpected = sorted(set(call_output.keys()) - expected_keys)
        if unexpected:
            raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

        call_status = _require_nonempty_text(
            call_output.get("call_status") if call_output.get("call_status") is not None else "validated",
            field_name=f"{field_name}.call_status",
        ).lower()
        if call_status != "validated":
            raise ValueError(f"{field_name}.call_status must be validated")

        call_trace = _normalize_call_trace(call_output.get("call_trace"), field_name=f"{field_name}.call_trace")
        if call_trace["trace_id"] in seen_trace_ids:
            raise ValueError(f"{field_name}.call_trace.trace_id duplicates {call_trace['trace_id']}")
        seen_trace_ids.add(call_trace["trace_id"])

        raw_recommendations = call_output.get("recommendations")
        if not isinstance(raw_recommendations, list) or not raw_recommendations:
            raise ValueError(f"{field_name}.recommendations must be a non-empty list")
        recommendations: list[dict[str, Any]] = []
        seen_recommendation_ids: set[str] = set()
        for recommendation_index, recommendation in enumerate(raw_recommendations):
            normalized = _normalize_input_recommendation(
                recommendation,
                field_name=f"{field_name}.recommendations[{recommendation_index}]",
            )
            recommendation_id = normalized["recommendation_id"]
            if recommendation_id in seen_recommendation_ids:
                raise ValueError(
                    f"{field_name}.recommendations[{recommendation_index}].recommendation_id duplicates {recommendation_id}"
                )
            seen_recommendation_ids.add(recommendation_id)
            recommendations.append(normalized)

        recommendations.sort(
            key=lambda row: (
                row["sequence_hint"],
                _priority_rank(row["priority"]),
                row["recommendation_id"],
            )
        )
        normalized_calls.append(
            {
                "requirement_id": _require_nonempty_text(
                    call_output.get("requirement_id"),
                    field_name=f"{field_name}.requirement_id",
                ),
                "call_id": _require_nonempty_text(call_output.get("call_id"), field_name=f"{field_name}.call_id"),
                "call_status": call_status,
                "call_trace": call_trace,
                "recommendations": recommendations,
            }
        )

    normalized_calls.sort(
        key=lambda row: (
            row["call_id"],
            row["requirement_id"],
            row["call_trace"]["trace_id"],
        )
    )
    return normalized_calls


def _lineage_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row["call_id"]), str(row["requirement_id"]), str(row["trace_id"]))


def _contribution_sort_key(row: Mapping[str, Any]) -> tuple[int, int, str, str, str]:
    return (
        int(row["sequence_hint"]),
        _priority_rank(str(row["priority"])),
        str(row["call_id"]),
        str(row["requirement_id"]),
        str(row["call_trace"]["trace_id"]),
    )


def _build_call_trace_lineage(contributions: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = [
        {
            "call_id": str(row["call_id"]),
            "requirement_id": str(row["requirement_id"]),
            "trace_id": str(row["call_trace"]["trace_id"]),
            "trace_ref": str(row["call_trace"]["trace_ref"]),
            "artifact_ref": str(row["call_trace"]["artifact_ref"]),
            "checked_at_utc": str(row["call_trace"]["checked_at_utc"]),
        }
        for row in contributions
    ]
    rows.sort(key=_lineage_sort_key)
    return rows


def _build_final_strategy_synthesis(
    *,
    target_project: Mapping[str, str],
    validated_call_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for call_output in validated_call_outputs:
        for recommendation in call_output["recommendations"]:
            grouped.setdefault(recommendation["recommendation_id"], []).append(
                {
                    **recommendation,
                    "call_id": call_output["call_id"],
                    "requirement_id": call_output["requirement_id"],
                    "call_trace": call_output["call_trace"],
                }
            )

    final_recommendations: list[dict[str, Any]] = []
    deferred_recommendations: list[dict[str, Any]] = []

    for recommendation_id in sorted(grouped):
        contributions = sorted(grouped[recommendation_id], key=_contribution_sort_key)
        canonical = contributions[0]
        packet_kind_candidates = sorted({str(row["packet_kind"]) for row in contributions})
        peer_project_candidates = sorted({str(row["peer_project_id"]) for row in contributions if row["peer_project_id"]})
        evidence_refs = _collect_unique_refs(*[list(row["evidence_refs"]) for row in contributions])
        call_trace_lineage = _build_call_trace_lineage(contributions)
        contributing_call_ids = sorted({str(row["call_id"]) for row in contributions})
        contributing_requirement_ids = sorted({str(row["requirement_id"]) for row in contributions})

        packet_kind = packet_kind_candidates[0]
        routing_conflict = len(packet_kind_candidates) != 1
        if not routing_conflict and packet_kind == "cross-project" and len(peer_project_candidates) != 1:
            routing_conflict = True
        if not routing_conflict and packet_kind == "target-project" and peer_project_candidates:
            routing_conflict = True

        if routing_conflict:
            deferred_recommendations.append(
                {
                    "recommendation_id": recommendation_id,
                    "summary": canonical["summary"],
                    "deferred_reason_code": _ROUTING_CONFLICT_REASON,
                    "packet_kind_candidates": packet_kind_candidates,
                    "peer_project_candidates": peer_project_candidates,
                    "evidence_refs": evidence_refs,
                    "call_trace_lineage": call_trace_lineage,
                    "contributing_call_ids": contributing_call_ids,
                }
            )
            continue

        final_recommendations.append(
            {
                "recommendation_id": recommendation_id,
                "summary": canonical["summary"],
                "rationale": canonical["rationale"],
                "packet_kind": packet_kind,
                "peer_project_id": peer_project_candidates[0] if peer_project_candidates else "",
                "lane": canonical["lane"],
                "sequence_hint": canonical["sequence_hint"],
                "priority": canonical["priority"],
                "evidence_refs": evidence_refs,
                "call_trace_lineage": call_trace_lineage,
                "contributing_call_ids": contributing_call_ids,
                "contributing_requirement_ids": contributing_requirement_ids,
                "supporting_call_count": len(call_trace_lineage),
                "strategy_packet_input_id": "",
            }
        )

    final_recommendations.sort(
        key=lambda row: (
            row["sequence_hint"],
            _priority_rank(str(row["priority"])),
            row["packet_kind"],
            row["peer_project_id"],
            row["recommendation_id"],
        )
    )
    deferred_recommendations.sort(key=lambda row: row["recommendation_id"])

    packet_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for recommendation in final_recommendations:
        group_key = (
            str(recommendation["packet_kind"]),
            str(recommendation["peer_project_id"]),
            str(recommendation["lane"]),
        )
        packet_groups.setdefault(group_key, []).append(recommendation)

    strategy_packet_inputs: list[dict[str, Any]] = []
    for packet_kind, peer_project_id, lane in sorted(packet_groups):
        recommendations = sorted(
            packet_groups[(packet_kind, peer_project_id, lane)],
            key=lambda row: (
                row["sequence_hint"],
                _priority_rank(str(row["priority"])),
                row["recommendation_id"],
            ),
        )
        packet_input_id = f"pkt.{_stable_id_fragment(packet_kind, peer_project_id or target_project['project_id'], lane)}"
        evidence_refs = _collect_unique_refs(*[list(row["evidence_refs"]) for row in recommendations])
        strategy_packet_inputs.append(
            {
                "packet_input_id": packet_input_id,
                "packet_kind": packet_kind,
                "target_project_id": str(target_project["project_id"]),
                "peer_project_id": peer_project_id,
                "lane": lane,
                "recommendation_ids": [str(row["recommendation_id"]) for row in recommendations],
                "recommendation_count": len(recommendations),
                "earliest_sequence_hint": min(int(row["sequence_hint"]) for row in recommendations),
                "evidence_refs": evidence_refs,
            }
        )
        for recommendation in recommendations:
            recommendation["strategy_packet_input_id"] = packet_input_id

    return {
        "final_recommendations": final_recommendations,
        "deferred_recommendations": deferred_recommendations,
        "strategy_packet_inputs": strategy_packet_inputs,
    }


def build_req_046_final_strategy_synthesis_composer(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-046 payload for final strategy synthesis composition."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_046_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_046_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")

    target_project = _normalize_target_project(raw.get("target_project"))
    validated_call_outputs = _normalize_validated_call_outputs(raw.get("validated_call_outputs"))
    synthesis = _build_final_strategy_synthesis(
        target_project=target_project,
        validated_call_outputs=validated_call_outputs,
    )

    output_payload = {
        "ok": True,
        "schema_version": REQ_046_SCHEMA_VERSION,
        "requirement_id": REQ_046_REQUIREMENT_ID,
        "analysis_type": REQ_046_ANALYSIS_TYPE,
        "call_id": REQ_046_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "final_strategy_synthesis": synthesis,
        "totals": {
            "validated_calls": len(validated_call_outputs),
            "candidate_recommendations": sum(len(row["recommendations"]) for row in validated_call_outputs),
            "final_recommendations": len(synthesis["final_recommendations"]),
            "deferred_recommendations": len(synthesis["deferred_recommendations"]),
            "strategy_packet_inputs": len(synthesis["strategy_packet_inputs"]),
            "call_trace_lineage_rows": sum(
                len(row["call_trace_lineage"])
                for row in (
                    list(synthesis["final_recommendations"]) + list(synthesis["deferred_recommendations"])
                )
            ),
        },
    }

    errors = validate_req_046_final_strategy_synthesis_composer(output_payload)
    if errors:
        raise ValueError(f"built REQ-046 payload failed validation: {errors}")
    return output_payload


def validate_req_046_final_strategy_synthesis_composer(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-046 final strategy synthesis composer payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "target_project",
        "final_strategy_synthesis",
        "totals",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_046_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_046_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_046_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_046_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_046_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_046_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_046_CALL_ID:
        errors.append(f"call_id must be {REQ_046_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    target_project_id = ""
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
    else:
        expected_target_keys = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target_keys - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target_keys)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        target_project_id = str(target_project.get("project_id") or "")
        if not target_project_id:
            errors.append("target_project.project_id must be a non-empty string")
        project_root = target_project.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not project_root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    synthesis = payload.get("final_strategy_synthesis")
    packet_input_ids: set[str] = set()
    if not isinstance(synthesis, Mapping):
        errors.append("final_strategy_synthesis must be an object")
        return errors

    expected_synthesis_keys = {
        "final_recommendations",
        "deferred_recommendations",
        "strategy_packet_inputs",
    }
    synthesis_keys = set(synthesis.keys())
    missing_synthesis = sorted(expected_synthesis_keys - synthesis_keys)
    if missing_synthesis:
        errors.append(f"final_strategy_synthesis missing keys: {missing_synthesis}")
    unexpected_synthesis = sorted(synthesis_keys - expected_synthesis_keys)
    if unexpected_synthesis:
        errors.append(f"final_strategy_synthesis has unexpected keys: {unexpected_synthesis}")

    strategy_packet_inputs = synthesis.get("strategy_packet_inputs")
    if not isinstance(strategy_packet_inputs, list):
        errors.append("final_strategy_synthesis.strategy_packet_inputs must be a list")
        strategy_packet_inputs = []
    else:
        for index, row in enumerate(strategy_packet_inputs):
            if not isinstance(row, Mapping):
                errors.append(f"final_strategy_synthesis.strategy_packet_inputs[{index}] must be an object")
                continue
            expected_keys = {
                "packet_input_id",
                "packet_kind",
                "target_project_id",
                "peer_project_id",
                "lane",
                "recommendation_ids",
                "recommendation_count",
                "earliest_sequence_hint",
                "evidence_refs",
            }
            row_keys = set(row.keys())
            missing_keys = sorted(expected_keys - row_keys)
            if missing_keys:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}] missing keys: {missing_keys}"
                )
            unexpected_keys = sorted(row_keys - expected_keys)
            if unexpected_keys:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}] has unexpected keys: {unexpected_keys}"
                )
            packet_input_id = row.get("packet_input_id")
            if not isinstance(packet_input_id, str) or not packet_input_id.startswith("pkt."):
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].packet_input_id must be like pkt.<id>"
                )
            elif packet_input_id in packet_input_ids:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].packet_input_id must be unique"
                )
            else:
                packet_input_ids.add(packet_input_id)
            packet_kind = row.get("packet_kind")
            if packet_kind not in _PACKET_KINDS:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].packet_kind must be one of: {list(_PACKET_KINDS)}"
                )
            target_project_id_value = row.get("target_project_id")
            if not isinstance(target_project_id_value, str) or not target_project_id_value.strip():
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].target_project_id must be a non-empty string"
                )
            elif target_project_id and target_project_id_value != target_project_id:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].target_project_id must match target_project.project_id"
                )
            peer_project_id = row.get("peer_project_id")
            if not isinstance(peer_project_id, str):
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].peer_project_id must be a string"
                )
            elif packet_kind == "cross-project" and not peer_project_id.strip():
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].peer_project_id must be set for cross-project packets"
                )
            elif packet_kind == "target-project" and peer_project_id.strip():
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].peer_project_id must be empty for target-project packets"
                )
            if not isinstance(row.get("lane"), str) or not str(row.get("lane")).strip():
                errors.append(f"final_strategy_synthesis.strategy_packet_inputs[{index}].lane must be a non-empty string")
            recommendation_ids = row.get("recommendation_ids")
            if not isinstance(recommendation_ids, list) or not recommendation_ids:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].recommendation_ids must be a non-empty list"
                )
            recommendation_count = row.get("recommendation_count")
            if not isinstance(recommendation_count, int) or recommendation_count < 1:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].recommendation_count must be a positive integer"
                )
            elif isinstance(recommendation_ids, list) and recommendation_count != len(recommendation_ids):
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].recommendation_count must match recommendation_ids length"
                )
            earliest_sequence_hint = row.get("earliest_sequence_hint")
            if not isinstance(earliest_sequence_hint, int) or earliest_sequence_hint < 1:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].earliest_sequence_hint must be a positive integer"
                )
            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(
                    f"final_strategy_synthesis.strategy_packet_inputs[{index}].evidence_refs must be a non-empty list"
                )

    def _validate_lineage_rows(rows: Any, *, field_name: str) -> None:
        if not isinstance(rows, list) or not rows:
            errors.append(f"{field_name} must be a non-empty list")
            return
        seen_trace_ids: set[str] = set()
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                errors.append(f"{field_name}[{index}] must be an object")
                continue
            expected_keys = {"call_id", "requirement_id", "trace_id", "trace_ref", "artifact_ref", "checked_at_utc"}
            row_keys = set(row.keys())
            missing_keys = sorted(expected_keys - row_keys)
            if missing_keys:
                errors.append(f"{field_name}[{index}] missing keys: {missing_keys}")
            unexpected_keys = sorted(row_keys - expected_keys)
            if unexpected_keys:
                errors.append(f"{field_name}[{index}] has unexpected keys: {unexpected_keys}")
            trace_id = row.get("trace_id")
            if not isinstance(trace_id, str) or not trace_id.strip():
                errors.append(f"{field_name}[{index}].trace_id must be a non-empty string")
            elif trace_id in seen_trace_ids:
                errors.append(f"{field_name}[{index}].trace_id must be unique within the lineage list")
            else:
                seen_trace_ids.add(trace_id)
            for key in ("call_id", "requirement_id", "trace_ref", "artifact_ref", "checked_at_utc"):
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{field_name}[{index}].{key} must be a non-empty string")

    final_recommendations = synthesis.get("final_recommendations")
    seen_final_ids: set[str] = set()
    referenced_packet_input_ids: set[str] = set()
    if not isinstance(final_recommendations, list):
        errors.append("final_strategy_synthesis.final_recommendations must be a list")
        final_recommendations = []
    else:
        for index, row in enumerate(final_recommendations):
            if not isinstance(row, Mapping):
                errors.append(f"final_strategy_synthesis.final_recommendations[{index}] must be an object")
                continue
            expected_keys = {
                "recommendation_id",
                "summary",
                "rationale",
                "packet_kind",
                "peer_project_id",
                "lane",
                "sequence_hint",
                "priority",
                "evidence_refs",
                "call_trace_lineage",
                "contributing_call_ids",
                "contributing_requirement_ids",
                "supporting_call_count",
                "strategy_packet_input_id",
            }
            row_keys = set(row.keys())
            missing_keys = sorted(expected_keys - row_keys)
            if missing_keys:
                errors.append(f"final_strategy_synthesis.final_recommendations[{index}] missing keys: {missing_keys}")
            unexpected_keys = sorted(row_keys - expected_keys)
            if unexpected_keys:
                errors.append(f"final_strategy_synthesis.final_recommendations[{index}] has unexpected keys: {unexpected_keys}")
            recommendation_id = row.get("recommendation_id")
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].recommendation_id must be a non-empty string"
                )
            elif recommendation_id in seen_final_ids:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].recommendation_id must be unique"
                )
            else:
                seen_final_ids.add(recommendation_id)
            for key in ("summary", "rationale", "lane"):
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"final_strategy_synthesis.final_recommendations[{index}].{key} must be a non-empty string")
            packet_kind = row.get("packet_kind")
            if packet_kind not in _PACKET_KINDS:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].packet_kind must be one of: {list(_PACKET_KINDS)}"
                )
            peer_project_id = row.get("peer_project_id")
            if not isinstance(peer_project_id, str):
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].peer_project_id must be a string"
                )
            elif packet_kind == "cross-project" and not peer_project_id.strip():
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].peer_project_id must be set for cross-project recommendations"
                )
            elif packet_kind == "target-project" and peer_project_id.strip():
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].peer_project_id must be empty for target-project recommendations"
                )
            sequence_hint = row.get("sequence_hint")
            if not isinstance(sequence_hint, int) or sequence_hint < 1:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].sequence_hint must be a positive integer"
                )
            priority = row.get("priority")
            if priority not in _PRIORITY_LEVELS:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].priority must be one of: {list(_PRIORITY_LEVELS)}"
                )
            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].evidence_refs must be a non-empty list"
                )
            _validate_lineage_rows(
                row.get("call_trace_lineage"),
                field_name=f"final_strategy_synthesis.final_recommendations[{index}].call_trace_lineage",
            )
            contributing_call_ids = row.get("contributing_call_ids")
            if not isinstance(contributing_call_ids, list) or not contributing_call_ids:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].contributing_call_ids must be a non-empty list"
                )
            contributing_requirement_ids = row.get("contributing_requirement_ids")
            if not isinstance(contributing_requirement_ids, list) or not contributing_requirement_ids:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].contributing_requirement_ids must be a non-empty list"
                )
            supporting_call_count = row.get("supporting_call_count")
            lineage_rows = row.get("call_trace_lineage") if isinstance(row.get("call_trace_lineage"), list) else []
            if not isinstance(supporting_call_count, int) or supporting_call_count < 1:
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].supporting_call_count must be a positive integer"
                )
            elif lineage_rows and supporting_call_count != len(lineage_rows):
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].supporting_call_count must match call_trace_lineage length"
                )
            strategy_packet_input_id = row.get("strategy_packet_input_id")
            if not isinstance(strategy_packet_input_id, str) or not strategy_packet_input_id.startswith("pkt."):
                errors.append(
                    f"final_strategy_synthesis.final_recommendations[{index}].strategy_packet_input_id must be like pkt.<id>"
                )
            else:
                referenced_packet_input_ids.add(strategy_packet_input_id)

    deferred_recommendations = synthesis.get("deferred_recommendations")
    seen_deferred_ids: set[str] = set()
    if not isinstance(deferred_recommendations, list):
        errors.append("final_strategy_synthesis.deferred_recommendations must be a list")
        deferred_recommendations = []
    else:
        for index, row in enumerate(deferred_recommendations):
            if not isinstance(row, Mapping):
                errors.append(f"final_strategy_synthesis.deferred_recommendations[{index}] must be an object")
                continue
            expected_keys = {
                "recommendation_id",
                "summary",
                "deferred_reason_code",
                "packet_kind_candidates",
                "peer_project_candidates",
                "evidence_refs",
                "call_trace_lineage",
                "contributing_call_ids",
            }
            row_keys = set(row.keys())
            missing_keys = sorted(expected_keys - row_keys)
            if missing_keys:
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}] missing keys: {missing_keys}"
                )
            unexpected_keys = sorted(row_keys - expected_keys)
            if unexpected_keys:
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}] has unexpected keys: {unexpected_keys}"
                )
            recommendation_id = row.get("recommendation_id")
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}].recommendation_id must be a non-empty string"
                )
            elif recommendation_id in seen_deferred_ids or recommendation_id in seen_final_ids:
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}].recommendation_id must be unique across synthesis output"
                )
            else:
                seen_deferred_ids.add(recommendation_id)
            if not isinstance(row.get("summary"), str) or not str(row.get("summary")).strip():
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}].summary must be a non-empty string"
                )
            if row.get("deferred_reason_code") != _ROUTING_CONFLICT_REASON:
                errors.append(
                    f"final_strategy_synthesis.deferred_recommendations[{index}].deferred_reason_code must be {_ROUTING_CONFLICT_REASON}"
                )
            for key in ("packet_kind_candidates", "peer_project_candidates", "evidence_refs", "contributing_call_ids"):
                value = row.get(key)
                if not isinstance(value, list):
                    errors.append(
                        f"final_strategy_synthesis.deferred_recommendations[{index}].{key} must be a list"
                    )
            _validate_lineage_rows(
                row.get("call_trace_lineage"),
                field_name=f"final_strategy_synthesis.deferred_recommendations[{index}].call_trace_lineage",
            )

    if packet_input_ids and referenced_packet_input_ids != packet_input_ids:
        errors.append(
            "final_strategy_synthesis.final_recommendations.strategy_packet_input_id values must cover all strategy_packet_inputs"
        )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "validated_calls",
            "candidate_recommendations",
            "final_recommendations",
            "deferred_recommendations",
            "strategy_packet_inputs",
            "call_trace_lineage_rows",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_total_keys - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_total_keys)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        for key in expected_total_keys:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")

        if totals.get("final_recommendations") != len(final_recommendations):
            errors.append("totals.final_recommendations must match synthesized final recommendations count")
        if totals.get("deferred_recommendations") != len(deferred_recommendations):
            errors.append("totals.deferred_recommendations must match synthesized deferred recommendations count")
        if totals.get("strategy_packet_inputs") != len(strategy_packet_inputs):
            errors.append("totals.strategy_packet_inputs must match synthesized packet input count")

        expected_lineage_rows = 0
        unique_trace_ids: set[str] = set()
        for collection in (final_recommendations, deferred_recommendations):
            for row in collection:
                if isinstance(row, Mapping) and isinstance(row.get("call_trace_lineage"), list):
                    expected_lineage_rows += len(row["call_trace_lineage"])
                    unique_trace_ids.update(
                        str(lineage_row.get("trace_id"))
                        for lineage_row in row["call_trace_lineage"]
                        if isinstance(lineage_row, Mapping) and str(lineage_row.get("trace_id") or "").strip()
                    )
        if totals.get("call_trace_lineage_rows") != expected_lineage_rows:
            errors.append("totals.call_trace_lineage_rows must match all synthesized lineage rows")
        if totals.get("candidate_recommendations") != expected_lineage_rows:
            errors.append("totals.candidate_recommendations must match all synthesized candidate recommendation rows")
        if totals.get("validated_calls") != len(unique_trace_ids):
            errors.append("totals.validated_calls must match unique call trace lineage rows")

    return errors


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type != REQ_046_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_046_ANALYSIS_TYPE}")
    return build_req_046_final_strategy_synthesis_composer(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit REQ-046 final strategy synthesis composer payload.")
    parser.add_argument("--input-json", required=True, help='Input payload path or "-" for stdin.')
    parser.add_argument("--output-json", default="-", help='Output path or "-" for stdout.')
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    try:
        if args.input_json == "-":
            payload = json.loads(sys.stdin.read())
        else:
            payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input payload must be a JSON object")

        output_payload = run(payload)
        rendered = json.dumps(output_payload, indent=2 if args.json_pretty else None, sort_keys=False)
        if args.output_json == "-":
            print(rendered)
        else:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered + "\n", encoding="utf-8")
        return 0
    except Exception as exc:  # pragma: no cover - CLI error path exercised indirectly.
        _emit_debug(f"REQ-046 CLI failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
