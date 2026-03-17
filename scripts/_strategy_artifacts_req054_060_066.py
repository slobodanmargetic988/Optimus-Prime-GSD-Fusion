#!/usr/bin/env python3
"""Contract/data-model surfaces for strategy artifact handoff requirements."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
for candidate in (SCRIPTS_ROOT,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


REQ_054_SCHEMA_VERSION = "req-054.recommendation-to-planner-mapping-artifact.v1"
REQ_054_REQUIREMENT_ID = "REQ-054"
REQ_054_ANALYSIS_TYPE = "recommendation_to_planner_mapping_artifact"
REQ_054_CALL_ID = "recommendation-to-planner-mapping"
REQ_060_REQUIREMENT_ID = "REQ-060"
REQ_060_ANALYSIS_TYPE = "strategy_packet_v1_schema_validator"
REQ_060_DEFAULT_SCHEMA_PATH = "contracts/strategy_packet.v1.schema.json"
REQ_066_REQUIREMENT_ID = "REQ-066"
REQ_066_ANALYSIS_TYPE = "validator_runner_and_aggregate_verdict"
REQUIRED_RECOMMENDATION_FIELDS = (
    "recommendation_id",
    "priority",
    "summary",
    "rationale",
    "expected_impact",
    "risk_level",
)
_REQ_054_REASON_MISSING_EARTH_SWEEP_EVIDENCE = "missing_earth_sweep_evidence_refs"
_REQ_054_REASON_UNKNOWN_RECOMMENDATIONS = "unknown_recommendation_ids"
_REQ_054_REASON_EARTH_EVIDENCE_OUTSIDE_CONTEXT = "earth_sweep_evidence_not_in_context"
_REQ_054_REASON_UNRESOLVED_IDEA = "unresolved_idea_open_risk"
_REQ_060_REASON_PACKET_PAYLOAD_NOT_OBJECT = "packet_payload_not_object"
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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_repo_json_path(raw_path: Any, *, field_name: str) -> Path:
    path_text = _require_nonempty_text(raw_path, field_name=field_name)
    candidate = Path(path_text).expanduser()
    if not candidate.is_absolute():
        candidate = _repo_root() / candidate
    return candidate.resolve()


def _load_json_from_field(raw_path: Any, *, field_name: str) -> Any:
    return _read_json_file(_resolve_repo_json_path(raw_path, field_name=field_name))


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


def _normalize_positive_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be a positive integer")
    if value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


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


def _stable_id_fragment(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _collect_unique_refs(*ref_groups: list[str]) -> list[str]:
    refs: set[str] = set()
    for group in ref_groups:
        refs.update(group)
    return sorted(refs)


def _string_list_from_any(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    values: set[str] = set()
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                values.add(text)
    return sorted(values)


def _normalize_input_mapping_row(raw_value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(raw_value, field_name=field_name)
    expected_keys = {
        "recommendation_id",
        "planner_task_intent_handle",
        "planner_task_intent_summary",
        "planner_lane",
        "sequence_hint",
        "call_trace_refs",
        "evidence_refs",
        "planner_packet_refs",
    }
    unexpected = sorted(set(row.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    return {
        "recommendation_id": _require_nonempty_text(row.get("recommendation_id"), field_name=f"{field_name}.recommendation_id"),
        "planner_task_intent_handle": _require_nonempty_text(
            row.get("planner_task_intent_handle"),
            field_name=f"{field_name}.planner_task_intent_handle",
        ),
        "planner_task_intent_summary": _require_nonempty_text(
            row.get("planner_task_intent_summary"),
            field_name=f"{field_name}.planner_task_intent_summary",
        ),
        "planner_lane": _require_nonempty_text(row.get("planner_lane"), field_name=f"{field_name}.planner_lane"),
        "sequence_hint": _normalize_positive_int(row.get("sequence_hint"), field_name=f"{field_name}.sequence_hint"),
        "call_trace_refs": _normalize_string_list(
            row.get("call_trace_refs"),
            field_name=f"{field_name}.call_trace_refs",
            allow_empty=False,
        ),
        "evidence_refs": _normalize_string_list(
            row.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
            allow_empty=False,
        ),
        "planner_packet_refs": _normalize_string_list(
            row.get("planner_packet_refs"),
            field_name=f"{field_name}.planner_packet_refs",
            allow_empty=True,
        ),
    }


def _normalize_recommendation_mappings(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("recommendation_mappings must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_value):
        row = _normalize_input_mapping_row(item, field_name=f"recommendation_mappings[{index}]")
        pair = (row["recommendation_id"], row["planner_task_intent_handle"])
        if pair in seen_pairs:
            raise ValueError(
                "recommendation_mappings"
                f"[{index}].recommendation_id + planner_task_intent_handle duplicates {pair[0]} -> {pair[1]}"
            )
        seen_pairs.add(pair)
        normalized.append(row)
    normalized.sort(
        key=lambda row: (
            row["sequence_hint"],
            row["planner_task_intent_handle"],
            row["recommendation_id"],
        )
    )
    return normalized


def _normalize_optional_text(value: Any, *, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    return value.strip()


def _normalize_cross_project_obligation_row(raw_value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(raw_value, field_name=field_name)
    obligation_id = _require_nonempty_text(row.get("obligation_id"), field_name=f"{field_name}.obligation_id")
    summary = _require_nonempty_text(row.get("summary"), field_name=f"{field_name}.summary")
    recommendation_ids = _normalize_string_list(
        row.get("recommendation_ids"),
        field_name=f"{field_name}.recommendation_ids",
        allow_empty=False,
    )
    project_ids = _normalize_string_list(
        row.get("project_ids"),
        field_name=f"{field_name}.project_ids",
        allow_empty=True,
    )
    earth_sweep_evidence_refs = _collect_unique_refs(
        _normalize_string_list(
            row.get("earth_sweep_evidence_refs"),
            field_name=f"{field_name}.earth_sweep_evidence_refs",
            allow_empty=True,
        ),
        _normalize_string_list(
            row.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
            allow_empty=True,
        ),
    )
    return {
        "obligation_id": obligation_id,
        "summary": summary,
        "recommendation_ids": recommendation_ids,
        "project_ids": project_ids,
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
    }


def _normalize_unresolved_idea_row(raw_value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(raw_value, field_name=field_name)
    idea_id = _require_nonempty_text(row.get("idea_id"), field_name=f"{field_name}.idea_id")
    summary = _require_nonempty_text(row.get("summary"), field_name=f"{field_name}.summary")
    recommendation_ids = _normalize_string_list(
        row.get("recommendation_ids"),
        field_name=f"{field_name}.recommendation_ids",
        allow_empty=True,
    )
    project_ids = _normalize_string_list(
        row.get("project_ids"),
        field_name=f"{field_name}.project_ids",
        allow_empty=True,
    )
    if not project_ids:
        project_id = _normalize_optional_text(row.get("project_id"), field_name=f"{field_name}.project_id")
        if project_id:
            project_ids = [project_id]
    required_earth_sweep_evidence_refs = _collect_unique_refs(
        _normalize_string_list(
            row.get("required_earth_sweep_evidence_refs"),
            field_name=f"{field_name}.required_earth_sweep_evidence_refs",
            allow_empty=True,
        ),
        _normalize_string_list(
            row.get("earth_sweep_evidence_refs"),
            field_name=f"{field_name}.earth_sweep_evidence_refs",
            allow_empty=True,
        ),
        _normalize_string_list(
            row.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
            allow_empty=True,
        ),
    )
    return {
        "idea_id": idea_id,
        "summary": summary,
        "recommendation_ids": recommendation_ids,
        "project_ids": project_ids,
        "required_earth_sweep_evidence_refs": required_earth_sweep_evidence_refs,
    }


def _normalize_broad_sweep_context(raw_value: Any) -> dict[str, Any]:
    if raw_value is None:
        return {
            "projects_considered": [],
            "earth_sweep_evidence_refs": [],
            "cross_project_obligations": [],
            "unresolved_ideas": [],
        }
    raw = _require_mapping(raw_value, field_name="broad_sweep_context")
    projects_considered = _normalize_string_list(
        raw.get("projects_considered"),
        field_name="broad_sweep_context.projects_considered",
        allow_empty=True,
    )
    earth_sweep_evidence_refs = _normalize_string_list(
        raw.get("earth_sweep_evidence_refs"),
        field_name="broad_sweep_context.earth_sweep_evidence_refs",
        allow_empty=True,
    )

    obligations: list[dict[str, Any]] = []
    raw_obligations = raw.get("cross_project_obligations")
    if raw_obligations is not None:
        if not isinstance(raw_obligations, list):
            raise ValueError("broad_sweep_context.cross_project_obligations must be a list")
        for index, item in enumerate(raw_obligations):
            obligations.append(
                _normalize_cross_project_obligation_row(
                    item,
                    field_name=f"broad_sweep_context.cross_project_obligations[{index}]",
                )
            )
    obligations.sort(key=lambda row: row["obligation_id"])

    unresolved_ideas: list[dict[str, Any]] = []
    raw_unresolved_ideas = raw.get("unresolved_ideas")
    if raw_unresolved_ideas is not None:
        if not isinstance(raw_unresolved_ideas, list):
            raise ValueError("broad_sweep_context.unresolved_ideas must be a list")
        for index, item in enumerate(raw_unresolved_ideas):
            unresolved_ideas.append(
                _normalize_unresolved_idea_row(
                    item,
                    field_name=f"broad_sweep_context.unresolved_ideas[{index}]",
                )
            )
    unresolved_ideas.sort(key=lambda row: row["idea_id"])

    return {
        "projects_considered": projects_considered,
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
        "cross_project_obligations": obligations,
        "unresolved_ideas": unresolved_ideas,
    }


def _context_project_ids(context: Mapping[str, Any]) -> list[str]:
    return _collect_unique_refs(
        list(context.get("projects_considered") or []),
        *[list(row.get("project_ids") or []) for row in list(context.get("cross_project_obligations") or [])],
        *[list(row.get("project_ids") or []) for row in list(context.get("unresolved_ideas") or [])],
    )


def _mapping_index_by_recommendation(output_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_recommendation: dict[str, set[str]] = {}
    for row in output_rows:
        recommendation_id = str(row["recommendation_id"])
        planner_handle = str(row["planner_task_intent_handle"])
        by_recommendation.setdefault(recommendation_id, set()).add(planner_handle)
    return {key: sorted(values) for key, values in sorted(by_recommendation.items())}


def _linked_planner_task_intent_handles(
    recommendation_ids: list[str],
    mapping_index: Mapping[str, list[str]],
) -> list[str]:
    return _collect_unique_refs(*[list(mapping_index.get(recommendation_id) or []) for recommendation_id in recommendation_ids])


def _build_req_054_processing_behavior(
    *,
    output_rows: list[dict[str, Any]],
    recommendation_ids: list[str],
    planner_task_intent_handles: list[str],
    broad_sweep_context: Mapping[str, Any],
) -> dict[str, Any]:
    mapping_index = _mapping_index_by_recommendation(output_rows)
    earth_refs = sorted(set(str(item) for item in list(broad_sweep_context.get("earth_sweep_evidence_refs") or [])))
    earth_ref_set = set(earth_refs)
    context_project_ids = _context_project_ids(broad_sweep_context)

    approved_cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    recommendation_ids_with_context: set[str] = set()

    for obligation in list(broad_sweep_context.get("cross_project_obligations") or []):
        linked_recommendation_ids = sorted(set(obligation["recommendation_ids"]).intersection(mapping_index))
        linked_handles = _linked_planner_task_intent_handles(linked_recommendation_ids, mapping_index)
        earth_evidence_refs = list(obligation["earth_sweep_evidence_refs"])
        evidence_refs_in_context = sorted(set(earth_evidence_refs).intersection(earth_ref_set))

        reason_codes: list[str] = []
        if not linked_recommendation_ids:
            reason_codes.append(_REQ_054_REASON_UNKNOWN_RECOMMENDATIONS)
        if not earth_evidence_refs:
            reason_codes.append(_REQ_054_REASON_MISSING_EARTH_SWEEP_EVIDENCE)
        elif not evidence_refs_in_context:
            reason_codes.append(_REQ_054_REASON_EARTH_EVIDENCE_OUTSIDE_CONTEXT)

        if reason_codes:
            required_evidence_refs = list(earth_evidence_refs)
            if not required_evidence_refs:
                required_evidence_refs = ["missing:earth-sweep-evidence-ref"]
            open_risks.append(
                {
                    "open_risk_id": f"open-risk.{_stable_id_fragment(obligation['obligation_id'], ','.join(reason_codes))}",
                    "source_type": "cross_project_obligation",
                    "source_id": obligation["obligation_id"],
                    "summary": obligation["summary"],
                    "reason_code": ",".join(reason_codes),
                    "project_ids": list(obligation["project_ids"]),
                    "required_evidence_refs": required_evidence_refs,
                    "evidence_refs": evidence_refs_in_context,
                    "linked_recommendation_ids": linked_recommendation_ids,
                    "linked_planner_task_intent_handles": linked_handles,
                }
            )
            continue

        recommendation_ids_with_context.update(linked_recommendation_ids)
        approved_cross_project_obligations.append(
            {
                "obligation_id": obligation["obligation_id"],
                "summary": obligation["summary"],
                "project_ids": list(obligation["project_ids"]),
                "evidence_refs": evidence_refs_in_context,
                "linked_recommendation_ids": linked_recommendation_ids,
                "linked_planner_task_intent_handles": linked_handles,
            }
        )

    for unresolved in list(broad_sweep_context.get("unresolved_ideas") or []):
        linked_recommendation_ids = sorted(set(unresolved["recommendation_ids"]).intersection(mapping_index))
        linked_handles = _linked_planner_task_intent_handles(linked_recommendation_ids, mapping_index)
        required_evidence_refs = list(unresolved["required_earth_sweep_evidence_refs"])
        evidence_refs = sorted(set(required_evidence_refs).intersection(earth_ref_set))
        if not required_evidence_refs:
            required_evidence_refs = ["missing:earth-sweep-evidence-ref"]

        recommendation_ids_with_context.update(linked_recommendation_ids)
        open_risks.append(
            {
                "open_risk_id": f"open-risk.{_stable_id_fragment(unresolved['idea_id'], _REQ_054_REASON_UNRESOLVED_IDEA)}",
                "source_type": "unresolved_idea",
                "source_id": unresolved["idea_id"],
                "summary": unresolved["summary"],
                "reason_code": _REQ_054_REASON_UNRESOLVED_IDEA,
                "project_ids": list(unresolved["project_ids"]),
                "required_evidence_refs": required_evidence_refs,
                "evidence_refs": evidence_refs,
                "linked_recommendation_ids": linked_recommendation_ids,
                "linked_planner_task_intent_handles": linked_handles,
            }
        )

    approved_cross_project_obligations.sort(key=lambda row: row["obligation_id"])
    open_risks.sort(key=lambda row: (row["source_type"], row["source_id"], row["open_risk_id"]))

    mapping_traceability_refs = _collect_unique_refs(*[list(row["traceability_refs"]) for row in output_rows])
    recommendation_evidence_refs = _collect_unique_refs(
        mapping_traceability_refs,
        earth_refs,
        *[list(row["evidence_refs"]) for row in approved_cross_project_obligations],
        *[list(row["required_evidence_refs"]) for row in open_risks],
    )

    decision = "ready_for_planning"
    if output_rows and open_risks:
        decision = "planning_with_open_risks"
    elif not output_rows and open_risks:
        decision = "blocked_by_open_risks"
    elif not output_rows:
        decision = "no_mappings"

    recommendation = {
        "decision": decision,
        "rationale": (
            f"mappings={len(output_rows)} obligations={len(broad_sweep_context['cross_project_obligations'])} "
            f"approved={len(approved_cross_project_obligations)} open_risks={len(open_risks)}"
        ),
        "evidence_refs": recommendation_evidence_refs,
        "context_project_ids": context_project_ids,
        "mapped_recommendation_ids": recommendation_ids,
        "mapped_task_intent_handles": planner_task_intent_handles,
        "approved_cross_project_obligations": approved_cross_project_obligations,
        "open_risks": open_risks,
    }

    usage = {
        "cross_project_context_provided": bool(
            broad_sweep_context["projects_considered"]
            or broad_sweep_context["earth_sweep_evidence_refs"]
            or broad_sweep_context["cross_project_obligations"]
            or broad_sweep_context["unresolved_ideas"]
        ),
        "cross_project_context_used": bool(
            approved_cross_project_obligations or open_risks or recommendation_ids_with_context
        ),
        "projects_considered": context_project_ids,
        "earth_sweep_evidence_refs_considered": earth_refs,
        "cross_project_obligation_count": len(broad_sweep_context["cross_project_obligations"]),
        "unresolved_idea_count": len(broad_sweep_context["unresolved_ideas"]),
        "recommendation_ids_with_context": sorted(recommendation_ids_with_context),
    }

    return {
        "recommendation": recommendation,
        "cross_project_context_usage": usage,
    }


def _req_060_packet_mapping_rows(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    artifact = packet.get("recommendation_to_planner_mapping_artifact")
    if not isinstance(artifact, Mapping):
        return []

    raw_rows = artifact.get("recommendation_to_task_intent_mappings")
    if not isinstance(raw_rows, list):
        return []

    normalized_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, Mapping):
            continue
        recommendation_id = row.get("recommendation_id")
        planner_task_intent_handle = row.get("planner_task_intent_handle")
        if not isinstance(recommendation_id, str) or not recommendation_id.strip():
            continue
        if not isinstance(planner_task_intent_handle, str) or not planner_task_intent_handle.strip():
            continue
        downstream_audit_trail = row.get("downstream_audit_trail")
        downstream = downstream_audit_trail if isinstance(downstream_audit_trail, Mapping) else {}
        traceability_refs = _collect_unique_refs(
            _string_list_from_any(row.get("traceability_refs")),
            _string_list_from_any(downstream.get("source_call_trace_refs")),
            _string_list_from_any(downstream.get("source_evidence_refs")),
            _string_list_from_any(downstream.get("source_packet_refs")),
        )
        normalized_rows.append(
            {
                "mapping_id": str(row.get("mapping_id") or ""),
                "recommendation_id": recommendation_id.strip(),
                "planner_task_intent_handle": planner_task_intent_handle.strip(),
                "traceability_refs": traceability_refs,
            }
        )
    normalized_rows.sort(
        key=lambda row: (
            row["planner_task_intent_handle"],
            row["recommendation_id"],
            row["mapping_id"],
        )
    )
    return normalized_rows


def _req_060_recommendation_id(raw_row: Any, *, index: int) -> str:
    if isinstance(raw_row, Mapping):
        value = raw_row.get("recommendation_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"recommendation-{index:03d}"


def _req_060_required_field_presence(raw_row: Any) -> tuple[list[str], list[str]]:
    row = raw_row if isinstance(raw_row, Mapping) else {}
    present: list[str] = []
    missing: list[str] = []
    for field_name in REQUIRED_RECOMMENDATION_FIELDS:
        value = row.get(field_name)
        if isinstance(value, str):
            if value.strip():
                present.append(field_name)
            else:
                missing.append(field_name)
            continue
        if value not in (None, "", [], {}):
            present.append(field_name)
        else:
            missing.append(field_name)
    return present, missing


def _build_req_060_processing_behavior(
    *,
    validation_output: Mapping[str, Any],
    packet: Mapping[str, Any],
    broad_sweep_context: Mapping[str, Any],
) -> dict[str, Any]:
    output_rows = _req_060_packet_mapping_rows(packet)
    mapped_recommendation_ids = sorted({row["recommendation_id"] for row in output_rows})
    planner_task_intent_handles = sorted({row["planner_task_intent_handle"] for row in output_rows})
    base_processing = _build_req_054_processing_behavior(
        output_rows=output_rows,
        recommendation_ids=mapped_recommendation_ids,
        planner_task_intent_handles=planner_task_intent_handles,
        broad_sweep_context=broad_sweep_context,
    )

    recommendation = dict(base_processing["recommendation"])
    recommendation_refs_by_id: dict[str, set[str]] = {}
    planner_handles_by_recommendation_id: dict[str, set[str]] = {}

    for row in output_rows:
        recommendation_id = row["recommendation_id"]
        recommendation_refs_by_id.setdefault(recommendation_id, set()).update(row["traceability_refs"])
        planner_handles_by_recommendation_id.setdefault(recommendation_id, set()).add(row["planner_task_intent_handle"])

    for row in recommendation["approved_cross_project_obligations"]:
        row_refs = set(row["evidence_refs"])
        for recommendation_id in row["linked_recommendation_ids"]:
            recommendation_refs_by_id.setdefault(recommendation_id, set()).update(row_refs)

    for row in recommendation["open_risks"]:
        row_refs = set(row["required_evidence_refs"]) | set(row["evidence_refs"])
        for recommendation_id in row["linked_recommendation_ids"]:
            recommendation_refs_by_id.setdefault(recommendation_id, set()).update(row_refs)

    recommendation_field_completeness: list[dict[str, Any]] = []
    raw_recommendations = packet.get("recommendations")
    if isinstance(raw_recommendations, list):
        for index, raw_row in enumerate(raw_recommendations, start=1):
            recommendation_id = _req_060_recommendation_id(raw_row, index=index)
            required_fields_present, missing_required_fields = _req_060_required_field_presence(raw_row)
            evidence_refs = sorted(recommendation_refs_by_id.get(recommendation_id, set()))
            recommendation_field_completeness.append(
                {
                    "recommendation_id": recommendation_id,
                    "required_fields_present": required_fields_present,
                    "missing_required_fields": missing_required_fields,
                    "has_complete_required_fields": not missing_required_fields,
                    "evidence_refs": evidence_refs,
                    "has_evidence_refs": bool(evidence_refs),
                    "planner_task_intent_handles": sorted(
                        planner_handles_by_recommendation_id.get(recommendation_id, set())
                    ),
                }
            )
    recommendation_field_completeness.sort(key=lambda row: row["recommendation_id"])

    complete_recommendation_count = sum(
        1 for row in recommendation_field_completeness if row["has_complete_required_fields"]
    )
    recommendations_with_evidence_count = sum(1 for row in recommendation_field_completeness if row["has_evidence_refs"])
    if validation_output.get("ok") is not True:
        decision = "planner_blocked"
    elif recommendation["open_risks"]:
        decision = "planner_ready_with_open_risks"
    else:
        decision = "planner_ready"

    recommendation["decision"] = decision
    recommendation["rationale"] = (
        f"packet_recommendations={len(recommendation_field_completeness)} "
        f"mapped_recommendations={len(mapped_recommendation_ids)} "
        f"complete_recommendations={complete_recommendation_count} "
        f"recommendations_with_evidence={recommendations_with_evidence_count} "
        f"approved={len(recommendation['approved_cross_project_obligations'])} "
        f"open_risks={len(recommendation['open_risks'])} "
        f"diagnostics={int(validation_output.get('diagnostic_count') or 0)}"
    )
    recommendation["recommendation_field_completeness"] = recommendation_field_completeness

    return {
        "recommendation": recommendation,
        "cross_project_context_usage": base_processing["cross_project_context_usage"],
    }


def build_req_054_recommendation_to_planner_mapping_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-054 recommendation-to-planner mapping artifact payload."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_054_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_054_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    recommendation_mappings = _normalize_recommendation_mappings(raw.get("recommendation_mappings"))
    broad_sweep_context = _normalize_broad_sweep_context(raw.get("broad_sweep_context")) if "broad_sweep_context" in raw else None

    output_rows: list[dict[str, Any]] = []
    unique_traceability_refs: set[str] = set()
    for row in recommendation_mappings:
        traceability_refs = _collect_unique_refs(
            row["call_trace_refs"],
            row["evidence_refs"],
            row["planner_packet_refs"],
        )
        unique_traceability_refs.update(traceability_refs)
        output_rows.append(
            {
                "mapping_id": (
                    "rtp."
                    + _stable_id_fragment(
                        row["recommendation_id"],
                        row["planner_task_intent_handle"],
                        row["planner_lane"],
                        str(row["sequence_hint"]),
                    )
                ),
                "recommendation_id": row["recommendation_id"],
                "planner_task_intent_handle": row["planner_task_intent_handle"],
                "planner_task_intent_summary": row["planner_task_intent_summary"],
                "planner_lane": row["planner_lane"],
                "sequence_hint": row["sequence_hint"],
                "traceability_refs": traceability_refs,
                "downstream_audit_trail": {
                    "source_call_trace_refs": row["call_trace_refs"],
                    "source_evidence_refs": row["evidence_refs"],
                    "source_packet_refs": row["planner_packet_refs"],
                    "emitted_at_utc": checked_at_utc,
                    "emitted_by_requirement_id": REQ_054_REQUIREMENT_ID,
                },
            }
        )

    recommendation_ids = sorted({row["recommendation_id"] for row in output_rows})
    planner_task_intent_handles = sorted({row["planner_task_intent_handle"] for row in output_rows})
    mapping_artifact = {
        "recommendation_to_task_intent_mappings": output_rows,
        "recommendation_ids": recommendation_ids,
        "planner_task_intent_handles": planner_task_intent_handles,
    }
    output_payload = {
        "ok": True,
        "schema_version": REQ_054_SCHEMA_VERSION,
        "requirement_id": REQ_054_REQUIREMENT_ID,
        "analysis_type": REQ_054_ANALYSIS_TYPE,
        "call_id": REQ_054_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "recommendation_to_planner_mapping_artifact": mapping_artifact,
        "totals": {
            "input_rows": len(recommendation_mappings),
            "mapping_rows": len(output_rows),
            "unique_recommendation_ids": len(recommendation_ids),
            "unique_planner_task_intent_handles": len(planner_task_intent_handles),
            "traceability_refs": len(unique_traceability_refs),
        },
    }
    if broad_sweep_context is not None:
        output_payload["processing_behavior"] = _build_req_054_processing_behavior(
            output_rows=output_rows,
            recommendation_ids=recommendation_ids,
            planner_task_intent_handles=planner_task_intent_handles,
            broad_sweep_context=broad_sweep_context,
        )

    errors = validate_req_054_recommendation_to_planner_mapping_artifact(output_payload)
    if errors:
        raise ValueError(f"built REQ-054 payload failed validation: {errors}")
    return output_payload


def validate_req_054_recommendation_to_planner_mapping_artifact(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-054 recommendation-to-planner mapping artifact payload shape."""
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
        "recommendation_to_planner_mapping_artifact",
        "totals",
    }
    optional_top = {"processing_behavior"}
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top - optional_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_054_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_054_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_054_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_054_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_054_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_054_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_054_CALL_ID:
        errors.append(f"call_id must be {REQ_054_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    artifact = payload.get("recommendation_to_planner_mapping_artifact")
    mappings: list[Mapping[str, Any]] = []
    if not isinstance(artifact, Mapping):
        errors.append("recommendation_to_planner_mapping_artifact must be an object")
    else:
        expected_artifact_keys = {
            "recommendation_to_task_intent_mappings",
            "recommendation_ids",
            "planner_task_intent_handles",
        }
        artifact_keys = set(artifact.keys())
        missing_artifact = sorted(expected_artifact_keys - artifact_keys)
        if missing_artifact:
            errors.append(f"recommendation_to_planner_mapping_artifact missing keys: {missing_artifact}")
        unexpected_artifact = sorted(artifact_keys - expected_artifact_keys)
        if unexpected_artifact:
            errors.append(f"recommendation_to_planner_mapping_artifact has unexpected keys: {unexpected_artifact}")

        raw_mappings = artifact.get("recommendation_to_task_intent_mappings")
        if not isinstance(raw_mappings, list) or not raw_mappings:
            errors.append("recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings must be a non-empty list")
        else:
            seen_mapping_ids: set[str] = set()
            seen_pairs: set[tuple[str, str]] = set()
            for index, row in enumerate(raw_mappings):
                if not isinstance(row, Mapping):
                    errors.append(
                        f"recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings[{index}] must be an object"
                    )
                    continue
                mappings.append(row)
                expected_mapping_keys = {
                    "mapping_id",
                    "recommendation_id",
                    "planner_task_intent_handle",
                    "planner_task_intent_summary",
                    "planner_lane",
                    "sequence_hint",
                    "traceability_refs",
                    "downstream_audit_trail",
                }
                mapping_keys = set(row.keys())
                missing_mapping = sorted(expected_mapping_keys - mapping_keys)
                if missing_mapping:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}] missing keys: {missing_mapping}"
                    )
                unexpected_mapping = sorted(mapping_keys - expected_mapping_keys)
                if unexpected_mapping:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}] has unexpected keys: {unexpected_mapping}"
                    )
                mapping_id = row.get("mapping_id")
                if not isinstance(mapping_id, str) or not mapping_id.startswith("rtp."):
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].mapping_id must be like rtp.<id>"
                    )
                elif mapping_id in seen_mapping_ids:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].mapping_id must be unique"
                    )
                else:
                    seen_mapping_ids.add(mapping_id)

                recommendation_id = row.get("recommendation_id")
                planner_task_intent_handle = row.get("planner_task_intent_handle")
                if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].recommendation_id must be a non-empty string"
                    )
                if not isinstance(planner_task_intent_handle, str) or not planner_task_intent_handle.strip():
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].planner_task_intent_handle must be a non-empty string"
                    )
                if (
                    isinstance(recommendation_id, str)
                    and recommendation_id.strip()
                    and isinstance(planner_task_intent_handle, str)
                    and planner_task_intent_handle.strip()
                ):
                    pair = (recommendation_id, planner_task_intent_handle)
                    if pair in seen_pairs:
                        errors.append(
                            "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                            f"[{index}] duplicate recommendation_id + planner_task_intent_handle pair"
                        )
                    else:
                        seen_pairs.add(pair)

                for key in ("planner_task_intent_summary", "planner_lane"):
                    value = row.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                            f"[{index}].{key} must be a non-empty string"
                        )
                sequence_hint = row.get("sequence_hint")
                if not isinstance(sequence_hint, int) or sequence_hint < 1:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].sequence_hint must be a positive integer"
                    )
                traceability_refs = row.get("traceability_refs")
                if not isinstance(traceability_refs, list) or not traceability_refs:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].traceability_refs must be a non-empty list"
                    )

                downstream_audit_trail = row.get("downstream_audit_trail")
                if not isinstance(downstream_audit_trail, Mapping):
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail must be an object"
                    )
                    continue
                expected_audit_keys = {
                    "source_call_trace_refs",
                    "source_evidence_refs",
                    "source_packet_refs",
                    "emitted_at_utc",
                    "emitted_by_requirement_id",
                }
                audit_keys = set(downstream_audit_trail.keys())
                missing_audit = sorted(expected_audit_keys - audit_keys)
                if missing_audit:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail missing keys: {missing_audit}"
                    )
                unexpected_audit = sorted(audit_keys - expected_audit_keys)
                if unexpected_audit:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail has unexpected keys: {unexpected_audit}"
                    )

                source_call_trace_refs = downstream_audit_trail.get("source_call_trace_refs")
                if not isinstance(source_call_trace_refs, list) or not source_call_trace_refs:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.source_call_trace_refs must be a non-empty list"
                    )
                source_evidence_refs = downstream_audit_trail.get("source_evidence_refs")
                if not isinstance(source_evidence_refs, list) or not source_evidence_refs:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.source_evidence_refs must be a non-empty list"
                    )
                source_packet_refs = downstream_audit_trail.get("source_packet_refs")
                if not isinstance(source_packet_refs, list):
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.source_packet_refs must be a list"
                    )
                emitted_at_utc = downstream_audit_trail.get("emitted_at_utc")
                if not isinstance(emitted_at_utc, str) or not emitted_at_utc.strip():
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.emitted_at_utc must be a non-empty string"
                    )
                emitted_by_requirement_id = downstream_audit_trail.get("emitted_by_requirement_id")
                if emitted_by_requirement_id != REQ_054_REQUIREMENT_ID:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.emitted_by_requirement_id must be {REQ_054_REQUIREMENT_ID}"
                    )

        recommendation_ids = artifact.get("recommendation_ids")
        if not isinstance(recommendation_ids, list):
            errors.append("recommendation_to_planner_mapping_artifact.recommendation_ids must be a list")
        planner_task_intent_handles = artifact.get("planner_task_intent_handles")
        if not isinstance(planner_task_intent_handles, list):
            errors.append("recommendation_to_planner_mapping_artifact.planner_task_intent_handles must be a list")

        if mappings:
            expected_recommendation_ids = sorted({str(row.get("recommendation_id")) for row in mappings})
            if recommendation_ids != expected_recommendation_ids:
                errors.append(
                    "recommendation_to_planner_mapping_artifact.recommendation_ids must match mapping recommendation ids"
                )
            expected_intent_handles = sorted({str(row.get("planner_task_intent_handle")) for row in mappings})
            if planner_task_intent_handles != expected_intent_handles:
                errors.append(
                    "recommendation_to_planner_mapping_artifact.planner_task_intent_handles must match mapping intent handles"
                )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "input_rows",
            "mapping_rows",
            "unique_recommendation_ids",
            "unique_planner_task_intent_handles",
            "traceability_refs",
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

        if mappings:
            unique_recommendation_ids = {str(row.get("recommendation_id")) for row in mappings}
            unique_intent_handles = {str(row.get("planner_task_intent_handle")) for row in mappings}
            unique_traceability_refs: set[str] = set()
            for row in mappings:
                traceability_refs = row.get("traceability_refs")
                if isinstance(traceability_refs, list):
                    unique_traceability_refs.update(str(item) for item in traceability_refs if str(item).strip())
            if totals.get("input_rows") != len(mappings):
                errors.append("totals.input_rows must match recommendation_to_task_intent_mappings length")
            if totals.get("mapping_rows") != len(mappings):
                errors.append("totals.mapping_rows must match recommendation_to_task_intent_mappings length")
            if totals.get("unique_recommendation_ids") != len(unique_recommendation_ids):
                errors.append("totals.unique_recommendation_ids must match unique recommendation ids in mappings")
            if totals.get("unique_planner_task_intent_handles") != len(unique_intent_handles):
                errors.append(
                    "totals.unique_planner_task_intent_handles must match unique planner task intent handles in mappings"
                )
            if totals.get("traceability_refs") != len(unique_traceability_refs):
                errors.append("totals.traceability_refs must match unique traceability refs in mappings")

    processing_behavior = payload.get("processing_behavior")
    if processing_behavior is not None:
        if not isinstance(processing_behavior, Mapping):
            errors.append("processing_behavior must be an object")
        else:
            expected_behavior_keys = {"recommendation", "cross_project_context_usage"}
            behavior_keys = set(processing_behavior.keys())
            missing_behavior = sorted(expected_behavior_keys - behavior_keys)
            if missing_behavior:
                errors.append(f"processing_behavior missing keys: {missing_behavior}")
            unexpected_behavior = sorted(behavior_keys - expected_behavior_keys)
            if unexpected_behavior:
                errors.append(f"processing_behavior has unexpected keys: {unexpected_behavior}")

            recommendation = processing_behavior.get("recommendation")
            if not isinstance(recommendation, Mapping):
                errors.append("processing_behavior.recommendation must be an object")
            else:
                expected_recommendation_keys = {
                    "decision",
                    "rationale",
                    "evidence_refs",
                    "context_project_ids",
                    "mapped_recommendation_ids",
                    "mapped_task_intent_handles",
                    "approved_cross_project_obligations",
                    "open_risks",
                }
                recommendation_keys = set(recommendation.keys())
                missing_recommendation = sorted(expected_recommendation_keys - recommendation_keys)
                if missing_recommendation:
                    errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
                unexpected_recommendation = sorted(recommendation_keys - expected_recommendation_keys)
                if unexpected_recommendation:
                    errors.append(f"processing_behavior.recommendation has unexpected keys: {unexpected_recommendation}")
                for key in ("decision", "rationale"):
                    value = recommendation.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"processing_behavior.recommendation.{key} must be a non-empty string")
                for key in ("evidence_refs", "context_project_ids", "mapped_recommendation_ids", "mapped_task_intent_handles"):
                    value = recommendation.get(key)
                    if not isinstance(value, list):
                        errors.append(f"processing_behavior.recommendation.{key} must be a list")

                expected_recommendation_ids = sorted({str(row.get("recommendation_id")) for row in mappings})
                mapped_recommendation_ids = recommendation.get("mapped_recommendation_ids")
                if isinstance(mapped_recommendation_ids, list) and mapped_recommendation_ids != expected_recommendation_ids:
                    errors.append("processing_behavior.recommendation.mapped_recommendation_ids must match mapping recommendation ids")

                expected_intent_handles = sorted({str(row.get("planner_task_intent_handle")) for row in mappings})
                mapped_intent_handles = recommendation.get("mapped_task_intent_handles")
                if isinstance(mapped_intent_handles, list) and mapped_intent_handles != expected_intent_handles:
                    errors.append("processing_behavior.recommendation.mapped_task_intent_handles must match mapping intent handles")

                approved_cross_project_obligations = recommendation.get("approved_cross_project_obligations")
                if not isinstance(approved_cross_project_obligations, list):
                    errors.append("processing_behavior.recommendation.approved_cross_project_obligations must be a list")
                else:
                    for index, row in enumerate(approved_cross_project_obligations):
                        if not isinstance(row, Mapping):
                            errors.append(
                                "processing_behavior.recommendation.approved_cross_project_obligations"
                                f"[{index}] must be an object"
                            )
                            continue
                        expected_obligation_keys = {
                            "obligation_id",
                            "summary",
                            "project_ids",
                            "evidence_refs",
                            "linked_recommendation_ids",
                            "linked_planner_task_intent_handles",
                        }
                        row_keys = set(row.keys())
                        missing_row = sorted(expected_obligation_keys - row_keys)
                        if missing_row:
                            errors.append(
                                "processing_behavior.recommendation.approved_cross_project_obligations"
                                f"[{index}] missing keys: {missing_row}"
                            )
                        unexpected_row = sorted(row_keys - expected_obligation_keys)
                        if unexpected_row:
                            errors.append(
                                "processing_behavior.recommendation.approved_cross_project_obligations"
                                f"[{index}] has unexpected keys: {unexpected_row}"
                            )
                        for key in ("obligation_id", "summary"):
                            value = row.get(key)
                            if not isinstance(value, str) or not value.strip():
                                errors.append(
                                    "processing_behavior.recommendation.approved_cross_project_obligations"
                                    f"[{index}].{key} must be a non-empty string"
                                )
                        for key in ("project_ids", "evidence_refs", "linked_recommendation_ids", "linked_planner_task_intent_handles"):
                            value = row.get(key)
                            if not isinstance(value, list):
                                errors.append(
                                    "processing_behavior.recommendation.approved_cross_project_obligations"
                                    f"[{index}].{key} must be a list"
                                )
                        evidence_refs = row.get("evidence_refs")
                        if isinstance(evidence_refs, list) and not evidence_refs:
                            errors.append(
                                "processing_behavior.recommendation.approved_cross_project_obligations"
                                f"[{index}].evidence_refs must be non-empty"
                            )

                open_risks = recommendation.get("open_risks")
                if not isinstance(open_risks, list):
                    errors.append("processing_behavior.recommendation.open_risks must be a list")
                else:
                    for index, row in enumerate(open_risks):
                        if not isinstance(row, Mapping):
                            errors.append(f"processing_behavior.recommendation.open_risks[{index}] must be an object")
                            continue
                        expected_risk_keys = {
                            "open_risk_id",
                            "source_type",
                            "source_id",
                            "summary",
                            "reason_code",
                            "project_ids",
                            "required_evidence_refs",
                            "evidence_refs",
                            "linked_recommendation_ids",
                            "linked_planner_task_intent_handles",
                        }
                        row_keys = set(row.keys())
                        missing_row = sorted(expected_risk_keys - row_keys)
                        if missing_row:
                            errors.append(f"processing_behavior.recommendation.open_risks[{index}] missing keys: {missing_row}")
                        unexpected_row = sorted(row_keys - expected_risk_keys)
                        if unexpected_row:
                            errors.append(f"processing_behavior.recommendation.open_risks[{index}] has unexpected keys: {unexpected_row}")
                        for key in ("open_risk_id", "source_type", "source_id", "summary", "reason_code"):
                            value = row.get(key)
                            if not isinstance(value, str) or not value.strip():
                                errors.append(
                                    f"processing_behavior.recommendation.open_risks[{index}].{key} must be a non-empty string"
                                )
                        for key in (
                            "project_ids",
                            "required_evidence_refs",
                            "evidence_refs",
                            "linked_recommendation_ids",
                            "linked_planner_task_intent_handles",
                        ):
                            value = row.get(key)
                            if not isinstance(value, list):
                                errors.append(f"processing_behavior.recommendation.open_risks[{index}].{key} must be a list")
                        required_evidence_refs = row.get("required_evidence_refs")
                        if isinstance(required_evidence_refs, list) and not required_evidence_refs:
                            errors.append(
                                f"processing_behavior.recommendation.open_risks[{index}].required_evidence_refs must be non-empty"
                            )

            usage = processing_behavior.get("cross_project_context_usage")
            if not isinstance(usage, Mapping):
                errors.append("processing_behavior.cross_project_context_usage must be an object")
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
                    errors.append(f"processing_behavior.cross_project_context_usage missing keys: {missing_usage}")
                unexpected_usage = sorted(usage_keys - expected_usage_keys)
                if unexpected_usage:
                    errors.append(f"processing_behavior.cross_project_context_usage has unexpected keys: {unexpected_usage}")
                for key in ("cross_project_context_provided", "cross_project_context_used"):
                    value = usage.get(key)
                    if not isinstance(value, bool):
                        errors.append(f"processing_behavior.cross_project_context_usage.{key} must be a boolean")
                for key in ("projects_considered", "earth_sweep_evidence_refs_considered", "recommendation_ids_with_context"):
                    value = usage.get(key)
                    if not isinstance(value, list):
                        errors.append(f"processing_behavior.cross_project_context_usage.{key} must be a list")
                for key in ("cross_project_obligation_count", "unresolved_idea_count"):
                    value = usage.get(key)
                    if not isinstance(value, int) or value < 0:
                        errors.append(f"processing_behavior.cross_project_context_usage.{key} must be a non-negative integer")

    return errors


