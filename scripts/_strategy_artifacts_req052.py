#!/usr/bin/env python3
"""REQ-048 contract/data-model surface for STRATEGY.md narrative generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REQ_048_SCHEMA_VERSION = "req-048.strategy-md-generator.v1"
REQ_048_REQUIREMENT_ID = "REQ-048"
REQ_048_ANALYSIS_TYPE = "strategy_md_generator"
REQ_048_CALL_ID = "strategy-md-generator"
REQ_050_SCHEMA_VERSION = "req-050.ecosystem-link-map-json-generator.v1"
REQ_050_REQUIREMENT_ID = "REQ-050"
REQ_050_ANALYSIS_TYPE = "ecosystem_link_map_json_generator"
REQ_050_CALL_ID = "ecosystem-link-map-json-generator"
REQ_051_SCHEMA_VERSION = "req-051.strategy-changelog-md-generator.v1"
REQ_051_REQUIREMENT_ID = "REQ-051"
REQ_051_ANALYSIS_TYPE = "strategy_changelog_md_generator"
REQ_051_CALL_ID = "strategy-changelog-md-generator"
REQ_052_SCHEMA_VERSION = "req-052.strategy-packet-v1-generator.v1"
REQ_052_REQUIREMENT_ID = "REQ-052"
REQ_052_ANALYSIS_TYPE = "strategy_packet_v1_generator"
REQ_052_CALL_ID = "strategy-packet-v1-generator"
REQ_053_SCHEMA_VERSION = "req-053.recommendation-id-stability-contract.v1"
REQ_053_REQUIREMENT_ID = "REQ-053"
REQ_053_ANALYSIS_TYPE = "recommendation_id_stability_contract"
REQ_053_CALL_ID = "recommendation-id-stability-contract"
STRATEGY_PACKET_V1_SCHEMA_VERSION = "strategy-packet.v1"
_PACKET_KINDS = ("target-project", "cross-project")
_PRIORITY_LEVELS = ("high", "medium", "low")
_CONFIDENCE_LEVELS = ("high", "medium", "low")
_OBLIGATION_STATUSES = ("active", "blocked", "proposed")
_CHANGE_SECTION_KEYS = ("mission_scope", "runtime_data", "ecosystem_signals")
_CHANGE_TYPES = ("added", "removed", "updated")
_DELTA_TYPES = ("new", "updated", "retained", "derived")
_RISK_LEVELS = ("low", "medium", "high", "critical")
_KPI_DIRECTIONS = ("increase", "decrease", "maintain")
_REQ_053_SCENARIO_KINDS = ("no-change", "substantive-change")
_REQ_053_RESULT_STATUSES = ("stable", "evolved", "added", "removed")
_REQ_053_STABILITY_FIELDS = (
    "summary",
    "rationale",
    "packet_kind",
    "peer_project_id",
    "lane",
    "priority",
)
_REQ_053_REQUIRED_RECOMMENDATION_FIELDS = (
    "lineage_key",
    "recommendation_id",
    "summary",
    "rationale",
    "packet_kind",
    "peer_project_id",
    "lane",
    "priority",
    "evidence_refs",
)
_REQ_052_REQUIRED_SYNTHESIS_RECOMMENDATION_FIELDS = (
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
)
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
    return _default_log_dir() / "strategy_artifacts_handoff.log"


def _log_budget_check_stamp() -> Path:
    return _default_log_dir() / ".log_budget_check.strategy_artifacts_handoff"


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


def _normalize_root(value: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_nonempty_text(value, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


def _normalize_nonempty_str_list(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: set[str] = set()
    for index, item in enumerate(value):
        normalized.add(_require_nonempty_text(item, field_name=f"{field_name}[{index}]"))
    values = sorted(normalized)
    if not values:
        raise ValueError(f"{field_name} must be a non-empty list of strings")
    return values


def _normalize_optional_str_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: set[str] = set()
    for index, item in enumerate(value):
        normalized.add(_require_nonempty_text(item, field_name=f"{field_name}[{index}]"))
    return sorted(normalized)


def _normalize_positive_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be a positive integer")
    if value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _normalize_non_negative_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _require_canonical_id(value: Any, *, field_name: str, prefix: str) -> str:
    text = _require_nonempty_text(value, field_name=field_name)
    if not re.fullmatch(rf"{re.escape(prefix)}\.[a-z0-9][a-z0-9-]{{1,95}}", text):
        raise ValueError(f"{field_name} must match {prefix}.<lowercase-hyphenated-id>")
    return text


def _normalize_trace_lineage_rows(value: Any, *, field_name: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[dict[str, str]] = []
    seen_trace_ids: set[str] = set()
    for index, row in enumerate(value):
        mapping = _require_mapping(row, field_name=f"{field_name}[{index}]")
        expected = {"call_id", "requirement_id", "trace_id", "trace_ref", "artifact_ref", "checked_at_utc"}
        unexpected = sorted(set(mapping.keys()) - expected)
        if unexpected:
            raise ValueError(f"{field_name}[{index}] has unexpected keys: {unexpected}")
        trace_id = _require_nonempty_text(mapping.get("trace_id"), field_name=f"{field_name}[{index}].trace_id")
        if trace_id in seen_trace_ids:
            raise ValueError(f"{field_name}[{index}].trace_id must be unique")
        seen_trace_ids.add(trace_id)
        normalized.append(
            {
                "call_id": _require_nonempty_text(mapping.get("call_id"), field_name=f"{field_name}[{index}].call_id"),
                "requirement_id": _require_nonempty_text(
                    mapping.get("requirement_id"),
                    field_name=f"{field_name}[{index}].requirement_id",
                ),
                "trace_id": trace_id,
                "trace_ref": _require_nonempty_text(
                    mapping.get("trace_ref"),
                    field_name=f"{field_name}[{index}].trace_ref",
                ),
                "artifact_ref": _require_nonempty_text(
                    mapping.get("artifact_ref"),
                    field_name=f"{field_name}[{index}].artifact_ref",
                ),
                "checked_at_utc": _require_nonempty_text(
                    mapping.get("checked_at_utc"),
                    field_name=f"{field_name}[{index}].checked_at_utc",
                ),
            }
        )
    return sorted(normalized, key=lambda row: (row["trace_id"], row["call_id"]))


def _normalize_target_project(value: Any) -> dict[str, str]:
    target_project = _require_mapping(value, field_name="target_project")
    expected = {"project_id", "project_root"}
    unexpected = sorted(set(target_project.keys()) - expected)
    if unexpected:
        raise ValueError(f"target_project has unexpected keys: {unexpected}")
    return {
        "project_id": _require_nonempty_text(target_project.get("project_id"), field_name="target_project.project_id"),
        "project_root": _normalize_root(target_project.get("project_root"), field_name="target_project.project_root"),
    }


def _priority_rank(priority: str) -> int:
    return {level: index for index, level in enumerate(_PRIORITY_LEVELS)}[priority]


def _normalize_final_recommendation(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {
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
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    packet_kind = _require_nonempty_text(row.get("packet_kind"), field_name=f"{field_name}.packet_kind").lower()
    if packet_kind not in _PACKET_KINDS:
        raise ValueError(f"{field_name}.packet_kind must be one of: {list(_PACKET_KINDS)}")

    peer_project_raw = row.get("peer_project_id")
    if peer_project_raw is None:
        peer_project_id = ""
    elif isinstance(peer_project_raw, str):
        peer_project_id = peer_project_raw.strip()
    else:
        raise ValueError(f"{field_name}.peer_project_id must be a string when provided")
    if packet_kind == "cross-project" and not peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be set for cross-project recommendations")
    if packet_kind == "target-project" and peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be empty for target-project recommendations")

    priority = _require_nonempty_text(row.get("priority"), field_name=f"{field_name}.priority").lower()
    if priority not in _PRIORITY_LEVELS:
        raise ValueError(f"{field_name}.priority must be one of: {list(_PRIORITY_LEVELS)}")

    contributing_call_ids = _normalize_nonempty_str_list(
        row.get("contributing_call_ids"),
        field_name=f"{field_name}.contributing_call_ids",
    )
    supporting_call_count = _normalize_positive_int(
        row.get("supporting_call_count"),
        field_name=f"{field_name}.supporting_call_count",
    )
    if supporting_call_count != len(contributing_call_ids):
        raise ValueError(
            f"{field_name}.supporting_call_count must equal len({field_name}.contributing_call_ids)"
        )

    strategy_packet_input_id = _require_nonempty_text(
        row.get("strategy_packet_input_id"),
        field_name=f"{field_name}.strategy_packet_input_id",
    )
    if not strategy_packet_input_id.startswith("pkt."):
        raise ValueError(f"{field_name}.strategy_packet_input_id must start with pkt.")

    return {
        "recommendation_id": _require_nonempty_text(row.get("recommendation_id"), field_name=f"{field_name}.recommendation_id"),
        "summary": _require_nonempty_text(row.get("summary"), field_name=f"{field_name}.summary"),
        "rationale": _require_nonempty_text(row.get("rationale"), field_name=f"{field_name}.rationale"),
        "packet_kind": packet_kind,
        "peer_project_id": peer_project_id,
        "lane": _require_nonempty_text(row.get("lane"), field_name=f"{field_name}.lane"),
        "sequence_hint": _normalize_positive_int(row.get("sequence_hint"), field_name=f"{field_name}.sequence_hint"),
        "priority": priority,
        "evidence_refs": _normalize_nonempty_str_list(row.get("evidence_refs"), field_name=f"{field_name}.evidence_refs"),
        "call_trace_lineage": _normalize_trace_lineage_rows(
            row.get("call_trace_lineage"),
            field_name=f"{field_name}.call_trace_lineage",
        ),
        "contributing_call_ids": contributing_call_ids,
        "contributing_requirement_ids": _normalize_nonempty_str_list(
            row.get("contributing_requirement_ids"),
            field_name=f"{field_name}.contributing_requirement_ids",
        ),
        "supporting_call_count": supporting_call_count,
        "strategy_packet_input_id": strategy_packet_input_id,
    }


def _normalize_deferred_recommendation(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {
        "recommendation_id",
        "summary",
        "deferred_reason_code",
        "packet_kind_candidates",
        "peer_project_candidates",
        "evidence_refs",
        "call_trace_lineage",
        "contributing_call_ids",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    packet_kind_candidates = _normalize_nonempty_str_list(
        row.get("packet_kind_candidates"),
        field_name=f"{field_name}.packet_kind_candidates",
    )
    for packet_kind in packet_kind_candidates:
        if packet_kind not in _PACKET_KINDS:
            raise ValueError(f"{field_name}.packet_kind_candidates contains unsupported packet kind: {packet_kind}")

    return {
        "recommendation_id": _require_nonempty_text(row.get("recommendation_id"), field_name=f"{field_name}.recommendation_id"),
        "summary": _require_nonempty_text(row.get("summary"), field_name=f"{field_name}.summary"),
        "deferred_reason_code": _require_nonempty_text(
            row.get("deferred_reason_code"),
            field_name=f"{field_name}.deferred_reason_code",
        ),
        "packet_kind_candidates": packet_kind_candidates,
        "peer_project_candidates": _normalize_optional_str_list(
            row.get("peer_project_candidates"),
            field_name=f"{field_name}.peer_project_candidates",
        ),
        "evidence_refs": _normalize_nonempty_str_list(row.get("evidence_refs"), field_name=f"{field_name}.evidence_refs"),
        "call_trace_lineage": _normalize_trace_lineage_rows(
            row.get("call_trace_lineage"),
            field_name=f"{field_name}.call_trace_lineage",
        ),
        "contributing_call_ids": _normalize_nonempty_str_list(
            row.get("contributing_call_ids"),
            field_name=f"{field_name}.contributing_call_ids",
        ),
    }


def _normalize_open_risk(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {
        "open_risk_id",
        "recommendation_id",
        "summary",
        "reason_code",
        "project_id",
        "required_evidence_refs",
        "evidence_refs",
        "linked_recommendation_ids",
        "call_trace_lineage",
        "contributing_call_ids",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    return {
        "open_risk_id": _require_nonempty_text(row.get("open_risk_id"), field_name=f"{field_name}.open_risk_id"),
        "recommendation_id": _require_nonempty_text(
            row.get("recommendation_id"),
            field_name=f"{field_name}.recommendation_id",
        ),
        "summary": _require_nonempty_text(row.get("summary"), field_name=f"{field_name}.summary"),
        "reason_code": _require_nonempty_text(row.get("reason_code"), field_name=f"{field_name}.reason_code"),
        "project_id": _require_nonempty_text(row.get("project_id"), field_name=f"{field_name}.project_id"),
        "required_evidence_refs": _normalize_nonempty_str_list(
            row.get("required_evidence_refs"),
            field_name=f"{field_name}.required_evidence_refs",
        ),
        "evidence_refs": _normalize_nonempty_str_list(row.get("evidence_refs"), field_name=f"{field_name}.evidence_refs"),
        "linked_recommendation_ids": _normalize_optional_str_list(
            row.get("linked_recommendation_ids"),
            field_name=f"{field_name}.linked_recommendation_ids",
        ),
        "call_trace_lineage": _normalize_trace_lineage_rows(
            row.get("call_trace_lineage") or [],
            field_name=f"{field_name}.call_trace_lineage",
        ),
        "contributing_call_ids": _normalize_optional_str_list(
            row.get("contributing_call_ids"),
            field_name=f"{field_name}.contributing_call_ids",
        ),
    }


def _normalize_strategy_packet_input(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {
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
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    packet_kind = _require_nonempty_text(row.get("packet_kind"), field_name=f"{field_name}.packet_kind")
    if packet_kind not in _PACKET_KINDS:
        raise ValueError(f"{field_name}.packet_kind must be one of: {list(_PACKET_KINDS)}")

    peer_project_raw = row.get("peer_project_id")
    if peer_project_raw is None:
        peer_project_id = ""
    elif isinstance(peer_project_raw, str):
        peer_project_id = peer_project_raw.strip()
    else:
        raise ValueError(f"{field_name}.peer_project_id must be a string when provided")
    if packet_kind == "cross-project" and not peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be set for cross-project packet inputs")
    if packet_kind == "target-project" and peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be empty for target-project packet inputs")

    recommendation_ids = _normalize_nonempty_str_list(
        row.get("recommendation_ids"),
        field_name=f"{field_name}.recommendation_ids",
    )
    recommendation_count = _normalize_positive_int(
        row.get("recommendation_count"),
        field_name=f"{field_name}.recommendation_count",
    )
    if recommendation_count != len(recommendation_ids):
        raise ValueError(f"{field_name}.recommendation_count must equal len({field_name}.recommendation_ids)")

    packet_input_id = _require_nonempty_text(row.get("packet_input_id"), field_name=f"{field_name}.packet_input_id")
    if not packet_input_id.startswith("pkt."):
        raise ValueError(f"{field_name}.packet_input_id must start with pkt.")

    return {
        "packet_input_id": packet_input_id,
        "packet_kind": packet_kind,
        "target_project_id": _require_nonempty_text(
            row.get("target_project_id"),
            field_name=f"{field_name}.target_project_id",
        ),
        "peer_project_id": peer_project_id,
        "lane": _require_nonempty_text(row.get("lane"), field_name=f"{field_name}.lane"),
        "recommendation_ids": recommendation_ids,
        "recommendation_count": recommendation_count,
        "earliest_sequence_hint": _normalize_positive_int(
            row.get("earliest_sequence_hint"),
            field_name=f"{field_name}.earliest_sequence_hint",
        ),
        "evidence_refs": _normalize_nonempty_str_list(row.get("evidence_refs"), field_name=f"{field_name}.evidence_refs"),
    }


def _normalize_cross_project_context_usage(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {
            "cross_project_context_provided": False,
            "cross_project_context_used": False,
            "projects_considered": [],
            "earth_sweep_evidence_refs_considered": [],
            "cross_project_obligation_count": 0,
            "unresolved_idea_count": 0,
            "recommendation_ids_with_context": [],
        }

    row = _require_mapping(value, field_name=field_name)
    expected = {
        "cross_project_context_provided",
        "cross_project_context_used",
        "projects_considered",
        "earth_sweep_evidence_refs_considered",
        "cross_project_obligation_count",
        "unresolved_idea_count",
        "recommendation_ids_with_context",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    provided = row.get("cross_project_context_provided")
    used = row.get("cross_project_context_used")
    if not isinstance(provided, bool):
        raise ValueError(f"{field_name}.cross_project_context_provided must be a boolean")
    if not isinstance(used, bool):
        raise ValueError(f"{field_name}.cross_project_context_used must be a boolean")

    return {
        "cross_project_context_provided": provided,
        "cross_project_context_used": used,
        "projects_considered": _normalize_optional_str_list(
            row.get("projects_considered"),
            field_name=f"{field_name}.projects_considered",
        ),
        "earth_sweep_evidence_refs_considered": _normalize_optional_str_list(
            row.get("earth_sweep_evidence_refs_considered"),
            field_name=f"{field_name}.earth_sweep_evidence_refs_considered",
        ),
        "cross_project_obligation_count": _normalize_non_negative_int(
            row.get("cross_project_obligation_count"),
            field_name=f"{field_name}.cross_project_obligation_count",
        ),
        "unresolved_idea_count": _normalize_non_negative_int(
            row.get("unresolved_idea_count"),
            field_name=f"{field_name}.unresolved_idea_count",
        ),
        "recommendation_ids_with_context": _normalize_optional_str_list(
            row.get("recommendation_ids_with_context"),
            field_name=f"{field_name}.recommendation_ids_with_context",
        ),
    }


def _normalize_req_053_cross_project_obligation(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {"target_project_id", "recommendation_ids", "earth_sweep_evidence_refs"}
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    missing = sorted({"target_project_id", "recommendation_ids"} - set(row.keys()))
    if missing:
        raise ValueError(f"{field_name} missing keys: {missing}")
    return {
        "target_project_id": _require_nonempty_text(
            row.get("target_project_id"),
            field_name=f"{field_name}.target_project_id",
        ),
        "recommendation_ids": _normalize_nonempty_str_list(
            row.get("recommendation_ids"),
            field_name=f"{field_name}.recommendation_ids",
        ),
        "earth_sweep_evidence_refs": _normalize_optional_str_list(
            row.get("earth_sweep_evidence_refs"),
            field_name=f"{field_name}.earth_sweep_evidence_refs",
        ),
    }


def _normalize_req_053_unresolved_idea(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {
        "idea_id",
        "summary",
        "target_project_id",
        "recommendation_ids",
        "earth_sweep_evidence_refs",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    missing = sorted({"idea_id", "summary", "target_project_id"} - set(row.keys()))
    if missing:
        raise ValueError(f"{field_name} missing keys: {missing}")
    return {
        "idea_id": _require_nonempty_text(row.get("idea_id"), field_name=f"{field_name}.idea_id"),
        "summary": _require_nonempty_text(row.get("summary"), field_name=f"{field_name}.summary"),
        "target_project_id": _require_nonempty_text(
            row.get("target_project_id"),
            field_name=f"{field_name}.target_project_id",
        ),
        "recommendation_ids": _normalize_optional_str_list(
            row.get("recommendation_ids"),
            field_name=f"{field_name}.recommendation_ids",
        ),
        "earth_sweep_evidence_refs": _normalize_optional_str_list(
            row.get("earth_sweep_evidence_refs"),
            field_name=f"{field_name}.earth_sweep_evidence_refs",
        ),
    }


def _normalize_req_053_broad_sweep_context(value: Any) -> dict[str, Any]:
    if value is None:
        return {
            "earth_sweep_evidence_refs": [],
            "projects_considered": [],
            "cross_project_obligations": [],
            "unresolved_ideas": [],
        }

    row = _require_mapping(value, field_name="broad_sweep_context")
    expected = {
        "earth_sweep_evidence_refs",
        "projects_considered",
        "cross_project_obligations",
        "unresolved_ideas",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"broad_sweep_context has unexpected keys: {unexpected}")

    obligations_raw = row.get("cross_project_obligations") or []
    if not isinstance(obligations_raw, list):
        raise ValueError("broad_sweep_context.cross_project_obligations must be a list")
    obligations = [
        _normalize_req_053_cross_project_obligation(
            item,
            field_name=f"broad_sweep_context.cross_project_obligations[{index}]",
        )
        for index, item in enumerate(obligations_raw)
    ]
    obligations.sort(
        key=lambda item: (
            item["target_project_id"],
            ",".join(item["recommendation_ids"]),
            ",".join(item["earth_sweep_evidence_refs"]),
        )
    )

    unresolved_raw = row.get("unresolved_ideas") or []
    if not isinstance(unresolved_raw, list):
        raise ValueError("broad_sweep_context.unresolved_ideas must be a list")
    unresolved_ideas = [
        _normalize_req_053_unresolved_idea(
            item,
            field_name=f"broad_sweep_context.unresolved_ideas[{index}]",
        )
        for index, item in enumerate(unresolved_raw)
    ]
    unresolved_ideas.sort(key=lambda item: (item["idea_id"], item["target_project_id"]))

    return {
        "earth_sweep_evidence_refs": _normalize_optional_str_list(
            row.get("earth_sweep_evidence_refs"),
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
        ),
        "projects_considered": _normalize_optional_str_list(
            row.get("projects_considered"),
            field_name="broad_sweep_context.projects_considered",
        ),
        "cross_project_obligations": obligations,
        "unresolved_ideas": unresolved_ideas,
    }


def _normalize_multi_call_trace(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("multi_call_orchestration_trace must be a list")
    rows: list[dict[str, Any]] = []
    seen_trace_ids: set[str] = set()
    for index, row in enumerate(value):
        mapping = _require_mapping(row, field_name=f"multi_call_orchestration_trace[{index}]")
        expected = {
            "call_id",
            "requirement_id",
            "trace_id",
            "trace_ref",
            "artifact_ref",
            "checked_at_utc",
            "call_objective",
            "input_refs",
            "output_refs",
            "handoff_summary",
        }
        unexpected = sorted(set(mapping.keys()) - expected)
        if unexpected:
            raise ValueError(f"multi_call_orchestration_trace[{index}] has unexpected keys: {unexpected}")
        trace_id = _require_nonempty_text(mapping.get("trace_id"), field_name=f"multi_call_orchestration_trace[{index}].trace_id")
        if trace_id in seen_trace_ids:
            raise ValueError(f"multi_call_orchestration_trace[{index}].trace_id must be unique")
        seen_trace_ids.add(trace_id)
        rows.append(
            {
                "call_id": _require_nonempty_text(
                    mapping.get("call_id"),
                    field_name=f"multi_call_orchestration_trace[{index}].call_id",
                ),
                "requirement_id": _require_nonempty_text(
                    mapping.get("requirement_id"),
                    field_name=f"multi_call_orchestration_trace[{index}].requirement_id",
                ),
                "trace_id": trace_id,
                "trace_ref": _require_nonempty_text(
                    mapping.get("trace_ref"),
                    field_name=f"multi_call_orchestration_trace[{index}].trace_ref",
                ),
                "artifact_ref": _require_nonempty_text(
                    mapping.get("artifact_ref"),
                    field_name=f"multi_call_orchestration_trace[{index}].artifact_ref",
                ),
                "checked_at_utc": _require_nonempty_text(
                    mapping.get("checked_at_utc"),
                    field_name=f"multi_call_orchestration_trace[{index}].checked_at_utc",
                ),
                "call_objective": _require_nonempty_text(
                    mapping.get("call_objective"),
                    field_name=f"multi_call_orchestration_trace[{index}].call_objective",
                ),
                "input_refs": _normalize_nonempty_str_list(
                    mapping.get("input_refs"),
                    field_name=f"multi_call_orchestration_trace[{index}].input_refs",
                ),
                "output_refs": _normalize_nonempty_str_list(
                    mapping.get("output_refs"),
                    field_name=f"multi_call_orchestration_trace[{index}].output_refs",
                ),
                "handoff_summary": _require_nonempty_text(
                    mapping.get("handoff_summary"),
                    field_name=f"multi_call_orchestration_trace[{index}].handoff_summary",
                ),
            }
        )
    return sorted(rows, key=lambda row: (row["trace_id"], row["call_id"]))


def _normalize_final_strategy_synthesis(value: Any) -> dict[str, Any]:
    synthesis = _require_mapping(value, field_name="final_strategy_synthesis")
    expected = {
        "final_recommendations",
        "deferred_recommendations",
        "open_risks",
        "strategy_packet_inputs",
        "cross_project_context_usage",
    }
    required = {
        "final_recommendations",
        "deferred_recommendations",
        "open_risks",
        "strategy_packet_inputs",
    }
    missing = sorted(required - set(synthesis.keys()))
    if missing:
        raise ValueError(f"final_strategy_synthesis missing keys: {missing}")
    unexpected = sorted(set(synthesis.keys()) - expected)
    if unexpected:
        raise ValueError(f"final_strategy_synthesis has unexpected keys: {unexpected}")

    final_recommendations_raw = synthesis.get("final_recommendations")
    if not isinstance(final_recommendations_raw, list):
        raise ValueError("final_strategy_synthesis.final_recommendations must be a list")
    final_recommendations = [
        _normalize_final_recommendation(row, field_name=f"final_strategy_synthesis.final_recommendations[{index}]")
        for index, row in enumerate(final_recommendations_raw)
    ]
    final_recommendations.sort(
        key=lambda row: (
            row["sequence_hint"],
            _priority_rank(row["priority"]),
            row["recommendation_id"],
        )
    )

    deferred_raw = synthesis.get("deferred_recommendations")
    if not isinstance(deferred_raw, list):
        raise ValueError("final_strategy_synthesis.deferred_recommendations must be a list")
    deferred_recommendations = [
        _normalize_deferred_recommendation(row, field_name=f"final_strategy_synthesis.deferred_recommendations[{index}]")
        for index, row in enumerate(deferred_raw)
    ]
    deferred_recommendations.sort(key=lambda row: row["recommendation_id"])

    open_risks_raw = synthesis.get("open_risks")
    if not isinstance(open_risks_raw, list):
        raise ValueError("final_strategy_synthesis.open_risks must be a list")
    open_risks = [
        _normalize_open_risk(row, field_name=f"final_strategy_synthesis.open_risks[{index}]")
        for index, row in enumerate(open_risks_raw)
    ]
    open_risks.sort(key=lambda row: row["open_risk_id"])

    packet_inputs_raw = synthesis.get("strategy_packet_inputs")
    if not isinstance(packet_inputs_raw, list):
        raise ValueError("final_strategy_synthesis.strategy_packet_inputs must be a list")
    strategy_packet_inputs = [
        _normalize_strategy_packet_input(
            row,
            field_name=f"final_strategy_synthesis.strategy_packet_inputs[{index}]",
        )
        for index, row in enumerate(packet_inputs_raw)
    ]
    strategy_packet_inputs.sort(
        key=lambda row: (row["packet_kind"], row["peer_project_id"], row["lane"], row["packet_input_id"])
    )

    return {
        "final_recommendations": final_recommendations,
        "deferred_recommendations": deferred_recommendations,
        "open_risks": open_risks,
        "strategy_packet_inputs": strategy_packet_inputs,
        "cross_project_context_usage": _normalize_cross_project_context_usage(
            synthesis.get("cross_project_context_usage"),
            field_name="final_strategy_synthesis.cross_project_context_usage",
        ),
    }


def _quote_join(values: list[str]) -> str:
    if not values:
        return "(none)"
    return ", ".join(f"`{value}`" for value in values)


def _render_strategy_markdown(
    *,
    checked_at_utc: str,
    target_project: Mapping[str, str],
    synthesis: Mapping[str, Any],
    multi_call_trace: list[Mapping[str, Any]],
    alignment: Mapping[str, list[str]],
) -> str:
    final_recommendations = list(synthesis["final_recommendations"])
    deferred_recommendations = list(synthesis["deferred_recommendations"])
    open_risks = list(synthesis["open_risks"])
    strategy_packet_inputs = list(synthesis["strategy_packet_inputs"])

    lines: list[str] = []
    lines.append("# STRATEGY")
    lines.append("")
    lines.append(f"Generated at `{checked_at_utc}` for project `{target_project['project_id']}`.")
    lines.append("This narrative is generated from validated recommendation outputs and formatted for clean diffs.")
    lines.append("")
    lines.append("## Final Recommendations (`final_strategy_synthesis.final_recommendations`)")
    if not final_recommendations:
        lines.append("No final recommendations were emitted.")
    for row in final_recommendations:
        lines.append("")
        lines.append(f"### {row['recommendation_id']}")
        lines.append(f"- Summary: {row['summary']}")
        lines.append(f"- Rationale: {row['rationale']}")
        lines.append(f"- Packet kind: `{row['packet_kind']}`")
        lines.append(f"- Peer project: `{row['peer_project_id'] or 'none'}`")
        lines.append(f"- Lane: `{row['lane']}`")
        lines.append(f"- Priority: `{row['priority']}`")
        lines.append(f"- Sequence hint: `{row['sequence_hint']}`")
        lines.append(f"- Strategy packet input: `{row['strategy_packet_input_id']}`")
        lines.append(f"- Supporting call count: `{row['supporting_call_count']}`")
        lines.append(f"- Contributing calls: {_quote_join(list(row['contributing_call_ids']))}")
        lines.append(f"- Contributing requirements: {_quote_join(list(row['contributing_requirement_ids']))}")
        lines.append("- Evidence refs:")
        for ref in row["evidence_refs"]:
            lines.append(f"  - `{ref}`")
        lines.append("- Call trace lineage:")
        for lineage in row["call_trace_lineage"]:
            lines.append(
                "  - "
                f"`{lineage['trace_id']}` ({lineage['call_id']} / {lineage['requirement_id']}) "
                f"at `{lineage['trace_ref']}`"
            )

    lines.append("")
    lines.append("## Deferred Recommendations (`final_strategy_synthesis.deferred_recommendations`)")
    if not deferred_recommendations:
        lines.append("No deferred recommendations were emitted.")
    for row in deferred_recommendations:
        lines.append("")
        lines.append(f"### {row['recommendation_id']}")
        lines.append(f"- Summary: {row['summary']}")
        lines.append(f"- Deferred reason code: `{row['deferred_reason_code']}`")
        lines.append(f"- Packet kind candidates: {_quote_join(list(row['packet_kind_candidates']))}")
        lines.append(f"- Peer project candidates: {_quote_join(list(row['peer_project_candidates']))}")
        lines.append(f"- Contributing calls: {_quote_join(list(row['contributing_call_ids']))}")
        lines.append("- Evidence refs:")
        for ref in row["evidence_refs"]:
            lines.append(f"  - `{ref}`")
        lines.append("- Call trace lineage:")
        for lineage in row["call_trace_lineage"]:
            lines.append(
                "  - "
                f"`{lineage['trace_id']}` ({lineage['call_id']} / {lineage['requirement_id']}) "
                f"at `{lineage['trace_ref']}`"
            )

    lines.append("")
    lines.append("## Open Risks (`final_strategy_synthesis.open_risks`)")
    if not open_risks:
        lines.append("No open risks were emitted.")
    for row in open_risks:
        lines.append("")
        lines.append(f"### {row['open_risk_id']}")
        lines.append(f"- Recommendation id: `{row['recommendation_id']}`")
        lines.append(f"- Summary: {row['summary']}")
        lines.append(f"- Reason code: `{row['reason_code']}`")
        lines.append(f"- Project id: `{row['project_id']}`")
        lines.append(f"- Linked recommendation ids: {_quote_join(list(row['linked_recommendation_ids']))}")
        lines.append(f"- Contributing calls: {_quote_join(list(row['contributing_call_ids']))}")
        lines.append("- Required evidence refs:")
        for ref in row["required_evidence_refs"]:
            lines.append(f"  - `{ref}`")
        lines.append("- Evidence refs:")
        for ref in row["evidence_refs"]:
            lines.append(f"  - `{ref}`")
        lines.append("- Call trace lineage:")
        if row["call_trace_lineage"]:
            for lineage in row["call_trace_lineage"]:
                lines.append(
                    "  - "
                    f"`{lineage['trace_id']}` ({lineage['call_id']} / {lineage['requirement_id']}) "
                    f"at `{lineage['trace_ref']}`"
                )
        else:
            lines.append("  - `(none)`")

    lines.append("")
    lines.append("## Strategy Packet Inputs (`final_strategy_synthesis.strategy_packet_inputs`)")
    if not strategy_packet_inputs:
        lines.append("No strategy packet inputs were emitted.")
    for row in strategy_packet_inputs:
        lines.append("")
        lines.append(f"### {row['packet_input_id']}")
        lines.append(f"- Packet kind: `{row['packet_kind']}`")
        lines.append(f"- Target project id: `{row['target_project_id']}`")
        lines.append(f"- Peer project id: `{row['peer_project_id'] or 'none'}`")
        lines.append(f"- Lane: `{row['lane']}`")
        lines.append(f"- Recommendation ids: {_quote_join(list(row['recommendation_ids']))}")
        lines.append(f"- Recommendation count: `{row['recommendation_count']}`")
        lines.append(f"- Earliest sequence hint: `{row['earliest_sequence_hint']}`")
        lines.append("- Evidence refs:")
        for ref in row["evidence_refs"]:
            lines.append(f"  - `{ref}`")

    lines.append("")
    lines.append("## Multi-Call Trace (`multi_call_orchestration_trace`)")
    if not multi_call_trace:
        lines.append("No trace rows were emitted.")
    for row in multi_call_trace:
        lines.append("")
        lines.append(f"### {row['trace_id']}")
        lines.append(f"- Call id: `{row['call_id']}`")
        lines.append(f"- Requirement id: `{row['requirement_id']}`")
        lines.append(f"- Trace ref: `{row['trace_ref']}`")
        lines.append(f"- Artifact ref: `{row['artifact_ref']}`")
        lines.append(f"- Checked at UTC: `{row['checked_at_utc']}`")
        lines.append(f"- Call objective: {row['call_objective']}")
        lines.append("- Input refs:")
        for ref in row["input_refs"]:
            lines.append(f"  - `{ref}`")
        lines.append("- Output refs:")
        for ref in row["output_refs"]:
            lines.append(f"  - `{ref}`")
        lines.append(f"- Handoff summary: {row['handoff_summary']}")

    lines.append("")
    lines.append("## Machine Alignment")
    lines.append(
        "- `final_strategy_synthesis.final_recommendations`: "
        f"{_quote_join(list(alignment['final_recommendation_ids']))}"
    )
    lines.append(
        "- `final_strategy_synthesis.deferred_recommendations`: "
        f"{_quote_join(list(alignment['deferred_recommendation_ids']))}"
    )
    lines.append("- `final_strategy_synthesis.open_risks`: " f"{_quote_join(list(alignment['open_risk_ids']))}")
    lines.append(
        "- `final_strategy_synthesis.strategy_packet_inputs`: "
        f"{_quote_join(list(alignment['strategy_packet_input_ids']))}"
    )
    lines.append("- `multi_call_orchestration_trace`: " f"{_quote_join(list(alignment['trace_ids']))}")
    lines.append("")
    lines.append("## Totals")
    lines.append(f"- Final recommendations: `{len(final_recommendations)}`")
    lines.append(f"- Deferred recommendations: `{len(deferred_recommendations)}`")
    lines.append(f"- Open risks: `{len(open_risks)}`")
    lines.append(f"- Strategy packet inputs: `{len(strategy_packet_inputs)}`")
    lines.append(f"- Multi-call trace rows: `{len(multi_call_trace)}`")

    return "\n".join(lines).rstrip() + "\n"


def build_req_048_strategy_md_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build the REQ-048 STRATEGY.md generator payload."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_048_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_048_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    synthesis = _normalize_final_strategy_synthesis(raw.get("final_strategy_synthesis"))
    multi_call_trace = _normalize_multi_call_trace(raw.get("multi_call_orchestration_trace"))

    alignment = {
        "final_recommendation_ids": sorted({row["recommendation_id"] for row in synthesis["final_recommendations"]}),
        "deferred_recommendation_ids": sorted({row["recommendation_id"] for row in synthesis["deferred_recommendations"]}),
        "open_risk_ids": sorted({row["open_risk_id"] for row in synthesis["open_risks"]}),
        "strategy_packet_input_ids": sorted({row["packet_input_id"] for row in synthesis["strategy_packet_inputs"]}),
        "trace_ids": sorted({row["trace_id"] for row in multi_call_trace}),
    }

    sections = [
        {
            "section_id": "final-recommendations",
            "title": "Final Recommendations",
            "machine_field": "final_strategy_synthesis.final_recommendations",
            "entry_count": len(alignment["final_recommendation_ids"]),
            "anchor_ids": list(alignment["final_recommendation_ids"]),
        },
        {
            "section_id": "deferred-recommendations",
            "title": "Deferred Recommendations",
            "machine_field": "final_strategy_synthesis.deferred_recommendations",
            "entry_count": len(alignment["deferred_recommendation_ids"]),
            "anchor_ids": list(alignment["deferred_recommendation_ids"]),
        },
        {
            "section_id": "open-risks",
            "title": "Open Risks",
            "machine_field": "final_strategy_synthesis.open_risks",
            "entry_count": len(alignment["open_risk_ids"]),
            "anchor_ids": list(alignment["open_risk_ids"]),
        },
        {
            "section_id": "strategy-packet-inputs",
            "title": "Strategy Packet Inputs",
            "machine_field": "final_strategy_synthesis.strategy_packet_inputs",
            "entry_count": len(alignment["strategy_packet_input_ids"]),
            "anchor_ids": list(alignment["strategy_packet_input_ids"]),
        },
        {
            "section_id": "multi-call-trace",
            "title": "Multi-Call Trace",
            "machine_field": "multi_call_orchestration_trace",
            "entry_count": len(alignment["trace_ids"]),
            "anchor_ids": list(alignment["trace_ids"]),
        },
    ]

    markdown = _render_strategy_markdown(
        checked_at_utc=checked_at_utc,
        target_project=target_project,
        synthesis=synthesis,
        multi_call_trace=multi_call_trace,
        alignment=alignment,
    )
    line_count = len(markdown.splitlines())
    content_sha256 = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

    output_payload = {
        "ok": True,
        "schema_version": REQ_048_SCHEMA_VERSION,
        "requirement_id": REQ_048_REQUIREMENT_ID,
        "analysis_type": REQ_048_ANALYSIS_TYPE,
        "call_id": REQ_048_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "strategy_md": {
            "artifact_path": "STRATEGY.md",
            "markdown": markdown,
            "content_sha256": content_sha256,
            "line_count": line_count,
            "sections": sections,
            "alignment": alignment,
        },
        "totals": {
            "final_recommendations": len(alignment["final_recommendation_ids"]),
            "deferred_recommendations": len(alignment["deferred_recommendation_ids"]),
            "open_risks": len(alignment["open_risk_ids"]),
            "strategy_packet_inputs": len(alignment["strategy_packet_input_ids"]),
            "multi_call_trace_rows": len(alignment["trace_ids"]),
            "markdown_sections": len(sections),
            "markdown_lines": line_count,
        },
    }

    errors = validate_req_048_strategy_md_generator(output_payload)
    if errors:
        raise ValueError(f"built REQ-048 payload failed validation: {errors}")
    return output_payload


def validate_req_048_strategy_md_generator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-048 STRATEGY.md generator payload shape."""
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
        "strategy_md",
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
    if payload.get("schema_version") != REQ_048_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_048_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_048_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_048_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_048_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_048_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_048_CALL_ID:
        errors.append(f"call_id must be {REQ_048_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
    else:
        expected_target = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        project_id = target_project.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            errors.append("target_project.project_id must be a non-empty string")
        project_root = target_project.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not project_root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    strategy_md = payload.get("strategy_md")
    if not isinstance(strategy_md, Mapping):
        errors.append("strategy_md must be an object")
        return errors

    expected_strategy_md = {"artifact_path", "markdown", "content_sha256", "line_count", "sections", "alignment"}
    strategy_md_keys = set(strategy_md.keys())
    missing_strategy_md = sorted(expected_strategy_md - strategy_md_keys)
    if missing_strategy_md:
        errors.append(f"strategy_md missing keys: {missing_strategy_md}")
    unexpected_strategy_md = sorted(strategy_md_keys - expected_strategy_md)
    if unexpected_strategy_md:
        errors.append(f"strategy_md has unexpected keys: {unexpected_strategy_md}")

    if strategy_md.get("artifact_path") != "STRATEGY.md":
        errors.append("strategy_md.artifact_path must be STRATEGY.md")
    markdown = strategy_md.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        errors.append("strategy_md.markdown must be a non-empty string")
        markdown = ""
    line_count = strategy_md.get("line_count")
    if not isinstance(line_count, int) or line_count < 1:
        errors.append("strategy_md.line_count must be a positive integer")
        line_count = 0
    if isinstance(markdown, str) and markdown:
        expected_sha = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        if strategy_md.get("content_sha256") != expected_sha:
            errors.append("strategy_md.content_sha256 must match strategy_md.markdown")
        if line_count != len(markdown.splitlines()):
            errors.append("strategy_md.line_count must match strategy_md.markdown line count")

    sections = strategy_md.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("strategy_md.sections must be a non-empty list")
        sections = []
    else:
        seen_section_ids: set[str] = set()
        for index, row in enumerate(sections):
            if not isinstance(row, Mapping):
                errors.append(f"strategy_md.sections[{index}] must be an object")
                continue
            expected_section_keys = {"section_id", "title", "machine_field", "entry_count", "anchor_ids"}
            row_keys = set(row.keys())
            missing_section_keys = sorted(expected_section_keys - row_keys)
            if missing_section_keys:
                errors.append(f"strategy_md.sections[{index}] missing keys: {missing_section_keys}")
            unexpected_section_keys = sorted(row_keys - expected_section_keys)
            if unexpected_section_keys:
                errors.append(f"strategy_md.sections[{index}] has unexpected keys: {unexpected_section_keys}")
            section_id = row.get("section_id")
            if not isinstance(section_id, str) or not section_id.strip():
                errors.append(f"strategy_md.sections[{index}].section_id must be a non-empty string")
            elif section_id in seen_section_ids:
                errors.append(f"strategy_md.sections[{index}].section_id must be unique")
            else:
                seen_section_ids.add(section_id)
            title = row.get("title")
            if not isinstance(title, str) or not title.strip():
                errors.append(f"strategy_md.sections[{index}].title must be a non-empty string")
            machine_field = row.get("machine_field")
            if not isinstance(machine_field, str) or not machine_field.strip():
                errors.append(f"strategy_md.sections[{index}].machine_field must be a non-empty string")
            entry_count = row.get("entry_count")
            if not isinstance(entry_count, int) or entry_count < 0:
                errors.append(f"strategy_md.sections[{index}].entry_count must be a non-negative integer")
            anchor_ids = row.get("anchor_ids")
            if not isinstance(anchor_ids, list):
                errors.append(f"strategy_md.sections[{index}].anchor_ids must be a list")
                continue
            normalized_anchor_ids: list[str] = []
            for anchor_index, anchor_id in enumerate(anchor_ids):
                if not isinstance(anchor_id, str) or not anchor_id.strip():
                    errors.append(
                        f"strategy_md.sections[{index}].anchor_ids[{anchor_index}] must be a non-empty string"
                    )
                    continue
                normalized_anchor_ids.append(anchor_id)
                if markdown and anchor_id not in markdown:
                    errors.append(f"strategy_md.sections[{index}].anchor_ids[{anchor_index}] must appear in markdown")
            if isinstance(entry_count, int) and entry_count >= 0 and entry_count != len(normalized_anchor_ids):
                errors.append(
                    f"strategy_md.sections[{index}].entry_count must equal number of non-empty anchor_ids"
                )

    alignment = strategy_md.get("alignment")
    alignment_keys = (
        "final_recommendation_ids",
        "deferred_recommendation_ids",
        "open_risk_ids",
        "strategy_packet_input_ids",
        "trace_ids",
    )
    if not isinstance(alignment, Mapping):
        errors.append("strategy_md.alignment must be an object")
        alignment = {}
    else:
        expected_alignment = set(alignment_keys)
        alignment_present = set(alignment.keys())
        missing_alignment = sorted(expected_alignment - alignment_present)
        if missing_alignment:
            errors.append(f"strategy_md.alignment missing keys: {missing_alignment}")
        unexpected_alignment = sorted(alignment_present - expected_alignment)
        if unexpected_alignment:
            errors.append(f"strategy_md.alignment has unexpected keys: {unexpected_alignment}")
        for key in alignment_keys:
            values = alignment.get(key)
            if not isinstance(values, list):
                errors.append(f"strategy_md.alignment.{key} must be a list")
                continue
            for index, item in enumerate(values):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"strategy_md.alignment.{key}[{index}] must be a non-empty string")
            if values != sorted(set(values)):
                errors.append(f"strategy_md.alignment.{key} must be sorted and unique")
            if markdown:
                for index, item in enumerate(values):
                    if isinstance(item, str) and item.strip() and item not in markdown:
                        errors.append(f"strategy_md.alignment.{key}[{index}] must appear in markdown")

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "final_recommendations",
            "deferred_recommendations",
            "open_risks",
            "strategy_packet_inputs",
            "multi_call_trace_rows",
            "markdown_sections",
            "markdown_lines",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        for key in expected_totals:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")
        if isinstance(alignment, Mapping):
            expected_from_alignment = {
                "final_recommendations": len(alignment.get("final_recommendation_ids", [])),
                "deferred_recommendations": len(alignment.get("deferred_recommendation_ids", [])),
                "open_risks": len(alignment.get("open_risk_ids", [])),
                "strategy_packet_inputs": len(alignment.get("strategy_packet_input_ids", [])),
                "multi_call_trace_rows": len(alignment.get("trace_ids", [])),
            }
            for key, expected_count in expected_from_alignment.items():
                if totals.get(key) != expected_count:
                    errors.append(f"totals.{key} must match strategy_md.alignment.{key}")
        if isinstance(sections, list) and totals.get("markdown_sections") != len(sections):
            errors.append("totals.markdown_sections must match strategy_md.sections count")
        if isinstance(line_count, int) and totals.get("markdown_lines") != line_count:
            errors.append("totals.markdown_lines must match strategy_md.line_count")

    if isinstance(markdown, str) and markdown:
        required_headers = (
            "## Final Recommendations",
            "## Deferred Recommendations",
            "## Open Risks",
            "## Strategy Packet Inputs",
            "## Multi-Call Trace",
            "## Machine Alignment",
        )
        for header in required_headers:
            if header not in markdown:
                errors.append(f"strategy_md.markdown must include section header: {header}")

    return errors


def _slug_token(value: str) -> str:
    chars: list[str] = []
    previous_dash = False
    for raw_char in value.strip().lower():
        if raw_char.isalnum():
            chars.append(raw_char)
            previous_dash = False
            continue
        if previous_dash:
            continue
        chars.append("-")
        previous_dash = True
    return "".join(chars).strip("-") or "unspecified"


def _normalize_link_output_row(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {
        "link_id",
        "status",
        "source_project_id",
        "peer_project_id",
        "lane",
        "confidence",
        "recommendation_ids",
        "packet_input_ids",
        "open_risk_ids",
        "evidence_refs",
        "required_evidence_refs",
        "obligation_metadata",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    status = _require_nonempty_text(row.get("status"), field_name=f"{field_name}.status").lower()
    if status not in {"current", "missing", "proposed"}:
        raise ValueError(f"{field_name}.status must be one of: ['current', 'missing', 'proposed']")

    confidence = _require_nonempty_text(row.get("confidence"), field_name=f"{field_name}.confidence").lower()
    if confidence not in _CONFIDENCE_LEVELS:
        raise ValueError(f"{field_name}.confidence must be one of: {list(_CONFIDENCE_LEVELS)}")

    obligation = _require_mapping(row.get("obligation_metadata"), field_name=f"{field_name}.obligation_metadata")
    expected_obligation = {
        "status",
        "source_field",
        "reason_codes",
        "evidence_refs",
        "required_evidence_refs",
    }
    unexpected_obligation = sorted(set(obligation.keys()) - expected_obligation)
    if unexpected_obligation:
        raise ValueError(f"{field_name}.obligation_metadata has unexpected keys: {unexpected_obligation}")
    obligation_status = _require_nonempty_text(
        obligation.get("status"),
        field_name=f"{field_name}.obligation_metadata.status",
    ).lower()
    if obligation_status not in _OBLIGATION_STATUSES:
        raise ValueError(
            f"{field_name}.obligation_metadata.status must be one of: {list(_OBLIGATION_STATUSES)}"
        )

    return {
        "link_id": _require_nonempty_text(row.get("link_id"), field_name=f"{field_name}.link_id"),
        "status": status,
        "source_project_id": _require_nonempty_text(
            row.get("source_project_id"),
            field_name=f"{field_name}.source_project_id",
        ),
        "peer_project_id": _require_nonempty_text(
            row.get("peer_project_id"),
            field_name=f"{field_name}.peer_project_id",
        ),
        "lane": _require_nonempty_text(row.get("lane"), field_name=f"{field_name}.lane"),
        "confidence": confidence,
        "recommendation_ids": _normalize_optional_str_list(
            row.get("recommendation_ids"),
            field_name=f"{field_name}.recommendation_ids",
        ),
        "packet_input_ids": _normalize_optional_str_list(
            row.get("packet_input_ids"),
            field_name=f"{field_name}.packet_input_ids",
        ),
        "open_risk_ids": _normalize_optional_str_list(
            row.get("open_risk_ids"),
            field_name=f"{field_name}.open_risk_ids",
        ),
        "evidence_refs": _normalize_optional_str_list(
            row.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
        ),
        "required_evidence_refs": _normalize_optional_str_list(
            row.get("required_evidence_refs"),
            field_name=f"{field_name}.required_evidence_refs",
        ),
        "obligation_metadata": {
            "status": obligation_status,
            "source_field": _require_nonempty_text(
                obligation.get("source_field"),
                field_name=f"{field_name}.obligation_metadata.source_field",
            ),
            "reason_codes": _normalize_optional_str_list(
                obligation.get("reason_codes"),
                field_name=f"{field_name}.obligation_metadata.reason_codes",
            ),
            "evidence_refs": _normalize_optional_str_list(
                obligation.get("evidence_refs"),
                field_name=f"{field_name}.obligation_metadata.evidence_refs",
            ),
            "required_evidence_refs": _normalize_optional_str_list(
                obligation.get("required_evidence_refs"),
                field_name=f"{field_name}.obligation_metadata.required_evidence_refs",
            ),
        },
    }


def _sort_link_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["peer_project_id"], row["lane"], row["link_id"]))