def _req_060_packet_payload_not_object_result(*, checked_at_utc: str) -> dict[str, Any]:
    return {
        "ok": False,
        "checked_at_utc": checked_at_utc,
        "verdict": "fail",
        "planner_consumability": "planner_blocked",
        "reason_codes": [_REQ_060_REASON_PACKET_PAYLOAD_NOT_OBJECT],
        "diagnostic_count": 1,
        "summary": "Strategy packet is not planner-consumable; packet JSON root must be an object.",
        "diagnostics": [
            {
                "severity": "error",
                "reason_code": _REQ_060_REASON_PACKET_PAYLOAD_NOT_OBJECT,
                "field_path": "$",
                "message": "strategy packet JSON root must be an object",
            }
        ],
    }


def build_req_060_strategy_packet_v1_schema_validator(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build deterministic strategy_packet.v1 validation results for REQ-060."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_060_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_060_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    broad_sweep_context = _normalize_broad_sweep_context(raw.get("broad_sweep_context")) if "broad_sweep_context" in raw else None

    has_inline_packet = "strategy_packet" in raw
    has_packet_path = "strategy_packet_path" in raw
    if has_inline_packet == has_packet_path:
        raise ValueError("provide exactly one of strategy_packet or strategy_packet_path")
    has_inline_schema = "schema" in raw
    has_schema_path = "schema_path" in raw
    if has_inline_schema and has_schema_path:
        raise ValueError("provide only one of schema or schema_path")

    strategy_packet = raw.get("strategy_packet") if has_inline_packet else _load_json_from_field(
        raw.get("strategy_packet_path"),
        field_name="strategy_packet_path",
    )
    schema = (
        raw.get("schema")
        if has_inline_schema
        else _load_json_from_field(
            raw.get("schema_path", REQ_060_DEFAULT_SCHEMA_PATH),
            field_name="schema_path",
        )
    )
    if not isinstance(schema, Mapping):
        raise ValueError("schema must be a JSON object")
    if not isinstance(strategy_packet, Mapping):
        return _req_060_packet_payload_not_object_result(checked_at_utc=checked_at_utc)

    from scripts.strategy_validators import validate_strategy_packet_payload

    output_payload = validate_strategy_packet_payload(strategy_packet, schema)
    output_payload["checked_at_utc"] = checked_at_utc
    if broad_sweep_context is not None:
        output_payload["processing_behavior"] = _build_req_060_processing_behavior(
            validation_output=output_payload,
            packet=strategy_packet,
            broad_sweep_context=broad_sweep_context,
        )
    errors = validate_req_060_strategy_packet_v1_schema_validator(output_payload)
    if errors:
        raise ValueError(f"built REQ-060 payload failed validation: {errors}")
    return output_payload


def validate_req_060_strategy_packet_v1_schema_validator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-060 strategy_packet.v1 schema validator output shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "ok",
        "checked_at_utc",
        "verdict",
        "planner_consumability",
        "reason_codes",
        "diagnostic_count",
        "summary",
        "diagnostics",
    }
    optional_top = {"processing_behavior"}
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top - optional_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    ok = payload.get("ok")
    if not isinstance(ok, bool):
        errors.append("ok must be a boolean")
    checked_at_utc = payload.get("checked_at_utc")
    if not isinstance(checked_at_utc, str) or not checked_at_utc.strip():
        errors.append("checked_at_utc must be a non-empty string")

    verdict = payload.get("verdict")
    if verdict not in {"pass", "fail"}:
        errors.append("verdict must be pass or fail")
    planner_consumability = payload.get("planner_consumability")
    if planner_consumability not in {"planner_ready", "planner_blocked"}:
        errors.append("planner_consumability must be planner_ready or planner_blocked")

    reason_codes = payload.get("reason_codes")
    if not isinstance(reason_codes, list):
        errors.append("reason_codes must be a list")
        normalized_reason_codes: list[str] = []
    else:
        normalized_reason_codes = []
        for index, item in enumerate(reason_codes):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"reason_codes[{index}] must be a non-empty string")
                continue
            normalized_reason_codes.append(item)

    diagnostic_count = payload.get("diagnostic_count")
    if not isinstance(diagnostic_count, int) or diagnostic_count < 0:
        errors.append("diagnostic_count must be a non-negative integer")
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append("summary must be a non-empty string")

    diagnostics = payload.get("diagnostics")
    normalized_diagnostic_codes: list[str] = []
    if not isinstance(diagnostics, list):
        errors.append("diagnostics must be a list")
    else:
        for index, row in enumerate(diagnostics):
            if not isinstance(row, Mapping):
                errors.append(f"diagnostics[{index}] must be an object")
                continue
            expected_keys = {"severity", "reason_code", "field_path", "message"}
            row_keys = set(row.keys())
            missing_row = sorted(expected_keys - row_keys)
            if missing_row:
                errors.append(f"diagnostics[{index}] missing keys: {missing_row}")
            unexpected_row = sorted(row_keys - expected_keys)
            if unexpected_row:
                errors.append(f"diagnostics[{index}] has unexpected keys: {unexpected_row}")
            for key in ("severity", "reason_code", "field_path", "message"):
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"diagnostics[{index}].{key} must be a non-empty string")
            reason_code = row.get("reason_code")
            if isinstance(reason_code, str) and reason_code.strip():
                normalized_diagnostic_codes.append(reason_code)

    if isinstance(diagnostic_count, int) and isinstance(diagnostics, list) and diagnostic_count != len(diagnostics):
        errors.append("diagnostic_count must match diagnostics length")
    if normalized_reason_codes and normalized_reason_codes != sorted(set(normalized_diagnostic_codes)):
        errors.append("reason_codes must match sorted unique diagnostic reason_code values")

    if ok is True:
        if verdict != "pass":
            errors.append("verdict must be pass when ok is true")
        if planner_consumability != "planner_ready":
            errors.append("planner_consumability must be planner_ready when ok is true")
        if isinstance(diagnostics, list) and diagnostics:
            errors.append("diagnostics must be empty when ok is true")
        if isinstance(reason_codes, list) and reason_codes:
            errors.append("reason_codes must be empty when ok is true")
    if ok is False:
        if verdict != "fail":
            errors.append("verdict must be fail when ok is false")
        if planner_consumability != "planner_blocked":
            errors.append("planner_consumability must be planner_blocked when ok is false")
        if isinstance(diagnostics, list) and not diagnostics:
            errors.append("diagnostics must be non-empty when ok is false")

    processing_behavior = payload.get("processing_behavior")
    if processing_behavior is not None:
        if not isinstance(processing_behavior, Mapping):
            errors.append("processing_behavior must be an object")
        else:
            expected_behavior_keys = {"recommendation", "cross_project_context_usage"}
            behavior_keys = set(processing_behavior.keys())
            missing_behavior = sorted(expected_behavior_keys - behavior_keys)
            if missing_behavior:
                errors.append(f"processing_behavior missing keys: {missing_behavior}")
            unexpected_behavior = sorted(behavior_keys - expected_behavior_keys)
            if unexpected_behavior:
                errors.append(f"processing_behavior has unexpected keys: {unexpected_behavior}")

            recommendation = processing_behavior.get("recommendation")
            if not isinstance(recommendation, Mapping):
                errors.append("processing_behavior.recommendation must be an object")
            else:
                expected_recommendation_keys = {
                    "decision",
                    "rationale",
                    "evidence_refs",
                    "context_project_ids",
                    "mapped_recommendation_ids",
                    "mapped_task_intent_handles",
                    "recommendation_field_completeness",
                    "approved_cross_project_obligations",
                    "open_risks",
                }
                recommendation_keys = set(recommendation.keys())
                missing_recommendation = sorted(expected_recommendation_keys - recommendation_keys)
                if missing_recommendation:
                    errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
                unexpected_recommendation = sorted(recommendation_keys - expected_recommendation_keys)
                if unexpected_recommendation:
                    errors.append(f"processing_behavior.recommendation has unexpected keys: {unexpected_recommendation}")
                for key in ("decision", "rationale"):
                    value = recommendation.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"processing_behavior.recommendation.{key} must be a non-empty string")
                for key in (
                    "evidence_refs",
                    "context_project_ids",
                    "mapped_recommendation_ids",
                    "mapped_task_intent_handles",
                ):
                    value = recommendation.get(key)
                    if not isinstance(value, list):
                        errors.append(f"processing_behavior.recommendation.{key} must be a list")

                completeness = recommendation.get("recommendation_field_completeness")
                if not isinstance(completeness, list):
                    errors.append("processing_behavior.recommendation.recommendation_field_completeness must be a list")
                else:
                    expected_required_fields = sorted(REQUIRED_RECOMMENDATION_FIELDS)
                    for index, row in enumerate(completeness):
                        if not isinstance(row, Mapping):
                            errors.append(
                                "processing_behavior.recommendation.recommendation_field_completeness"
                                f"[{index}] must be an object"
                            )
                            continue
                        expected_row_keys = {
                            "recommendation_id",
                            "required_fields_present",
                            "missing_required_fields",
                            "has_complete_required_fields",
                            "evidence_refs",
                            "has_evidence_refs",
                            "planner_task_intent_handles",
                        }
                        row_keys = set(row.keys())
                        missing_row = sorted(expected_row_keys - row_keys)
                        if missing_row:
                            errors.append(
                                "processing_behavior.recommendation.recommendation_field_completeness"
                                f"[{index}] missing keys: {missing_row}"
                            )
                        unexpected_row = sorted(row_keys - expected_row_keys)
                        if unexpected_row:
                            errors.append(
                                "processing_behavior.recommendation.recommendation_field_completeness"
                                f"[{index}] has unexpected keys: {unexpected_row}"
                            )
                        recommendation_id = row.get("recommendation_id")
                        if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                            errors.append(
                                "processing_behavior.recommendation.recommendation_field_completeness"
                                f"[{index}].recommendation_id must be a non-empty string"
                            )
                        for key in ("required_fields_present", "missing_required_fields", "evidence_refs", "planner_task_intent_handles"):
                            value = row.get(key)
                            if not isinstance(value, list):
                                errors.append(
                                    "processing_behavior.recommendation.recommendation_field_completeness"
                                    f"[{index}].{key} must be a list"
                                )
                        for key in ("has_complete_required_fields", "has_evidence_refs"):
                            value = row.get(key)
                            if not isinstance(value, bool):
                                errors.append(
                                    "processing_behavior.recommendation.recommendation_field_completeness"
                                    f"[{index}].{key} must be a boolean"
                                )
                        required_fields_present = row.get("required_fields_present")
                        missing_required_fields = row.get("missing_required_fields")
                        if isinstance(required_fields_present, list) and isinstance(missing_required_fields, list):
                            normalized_present = sorted(
                                item for item in required_fields_present if isinstance(item, str) and item.strip()
                            )
                            normalized_missing = sorted(
                                item for item in missing_required_fields if isinstance(item, str) and item.strip()
                            )
                            if sorted(normalized_present + normalized_missing) != expected_required_fields:
                                errors.append(
                                    "processing_behavior.recommendation.recommendation_field_completeness"
                                    f"[{index}] must account for all required recommendation fields"
                                )
                            has_complete_required_fields = row.get("has_complete_required_fields")
                            if isinstance(has_complete_required_fields, bool) and has_complete_required_fields != (not normalized_missing):
                                errors.append(
                                    "processing_behavior.recommendation.recommendation_field_completeness"
                                    f"[{index}].has_complete_required_fields must match missing_required_fields emptiness"
                                )
                        evidence_refs = row.get("evidence_refs")
                        has_evidence_refs = row.get("has_evidence_refs")
                        if isinstance(evidence_refs, list) and isinstance(has_evidence_refs, bool):
                            if has_evidence_refs != bool(evidence_refs):
                                errors.append(
                                    "processing_behavior.recommendation.recommendation_field_completeness"
                                    f"[{index}].has_evidence_refs must match evidence_refs emptiness"
                                )

                approved_cross_project_obligations = recommendation.get("approved_cross_project_obligations")
                if not isinstance(approved_cross_project_obligations, list):
                    errors.append("processing_behavior.recommendation.approved_cross_project_obligations must be a list")
                else:
                    for index, row in enumerate(approved_cross_project_obligations):
                        if not isinstance(row, Mapping):
                            errors.append(
                                "processing_behavior.recommendation.approved_cross_project_obligations"
                                f"[{index}] must be an object"
                            )
                            continue
                        expected_obligation_keys = {
                            "obligation_id",
                            "summary",
                            "project_ids",
                            "evidence_refs",
                            "linked_recommendation_ids",
                            "linked_planner_task_intent_handles",
                        }
                        row_keys = set(row.keys())
                        missing_row = sorted(expected_obligation_keys - row_keys)
                        if missing_row:
                            errors.append(
                                "processing_behavior.recommendation.approved_cross_project_obligations"
                                f"[{index}] missing keys: {missing_row}"
                            )
                        unexpected_row = sorted(row_keys - expected_obligation_keys)
                        if unexpected_row:
                            errors.append(
                                "processing_behavior.recommendation.approved_cross_project_obligations"
                                f"[{index}] has unexpected keys: {unexpected_row}"
                            )
                        for key in ("obligation_id", "summary"):
                            value = row.get(key)
                            if not isinstance(value, str) or not value.strip():
                                errors.append(
                                    "processing_behavior.recommendation.approved_cross_project_obligations"
                                    f"[{index}].{key} must be a non-empty string"
                                )
                        for key in ("project_ids", "evidence_refs", "linked_recommendation_ids", "linked_planner_task_intent_handles"):
                            value = row.get(key)
                            if not isinstance(value, list):
                                errors.append(
                                    "processing_behavior.recommendation.approved_cross_project_obligations"
                                    f"[{index}].{key} must be a list"
                                )
                        evidence_refs = row.get("evidence_refs")
                        if isinstance(evidence_refs, list) and not evidence_refs:
                            errors.append(
                                "processing_behavior.recommendation.approved_cross_project_obligations"
                                f"[{index}].evidence_refs must be non-empty"
                            )

                open_risks = recommendation.get("open_risks")
                if not isinstance(open_risks, list):
                    errors.append("processing_behavior.recommendation.open_risks must be a list")
                else:
                    for index, row in enumerate(open_risks):
                        if not isinstance(row, Mapping):
                            errors.append(f"processing_behavior.recommendation.open_risks[{index}] must be an object")
                            continue
                        expected_risk_keys = {
                            "open_risk_id",
                            "source_type",
                            "source_id",
                            "summary",
                            "reason_code",
                            "project_ids",
                            "required_evidence_refs",
                            "evidence_refs",
                            "linked_recommendation_ids",
                            "linked_planner_task_intent_handles",
                        }
                        row_keys = set(row.keys())
                        missing_row = sorted(expected_risk_keys - row_keys)
                        if missing_row:
                            errors.append(f"processing_behavior.recommendation.open_risks[{index}] missing keys: {missing_row}")
                        unexpected_row = sorted(row_keys - expected_risk_keys)
                        if unexpected_row:
                            errors.append(f"processing_behavior.recommendation.open_risks[{index}] has unexpected keys: {unexpected_row}")
                        for key in ("open_risk_id", "source_type", "source_id", "summary", "reason_code"):
                            value = row.get(key)
                            if not isinstance(value, str) or not value.strip():
                                errors.append(
                                    f"processing_behavior.recommendation.open_risks[{index}].{key} must be a non-empty string"
                                )
                        for key in (
                            "project_ids",
                            "required_evidence_refs",
                            "evidence_refs",
                            "linked_recommendation_ids",
                            "linked_planner_task_intent_handles",
                        ):
                            value = row.get(key)
                            if not isinstance(value, list):
                                errors.append(f"processing_behavior.recommendation.open_risks[{index}].{key} must be a list")
                        required_evidence_refs = row.get("required_evidence_refs")
                        if isinstance(required_evidence_refs, list) and not required_evidence_refs:
                            errors.append(
                                f"processing_behavior.recommendation.open_risks[{index}].required_evidence_refs must be non-empty"
                            )

            usage = processing_behavior.get("cross_project_context_usage")
            if not isinstance(usage, Mapping):
                errors.append("processing_behavior.cross_project_context_usage must be an object")
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
                    errors.append(f"processing_behavior.cross_project_context_usage missing keys: {missing_usage}")
                unexpected_usage = sorted(usage_keys - expected_usage_keys)
                if unexpected_usage:
                    errors.append(f"processing_behavior.cross_project_context_usage has unexpected keys: {unexpected_usage}")
                for key in ("cross_project_context_provided", "cross_project_context_used"):
                    value = usage.get(key)
                    if not isinstance(value, bool):
                        errors.append(f"processing_behavior.cross_project_context_usage.{key} must be a boolean")
                for key in ("projects_considered", "earth_sweep_evidence_refs_considered", "recommendation_ids_with_context"):
                    value = usage.get(key)
                    if not isinstance(value, list):
                        errors.append(f"processing_behavior.cross_project_context_usage.{key} must be a list")
                for key in ("cross_project_obligation_count", "unresolved_idea_count"):
                    value = usage.get(key)
                    if not isinstance(value, int) or value < 0:
                        errors.append(f"processing_behavior.cross_project_context_usage.{key} must be a non-negative integer")

    return errors


def _json_stable_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def _req_066_merge_recommendation_field_completeness(
    rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    required_fields = set(REQUIRED_RECOMMENDATION_FIELDS)
    by_recommendation_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        recommendation_id = str(row.get("recommendation_id") or "").strip()
        if not recommendation_id:
            continue
        state = by_recommendation_id.setdefault(
            recommendation_id,
            {
                "required_fields_present": set(),
                "missing_required_fields": set(),
                "evidence_refs": set(),
                "planner_task_intent_handles": set(),
            },
        )
        for field_name in _string_list_from_any(row.get("required_fields_present")):
            if field_name in required_fields:
                state["required_fields_present"].add(field_name)
        for field_name in _string_list_from_any(row.get("missing_required_fields")):
            if field_name in required_fields:
                state["missing_required_fields"].add(field_name)
        for evidence_ref in _string_list_from_any(row.get("evidence_refs")):
            state["evidence_refs"].add(evidence_ref)
        for planner_handle in _string_list_from_any(row.get("planner_task_intent_handles")):
            state["planner_task_intent_handles"].add(planner_handle)

    merged_rows: list[dict[str, Any]] = []
    for recommendation_id in sorted(by_recommendation_id):
        state = by_recommendation_id[recommendation_id]
        missing_required_fields = sorted(state["missing_required_fields"])
        required_fields_present = sorted(
            set(state["required_fields_present"]).union(required_fields - set(missing_required_fields))
        )
        evidence_refs = sorted(state["evidence_refs"])
        planner_task_intent_handles = sorted(state["planner_task_intent_handles"])
        merged_rows.append(
            {
                "recommendation_id": recommendation_id,
                "required_fields_present": required_fields_present,
                "missing_required_fields": missing_required_fields,
                "has_complete_required_fields": not missing_required_fields,
                "evidence_refs": evidence_refs,
                "has_evidence_refs": bool(evidence_refs),
                "planner_task_intent_handles": planner_task_intent_handles,
            }
        )
    return merged_rows


def _req_066_merge_approved_cross_project_obligations(
    rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        obligation_id = str(row.get("obligation_id") or "").strip()
        if not obligation_id:
            continue
        summary = str(row.get("summary") or "").strip()
        state = merged_by_id.setdefault(
            obligation_id,
            {
                "obligation_id": obligation_id,
                "summary": summary,
                "project_ids": set(),
                "evidence_refs": set(),
                "linked_recommendation_ids": set(),
                "linked_planner_task_intent_handles": set(),
            },
        )
        if summary and not str(state["summary"]).strip():
            state["summary"] = summary
        state["project_ids"].update(_string_list_from_any(row.get("project_ids")))
        state["evidence_refs"].update(_string_list_from_any(row.get("evidence_refs")))
        state["linked_recommendation_ids"].update(_string_list_from_any(row.get("linked_recommendation_ids")))
        state["linked_planner_task_intent_handles"].update(
            _string_list_from_any(row.get("linked_planner_task_intent_handles"))
        )

    merged_rows = []
    for obligation_id in sorted(merged_by_id):
        state = merged_by_id[obligation_id]
        merged_rows.append(
            {
                "obligation_id": obligation_id,
                "summary": str(state["summary"]),
                "project_ids": sorted(state["project_ids"]),
                "evidence_refs": sorted(state["evidence_refs"]),
                "linked_recommendation_ids": sorted(state["linked_recommendation_ids"]),
                "linked_planner_task_intent_handles": sorted(state["linked_planner_task_intent_handles"]),
            }
        )
    return merged_rows


def _req_066_merge_open_risks(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        open_risk_id = str(row.get("open_risk_id") or "").strip()
        if not open_risk_id:
            continue
        state = merged_by_id.setdefault(
            open_risk_id,
            {
                "open_risk_id": open_risk_id,
                "source_type": str(row.get("source_type") or "").strip(),
                "source_id": str(row.get("source_id") or "").strip(),
                "summary": str(row.get("summary") or "").strip(),
                "reason_code": str(row.get("reason_code") or "").strip(),
                "project_ids": set(),
                "required_evidence_refs": set(),
                "evidence_refs": set(),
                "linked_recommendation_ids": set(),
                "linked_planner_task_intent_handles": set(),
            },
        )
        state["project_ids"].update(_string_list_from_any(row.get("project_ids")))
        state["required_evidence_refs"].update(_string_list_from_any(row.get("required_evidence_refs")))
        state["evidence_refs"].update(_string_list_from_any(row.get("evidence_refs")))
        state["linked_recommendation_ids"].update(_string_list_from_any(row.get("linked_recommendation_ids")))
        state["linked_planner_task_intent_handles"].update(
            _string_list_from_any(row.get("linked_planner_task_intent_handles"))
        )

    merged_rows = []
    for open_risk_id in sorted(merged_by_id):
        state = merged_by_id[open_risk_id]
        merged_rows.append(
            {
                "open_risk_id": open_risk_id,
                "source_type": str(state["source_type"]),
                "source_id": str(state["source_id"]),
                "summary": str(state["summary"]),
                "reason_code": str(state["reason_code"]),
                "project_ids": sorted(state["project_ids"]),
                "required_evidence_refs": sorted(state["required_evidence_refs"]),
                "evidence_refs": sorted(state["evidence_refs"]),
                "linked_recommendation_ids": sorted(state["linked_recommendation_ids"]),
                "linked_planner_task_intent_handles": sorted(state["linked_planner_task_intent_handles"]),
            }
        )
    return merged_rows


def _req_066_merge_recommendation_processing(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    decisions = []
    evidence_refs: list[str] = []
    context_project_ids: list[str] = []
    mapped_recommendation_ids: list[str] = []
    mapped_task_intent_handles: list[str] = []
    recommendation_field_completeness_rows: list[Mapping[str, Any]] = []
    approved_obligation_rows: list[Mapping[str, Any]] = []
    open_risk_rows: list[Mapping[str, Any]] = []

    for row in rows:
        decision = str(row.get("decision") or "").strip()
        if decision:
            decisions.append(decision)
        evidence_refs.extend(_string_list_from_any(row.get("evidence_refs")))
        context_project_ids.extend(_string_list_from_any(row.get("context_project_ids")))
        mapped_recommendation_ids.extend(_string_list_from_any(row.get("mapped_recommendation_ids")))
        mapped_task_intent_handles.extend(_string_list_from_any(row.get("mapped_task_intent_handles")))
        raw_completeness = row.get("recommendation_field_completeness")
        if isinstance(raw_completeness, list):
            recommendation_field_completeness_rows.extend(
                item for item in raw_completeness if isinstance(item, Mapping)
            )
        raw_approved = row.get("approved_cross_project_obligations")
        if isinstance(raw_approved, list):
            approved_obligation_rows.extend(item for item in raw_approved if isinstance(item, Mapping))
        raw_open_risks = row.get("open_risks")
        if isinstance(raw_open_risks, list):
            open_risk_rows.extend(item for item in raw_open_risks if isinstance(item, Mapping))

    merged_completeness = _req_066_merge_recommendation_field_completeness(recommendation_field_completeness_rows)
    merged_approved = _req_066_merge_approved_cross_project_obligations(approved_obligation_rows)
    merged_open_risks = _req_066_merge_open_risks(open_risk_rows)

    if any(decision == "planner_blocked" for decision in decisions):
        merged_decision = "planner_blocked"
    elif merged_open_risks or any(
        decision in {"planner_ready_with_open_risks", "planning_with_open_risks", "blocked_by_open_risks"}
        for decision in decisions
    ):
        merged_decision = "planner_ready_with_open_risks"
    elif any(decision == "planner_ready" for decision in decisions):
        merged_decision = "planner_ready"
    else:
        merged_decision = "planner_ready_with_open_risks" if merged_open_risks else "planner_ready"

    complete_recommendation_count = sum(1 for row in merged_completeness if row["has_complete_required_fields"])
    recommendations_with_evidence_count = sum(1 for row in merged_completeness if row["has_evidence_refs"])
    rationale = (
        f"validator_processing_behaviors={len(rows)} "
        f"recommendation_rows={len(merged_completeness)} "
        f"complete_recommendations={complete_recommendation_count} "
        f"recommendations_with_evidence={recommendations_with_evidence_count} "
        f"approved={len(merged_approved)} "
        f"open_risks={len(merged_open_risks)}"
    )

    return {
        "decision": merged_decision,
        "rationale": rationale,
        "evidence_refs": _collect_unique_refs(
            evidence_refs,
            *[list(row.get("evidence_refs") or []) for row in merged_approved],
            *[list(row.get("required_evidence_refs") or []) for row in merged_open_risks],
            *[list(row.get("evidence_refs") or []) for row in merged_open_risks],
        ),
        "context_project_ids": sorted(set(context_project_ids)),
        "mapped_recommendation_ids": sorted(set(mapped_recommendation_ids)),
        "mapped_task_intent_handles": sorted(set(mapped_task_intent_handles)),
        "recommendation_field_completeness": merged_completeness,
        "approved_cross_project_obligations": merged_approved,
        "open_risks": merged_open_risks,
    }


def _req_066_merge_cross_project_context_usage(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "cross_project_context_provided": any(bool(row.get("cross_project_context_provided")) for row in rows),
        "cross_project_context_used": any(bool(row.get("cross_project_context_used")) for row in rows),
        "projects_considered": _collect_unique_refs(
            *[
                _string_list_from_any(row.get("projects_considered"))
                for row in rows
            ]
        ),
        "earth_sweep_evidence_refs_considered": _collect_unique_refs(
            *[
                _string_list_from_any(row.get("earth_sweep_evidence_refs_considered"))
                for row in rows
            ]
        ),
        "cross_project_obligation_count": sum(
            max(0, int(row.get("cross_project_obligation_count")))
            for row in rows
            if isinstance(row.get("cross_project_obligation_count"), int)
        ),
        "unresolved_idea_count": sum(
            max(0, int(row.get("unresolved_idea_count")))
            for row in rows
            if isinstance(row.get("unresolved_idea_count"), int)
        ),
        "recommendation_ids_with_context": _collect_unique_refs(
            *[
                _string_list_from_any(row.get("recommendation_ids_with_context"))
                for row in rows
            ]
        ),
    }


def _req_066_build_processing_behavior(validator_outputs: list[dict[str, Any]]) -> dict[str, Any] | None:
    behavior_rows: list[tuple[str, Mapping[str, Any]]] = []
    for row in validator_outputs:
        validator_id = str(row.get("validator_id") or "").strip()
        result = row.get("result")
        if not isinstance(result, Mapping):
            continue
        processing_behavior = result.get("processing_behavior")
        if not isinstance(processing_behavior, Mapping):
            continue
        behavior_rows.append((validator_id, processing_behavior))

    if not behavior_rows:
        return None

    behavior_rows.sort(key=lambda item: item[0])
    if len(behavior_rows) == 1:
        return _json_stable_copy(behavior_rows[0][1])

    recommendation_rows: list[Mapping[str, Any]] = []
    usage_rows: list[Mapping[str, Any]] = []
    for _, processing_behavior in behavior_rows:
        recommendation = processing_behavior.get("recommendation")
        if isinstance(recommendation, Mapping):
            recommendation_rows.append(recommendation)
        usage = processing_behavior.get("cross_project_context_usage")
        if isinstance(usage, Mapping):
            usage_rows.append(usage)

    return {
        "recommendation": _req_066_merge_recommendation_processing(recommendation_rows),
        "cross_project_context_usage": _req_066_merge_cross_project_context_usage(usage_rows),
    }


def _validate_processing_behavior_payload(
    processing_behavior: Any,
    *,
    field_name: str,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(processing_behavior, Mapping):
        return [f"{field_name} must be an object"]

    expected_behavior_keys = {"recommendation", "cross_project_context_usage"}
    behavior_keys = set(processing_behavior.keys())
    missing_behavior = sorted(expected_behavior_keys - behavior_keys)
    if missing_behavior:
        errors.append(f"{field_name} missing keys: {missing_behavior}")
    unexpected_behavior = sorted(behavior_keys - expected_behavior_keys)
    if unexpected_behavior:
        errors.append(f"{field_name} has unexpected keys: {unexpected_behavior}")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append(f"{field_name}.recommendation must be an object")
    else:
        expected_recommendation_keys = {
            "decision",
            "rationale",
            "evidence_refs",
            "context_project_ids",
            "mapped_recommendation_ids",
            "mapped_task_intent_handles",
            "recommendation_field_completeness",
            "approved_cross_project_obligations",
            "open_risks",
        }
        recommendation_keys = set(recommendation.keys())
        missing_recommendation = sorted(expected_recommendation_keys - recommendation_keys)
        if missing_recommendation:
            errors.append(f"{field_name}.recommendation missing keys: {missing_recommendation}")
        unexpected_recommendation = sorted(recommendation_keys - expected_recommendation_keys)
        if unexpected_recommendation:
            errors.append(f"{field_name}.recommendation has unexpected keys: {unexpected_recommendation}")
        for key in ("decision", "rationale"):
            value = recommendation.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{field_name}.recommendation.{key} must be a non-empty string")
        for key in (
            "evidence_refs",
            "context_project_ids",
            "mapped_recommendation_ids",
            "mapped_task_intent_handles",
            "recommendation_field_completeness",
            "approved_cross_project_obligations",
            "open_risks",
        ):
            value = recommendation.get(key)
            if not isinstance(value, list):
                errors.append(f"{field_name}.recommendation.{key} must be a list")

        recommendation_field_completeness = recommendation.get("recommendation_field_completeness")
        if isinstance(recommendation_field_completeness, list):
            for index, row in enumerate(recommendation_field_completeness):
                if not isinstance(row, Mapping):
                    errors.append(
                        f"{field_name}.recommendation.recommendation_field_completeness[{index}] must be an object"
                    )
                    continue
                expected_row_keys = {
                    "recommendation_id",
                    "required_fields_present",
                    "missing_required_fields",
                    "has_complete_required_fields",
                    "evidence_refs",
                    "has_evidence_refs",
                    "planner_task_intent_handles",
                }
                row_keys = set(row.keys())
                missing_row = sorted(expected_row_keys - row_keys)
                if missing_row:
                    errors.append(
                        f"{field_name}.recommendation.recommendation_field_completeness[{index}] missing keys: {missing_row}"
                    )
                unexpected_row = sorted(row_keys - expected_row_keys)
                if unexpected_row:
                    errors.append(
                        f"{field_name}.recommendation.recommendation_field_completeness[{index}] has unexpected keys: {unexpected_row}"
                    )

    usage = processing_behavior.get("cross_project_context_usage")
    if not isinstance(usage, Mapping):
        errors.append(f"{field_name}.cross_project_context_usage must be an object")
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
            errors.append(f"{field_name}.cross_project_context_usage missing keys: {missing_usage}")
        unexpected_usage = sorted(usage_keys - expected_usage_keys)
        if unexpected_usage:
            errors.append(f"{field_name}.cross_project_context_usage has unexpected keys: {unexpected_usage}")
        for key in ("cross_project_context_provided", "cross_project_context_used"):
            value = usage.get(key)
            if not isinstance(value, bool):
                errors.append(f"{field_name}.cross_project_context_usage.{key} must be a boolean")
        for key in (
            "projects_considered",
            "earth_sweep_evidence_refs_considered",
            "recommendation_ids_with_context",
        ):
            value = usage.get(key)
            if not isinstance(value, list):
                errors.append(f"{field_name}.cross_project_context_usage.{key} must be a list")
        for key in ("cross_project_obligation_count", "unresolved_idea_count"):
            value = usage.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"{field_name}.cross_project_context_usage.{key} must be a non-negative integer")

    return errors


def _req_066_validator_registry() -> tuple[dict[str, Any], ...]:
    return (
        {
            "validator_id": "strategy_packet_v1_schema_validator",
            "requirement_id": REQ_060_REQUIREMENT_ID,
            "analysis_type": REQ_060_ANALYSIS_TYPE,
            "builder": build_req_060_strategy_packet_v1_schema_validator,
        },
    )


def build_req_066_validator_runner_and_aggregate_verdict(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build deterministic aggregate validator verdicts for REQ-066."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_066_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_066_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")

    validators: list[dict[str, Any]] = []
    validator_outputs: list[dict[str, Any]] = []
    for definition in _req_066_validator_registry():
        validator_input = dict(raw)
        validator_input["analysis_type"] = definition["analysis_type"]
        result = definition["builder"](validator_input)
        row = {
            "validator_id": definition["validator_id"],
            "requirement_id": definition["requirement_id"],
            "analysis_type": definition["analysis_type"],
            "ok": result["ok"],
            "verdict": result["verdict"],
            "blocking_reason_codes": list(result["reason_codes"]),
            "diagnostic_count": result["diagnostic_count"],
            "summary": result["summary"],
        }
        validators.append(row)
        validator_outputs.append(
            {
                "validator_id": definition["validator_id"],
                "requirement_id": definition["requirement_id"],
                "analysis_type": definition["analysis_type"],
                "row": row,
                "result": result,
            }
        )

    validator_count = len(validators)
    failed_validator_count = sum(1 for row in validators if row["ok"] is False)
    passed_validator_count = validator_count - failed_validator_count
    ok = failed_validator_count == 0
    output_payload = {
        "requirement_id": REQ_066_REQUIREMENT_ID,
        "analysis_type": REQ_066_ANALYSIS_TYPE,
        "checked_at_utc": checked_at_utc,
        "ok": ok,
        "verdict": "pass" if ok else "fail",
        "blocking_reason_codes": sorted(
            {
                reason_code
                for row in validators
                for reason_code in row["blocking_reason_codes"]
            }
        ),
        "validator_count": validator_count,
        "passed_validator_count": passed_validator_count,
        "failed_validator_count": failed_validator_count,
        "summary": (
            "All validators passed; aggregate verdict is pass."
            if ok
            else f"{failed_validator_count} of {validator_count} validators reported blocking failures."
        ),
        "validators": validators,
    }
    processing_behavior = _req_066_build_processing_behavior(validator_outputs)
    if processing_behavior is not None:
        output_payload["processing_behavior"] = processing_behavior

    errors = validate_req_066_validator_runner_and_aggregate_verdict(output_payload)
    if errors:
        raise ValueError(f"built REQ-066 payload failed validation: {errors}")
    return output_payload


def validate_req_066_validator_runner_and_aggregate_verdict(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-066 aggregate validator verdict output shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "requirement_id",
        "analysis_type",
        "checked_at_utc",
        "ok",
        "verdict",
        "blocking_reason_codes",
        "validator_count",
        "passed_validator_count",
        "failed_validator_count",
        "summary",
        "validators",
    }
    optional_top = {"processing_behavior"}
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top - optional_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("requirement_id") != REQ_066_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_066_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_066_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_066_ANALYSIS_TYPE}")
    checked_at_utc = payload.get("checked_at_utc")
    if not isinstance(checked_at_utc, str) or not checked_at_utc.strip():
        errors.append("checked_at_utc must be a non-empty string")
    ok = payload.get("ok")
    if not isinstance(ok, bool):
        errors.append("ok must be a boolean")
    verdict = payload.get("verdict")
    if verdict not in {"pass", "fail"}:
        errors.append("verdict must be pass or fail")

    blocking_reason_codes = payload.get("blocking_reason_codes")
    normalized_aggregate_reason_codes: list[str] = []
    if not isinstance(blocking_reason_codes, list):
        errors.append("blocking_reason_codes must be a list")
    else:
        for index, item in enumerate(blocking_reason_codes):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"blocking_reason_codes[{index}] must be a non-empty string")
                continue
            normalized_aggregate_reason_codes.append(item)
        if normalized_aggregate_reason_codes != sorted(set(normalized_aggregate_reason_codes)):
            errors.append("blocking_reason_codes must be sorted unique strings")

    validator_count = payload.get("validator_count")
    passed_validator_count = payload.get("passed_validator_count")
    failed_validator_count = payload.get("failed_validator_count")
    for field_name, value in (
        ("validator_count", validator_count),
        ("passed_validator_count", passed_validator_count),
        ("failed_validator_count", failed_validator_count),
    ):
        if not isinstance(value, int) or value < 0:
            errors.append(f"{field_name} must be a non-negative integer")

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append("summary must be a non-empty string")

    validators = payload.get("validators")
    normalized_validator_reason_codes: list[str] = []
    if not isinstance(validators, list):
        errors.append("validators must be a list")
    else:
        if not validators:
            errors.append("validators must contain at least one validator result")
        for index, row in enumerate(validators):
            if not isinstance(row, Mapping):
                errors.append(f"validators[{index}] must be an object")
                continue
            expected_row_keys = {
                "validator_id",
                "requirement_id",
                "analysis_type",
                "ok",
                "verdict",
                "blocking_reason_codes",
                "diagnostic_count",
                "summary",
            }
            row_keys = set(row.keys())
            missing_row = sorted(expected_row_keys - row_keys)
            if missing_row:
                errors.append(f"validators[{index}] missing keys: {missing_row}")
            unexpected_row = sorted(row_keys - expected_row_keys)
            if unexpected_row:
                errors.append(f"validators[{index}] has unexpected keys: {unexpected_row}")
            for key in ("validator_id", "requirement_id", "analysis_type", "summary"):
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"validators[{index}].{key} must be a non-empty string")
            row_ok = row.get("ok")
            if not isinstance(row_ok, bool):
                errors.append(f"validators[{index}].ok must be a boolean")
            row_verdict = row.get("verdict")
            if row_verdict not in {"pass", "fail"}:
                errors.append(f"validators[{index}].verdict must be pass or fail")
            row_reason_codes = row.get("blocking_reason_codes")
            normalized_row_reason_codes: list[str] = []
            if not isinstance(row_reason_codes, list):
                errors.append(f"validators[{index}].blocking_reason_codes must be a list")
            else:
                for reason_index, reason_code in enumerate(row_reason_codes):
                    if not isinstance(reason_code, str) or not reason_code.strip():
                        errors.append(
                            f"validators[{index}].blocking_reason_codes[{reason_index}] must be a non-empty string"
                        )
                        continue
                    normalized_row_reason_codes.append(reason_code)
                    normalized_validator_reason_codes.append(reason_code)
                if normalized_row_reason_codes != sorted(set(normalized_row_reason_codes)):
                    errors.append(f"validators[{index}].blocking_reason_codes must be sorted unique strings")
            diagnostic_count = row.get("diagnostic_count")
            if not isinstance(diagnostic_count, int) or diagnostic_count < 0:
                errors.append(f"validators[{index}].diagnostic_count must be a non-negative integer")

            if row_ok is True:
                if row_verdict != "pass":
                    errors.append(f"validators[{index}].verdict must be pass when ok is true")
                if normalized_row_reason_codes:
                    errors.append(f"validators[{index}].blocking_reason_codes must be empty when ok is true")
                if isinstance(diagnostic_count, int) and diagnostic_count != 0:
                    errors.append(f"validators[{index}].diagnostic_count must be 0 when ok is true")
            if row_ok is False:
                if row_verdict != "fail":
                    errors.append(f"validators[{index}].verdict must be fail when ok is false")
                if not normalized_row_reason_codes:
                    errors.append(f"validators[{index}].blocking_reason_codes must be non-empty when ok is false")
                if isinstance(diagnostic_count, int) and diagnostic_count < 1:
                    errors.append(f"validators[{index}].diagnostic_count must be positive when ok is false")

    if isinstance(validators, list) and isinstance(validator_count, int) and validator_count != len(validators):
        errors.append("validator_count must match validators length")
    if (
        isinstance(validator_count, int)
        and isinstance(passed_validator_count, int)
        and isinstance(failed_validator_count, int)
        and passed_validator_count + failed_validator_count != validator_count
    ):
        errors.append("passed_validator_count plus failed_validator_count must equal validator_count")
    if normalized_aggregate_reason_codes and normalized_aggregate_reason_codes != sorted(set(normalized_validator_reason_codes)):
        errors.append("blocking_reason_codes must match the sorted unique validator blocking reason codes")

    if ok is True:
        if verdict != "pass":
            errors.append("verdict must be pass when ok is true")
        if isinstance(failed_validator_count, int) and failed_validator_count != 0:
            errors.append("failed_validator_count must be 0 when ok is true")
        if isinstance(validator_count, int) and isinstance(passed_validator_count, int) and passed_validator_count != validator_count:
            errors.append("passed_validator_count must equal validator_count when ok is true")
        if normalized_aggregate_reason_codes:
            errors.append("blocking_reason_codes must be empty when ok is true")
    if ok is False:
        if verdict != "fail":
            errors.append("verdict must be fail when ok is false")
        if isinstance(failed_validator_count, int) and failed_validator_count < 1:
            errors.append("failed_validator_count must be positive when ok is false")
        if not normalized_aggregate_reason_codes:
            errors.append("blocking_reason_codes must be non-empty when ok is false")

    processing_behavior = payload.get("processing_behavior")
    if processing_behavior is not None:
        errors.extend(
            _validate_processing_behavior_payload(
                processing_behavior,
                field_name="processing_behavior",
            )
        )

    return errors


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type == REQ_054_ANALYSIS_TYPE:
        return build_req_054_recommendation_to_planner_mapping_artifact(payload)
    if analysis_type == REQ_060_ANALYSIS_TYPE:
        return build_req_060_strategy_packet_v1_schema_validator(payload)
    if analysis_type == REQ_066_ANALYSIS_TYPE:
        return build_req_066_validator_runner_and_aggregate_verdict(payload)
    raise ValueError(
        "analysis_type must be one of: "
        f"{REQ_054_ANALYSIS_TYPE}, {REQ_060_ANALYSIS_TYPE}, {REQ_066_ANALYSIS_TYPE}"
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