def _build_req_050_current_links(
    *,
    target_project_id: str,
    synthesis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet in synthesis["strategy_packet_inputs"]:
        if packet["packet_kind"] != "cross-project":
            continue
        lane = packet["lane"]
        peer_project_id = packet["peer_project_id"]
        rows.append(
            {
                "link_id": (
                    f"link.current.{_slug_token(target_project_id)}."
                    f"{_slug_token(peer_project_id)}.{_slug_token(lane)}"
                ),
                "status": "current",
                "source_project_id": target_project_id,
                "peer_project_id": peer_project_id,
                "lane": lane,
                "confidence": "high",
                "recommendation_ids": list(packet["recommendation_ids"]),
                "packet_input_ids": [packet["packet_input_id"]],
                "open_risk_ids": [],
                "evidence_refs": list(packet["evidence_refs"]),
                "required_evidence_refs": list(packet["evidence_refs"]),
                "obligation_metadata": {
                    "status": "active",
                    "source_field": "final_strategy_synthesis.strategy_packet_inputs",
                    "reason_codes": [],
                    "evidence_refs": list(packet["evidence_refs"]),
                    "required_evidence_refs": list(packet["evidence_refs"]),
                },
            }
        )
    return _sort_link_rows(rows)


def _build_req_050_missing_links(
    *,
    target_project_id: str,
    synthesis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for risk in synthesis["open_risks"]:
        peer_project_id = risk["project_id"]
        if peer_project_id == target_project_id:
            continue
        lane = "unassigned"
        key = (peer_project_id, lane)
        row = grouped.setdefault(
            key,
            {
                "link_id": (
                    f"link.missing.{_slug_token(target_project_id)}."
                    f"{_slug_token(peer_project_id)}.{_slug_token(lane)}"
                ),
                "status": "missing",
                "source_project_id": target_project_id,
                "peer_project_id": peer_project_id,
                "lane": lane,
                "confidence": "low",
                "recommendation_ids": set(),
                "packet_input_ids": set(),
                "open_risk_ids": set(),
                "evidence_refs": set(),
                "required_evidence_refs": set(),
                "obligation_metadata": {
                    "status": "blocked",
                    "source_field": "final_strategy_synthesis.open_risks",
                    "reason_codes": set(),
                    "evidence_refs": set(),
                    "required_evidence_refs": set(),
                },
            },
        )
        recommendation_ids = list(risk["linked_recommendation_ids"]) or [risk["recommendation_id"]]
        row["recommendation_ids"].update(recommendation_ids)
        row["open_risk_ids"].add(risk["open_risk_id"])
        row["evidence_refs"].update(risk["evidence_refs"])
        row["required_evidence_refs"].update(risk["required_evidence_refs"])
        row["obligation_metadata"]["reason_codes"].add(risk["reason_code"])
        row["obligation_metadata"]["evidence_refs"].update(risk["evidence_refs"])
        row["obligation_metadata"]["required_evidence_refs"].update(risk["required_evidence_refs"])
    rows: list[dict[str, Any]] = []
    for row in grouped.values():
        rows.append(
            _normalize_link_output_row(
                {
                    **row,
                    "recommendation_ids": sorted(row["recommendation_ids"]),
                    "packet_input_ids": sorted(row["packet_input_ids"]),
                    "open_risk_ids": sorted(row["open_risk_ids"]),
                    "evidence_refs": sorted(row["evidence_refs"]),
                    "required_evidence_refs": sorted(row["required_evidence_refs"]),
                    "obligation_metadata": {
                        "status": row["obligation_metadata"]["status"],
                        "source_field": row["obligation_metadata"]["source_field"],
                        "reason_codes": sorted(row["obligation_metadata"]["reason_codes"]),
                        "evidence_refs": sorted(row["obligation_metadata"]["evidence_refs"]),
                        "required_evidence_refs": sorted(row["obligation_metadata"]["required_evidence_refs"]),
                    },
                },
                field_name="missing_link",
            )
        )
    return _sort_link_rows(rows)


def _build_req_050_proposed_links(
    *,
    target_project_id: str,
    synthesis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for deferred in synthesis["deferred_recommendations"]:
        if "cross-project" not in deferred["packet_kind_candidates"]:
            continue
        if not deferred["peer_project_candidates"]:
            raise ValueError(
                "final_strategy_synthesis.deferred_recommendations cross-project rows must include peer_project_candidates"
            )
        for peer_project_id in deferred["peer_project_candidates"]:
            lane = "unassigned"
            key = (peer_project_id, lane)
            row = grouped.setdefault(
                key,
                {
                    "link_id": (
                        f"link.proposed.{_slug_token(target_project_id)}."
                        f"{_slug_token(peer_project_id)}.{_slug_token(lane)}"
                    ),
                    "status": "proposed",
                    "source_project_id": target_project_id,
                    "peer_project_id": peer_project_id,
                    "lane": lane,
                    "confidence": "medium",
                    "recommendation_ids": set(),
                    "packet_input_ids": set(),
                    "open_risk_ids": set(),
                    "evidence_refs": set(),
                    "required_evidence_refs": set(),
                    "obligation_metadata": {
                        "status": "proposed",
                        "source_field": "final_strategy_synthesis.deferred_recommendations",
                        "reason_codes": set(),
                        "evidence_refs": set(),
                        "required_evidence_refs": set(),
                    },
                },
            )
            row["recommendation_ids"].add(deferred["recommendation_id"])
            row["evidence_refs"].update(deferred["evidence_refs"])
            row["obligation_metadata"]["reason_codes"].add(deferred["deferred_reason_code"])
            row["obligation_metadata"]["evidence_refs"].update(deferred["evidence_refs"])
    rows: list[dict[str, Any]] = []
    for row in grouped.values():
        rows.append(
            _normalize_link_output_row(
                {
                    **row,
                    "recommendation_ids": sorted(row["recommendation_ids"]),
                    "packet_input_ids": sorted(row["packet_input_ids"]),
                    "open_risk_ids": sorted(row["open_risk_ids"]),
                    "evidence_refs": sorted(row["evidence_refs"]),
                    "required_evidence_refs": sorted(row["required_evidence_refs"]),
                    "obligation_metadata": {
                        "status": row["obligation_metadata"]["status"],
                        "source_field": row["obligation_metadata"]["source_field"],
                        "reason_codes": sorted(row["obligation_metadata"]["reason_codes"]),
                        "evidence_refs": sorted(row["obligation_metadata"]["evidence_refs"]),
                        "required_evidence_refs": sorted(row["obligation_metadata"]["required_evidence_refs"]),
                    },
                },
                field_name="proposed_link",
            )
        )
    return _sort_link_rows(rows)


def build_req_050_ecosystem_link_map_json_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build the REQ-050 ECOSYSTEM_LINK_MAP.json generator payload."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_050_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_050_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    synthesis = _normalize_final_strategy_synthesis(raw.get("final_strategy_synthesis"))
    planning_context = dict(synthesis["cross_project_context_usage"])
    target_project_id = target_project["project_id"]

    current_links = _build_req_050_current_links(target_project_id=target_project_id, synthesis=synthesis)
    missing_links = _build_req_050_missing_links(target_project_id=target_project_id, synthesis=synthesis)
    proposed_links = _build_req_050_proposed_links(target_project_id=target_project_id, synthesis=synthesis)

    linked_project_ids = sorted(
        {
            *[row["peer_project_id"] for row in current_links],
            *[row["peer_project_id"] for row in missing_links],
            *[row["peer_project_id"] for row in proposed_links],
        }
    )

    output_payload = {
        "ok": True,
        "schema_version": REQ_050_SCHEMA_VERSION,
        "requirement_id": REQ_050_REQUIREMENT_ID,
        "analysis_type": REQ_050_ANALYSIS_TYPE,
        "call_id": REQ_050_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "ecosystem_link_map": {
            "artifact_path": "ECOSYSTEM_LINK_MAP.json",
            "planning_context": planning_context,
            "current_links": current_links,
            "missing_links": missing_links,
            "proposed_links": proposed_links,
            "summary": {
                "linked_project_ids": linked_project_ids,
                "current_link_count": len(current_links),
                "missing_link_count": len(missing_links),
                "proposed_link_count": len(proposed_links),
                "total_link_count": len(current_links) + len(missing_links) + len(proposed_links),
                "active_obligation_count": len(current_links),
                "blocked_obligation_count": len(missing_links),
                "proposed_obligation_count": len(proposed_links),
            },
        },
        "totals": {
            "current_links": len(current_links),
            "missing_links": len(missing_links),
            "proposed_links": len(proposed_links),
            "linked_projects": len(linked_project_ids),
            "obligation_rows": len(current_links) + len(missing_links) + len(proposed_links),
            "context_project_count": len(planning_context["projects_considered"]),
        },
    }

    errors = validate_req_050_ecosystem_link_map_json_generator(output_payload)
    if errors:
        raise ValueError(f"built REQ-050 payload failed validation: {errors}")
    return output_payload


def validate_req_050_ecosystem_link_map_json_generator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-050 ECOSYSTEM_LINK_MAP.json generator payload shape."""
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
        "ecosystem_link_map",
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
    if payload.get("schema_version") != REQ_050_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_050_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_050_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_050_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_050_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_050_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_050_CALL_ID:
        errors.append(f"call_id must be {REQ_050_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
        target_project_id = ""
    else:
        expected_target = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        target_project_id = str(target_project.get("project_id") or "").strip()
        if not target_project_id:
            errors.append("target_project.project_id must be a non-empty string")
        project_root = target_project.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not project_root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    link_map = payload.get("ecosystem_link_map")
    if not isinstance(link_map, Mapping):
        errors.append("ecosystem_link_map must be an object")
        return errors

    expected_link_map = {
        "artifact_path",
        "planning_context",
        "current_links",
        "missing_links",
        "proposed_links",
        "summary",
    }
    link_map_keys = set(link_map.keys())
    missing_link_map = sorted(expected_link_map - link_map_keys)
    if missing_link_map:
        errors.append(f"ecosystem_link_map missing keys: {missing_link_map}")
    unexpected_link_map = sorted(link_map_keys - expected_link_map)
    if unexpected_link_map:
        errors.append(f"ecosystem_link_map has unexpected keys: {unexpected_link_map}")

    if link_map.get("artifact_path") != "ECOSYSTEM_LINK_MAP.json":
        errors.append("ecosystem_link_map.artifact_path must be ECOSYSTEM_LINK_MAP.json")

    planning_context = link_map.get("planning_context")
    if not isinstance(planning_context, Mapping):
        errors.append("ecosystem_link_map.planning_context must be an object")
        planning_context = {}
    else:
        expected_context = {
            "cross_project_context_provided",
            "cross_project_context_used",
            "projects_considered",
            "earth_sweep_evidence_refs_considered",
            "cross_project_obligation_count",
            "unresolved_idea_count",
            "recommendation_ids_with_context",
        }
        context_keys = set(planning_context.keys())
        missing_context = sorted(expected_context - context_keys)
        if missing_context:
            errors.append(f"ecosystem_link_map.planning_context missing keys: {missing_context}")
        unexpected_context = sorted(context_keys - expected_context)
        if unexpected_context:
            errors.append(f"ecosystem_link_map.planning_context has unexpected keys: {unexpected_context}")
        if not isinstance(planning_context.get("cross_project_context_provided"), bool):
            errors.append("ecosystem_link_map.planning_context.cross_project_context_provided must be a boolean")
        if not isinstance(planning_context.get("cross_project_context_used"), bool):
            errors.append("ecosystem_link_map.planning_context.cross_project_context_used must be a boolean")
        for key in ("projects_considered", "earth_sweep_evidence_refs_considered", "recommendation_ids_with_context"):
            values = planning_context.get(key)
            if not isinstance(values, list):
                errors.append(f"ecosystem_link_map.planning_context.{key} must be a list")
                continue
            if values != sorted(set(values)):
                errors.append(f"ecosystem_link_map.planning_context.{key} must be sorted and unique")
        for key in ("cross_project_obligation_count", "unresolved_idea_count"):
            value = planning_context.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"ecosystem_link_map.planning_context.{key} must be a non-negative integer")

    all_rows: dict[str, list[dict[str, Any]]] = {}
    for key, expected_status in (
        ("current_links", "current"),
        ("missing_links", "missing"),
        ("proposed_links", "proposed"),
    ):
        raw_rows = link_map.get(key)
        if not isinstance(raw_rows, list):
            errors.append(f"ecosystem_link_map.{key} must be a list")
            all_rows[key] = []
            continue
        normalized_rows: list[dict[str, Any]] = []
        seen_link_ids: set[str] = set()
        for index, row in enumerate(raw_rows):
            try:
                normalized = _normalize_link_output_row(row, field_name=f"ecosystem_link_map.{key}[{index}]")
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if normalized["status"] != expected_status:
                errors.append(f"ecosystem_link_map.{key}[{index}].status must be {expected_status}")
            if target_project_id and normalized["source_project_id"] != target_project_id:
                errors.append(
                    f"ecosystem_link_map.{key}[{index}].source_project_id must match target_project.project_id"
                )
            if normalized["link_id"] in seen_link_ids:
                errors.append(f"ecosystem_link_map.{key}[{index}].link_id must be unique within {key}")
            else:
                seen_link_ids.add(normalized["link_id"])
            if key == "current_links" and normalized["confidence"] != "high":
                errors.append(f"ecosystem_link_map.{key}[{index}].confidence must be high")
            if key == "missing_links" and normalized["confidence"] != "low":
                errors.append(f"ecosystem_link_map.{key}[{index}].confidence must be low")
            if key == "proposed_links" and normalized["confidence"] not in {"medium", "low"}:
                errors.append(f"ecosystem_link_map.{key}[{index}].confidence must be medium or low")
            if key == "current_links" and not normalized["packet_input_ids"]:
                errors.append(f"ecosystem_link_map.{key}[{index}].packet_input_ids must be non-empty")
            if key == "missing_links" and not normalized["open_risk_ids"]:
                errors.append(f"ecosystem_link_map.{key}[{index}].open_risk_ids must be non-empty")
            if key == "missing_links" and not normalized["required_evidence_refs"]:
                errors.append(f"ecosystem_link_map.{key}[{index}].required_evidence_refs must be non-empty")
            if normalized["obligation_metadata"]["evidence_refs"] != normalized["evidence_refs"]:
                errors.append(
                    f"ecosystem_link_map.{key}[{index}].obligation_metadata.evidence_refs must match evidence_refs"
                )
            if normalized["obligation_metadata"]["required_evidence_refs"] != normalized["required_evidence_refs"]:
                errors.append(
                    "ecosystem_link_map."
                    f"{key}[{index}].obligation_metadata.required_evidence_refs must match required_evidence_refs"
                )
            normalized_rows.append(normalized)
        if raw_rows != _sort_link_rows(normalized_rows):
            errors.append(f"ecosystem_link_map.{key} must be sorted deterministically")
        all_rows[key] = normalized_rows

    summary = link_map.get("summary")
    if not isinstance(summary, Mapping):
        errors.append("ecosystem_link_map.summary must be an object")
    else:
        expected_summary = {
            "linked_project_ids",
            "current_link_count",
            "missing_link_count",
            "proposed_link_count",
            "total_link_count",
            "active_obligation_count",
            "blocked_obligation_count",
            "proposed_obligation_count",
        }
        summary_keys = set(summary.keys())
        missing_summary = sorted(expected_summary - summary_keys)
        if missing_summary:
            errors.append(f"ecosystem_link_map.summary missing keys: {missing_summary}")
        unexpected_summary = sorted(summary_keys - expected_summary)
        if unexpected_summary:
            errors.append(f"ecosystem_link_map.summary has unexpected keys: {unexpected_summary}")
        linked_project_ids = summary.get("linked_project_ids")
        if not isinstance(linked_project_ids, list):
            errors.append("ecosystem_link_map.summary.linked_project_ids must be a list")
            linked_project_ids = []
        elif linked_project_ids != sorted(set(linked_project_ids)):
            errors.append("ecosystem_link_map.summary.linked_project_ids must be sorted and unique")
        expected_counts = {
            "current_link_count": len(all_rows.get("current_links", [])),
            "missing_link_count": len(all_rows.get("missing_links", [])),
            "proposed_link_count": len(all_rows.get("proposed_links", [])),
            "total_link_count": sum(len(all_rows.get(key, [])) for key in ("current_links", "missing_links", "proposed_links")),
            "active_obligation_count": len(all_rows.get("current_links", [])),
            "blocked_obligation_count": len(all_rows.get("missing_links", [])),
            "proposed_obligation_count": len(all_rows.get("proposed_links", [])),
        }
        for key, expected_value in expected_counts.items():
            value = summary.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"ecosystem_link_map.summary.{key} must be a non-negative integer")
            elif value != expected_value:
                errors.append(f"ecosystem_link_map.summary.{key} must match derived row counts")
        derived_linked_projects = sorted(
            {
                row["peer_project_id"]
                for key in ("current_links", "missing_links", "proposed_links")
                for row in all_rows.get(key, [])
            }
        )
        if linked_project_ids != derived_linked_projects:
            errors.append("ecosystem_link_map.summary.linked_project_ids must match peer_project_id coverage")

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "current_links",
            "missing_links",
            "proposed_links",
            "linked_projects",
            "obligation_rows",
            "context_project_count",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        expected_values = {
            "current_links": len(all_rows.get("current_links", [])),
            "missing_links": len(all_rows.get("missing_links", [])),
            "proposed_links": len(all_rows.get("proposed_links", [])),
            "linked_projects": len(
                {
                    row["peer_project_id"]
                    for key in ("current_links", "missing_links", "proposed_links")
                    for row in all_rows.get(key, [])
                }
            ),
            "obligation_rows": sum(len(all_rows.get(key, [])) for key in ("current_links", "missing_links", "proposed_links")),
            "context_project_count": len(planning_context.get("projects_considered", [])),
        }
        for key, expected_value in expected_values.items():
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")
            elif value != expected_value:
                errors.append(f"totals.{key} must match derived ecosystem_link_map counts")

    return errors


def _normalize_revision_pair(value: Any) -> dict[str, str]:
    revision_pair = _require_mapping(value, field_name="revision_pair")
    expected = {"previous_revision_id", "current_revision_id"}
    unexpected = sorted(set(revision_pair.keys()) - expected)
    if unexpected:
        raise ValueError(f"revision_pair has unexpected keys: {unexpected}")
    previous_revision_id = _require_nonempty_text(
        revision_pair.get("previous_revision_id"),
        field_name="revision_pair.previous_revision_id",
    )
    current_revision_id = _require_nonempty_text(
        revision_pair.get("current_revision_id"),
        field_name="revision_pair.current_revision_id",
    )
    if previous_revision_id == current_revision_id:
        raise ValueError("revision_pair.previous_revision_id and current_revision_id must differ")
    return {
        "previous_revision_id": previous_revision_id,
        "current_revision_id": current_revision_id,
    }


def _normalize_change_row(value: Any, *, field_name: str, section_key: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {
        "change_id",
        "section_key",
        "path",
        "change_type",
        "previous_value",
        "current_value",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    normalized_section_key = _require_nonempty_text(
        row.get("section_key"),
        field_name=f"{field_name}.section_key",
    )
    if normalized_section_key != section_key:
        raise ValueError(f"{field_name}.section_key must be {section_key}")
    change_type = _require_nonempty_text(row.get("change_type"), field_name=f"{field_name}.change_type").lower()
    if change_type not in _CHANGE_TYPES:
        raise ValueError(f"{field_name}.change_type must be one of: {list(_CHANGE_TYPES)}")
    change_id = _require_nonempty_text(row.get("change_id"), field_name=f"{field_name}.change_id")
    if not change_id.startswith(f"chg.{section_key}."):
        raise ValueError(f"{field_name}.change_id must start with chg.{section_key}.")
    return {
        "change_id": change_id,
        "section_key": normalized_section_key,
        "path": _require_nonempty_text(row.get("path"), field_name=f"{field_name}.path"),
        "change_type": change_type,
        "previous_value": row.get("previous_value"),
        "current_value": row.get("current_value"),
    }


def _normalize_change_detection(value: Any) -> dict[str, dict[str, Any]]:
    detection = _require_mapping(value, field_name="change_detection")
    expected = set(_CHANGE_SECTION_KEYS)
    missing = sorted(expected - set(detection.keys()))
    if missing:
        raise ValueError(f"change_detection missing keys: {missing}")
    unexpected = sorted(set(detection.keys()) - expected)
    if unexpected:
        raise ValueError(f"change_detection has unexpected keys: {unexpected}")

    normalized: dict[str, dict[str, Any]] = {}
    seen_change_ids: set[str] = set()
    for section_key in _CHANGE_SECTION_KEYS:
        section = _require_mapping(detection.get(section_key), field_name=f"change_detection.{section_key}")
        expected_section = {"changed", "change_count", "changes"}
        unexpected_section = sorted(set(section.keys()) - expected_section)
        if unexpected_section:
            raise ValueError(f"change_detection.{section_key} has unexpected keys: {unexpected_section}")
        changed = section.get("changed")
        if not isinstance(changed, bool):
            raise ValueError(f"change_detection.{section_key}.changed must be a boolean")
        change_count = _normalize_non_negative_int(
            section.get("change_count"),
            field_name=f"change_detection.{section_key}.change_count",
        )
        raw_changes = section.get("changes")
        if not isinstance(raw_changes, list):
            raise ValueError(f"change_detection.{section_key}.changes must be a list")
        changes: list[dict[str, Any]] = []
        for index, row in enumerate(raw_changes):
            normalized_change = _normalize_change_row(
                row,
                field_name=f"change_detection.{section_key}.changes[{index}]",
                section_key=section_key,
            )
            if normalized_change["change_id"] in seen_change_ids:
                raise ValueError(f"change_detection.{section_key}.changes[{index}].change_id must be unique")
            seen_change_ids.add(normalized_change["change_id"])
            changes.append(normalized_change)
        changes.sort(key=lambda row: row["change_id"])
        if change_count != len(changes):
            raise ValueError(f"change_detection.{section_key}.change_count must equal len(change_detection.{section_key}.changes)")
        if changed != bool(changes):
            raise ValueError(f"change_detection.{section_key}.changed must match whether changes are present")
        normalized[section_key] = {
            "changed": changed,
            "change_count": change_count,
            "changes": changes,
        }
    return normalized


def _normalize_change_summary(
    value: Any,
    *,
    change_detection: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    summary = _require_mapping(value, field_name="change_summary")
    expected = {"total_change_count", "changed_sections", "change_ids"}
    unexpected = sorted(set(summary.keys()) - expected)
    if unexpected:
        raise ValueError(f"change_summary has unexpected keys: {unexpected}")
    changed_sections = _normalize_optional_str_list(
        summary.get("changed_sections"),
        field_name="change_summary.changed_sections",
    )
    for section_key in changed_sections:
        if section_key not in _CHANGE_SECTION_KEYS:
            raise ValueError(
                f"change_summary.changed_sections contains unsupported section key: {section_key}"
            )
    change_ids = _normalize_optional_str_list(summary.get("change_ids"), field_name="change_summary.change_ids")
    total_change_count = _normalize_non_negative_int(
        summary.get("total_change_count"),
        field_name="change_summary.total_change_count",
    )
    derived_changed_sections = sorted(
        section_key for section_key in _CHANGE_SECTION_KEYS if change_detection[section_key]["changed"]
    )
    derived_change_ids = sorted(
        change["change_id"]
        for section_key in _CHANGE_SECTION_KEYS
        for change in change_detection[section_key]["changes"]
    )
    if changed_sections != derived_changed_sections:
        raise ValueError("change_summary.changed_sections must match change_detection")
    if change_ids != derived_change_ids:
        raise ValueError("change_summary.change_ids must match change_detection")
    if total_change_count != len(derived_change_ids):
        raise ValueError("change_summary.total_change_count must match change_detection")
    return {
        "total_change_count": total_change_count,
        "changed_sections": changed_sections,
        "change_ids": change_ids,
    }


def _normalize_recommendation_delta(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {
        "recommendation_id",
        "summary",
        "anchors",
        "change_ids",
        "delta_type",
        "evidence_refs",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    anchors = _normalize_nonempty_str_list(row.get("anchors"), field_name=f"{field_name}.anchors")
    for anchor in anchors:
        if anchor not in _CHANGE_SECTION_KEYS:
            raise ValueError(f"{field_name}.anchors contains unsupported section key: {anchor}")
    change_ids = _normalize_nonempty_str_list(row.get("change_ids"), field_name=f"{field_name}.change_ids")
    delta_type = _require_nonempty_text(row.get("delta_type"), field_name=f"{field_name}.delta_type").lower()
    if delta_type not in _DELTA_TYPES:
        raise ValueError(f"{field_name}.delta_type must be one of: {list(_DELTA_TYPES)}")
    return {
        "recommendation_id": _require_nonempty_text(
            row.get("recommendation_id"),
            field_name=f"{field_name}.recommendation_id",
        ),
        "summary": _require_nonempty_text(row.get("summary"), field_name=f"{field_name}.summary"),
        "anchors": anchors,
        "change_ids": change_ids,
        "delta_type": delta_type,
        "evidence_refs": _normalize_nonempty_str_list(
            row.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
        ),
    }


def _normalize_recommendation_deltas(
    value: Any,
    *,
    allowed_change_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("recommendation_deltas must be a list")
    normalized: list[dict[str, Any]] = []
    seen_recommendation_ids: set[str] = set()
    covered_change_ids: set[str] = set()
    for index, row in enumerate(value):
        delta = _normalize_recommendation_delta(
            row,
            field_name=f"recommendation_deltas[{index}]",
        )
        recommendation_id = delta["recommendation_id"]
        if recommendation_id in seen_recommendation_ids:
            raise ValueError(f"recommendation_deltas[{index}].recommendation_id must be unique")
        seen_recommendation_ids.add(recommendation_id)
        invalid_change_ids = sorted(set(delta["change_ids"]) - allowed_change_ids)
        if invalid_change_ids:
            raise ValueError(
                f"recommendation_deltas[{index}].change_ids must reference change_summary.change_ids: {invalid_change_ids}"
            )
        covered_change_ids.update(delta["change_ids"])
        normalized.append(delta)
    normalized.sort(key=lambda row: row["recommendation_id"])
    if normalized and covered_change_ids != allowed_change_ids:
        missing_change_ids = sorted(allowed_change_ids - covered_change_ids)
        raise ValueError(f"recommendation_deltas must cover every change_summary.change_ids value: {missing_change_ids}")
    return normalized


def _recommendation_ref_map(synthesis: Mapping[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for row in synthesis["final_recommendations"]:
        refs[row["recommendation_id"]] = (
            f"final_strategy_synthesis.final_recommendations#{row['recommendation_id']}"
        )
    for row in synthesis["deferred_recommendations"]:
        refs[row["recommendation_id"]] = (
            f"final_strategy_synthesis.deferred_recommendations#{row['recommendation_id']}"
        )
    return refs


def _req_051_direction_title(section_key: str) -> str:
    return {
        "mission_scope": "Mission Scope Direction Change",
        "runtime_data": "Runtime Direction Change",
        "ecosystem_signals": "Ecosystem Direction Change",
    }[section_key]


def _build_req_051_direction_changes(
    *,
    change_detection: Mapping[str, Mapping[str, Any]],
    recommendation_deltas: list[dict[str, Any]],
    recommendation_refs: Mapping[str, str],
) -> list[dict[str, Any]]:
    direction_changes: list[dict[str, Any]] = []
    for section_key in _CHANGE_SECTION_KEYS:
        section = change_detection[section_key]
        if not section["changed"]:
            continue
        recommendation_ids = sorted(
            delta["recommendation_id"] for delta in recommendation_deltas if section_key in delta["anchors"]
        )
        recommendation_ref_rows = sorted(recommendation_refs[recommendation_id] for recommendation_id in recommendation_ids)
        evidence_refs = sorted(
            {
                ref
                for delta in recommendation_deltas
                if section_key in delta["anchors"]
                for ref in delta["evidence_refs"]
            }
        )
        direction_changes.append(
            {
                "direction_id": f"direction.{section_key}",
                "section_key": section_key,
                "title": _req_051_direction_title(section_key),
                "change_ids": [row["change_id"] for row in section["changes"]],
                "change_count": section["change_count"],
                "recommendation_ids": recommendation_ids,
                "recommendation_refs": recommendation_ref_rows,
                "evidence_refs": evidence_refs,
            }
        )
    return sorted(direction_changes, key=lambda row: row["section_key"])


def _render_strategy_changelog_markdown(
    *,
    checked_at_utc: str,
    target_project: Mapping[str, str],
    revision_pair: Mapping[str, str],
    change_summary: Mapping[str, Any],
    direction_changes: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    alignment: Mapping[str, list[str]],
) -> str:
    lines: list[str] = []
    lines.append("# STRATEGY_CHANGELOG")
    lines.append("")
    lines.append(
        "Generated at "
        f"`{checked_at_utc}` for project `{target_project['project_id']}` "
        f"from `{revision_pair['previous_revision_id']}` to `{revision_pair['current_revision_id']}`."
    )
    lines.append("This changelog summarizes revision deltas and links each changed recommendation to supporting evidence.")
    lines.append("")
    lines.append("## Revision Summary (`revision_pair`, `change_summary`)")
    lines.append(f"- Previous revision: `{revision_pair['previous_revision_id']}`")
    lines.append(f"- Current revision: `{revision_pair['current_revision_id']}`")
    lines.append(f"- Total change count: `{change_summary['total_change_count']}`")
    lines.append(f"- Changed sections: {_quote_join(list(change_summary['changed_sections']))}")
    lines.append(f"- Changed recommendation ids: {_quote_join(list(alignment['recommendation_ids']))}")
    lines.append("")
    lines.append("## Strategic Direction Changes (`change_detection`)")
    if not direction_changes:
        lines.append("No strategic direction changes were emitted.")
    for row in direction_changes:
        lines.append("")
        lines.append(f"### {row['direction_id']}")
        lines.append(f"- Title: {row['title']}")
        lines.append(f"- Section key: `{row['section_key']}`")
        lines.append(f"- Change count: `{row['change_count']}`")
        lines.append(f"- Change ids: {_quote_join(list(row['change_ids']))}")
        lines.append(f"- Changed recommendation ids: {_quote_join(list(row['recommendation_ids']))}")
        lines.append("- Recommendation refs:")
        for ref in row["recommendation_refs"]:
            lines.append(f"  - `{ref}`")
        lines.append("- Evidence refs:")
        for ref in row["evidence_refs"]:
            lines.append(f"  - `{ref}`")

    lines.append("")
    lines.append("## Changed Recommendations (`recommendation_deltas`)")
    if not entries:
        lines.append("No changed recommendations were emitted.")
    for row in entries:
        lines.append("")
        lines.append(f"### {row['entry_id']}")
        lines.append(f"- Recommendation id: `{row['recommendation_id']}`")
        lines.append(f"- Recommendation ref: `{row['recommendation_ref']}`")
        lines.append(f"- Delta type: `{row['delta_type']}`")
        lines.append(f"- Summary: {row['summary']}")
        lines.append(f"- Direction anchors: {_quote_join(list(row['anchors']))}")
        lines.append("- Change ids:")
        for change_id in row["change_ids"]:
            lines.append(f"  - `{change_id}`")
        lines.append("- Evidence refs:")
        for ref in row["evidence_refs"]:
            lines.append(f"  - `{ref}`")

    lines.append("")
    lines.append("## Evidence Index (`evidence_refs`)")
    if not alignment["evidence_refs"]:
        lines.append("No evidence refs were emitted.")
    for ref in alignment["evidence_refs"]:
        lines.append(f"- `{ref}`")

    lines.append("")
    lines.append("## Machine Alignment")
    lines.append(f"- `direction_changes`: {_quote_join(list(alignment['direction_ids']))}")
    lines.append(f"- `entries`: {_quote_join(list(alignment['entry_ids']))}")
    lines.append(f"- `recommendation_ids`: {_quote_join(list(alignment['recommendation_ids']))}")
    lines.append(f"- `recommendation_refs`: {_quote_join(list(alignment['recommendation_refs']))}")
    lines.append(f"- `change_ids`: {_quote_join(list(alignment['change_ids']))}")
    lines.append(f"- `evidence_refs`: {_quote_join(list(alignment['evidence_refs']))}")

    return "\n".join(lines).rstrip() + "\n"


def build_req_051_strategy_changelog_md_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build the REQ-051 STRATEGY_CHANGELOG.md generator payload."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_051_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_051_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    revision_pair = _normalize_revision_pair(raw.get("revision_pair"))
    change_detection = _normalize_change_detection(raw.get("change_detection"))
    change_summary = _normalize_change_summary(
        raw.get("change_summary"),
        change_detection=change_detection,
    )
    synthesis = _normalize_final_strategy_synthesis(raw.get("final_strategy_synthesis"))
    recommendation_refs = _recommendation_ref_map(synthesis)
    recommendation_deltas = _normalize_recommendation_deltas(
        raw.get("recommendation_deltas"),
        allowed_change_ids=set(change_summary["change_ids"]),
    )
    if not recommendation_deltas:
        raise ValueError("recommendation_deltas must be a non-empty list")
    missing_recommendation_ids = sorted(
        delta["recommendation_id"]
        for delta in recommendation_deltas
        if delta["recommendation_id"] not in recommendation_refs
    )
    if missing_recommendation_ids:
        raise ValueError(
            "recommendation_deltas.recommendation_id must resolve to "
            f"final_strategy_synthesis final/deferred recommendations: {missing_recommendation_ids}"
        )

    evidence_refs = _normalize_nonempty_str_list(raw.get("evidence_refs"), field_name="evidence_refs")
    delta_evidence_refs = sorted({ref for delta in recommendation_deltas for ref in delta["evidence_refs"]})
    missing_evidence_refs = sorted(set(delta_evidence_refs) - set(evidence_refs))
    if missing_evidence_refs:
        raise ValueError(
            f"recommendation_deltas evidence refs must be included in evidence_refs: {missing_evidence_refs}"
        )

    entries = [
        {
            "entry_id": f"changelog.{delta['recommendation_id']}",
            "recommendation_id": delta["recommendation_id"],
            "recommendation_ref": recommendation_refs[delta["recommendation_id"]],
            "summary": delta["summary"],
            "delta_type": delta["delta_type"],
            "anchors": list(delta["anchors"]),
            "change_ids": list(delta["change_ids"]),
            "evidence_refs": list(delta["evidence_refs"]),
        }
        for delta in recommendation_deltas
    ]
    direction_changes = _build_req_051_direction_changes(
        change_detection=change_detection,
        recommendation_deltas=recommendation_deltas,
        recommendation_refs=recommendation_refs,
    )
    alignment = {
        "direction_ids": [row["direction_id"] for row in direction_changes],
        "entry_ids": [row["entry_id"] for row in entries],
        "recommendation_ids": sorted({row["recommendation_id"] for row in entries}),
        "recommendation_refs": sorted({row["recommendation_ref"] for row in entries}),
        "change_ids": list(change_summary["change_ids"]),
        "evidence_refs": evidence_refs,
    }
    sections = [
        {
            "section_id": "revision-summary",
            "title": "Revision Summary",
            "machine_field": "revision_pair",
            "entry_count": 2,
            "anchor_ids": [
                revision_pair["previous_revision_id"],
                revision_pair["current_revision_id"],
            ],
        },
        {
            "section_id": "strategic-direction-changes",
            "title": "Strategic Direction Changes",
            "machine_field": "change_detection",
            "entry_count": len(direction_changes),
            "anchor_ids": list(alignment["direction_ids"]),
        },
        {
            "section_id": "changed-recommendations",
            "title": "Changed Recommendations",
            "machine_field": "recommendation_deltas",
            "entry_count": len(entries),
            "anchor_ids": list(alignment["entry_ids"]),
        },
        {
            "section_id": "evidence-index",
            "title": "Evidence Index",
            "machine_field": "evidence_refs",
            "entry_count": len(alignment["evidence_refs"]),
            "anchor_ids": list(alignment["evidence_refs"]),
        },
    ]

    markdown = _render_strategy_changelog_markdown(
        checked_at_utc=checked_at_utc,
        target_project=target_project,
        revision_pair=revision_pair,
        change_summary=change_summary,
        direction_changes=direction_changes,
        entries=entries,
        alignment=alignment,
    )
    line_count = len(markdown.splitlines())
    content_sha256 = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

    output_payload = {
        "ok": True,
        "schema_version": REQ_051_SCHEMA_VERSION,
        "requirement_id": REQ_051_REQUIREMENT_ID,
        "analysis_type": REQ_051_ANALYSIS_TYPE,
        "call_id": REQ_051_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "revision_pair": revision_pair,
        "change_summary": change_summary,
        "strategy_changelog_md": {
            "artifact_path": "STRATEGY_CHANGELOG.md",
            "markdown": markdown,
            "content_sha256": content_sha256,
            "line_count": line_count,
            "sections": sections,
            "direction_changes": direction_changes,
            "entries": entries,
            "alignment": alignment,
        },
        "totals": {
            "direction_changes": len(direction_changes),
            "changed_recommendations": len(entries),
            "change_count": change_summary["total_change_count"],
            "evidence_refs": len(alignment["evidence_refs"]),
            "markdown_sections": len(sections),
            "markdown_lines": line_count,
        },
    }

    errors = validate_req_051_strategy_changelog_md_generator(output_payload)
    if errors:
        raise ValueError(f"built REQ-051 payload failed validation: {errors}")
    return output_payload


def validate_req_051_strategy_changelog_md_generator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-051 STRATEGY_CHANGELOG.md generator payload shape."""
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
        "revision_pair",
        "change_summary",
        "strategy_changelog_md",
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
    if payload.get("schema_version") != REQ_051_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_051_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_051_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_051_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_051_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_051_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_051_CALL_ID:
        errors.append(f"call_id must be {REQ_051_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
    else:
        expected_target = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        project_id = target_project.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            errors.append("target_project.project_id must be a non-empty string")
        project_root = target_project.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not project_root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    revision_pair = payload.get("revision_pair")
    if not isinstance(revision_pair, Mapping):
        errors.append("revision_pair must be an object")
        revision_pair = {}
    else:
        expected_revision_pair = {"previous_revision_id", "current_revision_id"}
        pair_keys = set(revision_pair.keys())
        missing_pair = sorted(expected_revision_pair - pair_keys)
        if missing_pair:
            errors.append(f"revision_pair missing keys: {missing_pair}")
        unexpected_pair = sorted(pair_keys - expected_revision_pair)
        if unexpected_pair:
            errors.append(f"revision_pair has unexpected keys: {unexpected_pair}")
        previous_revision_id = revision_pair.get("previous_revision_id")
        current_revision_id = revision_pair.get("current_revision_id")
        if not isinstance(previous_revision_id, str) or not previous_revision_id.strip():
            errors.append("revision_pair.previous_revision_id must be a non-empty string")
        if not isinstance(current_revision_id, str) or not current_revision_id.strip():
            errors.append("revision_pair.current_revision_id must be a non-empty string")
        if (
            isinstance(previous_revision_id, str)
            and isinstance(current_revision_id, str)
            and previous_revision_id.strip()
            and current_revision_id.strip()
            and previous_revision_id == current_revision_id
        ):
            errors.append("revision_pair.previous_revision_id and current_revision_id must differ")

    change_summary = payload.get("change_summary")
    if not isinstance(change_summary, Mapping):
        errors.append("change_summary must be an object")
        change_summary = {}
    else:
        expected_summary = {"total_change_count", "changed_sections", "change_ids"}
        summary_keys = set(change_summary.keys())
        missing_summary = sorted(expected_summary - summary_keys)
        if missing_summary:
            errors.append(f"change_summary missing keys: {missing_summary}")
        unexpected_summary = sorted(summary_keys - expected_summary)
        if unexpected_summary:
            errors.append(f"change_summary has unexpected keys: {unexpected_summary}")
        total_change_count = change_summary.get("total_change_count")
        if not isinstance(total_change_count, int) or total_change_count < 0:
            errors.append("change_summary.total_change_count must be a non-negative integer")
        for key in ("changed_sections", "change_ids"):
            values = change_summary.get(key)
            if not isinstance(values, list):
                errors.append(f"change_summary.{key} must be a list")
                continue
            if values != sorted(set(values)):
                errors.append(f"change_summary.{key} must be sorted and unique")
            for index, item in enumerate(values):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"change_summary.{key}[{index}] must be a non-empty string")
            if key == "changed_sections":
                for index, item in enumerate(values):
                    if item not in _CHANGE_SECTION_KEYS:
                        errors.append(
                            f"change_summary.changed_sections[{index}] must be one of {', '.join(_CHANGE_SECTION_KEYS)}"
                        )

    changelog = payload.get("strategy_changelog_md")
    if not isinstance(changelog, Mapping):
        errors.append("strategy_changelog_md must be an object")
        return errors

    expected_changelog = {
        "artifact_path",
        "markdown",
        "content_sha256",
        "line_count",
        "sections",
        "direction_changes",
        "entries",
        "alignment",
    }
    changelog_keys = set(changelog.keys())
    missing_changelog = sorted(expected_changelog - changelog_keys)
    if missing_changelog:
        errors.append(f"strategy_changelog_md missing keys: {missing_changelog}")
    unexpected_changelog = sorted(changelog_keys - expected_changelog)
    if unexpected_changelog:
        errors.append(f"strategy_changelog_md has unexpected keys: {unexpected_changelog}")

    if changelog.get("artifact_path") != "STRATEGY_CHANGELOG.md":
        errors.append("strategy_changelog_md.artifact_path must be STRATEGY_CHANGELOG.md")
    markdown = changelog.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        errors.append("strategy_changelog_md.markdown must be a non-empty string")
        markdown = ""
    line_count = changelog.get("line_count")
    if not isinstance(line_count, int) or line_count < 1:
        errors.append("strategy_changelog_md.line_count must be a positive integer")
        line_count = 0
    if isinstance(markdown, str) and markdown:
        expected_sha = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        if changelog.get("content_sha256") != expected_sha:
            errors.append("strategy_changelog_md.content_sha256 must match strategy_changelog_md.markdown")
        if line_count != len(markdown.splitlines()):
            errors.append("strategy_changelog_md.line_count must match strategy_changelog_md.markdown line count")

    sections = changelog.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("strategy_changelog_md.sections must be a non-empty list")
        sections = []
    else:
        seen_section_ids: set[str] = set()
        for index, row in enumerate(sections):
            if not isinstance(row, Mapping):
                errors.append(f"strategy_changelog_md.sections[{index}] must be an object")
                continue
            expected_section = {"section_id", "title", "machine_field", "entry_count", "anchor_ids"}
            row_keys = set(row.keys())
            missing_section = sorted(expected_section - row_keys)
            if missing_section:
                errors.append(f"strategy_changelog_md.sections[{index}] missing keys: {missing_section}")
            unexpected_section = sorted(row_keys - expected_section)
            if unexpected_section:
                errors.append(f"strategy_changelog_md.sections[{index}] has unexpected keys: {unexpected_section}")
            section_id = row.get("section_id")
            if not isinstance(section_id, str) or not section_id.strip():
                errors.append(f"strategy_changelog_md.sections[{index}].section_id must be a non-empty string")
            elif section_id in seen_section_ids:
                errors.append(f"strategy_changelog_md.sections[{index}].section_id must be unique")
            else:
                seen_section_ids.add(section_id)
            title = row.get("title")
            if not isinstance(title, str) or not title.strip():
                errors.append(f"strategy_changelog_md.sections[{index}].title must be a non-empty string")
            machine_field = row.get("machine_field")
            if not isinstance(machine_field, str) or not machine_field.strip():
                errors.append(f"strategy_changelog_md.sections[{index}].machine_field must be a non-empty string")
            entry_count = row.get("entry_count")
            if not isinstance(entry_count, int) or entry_count < 0:
                errors.append(f"strategy_changelog_md.sections[{index}].entry_count must be a non-negative integer")
            anchor_ids = row.get("anchor_ids")
            if not isinstance(anchor_ids, list):
                errors.append(f"strategy_changelog_md.sections[{index}].anchor_ids must be a list")
                continue
            normalized_anchor_ids: list[str] = []
            for anchor_index, anchor_id in enumerate(anchor_ids):
                if not isinstance(anchor_id, str) or not anchor_id.strip():
                    errors.append(
                        f"strategy_changelog_md.sections[{index}].anchor_ids[{anchor_index}] must be a non-empty string"
                    )
                    continue
                normalized_anchor_ids.append(anchor_id)
                if markdown and anchor_id not in markdown:
                    errors.append(
                        f"strategy_changelog_md.sections[{index}].anchor_ids[{anchor_index}] must appear in markdown"
                    )
            if isinstance(entry_count, int) and entry_count >= 0 and entry_count != len(normalized_anchor_ids):
                errors.append(
                    f"strategy_changelog_md.sections[{index}].entry_count must equal number of non-empty anchor_ids"
                )

    direction_changes = changelog.get("direction_changes")
    if not isinstance(direction_changes, list):
        errors.append("strategy_changelog_md.direction_changes must be a list")
        direction_changes = []
    else:
        normalized_direction_changes: list[dict[str, Any]] = []
        seen_direction_ids: set[str] = set()
        for index, row in enumerate(direction_changes):
            mapping = _require_mapping(row, field_name=f"strategy_changelog_md.direction_changes[{index}]")
            expected_direction = {
                "direction_id",
                "section_key",
                "title",
                "change_ids",
                "change_count",
                "recommendation_ids",
                "recommendation_refs",
                "evidence_refs",
            }
            unexpected_direction = sorted(set(mapping.keys()) - expected_direction)
            if unexpected_direction:
                errors.append(
                    f"strategy_changelog_md.direction_changes[{index}] has unexpected keys: {unexpected_direction}"
                )
            direction_id = mapping.get("direction_id")
            if not isinstance(direction_id, str) or not direction_id.strip():
                errors.append(
                    f"strategy_changelog_md.direction_changes[{index}].direction_id must be a non-empty string"
                )
            elif direction_id in seen_direction_ids:
                errors.append(f"strategy_changelog_md.direction_changes[{index}].direction_id must be unique")
            else:
                seen_direction_ids.add(direction_id)
            section_key = mapping.get("section_key")
            if section_key not in _CHANGE_SECTION_KEYS:
                errors.append(
                    "strategy_changelog_md.direction_changes"
                    f"[{index}].section_key must be one of {', '.join(_CHANGE_SECTION_KEYS)}"
                )
            title = mapping.get("title")
            if not isinstance(title, str) or not title.strip():
                errors.append(f"strategy_changelog_md.direction_changes[{index}].title must be a non-empty string")
            change_ids = mapping.get("change_ids")
            if not isinstance(change_ids, list) or not change_ids:
                errors.append(f"strategy_changelog_md.direction_changes[{index}].change_ids must be a non-empty list")
                change_ids = []
            elif change_ids != sorted(set(change_ids)):
                errors.append(f"strategy_changelog_md.direction_changes[{index}].change_ids must be sorted and unique")
            recommendation_ids = mapping.get("recommendation_ids")
            if not isinstance(recommendation_ids, list):
                errors.append(
                    f"strategy_changelog_md.direction_changes[{index}].recommendation_ids must be a list"
                )
                recommendation_ids = []
            elif recommendation_ids != sorted(set(recommendation_ids)):
                errors.append(
                    f"strategy_changelog_md.direction_changes[{index}].recommendation_ids must be sorted and unique"
                )
            recommendation_refs = mapping.get("recommendation_refs")
            if not isinstance(recommendation_refs, list):
                errors.append(
                    f"strategy_changelog_md.direction_changes[{index}].recommendation_refs must be a list"
                )
                recommendation_refs = []
            elif recommendation_refs != sorted(set(recommendation_refs)):
                errors.append(
                    f"strategy_changelog_md.direction_changes[{index}].recommendation_refs must be sorted and unique"
                )
            evidence_refs = mapping.get("evidence_refs")
            if not isinstance(evidence_refs, list):
                errors.append(f"strategy_changelog_md.direction_changes[{index}].evidence_refs must be a list")
                evidence_refs = []
            elif evidence_refs != sorted(set(evidence_refs)):
                errors.append(
                    f"strategy_changelog_md.direction_changes[{index}].evidence_refs must be sorted and unique"
                )
            change_count = mapping.get("change_count")
            if not isinstance(change_count, int) or change_count < 0:
                errors.append(f"strategy_changelog_md.direction_changes[{index}].change_count must be a non-negative integer")
            elif change_count != len(change_ids):
                errors.append(
                    f"strategy_changelog_md.direction_changes[{index}].change_count must match change_ids length"
                )
            normalized_direction_changes.append(
                {
                    "direction_id": direction_id,
                    "section_key": section_key,
                    "title": title,
                    "change_ids": change_ids,
                    "change_count": change_count,
                    "recommendation_ids": recommendation_ids,
                    "recommendation_refs": recommendation_refs,
                    "evidence_refs": evidence_refs,
                }
            )
            if markdown:
                for collection_key, values in (
                    ("direction_id", [direction_id] if isinstance(direction_id, str) else []),
                    ("change_ids", change_ids),
                    ("recommendation_ids", recommendation_ids),
                    ("recommendation_refs", recommendation_refs),
                ):
                    for item_index, item in enumerate(values):
                        if isinstance(item, str) and item and item not in markdown:
                            errors.append(
                                "strategy_changelog_md.direction_changes"
                                f"[{index}].{collection_key}[{item_index}] must appear in markdown"
                            )
        if direction_changes != sorted(normalized_direction_changes, key=lambda row: row["section_key"]):
            errors.append("strategy_changelog_md.direction_changes must be sorted deterministically")

    entries = changelog.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("strategy_changelog_md.entries must be a non-empty list")
        entries = []
    else:
        normalized_entries: list[dict[str, Any]] = []
        seen_entry_ids: set[str] = set()
        seen_recommendation_ids: set[str] = set()
        for index, row in enumerate(entries):
            mapping = _require_mapping(row, field_name=f"strategy_changelog_md.entries[{index}]")
            expected_entry = {
                "entry_id",
                "recommendation_id",
                "recommendation_ref",
                "summary",
                "delta_type",
                "anchors",
                "change_ids",
                "evidence_refs",
            }
            unexpected_entry = sorted(set(mapping.keys()) - expected_entry)
            if unexpected_entry:
                errors.append(f"strategy_changelog_md.entries[{index}] has unexpected keys: {unexpected_entry}")
            entry_id = mapping.get("entry_id")
            if not isinstance(entry_id, str) or not entry_id.strip():
                errors.append(f"strategy_changelog_md.entries[{index}].entry_id must be a non-empty string")
            elif entry_id in seen_entry_ids:
                errors.append(f"strategy_changelog_md.entries[{index}].entry_id must be unique")
            else:
                seen_entry_ids.add(entry_id)
            recommendation_id = mapping.get("recommendation_id")
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                errors.append(
                    f"strategy_changelog_md.entries[{index}].recommendation_id must be a non-empty string"
                )
            elif recommendation_id in seen_recommendation_ids:
                errors.append(f"strategy_changelog_md.entries[{index}].recommendation_id must be unique")
            else:
                seen_recommendation_ids.add(recommendation_id)
            recommendation_ref = mapping.get("recommendation_ref")
            if not isinstance(recommendation_ref, str) or not recommendation_ref.strip():
                errors.append(
                    f"strategy_changelog_md.entries[{index}].recommendation_ref must be a non-empty string"
                )
            summary_value = mapping.get("summary")
            if not isinstance(summary_value, str) or not summary_value.strip():
                errors.append(f"strategy_changelog_md.entries[{index}].summary must be a non-empty string")
            delta_type = mapping.get("delta_type")
            if delta_type not in _DELTA_TYPES:
                errors.append(
                    f"strategy_changelog_md.entries[{index}].delta_type must be one of {', '.join(_DELTA_TYPES)}"
                )
            anchors = mapping.get("anchors")
            if not isinstance(anchors, list) or not anchors:
                errors.append(f"strategy_changelog_md.entries[{index}].anchors must be a non-empty list")
                anchors = []
            elif anchors != sorted(set(anchors)):
                errors.append(f"strategy_changelog_md.entries[{index}].anchors must be sorted and unique")
            else:
                for anchor_index, anchor in enumerate(anchors):
                    if anchor not in _CHANGE_SECTION_KEYS:
                        errors.append(
                            f"strategy_changelog_md.entries[{index}].anchors[{anchor_index}] must be one of "
                            f"{', '.join(_CHANGE_SECTION_KEYS)}"
                        )
            change_ids = mapping.get("change_ids")
            if not isinstance(change_ids, list) or not change_ids:
                errors.append(f"strategy_changelog_md.entries[{index}].change_ids must be a non-empty list")
                change_ids = []
            elif change_ids != sorted(set(change_ids)):
                errors.append(f"strategy_changelog_md.entries[{index}].change_ids must be sorted and unique")
            evidence_refs = mapping.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(f"strategy_changelog_md.entries[{index}].evidence_refs must be a non-empty list")
                evidence_refs = []
            elif evidence_refs != sorted(set(evidence_refs)):
                errors.append(f"strategy_changelog_md.entries[{index}].evidence_refs must be sorted and unique")
            normalized_entries.append(
                {
                    "entry_id": entry_id,
                    "recommendation_id": recommendation_id,
                    "recommendation_ref": recommendation_ref,
                    "summary": summary_value,
                    "delta_type": delta_type,
                    "anchors": anchors,
                    "change_ids": change_ids,
                    "evidence_refs": evidence_refs,
                }
            )
            if markdown:
                for collection_key, values in (
                    ("entry_id", [entry_id] if isinstance(entry_id, str) else []),
                    ("recommendation_id", [recommendation_id] if isinstance(recommendation_id, str) else []),
                    ("recommendation_ref", [recommendation_ref] if isinstance(recommendation_ref, str) else []),
                    ("change_ids", change_ids),
                    ("evidence_refs", evidence_refs),
                ):
                    for item_index, item in enumerate(values):
                        if isinstance(item, str) and item and item not in markdown:
                            errors.append(
                                f"strategy_changelog_md.entries[{index}].{collection_key}[{item_index}] must appear in markdown"
                            )
        if entries != sorted(normalized_entries, key=lambda row: row["recommendation_id"]):
            errors.append("strategy_changelog_md.entries must be sorted deterministically")

    alignment = changelog.get("alignment")
    alignment_keys = (
        "direction_ids",
        "entry_ids",
        "recommendation_ids",
        "recommendation_refs",
        "change_ids",
        "evidence_refs",
    )
    if not isinstance(alignment, Mapping):
        errors.append("strategy_changelog_md.alignment must be an object")
        alignment = {}
    else:
        expected_alignment = set(alignment_keys)
        alignment_present = set(alignment.keys())
        missing_alignment = sorted(expected_alignment - alignment_present)
        if missing_alignment:
            errors.append(f"strategy_changelog_md.alignment missing keys: {missing_alignment}")
        unexpected_alignment = sorted(alignment_present - expected_alignment)
        if unexpected_alignment:
            errors.append(f"strategy_changelog_md.alignment has unexpected keys: {unexpected_alignment}")
        for key in alignment_keys:
            values = alignment.get(key)
            if not isinstance(values, list):
                errors.append(f"strategy_changelog_md.alignment.{key} must be a list")
                continue
            if values != sorted(set(values)):
                errors.append(f"strategy_changelog_md.alignment.{key} must be sorted and unique")
            for index, item in enumerate(values):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"strategy_changelog_md.alignment.{key}[{index}] must be a non-empty string")
                elif markdown and item not in markdown:
                    errors.append(f"strategy_changelog_md.alignment.{key}[{index}] must appear in markdown")

    if isinstance(change_summary, Mapping) and isinstance(alignment, Mapping):
        if change_summary.get("change_ids") != alignment.get("change_ids"):
            errors.append("strategy_changelog_md.alignment.change_ids must match change_summary.change_ids")

    if isinstance(alignment, Mapping):
        expected_direction_ids = [
            row["direction_id"] for row in direction_changes if isinstance(row, Mapping) and "direction_id" in row
        ]
        expected_entry_ids = [row["entry_id"] for row in entries if isinstance(row, Mapping) and "entry_id" in row]
        expected_recommendation_ids = sorted(
            row["recommendation_id"] for row in entries if isinstance(row, Mapping) and "recommendation_id" in row
        )
        expected_recommendation_refs = sorted(
            row["recommendation_ref"] for row in entries if isinstance(row, Mapping) and "recommendation_ref" in row
        )
        expected_evidence_refs = sorted(
            {
                ref
                for row in entries
                if isinstance(row, Mapping)
                for ref in row.get("evidence_refs", [])
                if isinstance(ref, str) and ref.strip()
            }
        )
        if alignment.get("direction_ids") != expected_direction_ids:
            errors.append("strategy_changelog_md.alignment.direction_ids must match direction_changes")
        if alignment.get("entry_ids") != expected_entry_ids:
            errors.append("strategy_changelog_md.alignment.entry_ids must match entries")
        if alignment.get("recommendation_ids") != expected_recommendation_ids:
            errors.append("strategy_changelog_md.alignment.recommendation_ids must match entries")
        if alignment.get("recommendation_refs") != expected_recommendation_refs:
            errors.append("strategy_changelog_md.alignment.recommendation_refs must match entries")
        if alignment.get("evidence_refs") != expected_evidence_refs:
            errors.append("strategy_changelog_md.alignment.evidence_refs must match entries evidence coverage")

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "direction_changes",
            "changed_recommendations",
            "change_count",
            "evidence_refs",
            "markdown_sections",
            "markdown_lines",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        expected_values = {
            "direction_changes": len(direction_changes),
            "changed_recommendations": len(entries),
            "change_count": change_summary.get("total_change_count"),
            "evidence_refs": len(alignment.get("evidence_refs", [])) if isinstance(alignment, Mapping) else 0,
            "markdown_sections": len(sections),
            "markdown_lines": line_count,
        }
        for key, expected_value in expected_values.items():
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")
            elif value != expected_value:
                errors.append(f"totals.{key} must match derived strategy_changelog_md counts")

    if isinstance(markdown, str) and markdown:
        required_headers = (
            "## Revision Summary",
            "## Strategic Direction Changes",
            "## Changed Recommendations",
            "## Evidence Index",
            "## Machine Alignment",
        )
        for header in required_headers:
            if header not in markdown:
                errors.append(f"strategy_changelog_md.markdown must include section header: {header}")

    return errors


def _req_052_canonical_project_id(project_id: str) -> str:
    return f"prj.{_slug_token(project_id)}"


def _normalize_req_052_identity_input(value: Any) -> dict[str, str]:
    identity = _require_mapping(value, field_name="identity")
    expected = {"run_id", "event_id", "era_id", "plan_id"}
    unexpected = sorted(set(identity.keys()) - expected)
    if unexpected:
        raise ValueError(f"identity has unexpected keys: {unexpected}")

    normalized = {
        "run_id": _require_canonical_id(identity.get("run_id"), field_name="identity.run_id", prefix="run"),
        "event_id": _require_canonical_id(
            identity.get("event_id"),
            field_name="identity.event_id",
            prefix="event",
        ),
    }
    if "era_id" in identity:
        normalized["era_id"] = _require_canonical_id(
            identity.get("era_id"),
            field_name="identity.era_id",
            prefix="era",
        )
    if "plan_id" in identity:
        normalized["plan_id"] = _require_canonical_id(
            identity.get("plan_id"),
            field_name="identity.plan_id",
            prefix="plan",
        )
    return normalized


def _normalize_req_052_strategy_section(value: Any) -> dict[str, str]:
    strategy = _require_mapping(value, field_name="strategy")
    expected = {"revision_id", "summary", "link_map_ref"}
    unexpected = sorted(set(strategy.keys()) - expected)
    if unexpected:
        raise ValueError(f"strategy has unexpected keys: {unexpected}")

    normalized = {
        "revision_id": _require_nonempty_text(strategy.get("revision_id"), field_name="strategy.revision_id"),
        "summary": _require_nonempty_text(strategy.get("summary"), field_name="strategy.summary"),
    }
    if "link_map_ref" in strategy:
        normalized["link_map_ref"] = _require_nonempty_text(
            strategy.get("link_map_ref"),
            field_name="strategy.link_map_ref",
        )
    return normalized


def _normalize_req_052_recommendation_profile(value: Any, *, field_name: str) -> dict[str, str]:
    profile = _require_mapping(value, field_name=field_name)
    expected = {"recommendation_id", "expected_impact", "risk_level"}
    unexpected = sorted(set(profile.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    risk_level = _require_nonempty_text(profile.get("risk_level"), field_name=f"{field_name}.risk_level").lower()
    if risk_level not in _RISK_LEVELS:
        raise ValueError(f"{field_name}.risk_level must be one of: {list(_RISK_LEVELS)}")

    recommendation_id = _require_nonempty_text(
        profile.get("recommendation_id"),
        field_name=f"{field_name}.recommendation_id",
    )
    if not re.fullmatch(r"rec\.[a-z0-9][a-z0-9-]{1,95}", recommendation_id):
        raise ValueError(f"{field_name}.recommendation_id must match rec.<lowercase-hyphenated-id>")

    return {
        "recommendation_id": recommendation_id,
        "expected_impact": _require_nonempty_text(
            profile.get("expected_impact"),
            field_name=f"{field_name}.expected_impact",
        ),
        "risk_level": risk_level,
    }


def _normalize_req_052_recommendation_profiles(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("recommendation_profiles must be a list")
    profiles: list[dict[str, str]] = []
    seen_recommendation_ids: set[str] = set()
    for index, row in enumerate(value):
        profile = _normalize_req_052_recommendation_profile(
            row,
            field_name=f"recommendation_profiles[{index}]",
        )
        recommendation_id = profile["recommendation_id"]
        if recommendation_id in seen_recommendation_ids:
            raise ValueError(f"recommendation_profiles[{index}].recommendation_id must be unique")
        seen_recommendation_ids.add(recommendation_id)
        profiles.append(profile)
    return sorted(profiles, key=lambda row: row["recommendation_id"])


def _normalize_req_052_constraints(value: Any) -> dict[str, list[str]]:
    constraints = _require_mapping(value, field_name="constraints")
    expected = {"hard", "soft"}
    unexpected = sorted(set(constraints.keys()) - expected)
    if unexpected:
        raise ValueError(f"constraints has unexpected keys: {unexpected}")
    missing = sorted(expected - set(constraints.keys()))
    if missing:
        raise ValueError(f"constraints missing keys: {missing}")
    return {
        "hard": _normalize_optional_str_list(constraints.get("hard"), field_name="constraints.hard"),
        "soft": _normalize_optional_str_list(constraints.get("soft"), field_name="constraints.soft"),
    }


def _normalize_req_052_kpi_target(value: Any, *, field_name: str) -> dict[str, str]:
    target = _require_mapping(value, field_name=field_name)
    expected = {"metric", "direction", "target"}
    unexpected = sorted(set(target.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    direction = _require_nonempty_text(target.get("direction"), field_name=f"{field_name}.direction").lower()
    if direction not in _KPI_DIRECTIONS:
        raise ValueError(f"{field_name}.direction must be one of: {list(_KPI_DIRECTIONS)}")
    normalized = {
        "metric": _require_nonempty_text(target.get("metric"), field_name=f"{field_name}.metric"),
        "direction": direction,
    }
    if "target" in target:
        normalized["target"] = _require_nonempty_text(target.get("target"), field_name=f"{field_name}.target")
    return normalized


def _normalize_req_052_kpi_targets(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("kpi_targets must be a list")
    targets: list[dict[str, str]] = []
    seen_rows: set[tuple[str, str, str]] = set()
    for index, row in enumerate(value):
        normalized = _normalize_req_052_kpi_target(row, field_name=f"kpi_targets[{index}]")
        row_key = (normalized["metric"], normalized["direction"], normalized.get("target", ""))
        if row_key in seen_rows:
            raise ValueError(f"kpi_targets[{index}] must be unique")
        seen_rows.add(row_key)
        targets.append(normalized)
    return sorted(targets, key=lambda row: (row["metric"], row["direction"], row.get("target", "")))


def _normalize_req_052_source(value: Any) -> dict[str, str]:
    source = _require_mapping(value, field_name="source")
    expected = {"repo", "tool"}
    unexpected = sorted(set(source.keys()) - expected)
    if unexpected:
        raise ValueError(f"source has unexpected keys: {unexpected}")
    missing = sorted(expected - set(source.keys()))
    if missing:
        raise ValueError(f"source missing keys: {missing}")
    return {
        "repo": _require_nonempty_text(source.get("repo"), field_name="source.repo"),
        "tool": _require_nonempty_text(source.get("tool"), field_name="source.tool"),
    }


def _req_052_earth_sweep_evidence_refs(row: Mapping[str, Any]) -> list[str]:
    earth_refs = {
        ref
        for ref in row.get("evidence_refs", [])
        if isinstance(ref, str) and ref.startswith("reports/earth/sweeps/")
    }
    return sorted(earth_refs)


def _req_052_recommendation_field_completeness(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "required_fields": list(_REQ_052_REQUIRED_SYNTHESIS_RECOMMENDATION_FIELDS),
            "missing_fields": list(_REQ_052_REQUIRED_SYNTHESIS_RECOMMENDATION_FIELDS),
            "all_fields_present": False,
        }

    missing_fields: list[str] = []
    for field in _REQ_052_REQUIRED_SYNTHESIS_RECOMMENDATION_FIELDS:
        value = row.get(field)
        if field == "peer_project_id":
            if row.get("packet_kind") == "cross-project" and (not isinstance(value, str) or not value.strip()):
                missing_fields.append(field)
            continue
        if field in ("evidence_refs", "call_trace_lineage", "contributing_call_ids", "contributing_requirement_ids"):
            if not isinstance(value, list) or not value:
                missing_fields.append(field)
            continue
        if field in ("sequence_hint", "supporting_call_count"):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                missing_fields.append(field)
            continue
        if not isinstance(value, str) or not value.strip():
            missing_fields.append(field)

    return {
        "required_fields": list(_REQ_052_REQUIRED_SYNTHESIS_RECOMMENDATION_FIELDS),
        "missing_fields": missing_fields,
        "all_fields_present": not missing_fields,
    }


def _req_052_recommendation_readiness(
    *,
    final_recommendations: list[dict[str, Any]],
    strategy_packet_inputs: list[dict[str, Any]],
    target_project_id: str,
) -> list[dict[str, Any]]:
    packet_inputs_by_id = {row["packet_input_id"]: row for row in strategy_packet_inputs}
    covered_recommendation_ids: set[str] = set()
    readiness_rows: list[dict[str, Any]] = []

    for row in final_recommendations:
        packet_input_id = row["strategy_packet_input_id"]
        packet_input = packet_inputs_by_id.get(packet_input_id)
        if packet_input is None:
            raise ValueError(
                "final_strategy_synthesis.final_recommendations references unknown "
                f"strategy_packet_input_id: {packet_input_id}"
            )
        if packet_input["target_project_id"] != target_project_id:
            raise ValueError(
                "final_strategy_synthesis.strategy_packet_inputs target_project_id must match target_project.project_id "
                f"for {packet_input_id}"
            )
        if row["recommendation_id"] not in packet_input["recommendation_ids"]:
            raise ValueError(
                "final_strategy_synthesis.strategy_packet_inputs must include recommendation_id coverage for "
                f"{row['recommendation_id']}"
            )
        for key in ("packet_kind", "peer_project_id", "lane"):
            if row[key] != packet_input[key]:
                raise ValueError(
                    f"final_strategy_synthesis.strategy_packet_inputs[{packet_input_id}].{key} "
                    f"must match final recommendation {row['recommendation_id']}"
                )
        earth_sweep_evidence_refs = _req_052_earth_sweep_evidence_refs(row)
        if row["packet_kind"] == "cross-project" and not earth_sweep_evidence_refs:
            raise ValueError(
                "cross-project final recommendations must include direct Earth-sweep evidence refs: "
                f"{row['recommendation_id']}"
            )
        readiness_rows.append(
            {
                "recommendation_id": row["recommendation_id"],
                "strategy_packet_input_id": packet_input_id,
                "packet_kind": row["packet_kind"],
                "peer_project_id": row["peer_project_id"],
                "lane": row["lane"],
                "evidence_refs": list(row["evidence_refs"]),
                "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
                "recommendation_field_completeness": _req_052_recommendation_field_completeness(row),
            }
        )
        covered_recommendation_ids.add(row["recommendation_id"])

    expected_recommendation_ids = {
        recommendation_id
        for packet_input in strategy_packet_inputs
        for recommendation_id in packet_input["recommendation_ids"]
    }
    if covered_recommendation_ids != expected_recommendation_ids:
        missing_recommendation_ids = sorted(expected_recommendation_ids - covered_recommendation_ids)
        extra_recommendation_ids = sorted(covered_recommendation_ids - expected_recommendation_ids)
        details: list[str] = []
        if missing_recommendation_ids:
            details.append(f"missing={missing_recommendation_ids}")
        if extra_recommendation_ids:
            details.append(f"extra={extra_recommendation_ids}")
        raise ValueError(
            "final_strategy_synthesis.strategy_packet_inputs recommendation coverage must match final_recommendations"
            + (f": {', '.join(details)}" if details else "")
        )
    return readiness_rows


def _req_052_validate_open_risks(
    *,
    final_recommendation_ids: set[str],
    open_risks: list[dict[str, Any]],
) -> None:
    for row in open_risks:
        if row["reason_code"] != "unresolved_idea_open_risk":
            continue
        if row["recommendation_id"] in final_recommendation_ids:
            raise ValueError(
                "final_strategy_synthesis.open_risks unresolved ideas must not appear in final_recommendations: "
                f"{row['recommendation_id']}"
            )


def build_req_052_strategy_packet_v1_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build the REQ-052 strategy_packet.v1 generator payload."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_052_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_052_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    identity_input = _normalize_req_052_identity_input(raw.get("identity"))
    strategy = _normalize_req_052_strategy_section(raw.get("strategy"))
    recommendation_profiles = _normalize_req_052_recommendation_profiles(raw.get("recommendation_profiles"))
    constraints = _normalize_req_052_constraints(raw.get("constraints"))
    kpi_targets = _normalize_req_052_kpi_targets(raw.get("kpi_targets"))
    source = _normalize_req_052_source(raw.get("source"))
    synthesis = _normalize_final_strategy_synthesis(raw.get("final_strategy_synthesis"))

    final_recommendations = list(synthesis["final_recommendations"])
    if not final_recommendations:
        raise ValueError("final_strategy_synthesis.final_recommendations must be a non-empty list")
    _req_052_validate_open_risks(
        final_recommendation_ids={row["recommendation_id"] for row in final_recommendations},
        open_risks=list(synthesis["open_risks"]),
    )
    recommendation_readiness = _req_052_recommendation_readiness(
        final_recommendations=final_recommendations,
        strategy_packet_inputs=list(synthesis["strategy_packet_inputs"]),
        target_project_id=target_project["project_id"],
    )

    final_recommendation_ids = [row["recommendation_id"] for row in final_recommendations]
    profile_map = {row["recommendation_id"]: row for row in recommendation_profiles}
    missing_profile_ids = sorted(set(final_recommendation_ids) - set(profile_map.keys()))
    if missing_profile_ids:
        raise ValueError(
            "recommendation_profiles must cover every final_strategy_synthesis.final_recommendations id: "
            f"{missing_profile_ids}"
        )
    extra_profile_ids = sorted(set(profile_map.keys()) - set(final_recommendation_ids))
    if extra_profile_ids:
        raise ValueError(
            "recommendation_profiles must not include ids outside final_strategy_synthesis.final_recommendations: "
            f"{extra_profile_ids}"
        )

    packet_identity = {
        "project_id": _req_052_canonical_project_id(target_project["project_id"]),
        "run_id": identity_input["run_id"],
        "event_id": identity_input["event_id"],
    }
    for optional_key in ("era_id", "plan_id"):
        if optional_key in identity_input:
            packet_identity[optional_key] = identity_input[optional_key]

    packet_recommendations = []
    for row in final_recommendations:
        profile = profile_map[row["recommendation_id"]]
        packet_recommendations.append(
            {
                "recommendation_id": row["recommendation_id"],
                "priority": row["priority"],
                "summary": row["summary"],
                "rationale": row["rationale"],
                "expected_impact": profile["expected_impact"],
                "risk_level": profile["risk_level"],
            }
        )

    output_payload = {
        "ok": True,
        "schema_version": REQ_052_SCHEMA_VERSION,
        "requirement_id": REQ_052_REQUIREMENT_ID,
        "analysis_type": REQ_052_ANALYSIS_TYPE,
        "call_id": REQ_052_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "strategy_packet_v1": {
            "artifact_path": "strategy_packet.v1.json",
            "packet": {
                "schema_version": STRATEGY_PACKET_V1_SCHEMA_VERSION,
                "identity": packet_identity,
                "strategy": strategy,
                "recommendations": packet_recommendations,
                "constraints": constraints,
                "kpi_targets": kpi_targets,
                "source": source,
            },
        },
        "strategy_packet_context": {
            "recommendation_readiness": recommendation_readiness,
            "cross_project_context_usage": dict(synthesis["cross_project_context_usage"]),
            "open_risks": list(synthesis["open_risks"]),
        },
        "totals": {
            "recommendations": len(packet_recommendations),
            "hard_constraints": len(constraints["hard"]),
            "soft_constraints": len(constraints["soft"]),
            "kpi_targets": len(kpi_targets),
        },
    }

    errors = validate_req_052_strategy_packet_v1_generator(output_payload)
    if errors:
        raise ValueError(f"built REQ-052 payload failed validation: {errors}")
    return output_payload


def validate_req_052_strategy_packet_v1_generator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-052 strategy_packet.v1 generator payload shape."""
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
        "strategy_packet_v1",
        "strategy_packet_context",
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
    if payload.get("schema_version") != REQ_052_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_052_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_052_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_052_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_052_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_052_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_052_CALL_ID:
        errors.append(f"call_id must be {REQ_052_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    target_project_id = ""
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
    else:
        expected_target = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        target_project_id = str(target_project.get("project_id") or "").strip()
        if not target_project_id:
            errors.append("target_project.project_id must be a non-empty string")
        project_root = target_project.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not project_root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    strategy_packet_v1 = payload.get("strategy_packet_v1")
    if not isinstance(strategy_packet_v1, Mapping):
        errors.append("strategy_packet_v1 must be an object")
        return errors

    expected_packet_surface = {"artifact_path", "packet"}
    packet_surface_keys = set(strategy_packet_v1.keys())
    missing_packet_surface = sorted(expected_packet_surface - packet_surface_keys)
    if missing_packet_surface:
        errors.append(f"strategy_packet_v1 missing keys: {missing_packet_surface}")
    unexpected_packet_surface = sorted(packet_surface_keys - expected_packet_surface)
    if unexpected_packet_surface:
        errors.append(f"strategy_packet_v1 has unexpected keys: {unexpected_packet_surface}")
    if strategy_packet_v1.get("artifact_path") != "strategy_packet.v1.json":
        errors.append("strategy_packet_v1.artifact_path must be strategy_packet.v1.json")

    packet = strategy_packet_v1.get("packet")
    if not isinstance(packet, Mapping):
        errors.append("strategy_packet_v1.packet must be an object")
        return errors

    expected_packet_keys = {
        "schema_version",
        "identity",
        "strategy",
        "recommendations",
        "constraints",
        "kpi_targets",
        "source",
    }
    packet_keys = set(packet.keys())
    missing_packet_keys = sorted(expected_packet_keys - packet_keys)
    if missing_packet_keys:
        errors.append(f"strategy_packet_v1.packet missing keys: {missing_packet_keys}")
    unexpected_packet_keys = sorted(packet_keys - expected_packet_keys)
    if unexpected_packet_keys:
        errors.append(f"strategy_packet_v1.packet has unexpected keys: {unexpected_packet_keys}")
    if packet.get("schema_version") != STRATEGY_PACKET_V1_SCHEMA_VERSION:
        errors.append(f"strategy_packet_v1.packet.schema_version must be {STRATEGY_PACKET_V1_SCHEMA_VERSION}")

    identity = packet.get("identity")
    if not isinstance(identity, Mapping):
        errors.append("strategy_packet_v1.packet.identity must be an object")
    else:
        expected_identity_keys = {"project_id", "run_id", "event_id", "era_id", "plan_id"}
        unexpected_identity_keys = sorted(set(identity.keys()) - expected_identity_keys)
        if unexpected_identity_keys:
            errors.append(f"strategy_packet_v1.packet.identity has unexpected keys: {unexpected_identity_keys}")
        for required_key, prefix in (("project_id", "prj"), ("run_id", "run"), ("event_id", "event")):
            try:
                _require_canonical_id(
                    identity.get(required_key),
                    field_name=f"strategy_packet_v1.packet.identity.{required_key}",
                    prefix=prefix,
                )
            except ValueError as exc:
                errors.append(str(exc))
        for optional_key, prefix in (("era_id", "era"), ("plan_id", "plan")):
            if optional_key in identity:
                try:
                    _require_canonical_id(
                        identity.get(optional_key),
                        field_name=f"strategy_packet_v1.packet.identity.{optional_key}",
                        prefix=prefix,
                    )
                except ValueError as exc:
                    errors.append(str(exc))
        expected_project_id = _req_052_canonical_project_id(target_project_id) if target_project_id else ""
        if expected_project_id and identity.get("project_id") != expected_project_id:
            errors.append("strategy_packet_v1.packet.identity.project_id must match target_project.project_id")

    strategy = packet.get("strategy")
    if not isinstance(strategy, Mapping):
        errors.append("strategy_packet_v1.packet.strategy must be an object")
    else:
        try:
            normalized_strategy = _normalize_req_052_strategy_section(strategy)
            if dict(strategy) != normalized_strategy:
                errors.append("strategy_packet_v1.packet.strategy must be normalized deterministically")
        except ValueError as exc:
            errors.append(str(exc))

    recommendations = packet.get("recommendations")
    if not isinstance(recommendations, list) or not recommendations:
        errors.append("strategy_packet_v1.packet.recommendations must be a non-empty list")
        recommendations = []
    else:
        seen_recommendation_ids: set[str] = set()
        for index, row in enumerate(recommendations):
            if not isinstance(row, Mapping):
                errors.append(f"strategy_packet_v1.packet.recommendations[{index}] must be an object")
                continue
            try:
                profile = _normalize_req_052_recommendation_profile(
                    {
                        "recommendation_id": row.get("recommendation_id"),
                        "expected_impact": row.get("expected_impact"),
                        "risk_level": row.get("risk_level"),
                    },
                    field_name=f"strategy_packet_v1.packet.recommendations[{index}]",
                )
            except ValueError as exc:
                errors.append(str(exc))
                profile = None
            mapping = row
            expected_recommendation_keys = {
                "recommendation_id",
                "priority",
                "summary",
                "rationale",
                "expected_impact",
                "risk_level",
            }
            unexpected_recommendation_keys = sorted(set(mapping.keys()) - expected_recommendation_keys)
            if unexpected_recommendation_keys:
                errors.append(
                    "strategy_packet_v1.packet.recommendations"
                    f"[{index}] has unexpected keys: {unexpected_recommendation_keys}"
                )
            recommendation_id = mapping.get("recommendation_id")
            if isinstance(recommendation_id, str):
                if recommendation_id in seen_recommendation_ids:
                    errors.append(
                        f"strategy_packet_v1.packet.recommendations[{index}].recommendation_id must be unique"
                    )
                else:
                    seen_recommendation_ids.add(recommendation_id)
            priority = str(mapping.get("priority") or "").strip().lower()
            if priority not in _PRIORITY_LEVELS:
                errors.append(
                    "strategy_packet_v1.packet.recommendations"
                    f"[{index}].priority must be one of {', '.join(_PRIORITY_LEVELS)}"
                )
            for key in ("summary", "rationale"):
                value = mapping.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"strategy_packet_v1.packet.recommendations[{index}].{key} must be a non-empty string"
                    )
            if profile is None:
                continue

    constraints = packet.get("constraints")
    if not isinstance(constraints, Mapping):
        errors.append("strategy_packet_v1.packet.constraints must be an object")
        constraints = {}
    else:
        try:
            normalized_constraints = _normalize_req_052_constraints(constraints)
            if dict(constraints) != normalized_constraints:
                errors.append("strategy_packet_v1.packet.constraints must be sorted deterministically")
        except ValueError as exc:
            errors.append(str(exc))

    kpi_targets = packet.get("kpi_targets")
    if not isinstance(kpi_targets, list):
        errors.append("strategy_packet_v1.packet.kpi_targets must be a list")
        kpi_targets = []
    else:
        try:
            normalized_targets = _normalize_req_052_kpi_targets(kpi_targets)
            if kpi_targets != normalized_targets:
                errors.append("strategy_packet_v1.packet.kpi_targets must be sorted deterministically")
        except ValueError as exc:
            errors.append(str(exc))

    source = packet.get("source")
    if not isinstance(source, Mapping):
        errors.append("strategy_packet_v1.packet.source must be an object")
    else:
        try:
            normalized_source = _normalize_req_052_source(source)
            if dict(source) != normalized_source:
                errors.append("strategy_packet_v1.packet.source must be normalized deterministically")
        except ValueError as exc:
            errors.append(str(exc))

    strategy_packet_context = payload.get("strategy_packet_context")
    readiness_rows: list[Any] = []
    open_risks: list[Any] = []
    if not isinstance(strategy_packet_context, Mapping):
        errors.append("strategy_packet_context must be an object")
    else:
        expected_context_keys = {"recommendation_readiness", "cross_project_context_usage", "open_risks"}
        context_keys = set(strategy_packet_context.keys())
        missing_context = sorted(expected_context_keys - context_keys)
        if missing_context:
            errors.append(f"strategy_packet_context missing keys: {missing_context}")
        unexpected_context = sorted(context_keys - expected_context_keys)
        if unexpected_context:
            errors.append(f"strategy_packet_context has unexpected keys: {unexpected_context}")

        readiness_rows = strategy_packet_context.get("recommendation_readiness", [])
        if not isinstance(readiness_rows, list) or not readiness_rows:
            errors.append("strategy_packet_context.recommendation_readiness must be a non-empty list")
            readiness_rows = []
        else:
            expected_required_fields = list(_REQ_052_REQUIRED_SYNTHESIS_RECOMMENDATION_FIELDS)
            seen_recommendation_ids: set[str] = set()
            normalized_readiness: list[dict[str, Any]] = []
            for index, row in enumerate(readiness_rows):
                if not isinstance(row, Mapping):
                    errors.append(f"strategy_packet_context.recommendation_readiness[{index}] must be an object")
                    continue
                expected_readiness_keys = {
                    "recommendation_id",
                    "strategy_packet_input_id",
                    "packet_kind",
                    "peer_project_id",
                    "lane",
                    "evidence_refs",
                    "earth_sweep_evidence_refs",
                    "recommendation_field_completeness",
                }
                unexpected_readiness_keys = sorted(set(row.keys()) - expected_readiness_keys)
                if unexpected_readiness_keys:
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}] has unexpected keys: {unexpected_readiness_keys}"
                    )
                recommendation_id = row.get("recommendation_id")
                if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                    errors.append(
                        f"strategy_packet_context.recommendation_readiness[{index}].recommendation_id must be a non-empty string"
                    )
                elif recommendation_id in seen_recommendation_ids:
                    errors.append(
                        f"strategy_packet_context.recommendation_readiness[{index}].recommendation_id must be unique"
                    )
                else:
                    seen_recommendation_ids.add(recommendation_id)
                packet_input_id = row.get("strategy_packet_input_id")
                if not isinstance(packet_input_id, str) or not packet_input_id.startswith("pkt."):
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].strategy_packet_input_id must start with pkt."
                    )
                packet_kind = row.get("packet_kind")
                if packet_kind not in _PACKET_KINDS:
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].packet_kind must be one of {', '.join(_PACKET_KINDS)}"
                    )
                peer_project_id = row.get("peer_project_id")
                if not isinstance(peer_project_id, str):
                    errors.append(
                        f"strategy_packet_context.recommendation_readiness[{index}].peer_project_id must be a string"
                    )
                elif packet_kind == "cross-project" and not peer_project_id.strip():
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].peer_project_id must be set for cross-project rows"
                    )
                elif packet_kind == "target-project" and peer_project_id.strip():
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].peer_project_id must be empty for target-project rows"
                    )
                lane = row.get("lane")
                if not isinstance(lane, str) or not lane.strip():
                    errors.append(
                        f"strategy_packet_context.recommendation_readiness[{index}].lane must be a non-empty string"
                    )
                evidence_refs = row.get("evidence_refs")
                if not isinstance(evidence_refs, list) or not evidence_refs:
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].evidence_refs must be a non-empty list"
                    )
                    evidence_refs = []
                elif evidence_refs != sorted(set(evidence_refs)):
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].evidence_refs must be sorted and unique"
                    )
                earth_sweep_evidence_refs = row.get("earth_sweep_evidence_refs")
                if not isinstance(earth_sweep_evidence_refs, list):
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].earth_sweep_evidence_refs must be a list"
                    )
                    earth_sweep_evidence_refs = []
                elif earth_sweep_evidence_refs != sorted(set(earth_sweep_evidence_refs)):
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].earth_sweep_evidence_refs must be sorted and unique"
                    )
                if packet_kind == "cross-project" and not earth_sweep_evidence_refs:
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].earth_sweep_evidence_refs must be non-empty for cross-project rows"
                    )
                completeness = row.get("recommendation_field_completeness")
                if not isinstance(completeness, Mapping):
                    errors.append(
                        "strategy_packet_context.recommendation_readiness"
                        f"[{index}].recommendation_field_completeness must be an object"
                    )
                else:
                    if completeness.get("required_fields") != expected_required_fields:
                        errors.append(
                            "strategy_packet_context.recommendation_readiness"
                            f"[{index}].recommendation_field_completeness.required_fields must match REQ-052 required fields"
                        )
                    missing_fields = completeness.get("missing_fields")
                    if not isinstance(missing_fields, list):
                        errors.append(
                            "strategy_packet_context.recommendation_readiness"
                            f"[{index}].recommendation_field_completeness.missing_fields must be a list"
                        )
                        missing_fields = []
                    elif missing_fields != sorted(dict.fromkeys(missing_fields), key=missing_fields.index):
                        errors.append(
                            "strategy_packet_context.recommendation_readiness"
                            f"[{index}].recommendation_field_completeness.missing_fields must be unique and ordered"
                        )
                    all_fields_present = completeness.get("all_fields_present")
                    if not isinstance(all_fields_present, bool):
                        errors.append(
                            "strategy_packet_context.recommendation_readiness"
                            f"[{index}].recommendation_field_completeness.all_fields_present must be a boolean"
                        )
                    elif not all_fields_present or missing_fields:
                        errors.append(
                            "strategy_packet_context.recommendation_readiness"
                            f"[{index}].recommendation_field_completeness must report all fields present"
                        )
                normalized_readiness.append(
                    {
                        "recommendation_id": recommendation_id,
                        "strategy_packet_input_id": packet_input_id,
                        "packet_kind": packet_kind,
                        "peer_project_id": peer_project_id,
                        "lane": lane,
                        "evidence_refs": evidence_refs,
                        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
                    }
                )
        usage = strategy_packet_context.get("cross_project_context_usage")
        if not isinstance(usage, Mapping):
            errors.append("strategy_packet_context.cross_project_context_usage must be an object")
        else:
            expected_usage_keys = {
                "cross_project_context_provided",
                "cross_project_context_used",
                "projects_considered",
                "earth_sweep_evidence_refs_considered",
                "cross_project_obligation_count",
                "unresolved_idea_count",
                "recommendation_ids_with_context",
            }
            usage_keys = set(usage.keys())
            missing_usage = sorted(expected_usage_keys - usage_keys)
            if missing_usage:
                errors.append(f"strategy_packet_context.cross_project_context_usage missing keys: {missing_usage}")
            unexpected_usage = sorted(usage_keys - expected_usage_keys)
            if unexpected_usage:
                errors.append(
                    "strategy_packet_context.cross_project_context_usage has unexpected keys: "
                    f"{unexpected_usage}"
                )
            if not isinstance(usage.get("cross_project_context_provided"), bool):
                errors.append(
                    "strategy_packet_context.cross_project_context_usage.cross_project_context_provided must be a boolean"
                )
            if not isinstance(usage.get("cross_project_context_used"), bool):
                errors.append(
                    "strategy_packet_context.cross_project_context_usage.cross_project_context_used must be a boolean"
                )
            for key in ("projects_considered", "earth_sweep_evidence_refs_considered", "recommendation_ids_with_context"):
                values = usage.get(key)
                if not isinstance(values, list):
                    errors.append(f"strategy_packet_context.cross_project_context_usage.{key} must be a list")
                    continue
                if values != sorted(set(values)):
                    errors.append(
                        f"strategy_packet_context.cross_project_context_usage.{key} must be sorted and unique"
                    )
            for key in ("cross_project_obligation_count", "unresolved_idea_count"):
                value = usage.get(key)
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        f"strategy_packet_context.cross_project_context_usage.{key} must be a non-negative integer"
                    )

        open_risks = strategy_packet_context.get("open_risks", [])
        if not isinstance(open_risks, list):
            errors.append("strategy_packet_context.open_risks must be a list")
            open_risks = []
        else:
            normalized_open_risks = []
            for index, row in enumerate(open_risks):
                try:
                    normalized_open_risks.append(
                        _normalize_open_risk(row, field_name=f"strategy_packet_context.open_risks[{index}]")
                    )
                except ValueError as exc:
                    errors.append(str(exc))
            if open_risks != sorted(normalized_open_risks, key=lambda row: row["open_risk_id"]):
                errors.append("strategy_packet_context.open_risks must be sorted by open_risk_id")

    if isinstance(recommendations, list) and isinstance(readiness_rows, list):
        packet_recommendation_ids = [
            row["recommendation_id"] for row in recommendations if isinstance(row, Mapping) and "recommendation_id" in row
        ]
        readiness_recommendation_ids = [
            row["recommendation_id"] for row in readiness_rows if isinstance(row, Mapping) and "recommendation_id" in row
        ]
        if readiness_recommendation_ids and readiness_recommendation_ids != packet_recommendation_ids:
            errors.append(
                "strategy_packet_context.recommendation_readiness must align with strategy_packet_v1.packet.recommendations order"
            )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {"recommendations", "hard_constraints", "soft_constraints", "kpi_targets"}
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        expected_values = {
            "recommendations": len(recommendations),
            "hard_constraints": len(constraints.get("hard", [])) if isinstance(constraints, Mapping) else 0,
            "soft_constraints": len(constraints.get("soft", [])) if isinstance(constraints, Mapping) else 0,
            "kpi_targets": len(kpi_targets),
        }
        for key, expected_value in expected_values.items():
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")
            elif value != expected_value:
                errors.append(f"totals.{key} must match derived strategy_packet_v1 counts")

    return errors


def _normalize_req_053_recommendation_snapshot(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected = {
        "lineage_key",
        "recommendation_id",
        "summary",
        "rationale",
        "packet_kind",
        "peer_project_id",
        "lane",
        "priority",
        "evidence_refs",
    }
    unexpected = sorted(set(row.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")

    packet_kind = _require_nonempty_text(row.get("packet_kind"), field_name=f"{field_name}.packet_kind").lower()
    if packet_kind not in _PACKET_KINDS:
        raise ValueError(f"{field_name}.packet_kind must be one of: {list(_PACKET_KINDS)}")

    peer_project_raw = row.get("peer_project_id")
    if peer_project_raw is None:
        peer_project_id = ""
    elif isinstance(peer_project_raw, str):
        peer_project_id = peer_project_raw.strip()
    else:
        raise ValueError(f"{field_name}.peer_project_id must be a string when provided")
    if packet_kind == "cross-project" and not peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be set for cross-project recommendations")
    if packet_kind == "target-project" and peer_project_id:
        raise ValueError(f"{field_name}.peer_project_id must be empty for target-project recommendations")

    priority = _require_nonempty_text(row.get("priority"), field_name=f"{field_name}.priority").lower()
    if priority not in _PRIORITY_LEVELS:
        raise ValueError(f"{field_name}.priority must be one of: {list(_PRIORITY_LEVELS)}")

    return {
        "lineage_key": _require_canonical_id(row.get("lineage_key"), field_name=f"{field_name}.lineage_key", prefix="lineage"),
        "recommendation_id": _require_canonical_id(
            row.get("recommendation_id"),
            field_name=f"{field_name}.recommendation_id",
            prefix="rec",
        ),
        "summary": _require_nonempty_text(row.get("summary"), field_name=f"{field_name}.summary"),
        "rationale": _require_nonempty_text(row.get("rationale"), field_name=f"{field_name}.rationale"),
        "packet_kind": packet_kind,
        "peer_project_id": peer_project_id,
        "lane": _require_nonempty_text(row.get("lane"), field_name=f"{field_name}.lane"),
        "priority": priority,
        "evidence_refs": _normalize_nonempty_str_list(row.get("evidence_refs"), field_name=f"{field_name}.evidence_refs"),
    }


def _normalize_req_053_recommendation_snapshots(value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[dict[str, Any]] = []
    seen_lineage_keys: set[str] = set()
    seen_recommendation_ids: set[str] = set()
    for index, row in enumerate(value):
        snapshot = _normalize_req_053_recommendation_snapshot(row, field_name=f"{field_name}[{index}]")
        lineage_key = snapshot["lineage_key"]
        recommendation_id = snapshot["recommendation_id"]
        if lineage_key in seen_lineage_keys:
            raise ValueError(f"{field_name}[{index}].lineage_key must be unique")
        if recommendation_id in seen_recommendation_ids:
            raise ValueError(f"{field_name}[{index}].recommendation_id must be unique")
        seen_lineage_keys.add(lineage_key)
        seen_recommendation_ids.add(recommendation_id)
        normalized.append(snapshot)
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty list")
    return sorted(normalized, key=lambda row: row["lineage_key"])


def _normalize_req_053_baseline_revision(value: Any) -> dict[str, Any]:
    revision = _require_mapping(value, field_name="baseline_revision")
    expected = {"revision_id", "recommendations"}
    unexpected = sorted(set(revision.keys()) - expected)
    if unexpected:
        raise ValueError(f"baseline_revision has unexpected keys: {unexpected}")
    missing = sorted(expected - set(revision.keys()))
    if missing:
        raise ValueError(f"baseline_revision missing keys: {missing}")
    return {
        "revision_id": _require_nonempty_text(revision.get("revision_id"), field_name="baseline_revision.revision_id"),
        "recommendations": _normalize_req_053_recommendation_snapshots(
            revision.get("recommendations"),
            field_name="baseline_revision.recommendations",
        ),
    }


def _normalize_req_053_rerun_scenario(value: Any, *, field_name: str) -> dict[str, Any]:
    scenario = _require_mapping(value, field_name=field_name)
    expected = {"scenario_id", "scenario_kind", "description", "recommendations"}
    unexpected = sorted(set(scenario.keys()) - expected)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    missing = sorted(expected - set(scenario.keys()))
    if missing:
        raise ValueError(f"{field_name} missing keys: {missing}")

    scenario_kind = _require_nonempty_text(
        scenario.get("scenario_kind"),
        field_name=f"{field_name}.scenario_kind",
    ).lower()
    if scenario_kind not in _REQ_053_SCENARIO_KINDS:
        raise ValueError(f"{field_name}.scenario_kind must be one of: {list(_REQ_053_SCENARIO_KINDS)}")

    return {
        "scenario_id": _require_canonical_id(scenario.get("scenario_id"), field_name=f"{field_name}.scenario_id", prefix="scenario"),
        "scenario_kind": scenario_kind,
        "description": _require_nonempty_text(scenario.get("description"), field_name=f"{field_name}.description"),
        "recommendations": _normalize_req_053_recommendation_snapshots(
            scenario.get("recommendations"),
            field_name=f"{field_name}.recommendations",
        ),
    }


def _normalize_req_053_rerun_scenarios(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("rerun_scenarios must be a list")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        scenario = _normalize_req_053_rerun_scenario(row, field_name=f"rerun_scenarios[{index}]")
        scenario_id = scenario["scenario_id"]
        if scenario_id in seen_ids:
            raise ValueError(f"rerun_scenarios[{index}].scenario_id must be unique")
        seen_ids.add(scenario_id)
        normalized.append(scenario)
    if not normalized:
        raise ValueError("rerun_scenarios must be a non-empty list")
    return sorted(normalized, key=lambda row: row["scenario_id"])


def _req_053_stability_basis(row: Mapping[str, Any]) -> dict[str, str]:
    return {field: str(row[field]) for field in _REQ_053_STABILITY_FIELDS}


def _req_053_stability_key(row: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(_req_053_stability_basis(row), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    return f"ridkey.{digest}"


def _req_053_changed_fields(baseline_row: Mapping[str, Any], scenario_row: Mapping[str, Any]) -> list[str]:
    changed = [field for field in _REQ_053_STABILITY_FIELDS if baseline_row[field] != scenario_row[field]]
    return changed


def _req_053_earth_sweep_evidence_refs(
    row: Mapping[str, Any],
    *,
    broad_sweep_context: Mapping[str, Any],
) -> list[str]:
    known_context_refs = set(broad_sweep_context.get("earth_sweep_evidence_refs", []))
    earth_refs = {
        ref
        for ref in row.get("evidence_refs", [])
        if isinstance(ref, str) and (ref.startswith("reports/earth/sweeps/") or ref in known_context_refs)
    }
    return sorted(earth_refs)


def _req_053_recommendation_field_completeness(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "required_fields": list(_REQ_053_REQUIRED_RECOMMENDATION_FIELDS),
            "missing_fields": list(_REQ_053_REQUIRED_RECOMMENDATION_FIELDS),
            "all_fields_present": False,
        }

    missing_fields: list[str] = []
    for field in _REQ_053_REQUIRED_RECOMMENDATION_FIELDS:
        value = row.get(field)
        if field == "peer_project_id":
            if row.get("packet_kind") == "cross-project" and (not isinstance(value, str) or not value.strip()):
                missing_fields.append(field)
            continue
        if field == "evidence_refs":
            if not isinstance(value, list) or not value:
                missing_fields.append(field)
            continue
        if not isinstance(value, str) or not value.strip():
            missing_fields.append(field)

    return {
        "required_fields": list(_REQ_053_REQUIRED_RECOMMENDATION_FIELDS),
        "missing_fields": missing_fields,
        "all_fields_present": not missing_fields,
    }


def _req_053_open_risk_id(
    *,
    recommendation_id: str,
    project_id: str,
    reason_code: str,
    summary: str,
) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "project_id": project_id,
                "reason_code": reason_code,
                "recommendation_id": recommendation_id,
                "summary": summary,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"open-risk.{digest}"


def _req_053_project_required_evidence_refs(
    *,
    project_id: str,
    broad_sweep_context: Mapping[str, Any],
) -> list[str]:
    required_refs = {
        ref
        for ref in broad_sweep_context.get("earth_sweep_evidence_refs", [])
        if isinstance(ref, str) and project_id in ref
    }
    for row in broad_sweep_context.get("cross_project_obligations", []):
        if row.get("target_project_id") != project_id:
            continue
        required_refs.update(ref for ref in row.get("earth_sweep_evidence_refs", []) if isinstance(ref, str))
    for row in broad_sweep_context.get("unresolved_ideas", []):
        if row.get("target_project_id") != project_id:
            continue
        required_refs.update(ref for ref in row.get("earth_sweep_evidence_refs", []) if isinstance(ref, str))
    return sorted(required_refs) or ["missing:earth-sweep-evidence-ref"]


def _req_053_context_usage(
    *,
    baseline_rows: list[dict[str, Any]],
    rerun_scenarios: list[dict[str, Any]],
    broad_sweep_context: Mapping[str, Any],
) -> dict[str, Any]:
    all_rows = list(baseline_rows)
    for scenario in rerun_scenarios:
        all_rows.extend(scenario["recommendations"])

    recommendation_ids = {row["recommendation_id"] for row in all_rows}
    projects_considered = set(broad_sweep_context.get("projects_considered", []))
    projects_considered.update(
        row["target_project_id"] for row in broad_sweep_context.get("cross_project_obligations", [])
    )
    projects_considered.update(row["target_project_id"] for row in broad_sweep_context.get("unresolved_ideas", []))
    projects_considered.update(
        row["peer_project_id"] for row in all_rows if row["packet_kind"] == "cross-project" and row["peer_project_id"]
    )

    recommendation_ids_with_context = {
        recommendation_id
        for row in broad_sweep_context.get("cross_project_obligations", [])
        if row.get("earth_sweep_evidence_refs")
        for recommendation_id in row.get("recommendation_ids", [])
        if recommendation_id in recommendation_ids
    }
    recommendation_ids_with_context.update(
        recommendation_id
        for row in broad_sweep_context.get("unresolved_ideas", [])
        for recommendation_id in row.get("recommendation_ids", [])
        if recommendation_id in recommendation_ids
    )

    earth_refs_considered = set(broad_sweep_context.get("earth_sweep_evidence_refs", []))
    for row in broad_sweep_context.get("cross_project_obligations", []):
        earth_refs_considered.update(row.get("earth_sweep_evidence_refs", []))
    for row in broad_sweep_context.get("unresolved_ideas", []):
        earth_refs_considered.update(row.get("earth_sweep_evidence_refs", []))

    provided = any(
        (
            broad_sweep_context.get("earth_sweep_evidence_refs"),
            broad_sweep_context.get("projects_considered"),
            broad_sweep_context.get("cross_project_obligations"),
            broad_sweep_context.get("unresolved_ideas"),
        )
    )
    used = provided or any(row["packet_kind"] == "cross-project" for row in all_rows)

    return {
        "cross_project_context_provided": provided,
        "cross_project_context_used": used,
        "projects_considered": sorted(projects_considered),
        "earth_sweep_evidence_refs_considered": sorted(earth_refs_considered),
        "cross_project_obligation_count": len(broad_sweep_context.get("cross_project_obligations", [])),
        "unresolved_idea_count": len(broad_sweep_context.get("unresolved_ideas", [])),
        "recommendation_ids_with_context": sorted(recommendation_ids_with_context),
    }


def _req_053_open_risks(
    *,
    baseline_rows: list[dict[str, Any]],
    rerun_scenarios: list[dict[str, Any]],
    broad_sweep_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    open_risks: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for row in broad_sweep_context.get("unresolved_ideas", []):
        key = (row["idea_id"], row["target_project_id"], "unresolved_idea_open_risk")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        open_risks.append(
            {
                "open_risk_id": _req_053_open_risk_id(
                    recommendation_id=row["idea_id"],
                    project_id=row["target_project_id"],
                    reason_code="unresolved_idea_open_risk",
                    summary=row["summary"],
                ),
                "recommendation_id": row["idea_id"],
                "summary": row["summary"],
                "reason_code": "unresolved_idea_open_risk",
                "project_id": row["target_project_id"],
                "required_evidence_refs": _req_053_project_required_evidence_refs(
                    project_id=row["target_project_id"],
                    broad_sweep_context=broad_sweep_context,
                ),
                "evidence_refs": list(row["earth_sweep_evidence_refs"]),
                "linked_recommendation_ids": list(row["recommendation_ids"]),
                "call_trace_lineage": [],
                "contributing_call_ids": [],
            }
        )

    all_rows = list(baseline_rows)
    for scenario in rerun_scenarios:
        all_rows.extend(scenario["recommendations"])

    for row in all_rows:
        if row["packet_kind"] != "cross-project":
            continue
        if _req_053_earth_sweep_evidence_refs(row, broad_sweep_context=broad_sweep_context):
            continue
        key = (row["recommendation_id"], row["peer_project_id"], "missing_earth_sweep_evidence_refs")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        summary = (
            f"Attach Earth-sweep evidence refs before treating {row['recommendation_id']} as a cross-project obligation."
        )
        open_risks.append(
            {
                "open_risk_id": _req_053_open_risk_id(
                    recommendation_id=row["recommendation_id"],
                    project_id=row["peer_project_id"],
                    reason_code="missing_earth_sweep_evidence_refs",
                    summary=summary,
                ),
                "recommendation_id": row["recommendation_id"],
                "summary": summary,
                "reason_code": "missing_earth_sweep_evidence_refs",
                "project_id": row["peer_project_id"],
                "required_evidence_refs": _req_053_project_required_evidence_refs(
                    project_id=row["peer_project_id"],
                    broad_sweep_context=broad_sweep_context,
                ),
                "evidence_refs": list(row["evidence_refs"]),
                "linked_recommendation_ids": [row["recommendation_id"]],
                "call_trace_lineage": [],
                "contributing_call_ids": [],
            }
        )

    open_risks.sort(key=lambda row: row["open_risk_id"])
    return open_risks


def _req_053_baseline_surface(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _req_053_baseline_surface_with_context(rows, broad_sweep_context={"earth_sweep_evidence_refs": []})


def _req_053_baseline_surface_with_context(
    rows: list[dict[str, Any]],
    *,
    broad_sweep_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    baseline_surface = []
    for row in rows:
        baseline_surface.append(
            {
                "lineage_key": row["lineage_key"],
                "recommendation_id": row["recommendation_id"],
                "stability_key": _req_053_stability_key(row),
                "stability_basis": _req_053_stability_basis(row),
                "evidence_refs": list(row["evidence_refs"]),
                "earth_sweep_evidence_refs": _req_053_earth_sweep_evidence_refs(
                    row,
                    broad_sweep_context=broad_sweep_context,
                ),
                "recommendation_field_completeness": _req_053_recommendation_field_completeness(row),
            }
        )
    return baseline_surface


def _build_req_053_scenario_result(
    baseline_rows: list[dict[str, Any]],
    scenario: dict[str, Any],
    *,
    broad_sweep_context: Mapping[str, Any],
) -> dict[str, Any]:
    baseline_by_lineage = {row["lineage_key"]: row for row in baseline_rows}
    scenario_by_lineage = {row["lineage_key"]: row for row in scenario["recommendations"]}

    stable_recommendation_ids: list[str] = []
    evolved_recommendation_ids: list[str] = []
    added_recommendation_ids: list[str] = []
    removed_recommendation_ids: list[str] = []
    recommendation_results: list[dict[str, Any]] = []

    for lineage_key in sorted(set(baseline_by_lineage) | set(scenario_by_lineage)):
        baseline_row = baseline_by_lineage.get(lineage_key)
        scenario_row = scenario_by_lineage.get(lineage_key)
        if baseline_row and scenario_row:
            baseline_key = _req_053_stability_key(baseline_row)
            scenario_key = _req_053_stability_key(scenario_row)
            changed_fields = _req_053_changed_fields(baseline_row, scenario_row)
            if baseline_key == scenario_key:
                if baseline_row["recommendation_id"] != scenario_row["recommendation_id"]:
                    raise ValueError(
                        f"{scenario['scenario_id']} reused stability basis for {lineage_key} but changed recommendation_id"
                    )
                result_status = "stable"
                stable_recommendation_ids.append(scenario_row["recommendation_id"])
            else:
                if scenario["scenario_kind"] == "no-change":
                    raise ValueError(
                        f"{scenario['scenario_id']} must preserve recommendation_id stability for {lineage_key}"
                    )
                if baseline_row["recommendation_id"] == scenario_row["recommendation_id"]:
                    raise ValueError(
                        f"{scenario['scenario_id']} changed substantive recommendation basis for {lineage_key} without changing recommendation_id"
                    )
                result_status = "evolved"
                evolved_recommendation_ids.append(scenario_row["recommendation_id"])

            recommendation_results.append(
                {
                    "lineage_key": lineage_key,
                    "baseline_recommendation_id": baseline_row["recommendation_id"],
                    "scenario_recommendation_id": scenario_row["recommendation_id"],
                    "baseline_stability_key": baseline_key,
                    "scenario_stability_key": scenario_key,
                    "id_status": result_status,
                    "changed_fields": changed_fields,
                    "baseline_evidence_refs": list(baseline_row["evidence_refs"]),
                    "scenario_evidence_refs": list(scenario_row["evidence_refs"]),
                    "baseline_earth_sweep_evidence_refs": _req_053_earth_sweep_evidence_refs(
                        baseline_row,
                        broad_sweep_context=broad_sweep_context,
                    ),
                    "scenario_earth_sweep_evidence_refs": _req_053_earth_sweep_evidence_refs(
                        scenario_row,
                        broad_sweep_context=broad_sweep_context,
                    ),
                    "baseline_recommendation_field_completeness": _req_053_recommendation_field_completeness(
                        baseline_row
                    ),
                    "scenario_recommendation_field_completeness": _req_053_recommendation_field_completeness(
                        scenario_row
                    ),
                }
            )
            continue

        if scenario["scenario_kind"] == "no-change":
            raise ValueError(f"{scenario['scenario_id']} must preserve the baseline lineage set exactly")

        if scenario_row:
            scenario_key = _req_053_stability_key(scenario_row)
            added_recommendation_ids.append(scenario_row["recommendation_id"])
            recommendation_results.append(
                {
                    "lineage_key": lineage_key,
                    "baseline_recommendation_id": "",
                    "scenario_recommendation_id": scenario_row["recommendation_id"],
                    "baseline_stability_key": "",
                    "scenario_stability_key": scenario_key,
                    "id_status": "added",
                    "changed_fields": [],
                    "baseline_evidence_refs": [],
                    "scenario_evidence_refs": list(scenario_row["evidence_refs"]),
                    "baseline_earth_sweep_evidence_refs": [],
                    "scenario_earth_sweep_evidence_refs": _req_053_earth_sweep_evidence_refs(
                        scenario_row,
                        broad_sweep_context=broad_sweep_context,
                    ),
                    "baseline_recommendation_field_completeness": _req_053_recommendation_field_completeness(None),
                    "scenario_recommendation_field_completeness": _req_053_recommendation_field_completeness(
                        scenario_row
                    ),
                }
            )
            continue

        assert baseline_row is not None
        baseline_key = _req_053_stability_key(baseline_row)
        removed_recommendation_ids.append(baseline_row["recommendation_id"])
        recommendation_results.append(
            {
                "lineage_key": lineage_key,
                "baseline_recommendation_id": baseline_row["recommendation_id"],
                "scenario_recommendation_id": "",
                "baseline_stability_key": baseline_key,
                "scenario_stability_key": "",
                "id_status": "removed",
                "changed_fields": [],
                "baseline_evidence_refs": list(baseline_row["evidence_refs"]),
                "scenario_evidence_refs": [],
                "baseline_earth_sweep_evidence_refs": _req_053_earth_sweep_evidence_refs(
                    baseline_row,
                    broad_sweep_context=broad_sweep_context,
                ),
                "scenario_earth_sweep_evidence_refs": [],
                "baseline_recommendation_field_completeness": _req_053_recommendation_field_completeness(
                    baseline_row
                ),
                "scenario_recommendation_field_completeness": _req_053_recommendation_field_completeness(None),
            }
        )

    return {
        "scenario_id": scenario["scenario_id"],
        "scenario_kind": scenario["scenario_kind"],
        "description": scenario["description"],
        "recommendation_results": recommendation_results,
        "stable_recommendation_ids": sorted(stable_recommendation_ids),
        "evolved_recommendation_ids": sorted(evolved_recommendation_ids),
        "added_recommendation_ids": sorted(added_recommendation_ids),
        "removed_recommendation_ids": sorted(removed_recommendation_ids),
    }


def build_req_053_recommendation_id_stability_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build the REQ-053 recommendation id stability contract payload."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_053_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_053_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    broad_sweep_context = _normalize_req_053_broad_sweep_context(raw.get("broad_sweep_context"))
    baseline_revision = _normalize_req_053_baseline_revision(raw.get("baseline_revision"))
    rerun_scenarios = _normalize_req_053_rerun_scenarios(raw.get("rerun_scenarios"))

    baseline_recommendations = _req_053_baseline_surface_with_context(
        baseline_revision["recommendations"],
        broad_sweep_context=broad_sweep_context,
    )
    scenario_results = [
        _build_req_053_scenario_result(
            baseline_revision["recommendations"],
            scenario,
            broad_sweep_context=broad_sweep_context,
        )
        for scenario in rerun_scenarios
    ]
    cross_project_context_usage = _req_053_context_usage(
        baseline_rows=baseline_revision["recommendations"],
        rerun_scenarios=rerun_scenarios,
        broad_sweep_context=broad_sweep_context,
    )
    open_risks = _req_053_open_risks(
        baseline_rows=baseline_revision["recommendations"],
        rerun_scenarios=rerun_scenarios,
        broad_sweep_context=broad_sweep_context,
    )

    output_payload = {
        "ok": True,
        "schema_version": REQ_053_SCHEMA_VERSION,
        "requirement_id": REQ_053_REQUIREMENT_ID,
        "analysis_type": REQ_053_ANALYSIS_TYPE,
        "call_id": REQ_053_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "recommendation_id_stability": {
            "baseline_revision_id": baseline_revision["revision_id"],
            "stability_basis_fields": list(_REQ_053_STABILITY_FIELDS),
            "baseline_recommendations": baseline_recommendations,
            "scenario_results": scenario_results,
            "cross_project_context_usage": cross_project_context_usage,
            "open_risks": open_risks,
        },
        "totals": {
            "baseline_recommendations": len(baseline_recommendations),
            "scenario_count": len(scenario_results),
            "stable_results": sum(len(row["stable_recommendation_ids"]) for row in scenario_results),
            "evolved_results": sum(len(row["evolved_recommendation_ids"]) for row in scenario_results),
            "added_results": sum(len(row["added_recommendation_ids"]) for row in scenario_results),
            "removed_results": sum(len(row["removed_recommendation_ids"]) for row in scenario_results),
            "open_risk_count": len(open_risks),
        },
    }

    errors = validate_req_053_recommendation_id_stability_contract(output_payload)
    if errors:
        raise ValueError(f"built REQ-053 payload failed validation: {errors}")
    return output_payload


def _req_053_collect_unique_refs(*ref_groups: list[Any]) -> list[str]:
    refs: set[str] = set()
    for group in ref_groups:
        for ref in group:
            if isinstance(ref, str) and ref.strip():
                refs.add(ref.strip())
    return sorted(refs)


def build_req_053_planner_recommendation_mapping_set(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic planner-facing recommendation mapping surface from a validated REQ-053 payload."""
    errors = validate_req_053_recommendation_id_stability_contract(payload)
    if errors:
        raise ValueError(f"REQ-053 planner recommendation mapping set requires a valid contract payload: {errors}")

    stability = _require_mapping(payload.get("recommendation_id_stability"), field_name="recommendation_id_stability")
    baseline_rows = stability.get("baseline_recommendations", [])
    scenario_results = stability.get("scenario_results", [])

    recommendation_mappings: list[dict[str, Any]] = []
    recommendation_id_inventory: set[str] = set()
    lineage_inventory: set[str] = set()
    scenario_ids = ["baseline"]

    for row in baseline_rows:
        if not isinstance(row, Mapping):
            continue
        recommendation_mappings.append(
            {
                "scenario_id": "baseline",
                "scenario_kind": "baseline",
                "lineage_key": row["lineage_key"],
                "baseline_recommendation_id": row["recommendation_id"],
                "scenario_recommendation_id": row["recommendation_id"],
                "baseline_stability_key": row["stability_key"],
                "scenario_stability_key": row["stability_key"],
                "id_status": "stable",
                "changed_fields": [],
                "baseline_evidence_refs": list(row["evidence_refs"]),
                "scenario_evidence_refs": list(row["evidence_refs"]),
            }
        )
        recommendation_id_inventory.add(str(row["recommendation_id"]))
        lineage_inventory.add(str(row["lineage_key"]))

    for scenario in scenario_results:
        if not isinstance(scenario, Mapping):
            continue
        scenario_id = str(scenario["scenario_id"])
        scenario_ids.append(scenario_id)
        for row in scenario.get("recommendation_results", []):
            if not isinstance(row, Mapping):
                continue
            recommendation_mappings.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_kind": str(scenario["scenario_kind"]),
                    "lineage_key": row["lineage_key"],
                    "baseline_recommendation_id": row["baseline_recommendation_id"],
                    "scenario_recommendation_id": row["scenario_recommendation_id"],
                    "baseline_stability_key": row["baseline_stability_key"],
                    "scenario_stability_key": row["scenario_stability_key"],
                    "id_status": row["id_status"],
                    "changed_fields": list(row["changed_fields"]),
                    "baseline_evidence_refs": list(row["baseline_evidence_refs"]),
                    "scenario_evidence_refs": list(row["scenario_evidence_refs"]),
                }
            )
            lineage_inventory.add(str(row["lineage_key"]))
            for recommendation_id in (row["baseline_recommendation_id"], row["scenario_recommendation_id"]):
                if isinstance(recommendation_id, str) and recommendation_id:
                    recommendation_id_inventory.add(recommendation_id)

    recommendation_mappings.sort(key=lambda row: (row["scenario_id"], row["lineage_key"]))
    return {
        "requirement_id": str(payload["requirement_id"]),
        "baseline_revision_id": str(stability["baseline_revision_id"]),
        "scenario_ids": scenario_ids,
        "recommendation_id_inventory": sorted(recommendation_id_inventory),
        "lineage_inventory": sorted(lineage_inventory),
        "mapping_row_count": len(recommendation_mappings),
        "recommendation_mappings": recommendation_mappings,
    }


def build_req_053_acceptance_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic acceptance packet for replay diagnostics from a validated REQ-053 payload."""
    errors = validate_req_053_recommendation_id_stability_contract(payload)
    if errors:
        raise ValueError(f"REQ-053 acceptance packet requires a valid contract payload: {errors}")

    stability = _require_mapping(payload.get("recommendation_id_stability"), field_name="recommendation_id_stability")
    open_risks = stability.get("open_risks", [])
    mapping_set = build_req_053_planner_recommendation_mapping_set(payload)

    required_evidence_refs = _req_053_collect_unique_refs(
        *[
            list(row.get("required_evidence_refs", []))
            for row in open_risks
            if isinstance(row, Mapping)
        ]
    )
    evidence_refs = _req_053_collect_unique_refs(
        *[list(row.get("evidence_refs", [])) for row in stability.get("baseline_recommendations", []) if isinstance(row, Mapping)],
        *[
            list(result.get("baseline_evidence_refs", []))
            for scenario in stability.get("scenario_results", [])
            if isinstance(scenario, Mapping)
            for result in scenario.get("recommendation_results", [])
            if isinstance(result, Mapping)
        ],
        *[
            list(result.get("scenario_evidence_refs", []))
            for scenario in stability.get("scenario_results", [])
            if isinstance(scenario, Mapping)
            for result in scenario.get("recommendation_results", [])
            if isinstance(result, Mapping)
        ],
        *[list(row.get("evidence_refs", [])) for row in open_risks if isinstance(row, Mapping)],
        required_evidence_refs,
    )

    open_risk_ids = [
        str(row["open_risk_id"])
        for row in open_risks
        if isinstance(row, Mapping) and isinstance(row.get("open_risk_id"), str) and str(row["open_risk_id"]).strip()
    ]
    open_risk_reason_codes = sorted(
        {
            str(row["reason_code"])
            for row in open_risks
            if isinstance(row, Mapping) and isinstance(row.get("reason_code"), str) and str(row["reason_code"]).strip()
        }
    )

    return {
        "requirement_id": str(payload["requirement_id"]),
        "baseline_revision_id": str(stability["baseline_revision_id"]),
        "decision": "acceptance-with-open-risks" if open_risk_ids else "acceptance-ready",
        "mapping_row_count": mapping_set["mapping_row_count"],
        "scenario_ids": list(mapping_set["scenario_ids"]),
        "recommendation_id_inventory": list(mapping_set["recommendation_id_inventory"]),
        "required_evidence_refs": required_evidence_refs,
        "evidence_refs": evidence_refs,
        "open_risk_ids": sorted(open_risk_ids),
        "open_risk_reason_codes": open_risk_reason_codes,
    }


def validate_req_053_recommendation_id_stability_contract(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-053 recommendation id stability contract payload shape."""
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
        "recommendation_id_stability",
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
    if payload.get("schema_version") != REQ_053_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_053_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_053_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_053_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_053_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_053_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_053_CALL_ID:
        errors.append(f"call_id must be {REQ_053_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
    else:
        expected_target = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        if not isinstance(target_project.get("project_id"), str) or not str(target_project.get("project_id")).strip():
            errors.append("target_project.project_id must be a non-empty string")
        project_root = target_project.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not project_root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    stability = payload.get("recommendation_id_stability")
    baseline_recommendations: list[Any] = []
    scenario_results: list[Any] = []
    open_risks: list[Any] = []
    if not isinstance(stability, Mapping):
        errors.append("recommendation_id_stability must be an object")
    else:
        expected_stability_keys = {
            "baseline_revision_id",
            "stability_basis_fields",
            "baseline_recommendations",
            "scenario_results",
            "cross_project_context_usage",
            "open_risks",
        }
        stability_keys = set(stability.keys())
        missing_stability = sorted(expected_stability_keys - stability_keys)
        if missing_stability:
            errors.append(f"recommendation_id_stability missing keys: {missing_stability}")
        unexpected_stability = sorted(stability_keys - expected_stability_keys)
        if unexpected_stability:
            errors.append(f"recommendation_id_stability has unexpected keys: {unexpected_stability}")

        baseline_revision_id = stability.get("baseline_revision_id")
        if not isinstance(baseline_revision_id, str) or not baseline_revision_id.strip():
            errors.append("recommendation_id_stability.baseline_revision_id must be a non-empty string")

        stability_basis_fields = stability.get("stability_basis_fields")
        if stability_basis_fields != list(_REQ_053_STABILITY_FIELDS):
            errors.append("recommendation_id_stability.stability_basis_fields must match the documented REQ-053 basis")

        baseline_recommendations = stability.get("baseline_recommendations", [])
        if not isinstance(baseline_recommendations, list) or not baseline_recommendations:
            errors.append("recommendation_id_stability.baseline_recommendations must be a non-empty list")
            baseline_recommendations = []
        else:
            seen_lineage_keys: set[str] = set()
            seen_recommendation_ids: set[str] = set()
            last_lineage_key = ""
            for index, row in enumerate(baseline_recommendations):
                if not isinstance(row, Mapping):
                    errors.append(f"recommendation_id_stability.baseline_recommendations[{index}] must be an object")
                    continue
                expected_row_keys = {
                    "lineage_key",
                    "recommendation_id",
                    "stability_key",
                    "stability_basis",
                    "evidence_refs",
                    "earth_sweep_evidence_refs",
                    "recommendation_field_completeness",
                }
                row_keys = set(row.keys())
                missing_row = sorted(expected_row_keys - row_keys)
                if missing_row:
                    errors.append(
                        "recommendation_id_stability.baseline_recommendations"
                        f"[{index}] missing keys: {missing_row}"
                    )
                unexpected_row = sorted(row_keys - expected_row_keys)
                if unexpected_row:
                    errors.append(
                        "recommendation_id_stability.baseline_recommendations"
                        f"[{index}] has unexpected keys: {unexpected_row}"
                    )

                lineage_key = row.get("lineage_key")
                recommendation_id = row.get("recommendation_id")
                stability_key = row.get("stability_key")
                try:
                    normalized_lineage = _require_canonical_id(
                        lineage_key,
                        field_name=f"recommendation_id_stability.baseline_recommendations[{index}].lineage_key",
                        prefix="lineage",
                    )
                except ValueError as exc:
                    errors.append(str(exc))
                    normalized_lineage = ""
                try:
                    normalized_recommendation_id = _require_canonical_id(
                        recommendation_id,
                        field_name=f"recommendation_id_stability.baseline_recommendations[{index}].recommendation_id",
                        prefix="rec",
                    )
                except ValueError as exc:
                    errors.append(str(exc))
                    normalized_recommendation_id = ""
                try:
                    _require_canonical_id(
                        stability_key,
                        field_name=f"recommendation_id_stability.baseline_recommendations[{index}].stability_key",
                        prefix="ridkey",
                    )
                except ValueError as exc:
                    errors.append(str(exc))

                if normalized_lineage:
                    if normalized_lineage in seen_lineage_keys:
                        errors.append(
                            "recommendation_id_stability.baseline_recommendations"
                            f"[{index}].lineage_key must be unique"
                        )
                    seen_lineage_keys.add(normalized_lineage)
                    if last_lineage_key and normalized_lineage < last_lineage_key:
                        errors.append("recommendation_id_stability.baseline_recommendations must be sorted by lineage_key")
                    last_lineage_key = normalized_lineage

                if normalized_recommendation_id:
                    if normalized_recommendation_id in seen_recommendation_ids:
                        errors.append(
                            "recommendation_id_stability.baseline_recommendations"
                            f"[{index}].recommendation_id must be unique"
                        )
                    seen_recommendation_ids.add(normalized_recommendation_id)

                stability_basis = row.get("stability_basis")
                if not isinstance(stability_basis, Mapping):
                    errors.append(
                        f"recommendation_id_stability.baseline_recommendations[{index}].stability_basis must be an object"
                    )
                    continue
                if set(stability_basis.keys()) != set(_REQ_053_STABILITY_FIELDS):
                    errors.append(
                        "recommendation_id_stability.baseline_recommendations"
                        f"[{index}].stability_basis must include only {list(_REQ_053_STABILITY_FIELDS)}"
                    )
                for field in _REQ_053_STABILITY_FIELDS:
                    value = stability_basis.get(field)
                    if not isinstance(value, str):
                        errors.append(
                            "recommendation_id_stability.baseline_recommendations"
                            f"[{index}].stability_basis.{field} must be a non-empty string"
                        )
                    elif field != "peer_project_id" and not value.strip():
                        errors.append(
                            "recommendation_id_stability.baseline_recommendations"
                            f"[{index}].stability_basis.{field} must be a non-empty string"
                        )

                evidence_refs = row.get("evidence_refs")
                if not isinstance(evidence_refs, list) or not evidence_refs:
                    errors.append(
                        f"recommendation_id_stability.baseline_recommendations[{index}].evidence_refs must be a non-empty list"
                    )
                elif evidence_refs != sorted(set(evidence_refs)):
                    errors.append(
                        f"recommendation_id_stability.baseline_recommendations[{index}].evidence_refs must be sorted and unique"
                    )

                earth_sweep_refs = row.get("earth_sweep_evidence_refs")
                if not isinstance(earth_sweep_refs, list):
                    errors.append(
                        "recommendation_id_stability.baseline_recommendations"
                        f"[{index}].earth_sweep_evidence_refs must be a list"
                    )
                elif earth_sweep_refs != sorted(set(earth_sweep_refs)):
                    errors.append(
                        "recommendation_id_stability.baseline_recommendations"
                        f"[{index}].earth_sweep_evidence_refs must be sorted and unique"
                    )

                completeness = row.get("recommendation_field_completeness")
                if not isinstance(completeness, Mapping):
                    errors.append(
                        "recommendation_id_stability.baseline_recommendations"
                        f"[{index}].recommendation_field_completeness must be an object"
                    )
                else:
                    if completeness.get("required_fields") != list(_REQ_053_REQUIRED_RECOMMENDATION_FIELDS):
                        errors.append(
                            "recommendation_id_stability.baseline_recommendations"
                            f"[{index}].recommendation_field_completeness.required_fields must match the REQ-053 recommendation fields"
                        )
                    missing_fields = completeness.get("missing_fields")
                    if not isinstance(missing_fields, list):
                        errors.append(
                            "recommendation_id_stability.baseline_recommendations"
                            f"[{index}].recommendation_field_completeness.missing_fields must be a list"
                        )
                    elif [
                        field for field in _REQ_053_REQUIRED_RECOMMENDATION_FIELDS if field in set(missing_fields)
                    ] != missing_fields:
                        errors.append(
                            "recommendation_id_stability.baseline_recommendations"
                            f"[{index}].recommendation_field_completeness.missing_fields must be unique and ordered"
                        )
                    all_fields_present = completeness.get("all_fields_present")
                    if not isinstance(all_fields_present, bool):
                        errors.append(
                            "recommendation_id_stability.baseline_recommendations"
                            f"[{index}].recommendation_field_completeness.all_fields_present must be a boolean"
                        )
                    elif all_fields_present is not True:
                        errors.append(
                            "recommendation_id_stability.baseline_recommendations"
                            f"[{index}].recommendation_field_completeness.all_fields_present must be true"
                        )

        scenario_results = stability.get("scenario_results", [])
        if not isinstance(scenario_results, list) or not scenario_results:
            errors.append("recommendation_id_stability.scenario_results must be a non-empty list")
            scenario_results = []
        else:
            seen_scenario_ids: set[str] = set()
            last_scenario_id = ""
            for index, row in enumerate(scenario_results):
                if not isinstance(row, Mapping):
                    errors.append(f"recommendation_id_stability.scenario_results[{index}] must be an object")
                    continue
                expected_row_keys = {
                    "scenario_id",
                    "scenario_kind",
                    "description",
                    "recommendation_results",
                    "stable_recommendation_ids",
                    "evolved_recommendation_ids",
                    "added_recommendation_ids",
                    "removed_recommendation_ids",
                }
                row_keys = set(row.keys())
                missing_row = sorted(expected_row_keys - row_keys)
                if missing_row:
                    errors.append(f"recommendation_id_stability.scenario_results[{index}] missing keys: {missing_row}")
                unexpected_row = sorted(row_keys - expected_row_keys)
                if unexpected_row:
                    errors.append(
                        f"recommendation_id_stability.scenario_results[{index}] has unexpected keys: {unexpected_row}"
                    )

                scenario_id = row.get("scenario_id")
                scenario_kind = row.get("scenario_kind")
                try:
                    normalized_scenario_id = _require_canonical_id(
                        scenario_id,
                        field_name=f"recommendation_id_stability.scenario_results[{index}].scenario_id",
                        prefix="scenario",
                    )
                except ValueError as exc:
                    errors.append(str(exc))
                    normalized_scenario_id = ""
                if normalized_scenario_id:
                    if normalized_scenario_id in seen_scenario_ids:
                        errors.append(
                            f"recommendation_id_stability.scenario_results[{index}].scenario_id must be unique"
                        )
                    seen_scenario_ids.add(normalized_scenario_id)
                    if last_scenario_id and normalized_scenario_id < last_scenario_id:
                        errors.append("recommendation_id_stability.scenario_results must be sorted by scenario_id")
                    last_scenario_id = normalized_scenario_id
                if scenario_kind not in _REQ_053_SCENARIO_KINDS:
                    errors.append(
                        "recommendation_id_stability.scenario_results"
                        f"[{index}].scenario_kind must be one of {', '.join(_REQ_053_SCENARIO_KINDS)}"
                    )
                if not isinstance(row.get("description"), str) or not str(row.get("description")).strip():
                    errors.append(
                        f"recommendation_id_stability.scenario_results[{index}].description must be a non-empty string"
                    )

                for list_key in (
                    "stable_recommendation_ids",
                    "evolved_recommendation_ids",
                    "added_recommendation_ids",
                    "removed_recommendation_ids",
                ):
                    ids = row.get(list_key)
                    if not isinstance(ids, list):
                        errors.append(
                            f"recommendation_id_stability.scenario_results[{index}].{list_key} must be a list"
                        )
                        continue
                    if ids != sorted(ids):
                        errors.append(
                            f"recommendation_id_stability.scenario_results[{index}].{list_key} must be sorted"
                        )
                    seen_ids: set[str] = set()
                    for id_index, recommendation_id in enumerate(ids):
                        try:
                            normalized_recommendation_id = _require_canonical_id(
                                recommendation_id,
                                field_name=(
                                    "recommendation_id_stability.scenario_results"
                                    f"[{index}].{list_key}[{id_index}]"
                                ),
                                prefix="rec",
                            )
                        except ValueError as exc:
                            errors.append(str(exc))
                            continue
                        if normalized_recommendation_id in seen_ids:
                            errors.append(
                                f"recommendation_id_stability.scenario_results[{index}].{list_key} must be unique"
                            )
                            break
                        seen_ids.add(normalized_recommendation_id)

                recommendation_results = row.get("recommendation_results")
                if not isinstance(recommendation_results, list) or not recommendation_results:
                    errors.append(
                        f"recommendation_id_stability.scenario_results[{index}].recommendation_results must be a non-empty list"
                    )
                    continue

                derived_ids = {status: [] for status in _REQ_053_RESULT_STATUSES}
                last_lineage_key = ""
                for result_index, result in enumerate(recommendation_results):
                    if not isinstance(result, Mapping):
                        errors.append(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}] must be an object"
                        )
                        continue
                    expected_result_keys = {
                        "lineage_key",
                        "baseline_recommendation_id",
                        "scenario_recommendation_id",
                        "baseline_stability_key",
                        "scenario_stability_key",
                        "id_status",
                        "changed_fields",
                        "baseline_evidence_refs",
                        "scenario_evidence_refs",
                        "baseline_earth_sweep_evidence_refs",
                        "scenario_earth_sweep_evidence_refs",
                        "baseline_recommendation_field_completeness",
                        "scenario_recommendation_field_completeness",
                    }
                    result_keys = set(result.keys())
                    missing_result = sorted(expected_result_keys - result_keys)
                    if missing_result:
                        errors.append(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}] missing keys: {missing_result}"
                        )
                    unexpected_result = sorted(result_keys - expected_result_keys)
                    if unexpected_result:
                        errors.append(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}] has unexpected keys: {unexpected_result}"
                        )

                    try:
                        normalized_lineage = _require_canonical_id(
                            result.get("lineage_key"),
                            field_name=(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}].lineage_key"
                            ),
                            prefix="lineage",
                        )
                    except ValueError as exc:
                        errors.append(str(exc))
                        normalized_lineage = ""
                    if normalized_lineage:
                        if last_lineage_key and normalized_lineage < last_lineage_key:
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results must be sorted by lineage_key"
                            )
                        last_lineage_key = normalized_lineage

                    id_status = result.get("id_status")
                    if id_status not in _REQ_053_RESULT_STATUSES:
                        errors.append(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}].id_status must be one of "
                            f"{', '.join(_REQ_053_RESULT_STATUSES)}"
                        )
                        continue

                    changed_fields = result.get("changed_fields")
                    if not isinstance(changed_fields, list):
                        errors.append(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}].changed_fields must be a list"
                        )
                        changed_fields = []
                    elif changed_fields != [field for field in _REQ_053_STABILITY_FIELDS if field in changed_fields]:
                        errors.append(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}].changed_fields must follow REQ-053 basis order"
                        )

                    baseline_recommendation_id = result.get("baseline_recommendation_id")
                    scenario_recommendation_id = result.get("scenario_recommendation_id")
                    baseline_stability_key = result.get("baseline_stability_key")
                    scenario_stability_key = result.get("scenario_stability_key")

                    for list_key in (
                        "baseline_evidence_refs",
                        "scenario_evidence_refs",
                        "baseline_earth_sweep_evidence_refs",
                        "scenario_earth_sweep_evidence_refs",
                    ):
                        refs = result.get(list_key)
                        if not isinstance(refs, list):
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}].{list_key} must be a list"
                            )
                        elif refs != sorted(set(refs)):
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}].{list_key} must be sorted and unique"
                            )

                    for completeness_key in (
                        "baseline_recommendation_field_completeness",
                        "scenario_recommendation_field_completeness",
                    ):
                        completeness = result.get(completeness_key)
                        if not isinstance(completeness, Mapping):
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}].{completeness_key} must be an object"
                            )
                            continue
                        if completeness.get("required_fields") != list(_REQ_053_REQUIRED_RECOMMENDATION_FIELDS):
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}].{completeness_key}.required_fields must match the REQ-053 recommendation fields"
                            )
                        if not isinstance(completeness.get("missing_fields"), list):
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}].{completeness_key}.missing_fields must be a list"
                            )
                        if not isinstance(completeness.get("all_fields_present"), bool):
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}].{completeness_key}.all_fields_present must be a boolean"
                            )

                    def _validate_optional_canonical(value: Any, *, field_name: str, prefix: str) -> bool:
                        if value == "":
                            return True
                        try:
                            _require_canonical_id(value, field_name=field_name, prefix=prefix)
                        except ValueError as exc:
                            errors.append(str(exc))
                            return False
                        return True

                    _validate_optional_canonical(
                        baseline_recommendation_id,
                        field_name=(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}].baseline_recommendation_id"
                        ),
                        prefix="rec",
                    )
                    _validate_optional_canonical(
                        scenario_recommendation_id,
                        field_name=(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}].scenario_recommendation_id"
                        ),
                        prefix="rec",
                    )
                    _validate_optional_canonical(
                        baseline_stability_key,
                        field_name=(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}].baseline_stability_key"
                        ),
                        prefix="ridkey",
                    )
                    _validate_optional_canonical(
                        scenario_stability_key,
                        field_name=(
                            "recommendation_id_stability.scenario_results"
                            f"[{index}].recommendation_results[{result_index}].scenario_stability_key"
                        ),
                        prefix="ridkey",
                    )

                    if id_status == "stable":
                        if changed_fields:
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}].changed_fields must be empty for stable rows"
                            )
                        if baseline_recommendation_id != scenario_recommendation_id:
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}] stable rows must preserve recommendation_id"
                            )
                        if baseline_stability_key != scenario_stability_key:
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}] stable rows must preserve stability_key"
                            )
                        if result.get("baseline_evidence_refs") != result.get("scenario_evidence_refs"):
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}] stable rows must preserve evidence_refs"
                            )
                        if isinstance(scenario_recommendation_id, str) and scenario_recommendation_id:
                            derived_ids["stable"].append(scenario_recommendation_id)
                    elif id_status == "evolved":
                        if not changed_fields:
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}].changed_fields must be non-empty for evolved rows"
                            )
                        if baseline_recommendation_id == scenario_recommendation_id:
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}] evolved rows must change recommendation_id"
                            )
                        if baseline_stability_key == scenario_stability_key:
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}] evolved rows must change stability_key"
                            )
                        if isinstance(scenario_recommendation_id, str) and scenario_recommendation_id:
                            derived_ids["evolved"].append(scenario_recommendation_id)
                    elif id_status == "added":
                        if baseline_recommendation_id != "" or baseline_stability_key != "":
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}] added rows must omit baseline ids and keys"
                            )
                        if result.get("baseline_evidence_refs") != []:
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}] added rows must omit baseline evidence refs"
                            )
                        if isinstance(scenario_recommendation_id, str) and scenario_recommendation_id:
                            derived_ids["added"].append(scenario_recommendation_id)
                    elif id_status == "removed":
                        if scenario_recommendation_id != "" or scenario_stability_key != "":
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}] removed rows must omit scenario ids and keys"
                            )
                        if result.get("scenario_evidence_refs") != []:
                            errors.append(
                                "recommendation_id_stability.scenario_results"
                                f"[{index}].recommendation_results[{result_index}] removed rows must omit scenario evidence refs"
                            )
                        if isinstance(baseline_recommendation_id, str) and baseline_recommendation_id:
                            derived_ids["removed"].append(baseline_recommendation_id)

                expected_lists = {
                    "stable_recommendation_ids": sorted(derived_ids["stable"]),
                    "evolved_recommendation_ids": sorted(derived_ids["evolved"]),
                    "added_recommendation_ids": sorted(derived_ids["added"]),
                    "removed_recommendation_ids": sorted(derived_ids["removed"]),
                }
                for list_key, expected_ids in expected_lists.items():
                    if row.get(list_key) != expected_ids:
                        errors.append(
                            f"recommendation_id_stability.scenario_results[{index}].{list_key} must match recommendation_results"
                        )
                if scenario_kind == "no-change":
                    non_stable = (
                        row.get("evolved_recommendation_ids")
                        or row.get("added_recommendation_ids")
                        or row.get("removed_recommendation_ids")
                    )
                    if non_stable:
                        errors.append(
                            f"recommendation_id_stability.scenario_results[{index}] no-change scenarios must emit only stable results"
                        )

        usage = stability.get("cross_project_context_usage")
        if not isinstance(usage, Mapping):
            errors.append("recommendation_id_stability.cross_project_context_usage must be an object")
        else:
            expected_context = {
                "cross_project_context_provided",
                "cross_project_context_used",
                "projects_considered",
                "earth_sweep_evidence_refs_considered",
                "cross_project_obligation_count",
                "unresolved_idea_count",
                "recommendation_ids_with_context",
            }
            context_keys = set(usage.keys())
            missing_context = sorted(expected_context - context_keys)
            if missing_context:
                errors.append(f"recommendation_id_stability.cross_project_context_usage missing keys: {missing_context}")
            unexpected_context = sorted(context_keys - expected_context)
            if unexpected_context:
                errors.append(
                    f"recommendation_id_stability.cross_project_context_usage has unexpected keys: {unexpected_context}"
                )
            if not isinstance(usage.get("cross_project_context_provided"), bool):
                errors.append(
                    "recommendation_id_stability.cross_project_context_usage.cross_project_context_provided must be a boolean"
                )
            if not isinstance(usage.get("cross_project_context_used"), bool):
                errors.append(
                    "recommendation_id_stability.cross_project_context_usage.cross_project_context_used must be a boolean"
                )
            for key in ("projects_considered", "earth_sweep_evidence_refs_considered", "recommendation_ids_with_context"):
                values = usage.get(key)
                if not isinstance(values, list):
                    errors.append(f"recommendation_id_stability.cross_project_context_usage.{key} must be a list")
                elif values != sorted(set(values)):
                    errors.append(
                        f"recommendation_id_stability.cross_project_context_usage.{key} must be sorted and unique"
                    )
            for key in ("cross_project_obligation_count", "unresolved_idea_count"):
                value = usage.get(key)
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        f"recommendation_id_stability.cross_project_context_usage.{key} must be a non-negative integer"
                    )

        open_risks = stability.get("open_risks", [])
        if not isinstance(open_risks, list):
            errors.append("recommendation_id_stability.open_risks must be a list")
            open_risks = []
        else:
            last_open_risk_id = ""
            for index, row in enumerate(open_risks):
                try:
                    normalized = _normalize_open_risk(
                        row,
                        field_name=f"recommendation_id_stability.open_risks[{index}]",
                    )
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                if last_open_risk_id and normalized["open_risk_id"] < last_open_risk_id:
                    errors.append("recommendation_id_stability.open_risks must be sorted by open_risk_id")
                last_open_risk_id = normalized["open_risk_id"]

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "baseline_recommendations",
            "scenario_count",
            "stable_results",
            "evolved_results",
            "added_results",
            "removed_results",
            "open_risk_count",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")

        expected_values = {
            "baseline_recommendations": len(baseline_recommendations),
            "scenario_count": len(scenario_results),
            "stable_results": sum(len(row.get("stable_recommendation_ids", [])) for row in scenario_results if isinstance(row, Mapping)),
            "evolved_results": sum(
                len(row.get("evolved_recommendation_ids", [])) for row in scenario_results if isinstance(row, Mapping)
            ),
            "added_results": sum(len(row.get("added_recommendation_ids", [])) for row in scenario_results if isinstance(row, Mapping)),
            "removed_results": sum(
                len(row.get("removed_recommendation_ids", [])) for row in scenario_results if isinstance(row, Mapping)
            ),
            "open_risk_count": len(open_risks) if isinstance(open_risks, list) else 0,
        }
        for key, expected_value in expected_values.items():
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")
            elif value != expected_value:
                errors.append(f"totals.{key} must match derived recommendation_id_stability counts")

    return errors


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type == REQ_048_ANALYSIS_TYPE:
        return build_req_048_strategy_md_generator(payload)
    if analysis_type == REQ_050_ANALYSIS_TYPE:
        return build_req_050_ecosystem_link_map_json_generator(payload)
    if analysis_type == REQ_051_ANALYSIS_TYPE:
        return build_req_051_strategy_changelog_md_generator(payload)
    if analysis_type == REQ_052_ANALYSIS_TYPE:
        return build_req_052_strategy_packet_v1_generator(payload)
    if analysis_type == REQ_053_ANALYSIS_TYPE:
        return build_req_053_recommendation_id_stability_contract(payload)
    raise ValueError(
        "analysis_type must be one of: "
        f"{REQ_048_ANALYSIS_TYPE}, {REQ_050_ANALYSIS_TYPE}, {REQ_051_ANALYSIS_TYPE}, "
        f"{REQ_052_ANALYSIS_TYPE}, {REQ_053_ANALYSIS_TYPE}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit strategy artifact handoff payloads.")
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
        _emit_debug(f"strategy_artifacts_handoff CLI failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
