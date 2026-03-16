#!/usr/bin/env python3
"""Contract/data-model surfaces for strategy LLM pipeline calls.

Implemented requirement surfaces:
- REQ-027 Call-2 ecosystem linkage reasoning.
- REQ-030 Call-5 sequencing and lane design reasoning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


REQ_027_SCHEMA_VERSION = "req-027.call-2-ecosystem-linkage-reasoning.v1"
REQ_027_PROCESSING_SCHEMA_VERSION = "req-027.call-2-ecosystem-linkage-processing.v1"
REQ_027_REQUIREMENT_ID = "REQ-027"
REQ_027_ANALYSIS_TYPE = "call_2_ecosystem_linkage_reasoning"
REQ_027_CALL_ID = "call-2"

REQ_030_SCHEMA_VERSION = "req-030.call-5-sequencing-and-lane-design-reasoning.v1"
REQ_030_REQUIREMENT_ID = "REQ-030"
REQ_030_ANALYSIS_TYPE = "call_5_sequencing_and_lane_design_reasoning"
REQ_030_CALL_ID = "call-5"

_CONFIDENCE_TAGS = ("high", "medium", "low")
_DIRECTIONS = ("target_to_peer", "peer_to_target", "bidirectional")
_OBLIGATED_PARTIES = ("target", "peer", "both")
_RISK_LEVELS = ("high", "medium", "low")
_DEPENDS_ON_TYPES = ("recommendation", "external")
_LOG_CHECK_SENTINEL = ".log_size_check.json"
_MAX_LOG_BYTES = 3_000_000_000
_LLM_CALL_TRACE_SCHEMA_VERSION = "optimus-prime.llm-call-trace.v1"
_REQ_027_CALL_2_OBJECTIVE = (
    "Reason about ecosystem links and interaction obligations between the target project and peer projects; "
    "distinguish existing links, missing links, and proposed links with confidence tags; "
    "surface evidence-backed cross-project obligations plus context gaps that block promotion."
)


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


def _normalize_string_list(raw_value: Any, *, field_name: str) -> list[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: set[str] = set()
    for index, item in enumerate(raw_value):
        normalized.add(_require_nonempty_text(item, field_name=f"{field_name}[{index}]"))
    return sorted(normalized)


def _normalize_direction(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "bidirectional"
    direction = _require_nonempty_text(raw_value, field_name=field_name).lower()
    if direction not in _DIRECTIONS:
        raise ValueError(f"{field_name} must be one of: {list(_DIRECTIONS)}")
    return direction


def _normalize_confidence_tag(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        raise ValueError(f"{field_name} must be set to one of: {list(_CONFIDENCE_TAGS)}")
    tag = _require_nonempty_text(raw_value, field_name=field_name).lower()
    if tag not in _CONFIDENCE_TAGS:
        raise ValueError(f"{field_name} must be one of: {list(_CONFIDENCE_TAGS)}")
    return tag


def _normalize_risk_level(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        raise ValueError(f"{field_name} must be set to one of: {list(_RISK_LEVELS)}")
    level = _require_nonempty_text(raw_value, field_name=field_name).lower()
    if level not in _RISK_LEVELS:
        raise ValueError(f"{field_name} must be one of: {list(_RISK_LEVELS)}")
    return level


def _stable_id_fragment(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_ts_line(message: str, *, now_utc: str | None = None) -> str:
    stamp = now_utc.strip() if isinstance(now_utc, str) and now_utc.strip() else _utc_timestamp()
    return f"[{stamp}] {message}"


def _default_log_dir() -> Path:
    return Path.home() / "projects" / "LOGS"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_llm_call_trace_path() -> Path:
    return _repo_root() / "strategy" / "current" / "llm_call_trace.jsonl"


def _default_llm_call_trace_artifacts_dir() -> Path:
    return _repo_root() / "strategy" / "current" / "llm_call_trace_artifacts"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _write_json_artifact(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_row(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def _best_effort_extract_string_refs(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        ref = raw_value.strip()
        return [ref] if ref else []
    if isinstance(raw_value, list):
        out: list[str] = []
        for item in raw_value:
            if item is None:
                continue
            ref = str(item).strip()
            if ref:
                out.append(ref)
        return out
    return []


def _trace_input_refs(
    *,
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    earth_sweep_projects: list[dict[str, Any]],
) -> list[str]:
    refs: set[str] = set()
    refs.update(earth_sweep_evidence_refs)
    for row in cross_project_context:
        refs.update(_best_effort_extract_string_refs(row.get("evidence_refs")))
    for project in earth_sweep_projects:
        for obligation in project.get("obligations") or []:
            if not isinstance(obligation, Mapping):
                continue
            refs.update(_best_effort_extract_string_refs(obligation.get("earth_sweep_evidence_refs")))
            refs.update(_best_effort_extract_string_refs(obligation.get("evidence_refs")))
        for idea in project.get("unresolved_ideas") or []:
            if not isinstance(idea, Mapping):
                continue
            refs.update(_best_effort_extract_string_refs(idea.get("evidence_refs")))
    return sorted(refs)


def _handoff_summary_for_req_027_call_2(result: Mapping[str, Any]) -> str:
    totals = result.get("totals") if isinstance(result.get("totals"), Mapping) else {}
    behavior = result.get("processing_behavior") if isinstance(result.get("processing_behavior"), Mapping) else {}
    recommendation = behavior.get("recommendation") if isinstance(behavior.get("recommendation"), Mapping) else {}
    decision = str(recommendation.get("decision") or "").strip() or "unknown"
    confidence = str(recommendation.get("confidence") or "").strip() or "unknown"
    obligations = recommendation.get("cross_project_obligations") if isinstance(recommendation.get("cross_project_obligations"), list) else []
    risks = recommendation.get("open_risks") if isinstance(recommendation.get("open_risks"), list) else []
    return (
        f"{REQ_027_REQUIREMENT_ID} {REQ_027_CALL_ID} handoff: "
        f"decision={decision} confidence={confidence} "
        f"peers={int(totals.get('peer_projects') or 0)} "
        f"existing={int(totals.get('existing_links') or 0)} "
        f"missing={int(totals.get('missing_links') or 0)} "
        f"proposed={int(totals.get('proposed_links') or 0)} "
        f"obligations={len(obligations)} open_risks={len(risks)}"
    )


def _record_req_027_call_2_llm_call_trace(
    *,
    checked_at_utc: str,
    target_project: Mapping[str, Any],
    peer_projects: list[dict[str, Any]],
    earth_sweep_evidence_refs: list[str],
    earth_sweep_projects: list[dict[str, Any]],
    cross_project_context: list[dict[str, Any]],
    result: Mapping[str, Any],
    trace_path: Path | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    trace_file = trace_path or _default_llm_call_trace_path()
    artifacts_root = artifacts_dir or _default_llm_call_trace_artifacts_dir()
    peer_project_ids = sorted({str(row.get("project_id") or "").strip() for row in peer_projects if row.get("project_id")})

    input_snapshot = {
        "schema_version": "optimus-prime.req-027.call-2-input-snapshot.v1",
        "checked_at_utc": checked_at_utc,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "target_project": dict(target_project),
        "peer_projects": peer_projects,
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
            "earth_sweep_projects": earth_sweep_projects,
            "cross_project_context": cross_project_context,
        },
    }
    output_snapshot = {
        "schema_version": "optimus-prime.req-027.call-2-output-snapshot.v1",
        "checked_at_utc": checked_at_utc,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "result": dict(result),
    }

    input_digest = _sha256_hex(input_snapshot)
    output_digest = _sha256_hex(output_snapshot)
    bundle_dir = artifacts_root / "req-027" / "call-2" / input_digest[:16]
    input_path = bundle_dir / "input.normalized.json"
    output_path = bundle_dir / "output.normalized.json"
    _write_json_artifact(input_path, input_snapshot)
    _write_json_artifact(output_path, output_snapshot)

    input_refs = _trace_input_refs(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        earth_sweep_projects=earth_sweep_projects,
    )
    behavior = result.get("processing_behavior") if isinstance(result.get("processing_behavior"), Mapping) else {}
    usage = behavior.get("context_usage") if isinstance(behavior.get("context_usage"), Mapping) else {}
    output_refs = sorted({str(ref) for ref in (usage.get("evidence_refs_used") or []) if str(ref).strip()})

    row = {
        "schema_version": _LLM_CALL_TRACE_SCHEMA_VERSION,
        "checked_at_utc": checked_at_utc,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "call_objective": _REQ_027_CALL_2_OBJECTIVE,
        "target_project_id": str(target_project.get("project_id") or "").strip(),
        "peer_project_ids": peer_project_ids,
        "input_refs": input_refs,
        "output_refs": output_refs,
        "artifacts": [
            {"kind": "input_snapshot", "path": str(input_path), "sha256": input_digest},
            {"kind": "output_snapshot", "path": str(output_path), "sha256": output_digest},
        ],
        "handoff_summary": _handoff_summary_for_req_027_call_2(result),
        "totals": dict(result.get("totals") or {}) if isinstance(result.get("totals"), Mapping) else {},
    }
    _append_jsonl_row(trace_file, row)
    return row


def _tail_file(path: Path, *, keep_bytes: int) -> bytes:
    if keep_bytes <= 0:
        return b""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - keep_bytes), os.SEEK_SET)
        return handle.read()


def _maybe_truncate_large_logs(log_dir: Path, *, now_utc: str | None = None) -> None:
    """Best-effort log truncation guardrail.

    Only checks periodically (sentinel file) and truncates any single log file
    exceeding ~3GB by keeping the tail so debugging remains possible.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    sentinel = log_dir / _LOG_CHECK_SENTINEL
    now_epoch = int(time.time())
    check_interval_seconds = 6 * 60 * 60  # 6 hours
    last_checked = 0
    if sentinel.exists():
        try:
            payload = json.loads(sentinel.read_text(encoding="utf-8"))
            last_checked = int(payload.get("last_checked_epoch") or 0)
        except (OSError, ValueError, TypeError):
            last_checked = 0

    if last_checked and now_epoch - last_checked < check_interval_seconds:
        return

    checked_files: list[dict[str, Any]] = []
    for path in sorted(log_dir.glob("*.log")):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        truncated = False
        if size > _MAX_LOG_BYTES:
            keep_bytes = 25_000_000  # keep last ~25MB
            try:
                tail = _tail_file(path, keep_bytes=keep_bytes)
                path.write_bytes(tail)
                truncated = True
                size = len(tail)
            except OSError:
                continue
        checked_files.append({"path": str(path), "size_bytes": size, "truncated": truncated})

    sentinel.write_text(
        json.dumps(
            {
                "checked_at_utc": (now_utc or _utc_timestamp()),
                "last_checked_epoch": now_epoch,
                "max_log_bytes": _MAX_LOG_BYTES,
                "files_checked": checked_files,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def make_log_emitter(
    *,
    log_name: str,
    log_dir: Path | None = None,
    now_utc: str | None = None,
) -> Callable[[str], None]:
    """Return an emitter that appends timestamped lines under `~/projects/LOGS/`."""
    directory = log_dir or _default_log_dir()
    _maybe_truncate_large_logs(directory, now_utc=now_utc)
    target = directory / f"{log_name}.log"
    target.parent.mkdir(parents=True, exist_ok=True)

    def emit(message: str) -> None:
        line = _format_ts_line(str(message), now_utc=now_utc)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    return emit


def _normalize_target_project(raw_value: Any) -> dict[str, str]:
    target = _require_mapping(raw_value, field_name="target_project")
    project_id = _require_nonempty_text(target.get("project_id"), field_name="target_project.project_id")
    project_root = _normalize_root(target.get("project_root"), field_name="target_project.project_root")
    normalized = {"project_id": project_id, "project_root": project_root}
    extra = sorted(set(target.keys()) - set(normalized.keys()))
    if extra:
        raise ValueError(f"target_project has unexpected keys: {extra}")
    return normalized


def _normalize_peer_projects(raw_value: Any) -> list[dict[str, str]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("peer_projects must be a non-empty list")
    peers: list[dict[str, str]] = []
    for index, item in enumerate(raw_value):
        peer = _require_mapping(item, field_name=f"peer_projects[{index}]")
        project_id = _require_nonempty_text(peer.get("project_id"), field_name=f"peer_projects[{index}].project_id")
        project_root = _normalize_root(peer.get("project_root"), field_name=f"peer_projects[{index}].project_root")
        row = {"project_id": project_id, "project_root": project_root}
        extra = sorted(set(peer.keys()) - set(row.keys()))
        if extra:
            raise ValueError(f"peer_projects[{index}] has unexpected keys: {extra}")
        peers.append(row)
    peers.sort(key=lambda row: row["project_id"])
    return peers


def _normalize_req_030_constraints(raw_value: Any) -> dict[str, Any]:
    if raw_value is None:
        raise ValueError("constraints must be an object")
    constraints = _require_mapping(raw_value, field_name="constraints")
    max_parallel_lanes = constraints.get("max_parallel_lanes")
    if not isinstance(max_parallel_lanes, int) or max_parallel_lanes <= 0:
        raise ValueError("constraints.max_parallel_lanes must be a positive integer")
    max_active_work_items = constraints.get("max_active_work_items")
    if not isinstance(max_active_work_items, int) or max_active_work_items <= 0:
        raise ValueError("constraints.max_active_work_items must be a positive integer")
    notes = _normalize_string_list(constraints.get("notes"), field_name="constraints.notes")
    normalized = {
        "max_parallel_lanes": max_parallel_lanes,
        "max_active_work_items": max_active_work_items,
        "notes": notes,
    }
    extra = sorted(set(constraints.keys()) - set(normalized.keys()))
    if extra:
        raise ValueError(f"constraints has unexpected keys: {extra}")
    return normalized


def _normalize_req_030_recommendations(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        raise ValueError("recommendations must be a list")
    if not isinstance(raw_value, list):
        raise ValueError("recommendations must be a list")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_value):
        rec = _require_mapping(item, field_name=f"recommendations[{idx}]")
        recommendation_id = _require_nonempty_text(
            rec.get("recommendation_id"),
            field_name=f"recommendations[{idx}].recommendation_id",
        )
        if recommendation_id in seen:
            raise ValueError(
                f"recommendations[{idx}].recommendation_id must be unique (duplicate: {recommendation_id})"
            )
        seen.add(recommendation_id)
        summary = _require_nonempty_text(rec.get("summary"), field_name=f"recommendations[{idx}].summary")
        rationale = _require_nonempty_text(rec.get("rationale"), field_name=f"recommendations[{idx}].rationale")
        expected_impact = _require_nonempty_text(
            rec.get("expected_impact"),
            field_name=f"recommendations[{idx}].expected_impact",
        )
        risk_level = _normalize_risk_level(rec.get("risk_level"), field_name=f"recommendations[{idx}].risk_level")
        row = {
            "recommendation_id": recommendation_id,
            "summary": summary,
            "rationale": rationale,
            "expected_impact": expected_impact,
            "risk_level": risk_level,
        }
        extra = sorted(set(rec.keys()) - set(row.keys()))
        if extra:
            raise ValueError(f"recommendations[{idx}] has unexpected keys: {extra}")
        normalized.append(row)
    normalized.sort(key=lambda r: r["recommendation_id"])
    return normalized


def _normalize_req_030_coordination_dependencies(
    raw_value: Any,
    *,
    field_name: str,
    target_project_id: str,
    parent_kind: str,
    parent_id: str,
    recommendation_ids: set[str],
) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")
    deps: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_value):
        dep = _require_mapping(item, field_name=f"{field_name}[{idx}]")
        dependency_kind = _require_nonempty_text(
            dep.get("dependency_kind"),
            field_name=f"{field_name}[{idx}].dependency_kind",
        )
        depends_on = _require_nonempty_text(dep.get("depends_on"), field_name=f"{field_name}[{idx}].depends_on")
        summary = _require_nonempty_text(dep.get("summary"), field_name=f"{field_name}[{idx}].summary")
        depends_on_type = "recommendation" if depends_on in recommendation_ids else "external"
        dependency_id = (
            f"dep.{_stable_id_fragment(target_project_id, parent_kind, parent_id, depends_on_type, depends_on, dependency_kind, summary)}"
        )
        row = {
            "dependency_id": dependency_id,
            "dependency_kind": dependency_kind,
            "depends_on_type": depends_on_type,
            "depends_on": depends_on,
            "summary": summary,
        }
        extra = sorted(set(dep.keys()) - {"dependency_kind", "depends_on", "summary"})
        if extra:
            raise ValueError(f"{field_name}[{idx}] has unexpected keys: {extra}")
        deps.append(row)
    deps.sort(key=lambda d: (d["depends_on_type"], d["depends_on"], d["dependency_kind"], d["dependency_id"]))
    return deps


def _normalize_req_030_lanes(
    raw_value: Any,
    *,
    target_project_id: str,
    recommendation_ids: set[str],
) -> list[dict[str, Any]]:
    if raw_value is None:
        raise ValueError("lanes must be a list")
    if not isinstance(raw_value, list):
        raise ValueError("lanes must be a list")
    lanes: list[dict[str, Any]] = []
    lane_names_seen: set[str] = set()
    for idx, item in enumerate(raw_value):
        lane = _require_mapping(item, field_name=f"lanes[{idx}]")
        lane_name = _require_nonempty_text(lane.get("lane_name"), field_name=f"lanes[{idx}].lane_name")
        if lane_name in lane_names_seen:
            raise ValueError(f"lanes[{idx}].lane_name must be unique (duplicate: {lane_name})")
        lane_names_seen.add(lane_name)
        lane_kind = _require_nonempty_text(lane.get("lane_kind"), field_name=f"lanes[{idx}].lane_kind")
        lane_goal = _require_nonempty_text(lane.get("lane_goal"), field_name=f"lanes[{idx}].lane_goal")
        why_now = _require_nonempty_text(lane.get("why_now"), field_name=f"lanes[{idx}].why_now")
        raw_recommendation_ids = lane.get("recommendation_ids")
        if not isinstance(raw_recommendation_ids, list) or not raw_recommendation_ids:
            raise ValueError(f"lanes[{idx}].recommendation_ids must be a non-empty list of recommendation ids")
        normalized_rec_ids: list[str] = []
        for ridx, rec_id in enumerate(raw_recommendation_ids):
            rec_text = _require_nonempty_text(rec_id, field_name=f"lanes[{idx}].recommendation_ids[{ridx}]")
            if rec_text not in recommendation_ids:
                raise ValueError(f"lanes[{idx}].recommendation_ids[{ridx}] must be declared in recommendations")
            normalized_rec_ids.append(rec_text)
        normalized_rec_ids = sorted(set(normalized_rec_ids))
        lane_id = f"lane.{_stable_id_fragment(target_project_id, lane_name)}"
        coordination_dependencies = _normalize_req_030_coordination_dependencies(
            lane.get("coordination_dependencies"),
            field_name=f"lanes[{idx}].coordination_dependencies",
            target_project_id=target_project_id,
            parent_kind="lane",
            parent_id=lane_id,
            recommendation_ids=recommendation_ids,
        )
        row = {
            "lane_id": lane_id,
            "lane_name": lane_name,
            "lane_kind": lane_kind,
            "lane_goal": lane_goal,
            "why_now": why_now,
            "recommendation_ids": normalized_rec_ids,
            "coordination_dependencies": coordination_dependencies,
        }
        extra = sorted(
            set(lane.keys())
            - {
                "lane_name",
                "lane_kind",
                "lane_goal",
                "why_now",
                "recommendation_ids",
                "coordination_dependencies",
            }
        )
        if extra:
            raise ValueError(f"lanes[{idx}] has unexpected keys: {extra}")
        lanes.append(row)
    lanes.sort(key=lambda l: (l["lane_name"], l["lane_id"]))
    return lanes


def _normalize_req_030_sequence(
    raw_value: Any,
    *,
    target_project_id: str,
    lanes_by_name: Mapping[str, Mapping[str, Any]],
    recommendation_ids: set[str],
) -> list[dict[str, Any]]:
    if raw_value is None:
        raise ValueError("sequence must be a list")
    if not isinstance(raw_value, list):
        raise ValueError("sequence must be a list")
    sequence_rows: list[dict[str, Any]] = []
    orders_seen: set[int] = set()
    recommendation_seen: set[str] = set()
    for idx, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f"sequence[{idx}]")
        order = row.get("order")
        if not isinstance(order, int) or order <= 0:
            raise ValueError(f"sequence[{idx}].order must be a positive integer")
        if order in orders_seen:
            raise ValueError(f"sequence[{idx}].order must be unique (duplicate: {order})")
        orders_seen.add(order)
        recommendation_id = _require_nonempty_text(
            row.get("recommendation_id"),
            field_name=f"sequence[{idx}].recommendation_id",
        )
        if recommendation_id not in recommendation_ids:
            raise ValueError(f"sequence[{idx}].recommendation_id must be declared in recommendations")
        if recommendation_id in recommendation_seen:
            raise ValueError(f"sequence[{idx}].recommendation_id must be unique (duplicate: {recommendation_id})")
        recommendation_seen.add(recommendation_id)
        lane_name = _require_nonempty_text(row.get("lane_name"), field_name=f"sequence[{idx}].lane_name")
        if lane_name not in lanes_by_name:
            raise ValueError(f"sequence[{idx}].lane_name must match a declared lane")
        why_now = _require_nonempty_text(row.get("why_now"), field_name=f"sequence[{idx}].why_now")
        lane_id = str(lanes_by_name[lane_name].get("lane_id") or "").strip()
        if not lane_id:
            raise ValueError("internal error: lane_id missing while normalizing sequence")
        sequence_id = f"seq.{_stable_id_fragment(target_project_id, recommendation_id, lane_id, str(order))}"
        coordination_dependencies = _normalize_req_030_coordination_dependencies(
            row.get("coordination_dependencies"),
            field_name=f"sequence[{idx}].coordination_dependencies",
            target_project_id=target_project_id,
            parent_kind="sequence_item",
            parent_id=sequence_id,
            recommendation_ids=recommendation_ids,
        )
        normalized = {
            "sequence_id": sequence_id,
            "order": order,
            "recommendation_id": recommendation_id,
            "lane_id": lane_id,
            "lane_name": lane_name,
            "why_now": why_now,
            "coordination_dependencies": coordination_dependencies,
        }
        extra = sorted(
            set(row.keys()) - {"order", "recommendation_id", "lane_name", "why_now", "coordination_dependencies"}
        )
        if extra:
            raise ValueError(f"sequence[{idx}] has unexpected keys: {extra}")
        sequence_rows.append(normalized)
    sequence_rows.sort(key=lambda r: r["order"])
    return sequence_rows


def _normalize_interaction_obligations(
    raw_value: Any,
    *,
    field_name: str,
    target_project_id: str,
    peer_project_id: str,
    link_kind: str,
    direction: str,
) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")
    obligations: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        obligation = _require_mapping(item, field_name=f"{field_name}[{index}]")
        obligated_party = _require_nonempty_text(
            obligation.get("obligated_party"),
            field_name=f"{field_name}[{index}].obligated_party",
        ).lower()
        if obligated_party not in _OBLIGATED_PARTIES:
            raise ValueError(f"{field_name}[{index}].obligated_party must be one of: {list(_OBLIGATED_PARTIES)}")
        summary = _require_nonempty_text(obligation.get("summary"), field_name=f"{field_name}[{index}].summary")
        obligation_kind = _require_nonempty_text(
            obligation.get("obligation_kind"),
            field_name=f"{field_name}[{index}].obligation_kind",
        )
        evidence_refs = _normalize_string_list(
            obligation.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
        )
        obligation_id = f"obl.{_stable_id_fragment(target_project_id, peer_project_id, link_kind, direction, obligation_kind, summary)}"
        row = {
            "obligation_id": obligation_id,
            "obligated_party": obligated_party,
            "obligation_kind": obligation_kind,
            "summary": summary,
            "evidence_refs": evidence_refs,
        }
        extra = sorted(set(obligation.keys()) - {"obligated_party", "obligation_kind", "summary", "evidence_refs"})
        if extra:
            raise ValueError(f"{field_name}[{index}] has unexpected keys: {extra}")
        obligations.append(row)
    obligations.sort(key=lambda row: (row["obligated_party"], row["obligation_kind"], row["obligation_id"]))
    return obligations


def _normalize_link_rows(
    raw_value: Any,
    *,
    field_name: str,
    target_project_id: str,
    peer_project_ids: set[str],
    bucket: str,
) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        link = _require_mapping(item, field_name=f"{field_name}[{index}]")
        peer_project_id = _require_nonempty_text(
            link.get("peer_project_id"),
            field_name=f"{field_name}[{index}].peer_project_id",
        )
        if peer_project_id not in peer_project_ids:
            raise ValueError(f"{field_name}[{index}].peer_project_id must be declared in peer_projects")
        link_kind = _require_nonempty_text(link.get("link_kind"), field_name=f"{field_name}[{index}].link_kind")
        direction = _normalize_direction(link.get("direction"), field_name=f"{field_name}[{index}].direction")
        summary = _require_nonempty_text(link.get("summary"), field_name=f"{field_name}[{index}].summary")
        evidence_refs = _normalize_string_list(
            link.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
        )
        confidence_tag = _normalize_confidence_tag(
            link.get("confidence_tag"),
            field_name=f"{field_name}[{index}].confidence_tag",
        )
        interaction_obligations = _normalize_interaction_obligations(
            link.get("interaction_obligations"),
            field_name=f"{field_name}[{index}].interaction_obligations",
            target_project_id=target_project_id,
            peer_project_id=peer_project_id,
            link_kind=link_kind,
            direction=direction,
        )
        link_id = f"lnk.{_stable_id_fragment(target_project_id, peer_project_id, link_kind, direction, bucket)}"
        row = {
            "link_id": link_id,
            "peer_project_id": peer_project_id,
            "link_kind": link_kind,
            "direction": direction,
            "summary": summary,
            "evidence_refs": evidence_refs,
            "confidence_tag": confidence_tag,
            "interaction_obligations": interaction_obligations,
        }
        extra = sorted(
            set(link.keys())
            - {
                "peer_project_id",
                "link_kind",
                "direction",
                "summary",
                "evidence_refs",
                "confidence_tag",
                "interaction_obligations",
            }
        )
        if extra:
            raise ValueError(f"{field_name}[{index}] has unexpected keys: {extra}")
        normalized.append(row)
    normalized.sort(key=lambda row: (row["peer_project_id"], row["link_kind"], row["direction"], row["link_id"]))
    return normalized


def _normalize_cross_project_context(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("cross_project_context must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        row = _require_mapping(item, field_name=f"cross_project_context[{index}]")
        project_id = _require_nonempty_text(
            row.get("project_id"),
            field_name=f"cross_project_context[{index}].project_id",
        )
        evidence_refs = _normalize_string_list(
            row.get("evidence_refs"),
            field_name=f"cross_project_context[{index}].evidence_refs",
        )
        context_note = ""
        if row.get("context_note") is not None:
            context_note = str(row.get("context_note") or "").strip()
        project_root = ""
        if row.get("project_root") is not None:
            project_root = _normalize_root(
                row.get("project_root"),
                field_name=f"cross_project_context[{index}].project_root",
            )
        normalized.append(
            {
                "project_id": project_id,
                "project_root": project_root,
                "evidence_refs": evidence_refs,
                "context_note": context_note,
            }
        )
    normalized.sort(key=lambda r: (r["project_id"], r["project_root"]))
    return normalized


def _extract_earth_sweep_inputs(raw_value: Any) -> tuple[list[str], list[dict[str, Any]]]:
    """Return (earth_sweep_evidence_refs, earth_sweep_projects)."""
    if raw_value is None:
        return ([], [])
    broad = _require_mapping(raw_value, field_name="broad_sweep_context")

    evidence_refs: list[str] = []
    earth_sweep_projects: list[dict[str, Any]] = []

    if broad.get("earth_sweep_evidence_refs") is not None:
        evidence_refs = _normalize_string_list(
            broad.get("earth_sweep_evidence_refs"),
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
        )

    earth_sweep = broad.get("earth_sweep")
    if earth_sweep is None:
        return (evidence_refs, earth_sweep_projects)

    sweep = _require_mapping(earth_sweep, field_name="broad_sweep_context.earth_sweep")
    if sweep.get("evidence_refs") is not None and not evidence_refs:
        evidence_refs = _normalize_string_list(
            sweep.get("evidence_refs"),
            field_name="broad_sweep_context.earth_sweep.evidence_refs",
        )

    raw_projects = sweep.get("projects")
    if raw_projects is None:
        return (evidence_refs, earth_sweep_projects)
    if not isinstance(raw_projects, list):
        raise ValueError("broad_sweep_context.earth_sweep.projects must be a list")

    for index, item in enumerate(raw_projects):
        project = _require_mapping(item, field_name=f"broad_sweep_context.earth_sweep.projects[{index}]")
        project_id = _require_nonempty_text(
            project.get("project_id"),
            field_name=f"broad_sweep_context.earth_sweep.projects[{index}].project_id",
        )
        obligations = project.get("obligations") or []
        unresolved = project.get("unresolved_ideas") or []
        if not isinstance(obligations, list):
            raise ValueError(f"broad_sweep_context.earth_sweep.projects[{index}].obligations must be a list")
        if not isinstance(unresolved, list):
            raise ValueError(f"broad_sweep_context.earth_sweep.projects[{index}].unresolved_ideas must be a list")
        earth_sweep_projects.append(
            {
                "project_id": project_id,
                "obligations": obligations,
                "unresolved_ideas": unresolved,
            }
        )

    earth_sweep_projects.sort(key=lambda r: r["project_id"])
    return (evidence_refs, earth_sweep_projects)


def _collect_unique_refs(*lists: list[str]) -> list[str]:
    out: set[str] = set()
    for items in lists:
        out.update([str(item) for item in items if str(item).strip()])
    return sorted(out)


def _recommendation_decision(*, recommended_actions: list[dict[str, Any]], open_risks: list[dict[str, Any]]) -> str:
    if open_risks:
        if any(str(row.get("reason_code")) != "missing_earth_sweep_evidence_refs" for row in open_risks):
            return "resolve-context-gaps"
        return "collect-earth-evidence"
    if recommended_actions:
        return "resolve-context-gaps"
    return "insufficient-context"


def _recommendation_rationale(*, decision: str, totals: Mapping[str, Any], open_risks: list[dict[str, Any]]) -> str:
    peer_count = int(totals.get("peer_projects") or 0)
    existing = int(totals.get("existing_links") or 0)
    missing = int(totals.get("missing_links") or 0)
    proposed = int(totals.get("proposed_links") or 0)
    risks = len(open_risks)
    if decision == "proceed":
        return f"links validated (peers={peer_count} existing={existing} proposed={proposed}) with evidence-backed obligations."
    if decision == "proceed-with-open-risks":
        return f"some ecosystem links are evidence-backed, but open risks remain (risks={risks})."
    if decision == "collect-earth-evidence":
        return "ecosystem obligations require Earth-sweep evidence refs before promotion."
    if decision == "resolve-context-gaps":
        return f"context gaps detected while reasoning about ecosystem links (risks={risks})."
    return f"insufficient evidence-backed linkage data (peers={peer_count} existing={existing} missing={missing} proposed={proposed})."


def _recommendation_confidence(*, evidence_refs: list[str], open_risks: list[dict[str, Any]]) -> str:
    if not evidence_refs:
        return "low"
    if open_risks:
        return "medium"
    return "high"


def process_req_027_call_2_ecosystem_linkage_reasoning(
    payload: Mapping[str, Any],
    *,
    emit: Callable[[str], None] | None = None,
    trace_path: str | Path | None = None,
    trace_artifacts_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Implement REQ-027 reasoning/processing behavior using broad-sweep context inputs.

    The strict REQ-027 contract builder remains the source of truth for deterministic
    link/obligation ids. This processor derives input link buckets from Earth-sweep
    context and records unresolved ideas/insufficient evidence as open risks.
    """
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_027_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_027_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    peer_projects = _normalize_peer_projects(raw.get("peer_projects"))
    peer_project_ids = {row["project_id"] for row in peer_projects}

    broad_sweep_context = raw.get("broad_sweep_context")
    earth_sweep_evidence_refs, earth_sweep_projects = _extract_earth_sweep_inputs(broad_sweep_context)
    broad_mapping: Mapping[str, Any] = _require_mapping(broad_sweep_context, field_name="broad_sweep_context") if broad_sweep_context is not None else {}
    cross_project_context = _normalize_cross_project_context(broad_mapping.get("cross_project_context"))
    cross_context_by_project: dict[str, list[dict[str, Any]]] = {}
    for row in cross_project_context:
        cross_context_by_project.setdefault(row["project_id"], []).append(row)
    earth_projects_by_id: dict[str, dict[str, Any]] = {row["project_id"]: row for row in earth_sweep_projects}

    if emit is not None:
        emit(_format_ts_line(f"REQ-027 processing start peers={len(peer_projects)}", now_utc=checked_at_utc))

    existing_links_raw: list[dict[str, Any]] = []
    missing_links_raw: list[dict[str, Any]] = []
    proposed_links_raw: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    for peer in peer_projects:
        peer_id = peer["project_id"]
        cross_rows = cross_context_by_project.get(peer_id, [])
        earth_row = earth_projects_by_id.get(peer_id)

        if cross_rows:
            context_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_rows])
            note = next((row["context_note"] for row in cross_rows if row.get("context_note")), "")
            summary = note or f"Broad-sweep cross-project context references peer project '{peer_id}'."
            combined_refs = _collect_unique_refs(context_refs, earth_sweep_evidence_refs)
            if not combined_refs:
                open_risks.append(
                    {
                        "risk_id": f"risk.{_stable_id_fragment(peer_id, 'uncited-cross-project-context', summary)}",
                        "summary": summary,
                        "reason_code": "uncited_strategic_claim",
                        "required_evidence_refs": [],
                    }
                )
                missing_links_raw.append(
                    {
                        "peer_project_id": peer_id,
                        "link_kind": "cross-project-context",
                        "direction": "bidirectional",
                        "summary": f"Cross-project context for '{peer_id}' is present but has no evidence refs; attach citations before promotion.",
                        "evidence_refs": [],
                        "confidence_tag": "low",
                        "interaction_obligations": [],
                    }
                )
            else:
                existing_links_raw.append(
                    {
                        "peer_project_id": peer_id,
                        "link_kind": "cross-project-context",
                        "direction": "bidirectional",
                        "summary": summary,
                        "evidence_refs": combined_refs,
                        "confidence_tag": "high" if context_refs else "medium",
                        "interaction_obligations": [],
                    }
                )

        if earth_row is not None:
            invalid_obligation_count = 0
            for obligation_index, obligation in enumerate(earth_row.get("obligations") or []):
                if not isinstance(obligation, Mapping):
                    invalid_obligation_count += 1
                    continue

                obligation_summary = str(obligation.get("summary") or "").strip() or (
                    f"Earth-sweep obligation entry #{obligation_index} for '{peer_id}'."
                )
                obligation_refs = _normalize_string_list(
                    obligation.get("earth_sweep_evidence_refs") or obligation.get("evidence_refs"),
                    field_name=f"broad_sweep_context.earth_sweep.projects[project_id={peer_id}].obligations[{obligation_index}].evidence_refs",
                )
                if not obligation_refs:
                    open_risks.append(
                        {
                            "risk_id": f"risk.{_stable_id_fragment(peer_id, 'obligation-missing-evidence', obligation_summary)}",
                            "summary": obligation_summary,
                            "reason_code": "missing_obligation_evidence_refs",
                            "required_evidence_refs": [],
                        }
                    )
                    continue

                if not earth_sweep_evidence_refs:
                    open_risks.append(
                        {
                            "risk_id": f"risk.{_stable_id_fragment(peer_id, 'missing-earth-sweep-evidence', obligation_summary)}",
                            "summary": obligation_summary,
                            "reason_code": "missing_earth_sweep_evidence_refs",
                            "required_evidence_refs": obligation_refs,
                        }
                    )
                    continue

                combined_refs = _collect_unique_refs(obligation_refs, earth_sweep_evidence_refs)
                proposed_links_raw.append(
                    {
                        "peer_project_id": peer_id,
                        "link_kind": "earth-sweep-obligation",
                        "direction": "bidirectional",
                        "summary": obligation_summary,
                        "evidence_refs": combined_refs,
                        "confidence_tag": "medium",
                        "interaction_obligations": [
                            {
                                "obligated_party": "both",
                                "obligation_kind": "coordination",
                                "summary": obligation_summary,
                                "evidence_refs": combined_refs,
                            }
                        ],
                    }
                )

            if invalid_obligation_count:
                open_risks.append(
                    {
                        "risk_id": f"risk.{_stable_id_fragment(peer_id, 'invalid-earth-sweep-obligations', str(invalid_obligation_count))}",
                        "summary": f"Malformed Earth-sweep obligation entries for '{peer_id}' (count={invalid_obligation_count}).",
                        "reason_code": "invalid_earth_sweep_obligation_shape",
                        "required_evidence_refs": earth_sweep_evidence_refs,
                    }
                )

            for idea_index, idea_row in enumerate(earth_row.get("unresolved_ideas") or []):
                if not isinstance(idea_row, Mapping):
                    continue
                idea = str(idea_row.get("idea") or idea_row.get("summary") or "").strip()
                if not idea:
                    continue
                idea_refs = _normalize_string_list(
                    idea_row.get("earth_sweep_evidence_refs") or idea_row.get("evidence_refs"),
                    field_name=f"broad_sweep_context.earth_sweep.projects[project_id={peer_id}].unresolved_ideas[{idea_index}].evidence_refs",
                )
                open_risks.append(
                    {
                        "risk_id": f"risk.{_stable_id_fragment(peer_id, 'unresolved-idea', idea)}",
                        "summary": idea,
                        "reason_code": "unresolved_cross_project_idea",
                        "required_evidence_refs": idea_refs,
                    }
                )

        if not cross_rows and earth_row is None:
            missing_links_raw.append(
                {
                    "peer_project_id": peer_id,
                    "link_kind": "context-missing",
                    "direction": "bidirectional",
                    "summary": f"No Earth-sweep context was supplied for peer project '{peer_id}'.",
                    "evidence_refs": earth_sweep_evidence_refs,
                    "confidence_tag": "low",
                    "interaction_obligations": [],
                }
            )

    contract_payload = build_req_027_call_2_ecosystem_linkage_reasoning(
        {
            "analysis_type": REQ_027_ANALYSIS_TYPE,
            "now_utc": checked_at_utc,
            "target_project": target_project,
            "peer_projects": peer_projects,
            "existing_links": existing_links_raw,
            "missing_links": missing_links_raw,
            "proposed_links": proposed_links_raw,
        }
    )

    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    obligations: list[dict[str, Any]] = []
    link_refs: list[str] = []
    for bucket in ("existing_links", "missing_links", "proposed_links"):
        for link in contract_payload["linkage_reasoning"][bucket]:
            link_refs.extend(link.get("evidence_refs") or [])
            for obligation in link.get("interaction_obligations") or []:
                obligations.append(
                    {
                        "obligation_id": obligation["obligation_id"],
                        "project_id": link["peer_project_id"],
                        "summary": obligation["summary"],
                        "evidence_refs": obligation["evidence_refs"],
                    }
                )
    link_refs = _collect_unique_refs(link_refs)

    recommended_actions: list[dict[str, Any]] = []
    for link in contract_payload["linkage_reasoning"]["missing_links"]:
        action_id = f"action.{_stable_id_fragment('collect-context', link['peer_project_id'], link['link_kind'])}"
        recommended_actions.append(
            {
                "action_id": action_id,
                "summary": f"Collect missing ecosystem linkage context for peer '{link['peer_project_id']}'.",
                "rationale": link["summary"],
                "action_scope": "cross-project",
                "next_step": "Attach Earth-sweep evidence refs and re-run linkage reasoning.",
                "evidence_refs": link.get("evidence_refs") or [],
            }
        )

    missing_links_total = int(contract_payload["totals"].get("missing_links") or 0)
    if missing_links_total:
        missing_link_ids = sorted(
            {str(link.get("link_id") or "") for link in contract_payload["linkage_reasoning"]["missing_links"]}
        )
        open_risks.append(
            {
                "risk_id": f"risk.{_stable_id_fragment('missing-links', json.dumps(missing_link_ids, sort_keys=True))}",
                "summary": f"Missing ecosystem linkage context detected (missing_links={missing_links_total}); resolve gaps before promotion.",
                "reason_code": "analysis_synthesis_contradiction_missing_links",
                "required_evidence_refs": _collect_unique_refs(
                    earth_sweep_evidence_refs,
                    *[
                        _best_effort_extract_string_refs(link.get('evidence_refs'))
                        for link in contract_payload['linkage_reasoning']['missing_links']
                    ],
                ),
            }
        )

    evidence_refs_used = _collect_unique_refs(
        earth_sweep_evidence_refs,
        cross_project_refs,
        link_refs,
        *[row.get("required_evidence_refs") or [] for row in open_risks],
        *[row.get("evidence_refs") or [] for row in recommended_actions],
        *[row.get("evidence_refs") or [] for row in obligations],
    )
    decision = _recommendation_decision(recommended_actions=recommended_actions, open_risks=open_risks)

    processing_behavior = {
        "strategy": "llm-first-broad-sweep",
        "reasoning_mode": "long-thinking",
        "heuristic_summarization_only": False,
        "context_inputs": {
            "target_project": {
                "project_id": target_project["project_id"],
                "project_root": target_project["project_root"],
            },
            "earth_sweep": {
                "evidence_refs": earth_sweep_evidence_refs,
                "projects_considered": sorted(
                    {row["project_id"] for row in earth_sweep_projects if row["project_id"] in peer_project_ids}
                ),
            },
            "cross_project_context": cross_project_context,
        },
        "context_usage": {
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs or earth_sweep_projects),
            "cross_project_context_used": bool(cross_project_context),
            "cross_project_projects_considered": sorted({row["project_id"] for row in cross_project_context}),
            "earth_sweep_refs_used": earth_sweep_evidence_refs,
            "cross_project_refs_used": cross_project_refs,
            "evidence_refs_used": evidence_refs_used,
        },
        "recommendation": {
            "decision": decision,
            "rationale": _recommendation_rationale(
                decision=decision,
                totals=contract_payload["totals"],
                open_risks=open_risks,
            ),
            "confidence": _recommendation_confidence(evidence_refs=evidence_refs_used, open_risks=open_risks),
            "evidence_refs": evidence_refs_used,
            "recommended_actions": recommended_actions,
            "cross_project_obligations": obligations,
            "open_risks": sorted(open_risks, key=lambda r: (r.get("reason_code", ""), r.get("risk_id", ""))),
        },
    }

    if emit is not None:
        emit(_format_ts_line(f"REQ-027 processing decision={decision}", now_utc=checked_at_utc))

    result = {
        "ok": True,
        "schema_version": REQ_027_PROCESSING_SCHEMA_VERSION,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "checked_at_utc": contract_payload["checked_at_utc"],
        "target_project": contract_payload["target_project"],
        "peer_projects": contract_payload["peer_projects"],
        "linkage_reasoning": contract_payload["linkage_reasoning"],
        "totals": contract_payload["totals"],
        "processing_behavior": processing_behavior,
    }
    _record_req_027_call_2_llm_call_trace(
        checked_at_utc=checked_at_utc,
        target_project=target_project,
        peer_projects=peer_projects,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        earth_sweep_projects=[row for row in earth_sweep_projects if row.get("project_id") in peer_project_ids],
        cross_project_context=cross_project_context,
        result=result,
        trace_path=Path(trace_path) if trace_path is not None else None,
        artifacts_dir=Path(trace_artifacts_dir) if trace_artifacts_dir is not None else None,
    )
    return result


def build_req_027_call_2_ecosystem_linkage_reasoning(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-027 payload for ecosystem linkage reasoning."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_027_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_027_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")

    target_project = _normalize_target_project(raw.get("target_project"))
    peer_projects = _normalize_peer_projects(raw.get("peer_projects"))
    peer_project_ids = {row["project_id"] for row in peer_projects}

    existing_links = _normalize_link_rows(
        raw.get("existing_links"),
        field_name="existing_links",
        target_project_id=target_project["project_id"],
        peer_project_ids=peer_project_ids,
        bucket="existing",
    )
    missing_links = _normalize_link_rows(
        raw.get("missing_links"),
        field_name="missing_links",
        target_project_id=target_project["project_id"],
        peer_project_ids=peer_project_ids,
        bucket="missing",
    )
    proposed_links = _normalize_link_rows(
        raw.get("proposed_links"),
        field_name="proposed_links",
        target_project_id=target_project["project_id"],
        peer_project_ids=peer_project_ids,
        bucket="proposed",
    )

    totals = {
        "peer_projects": len(peer_projects),
        "existing_links": len(existing_links),
        "missing_links": len(missing_links),
        "proposed_links": len(proposed_links),
        "interaction_obligations": sum(
            len(row["interaction_obligations"]) for row in (existing_links + missing_links + proposed_links)
        ),
    }

    output_payload = {
        "ok": True,
        "schema_version": REQ_027_SCHEMA_VERSION,
        "requirement_id": REQ_027_REQUIREMENT_ID,
        "analysis_type": REQ_027_ANALYSIS_TYPE,
        "call_id": REQ_027_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "peer_projects": peer_projects,
        "linkage_reasoning": {
            "existing_links": existing_links,
            "missing_links": missing_links,
            "proposed_links": proposed_links,
        },
        "totals": totals,
    }

    errors = validate_req_027_call_2_ecosystem_linkage_reasoning(output_payload)
    if errors:
        raise ValueError(f"built REQ-027 payload failed validation: {errors}")
    return output_payload


def validate_req_027_call_2_ecosystem_linkage_reasoning(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-027 Call-2 ecosystem linkage reasoning payload shape."""
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
        "peer_projects",
        "linkage_reasoning",
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
    if payload.get("schema_version") != REQ_027_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_027_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_027_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_027_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_027_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_027_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_027_CALL_ID:
        errors.append(f"call_id must be {REQ_027_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
        target_project = {}
    else:
        expected_target_keys = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target_keys - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target_keys)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        if not isinstance(target_project.get("project_id"), str) or not str(target_project.get("project_id")).strip():
            errors.append("target_project.project_id must be a non-empty string")
        root = target_project.get("project_root")
        if not isinstance(root, str) or not root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    peer_projects = payload.get("peer_projects")
    peer_project_ids: set[str] = set()
    if not isinstance(peer_projects, list) or not peer_projects:
        errors.append("peer_projects must be a non-empty list")
        peer_projects = []
    else:
        for index, item in enumerate(peer_projects):
            if not isinstance(item, Mapping):
                errors.append(f"peer_projects[{index}] must be an object")
                continue
            expected_peer_keys = {"project_id", "project_root"}
            peer_keys = set(item.keys())
            missing_peer = sorted(expected_peer_keys - peer_keys)
            if missing_peer:
                errors.append(f"peer_projects[{index}] missing keys: {missing_peer}")
            unexpected_peer = sorted(peer_keys - expected_peer_keys)
            if unexpected_peer:
                errors.append(f"peer_projects[{index}] has unexpected keys: {unexpected_peer}")
            project_id = item.get("project_id")
            if not isinstance(project_id, str) or not project_id.strip():
                errors.append(f"peer_projects[{index}].project_id must be a non-empty string")
            else:
                peer_project_ids.add(project_id)
            root = item.get("project_root")
            if not isinstance(root, str) or not root.strip():
                errors.append(f"peer_projects[{index}].project_root must be a non-empty string")
            elif not root.startswith("/"):
                errors.append(f"peer_projects[{index}].project_root must be an absolute path")

    linkage_reasoning = payload.get("linkage_reasoning")
    if not isinstance(linkage_reasoning, Mapping):
        errors.append("linkage_reasoning must be an object")
        return errors

    expected_reasoning_keys = {"existing_links", "missing_links", "proposed_links"}
    reasoning_keys = set(linkage_reasoning.keys())
    missing_reasoning = sorted(expected_reasoning_keys - reasoning_keys)
    if missing_reasoning:
        errors.append(f"linkage_reasoning missing keys: {missing_reasoning}")
    unexpected_reasoning = sorted(reasoning_keys - expected_reasoning_keys)
    if unexpected_reasoning:
        errors.append(f"linkage_reasoning has unexpected keys: {unexpected_reasoning}")

    for bucket in ("existing_links", "missing_links", "proposed_links"):
        rows = linkage_reasoning.get(bucket)
        if not isinstance(rows, list):
            errors.append(f"linkage_reasoning.{bucket} must be a list")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                errors.append(f"linkage_reasoning.{bucket}[{index}] must be an object")
                continue
            expected_link_keys = {
                "link_id",
                "peer_project_id",
                "link_kind",
                "direction",
                "summary",
                "evidence_refs",
                "confidence_tag",
                "interaction_obligations",
            }
            row_keys = set(row.keys())
            missing_link = sorted(expected_link_keys - row_keys)
            if missing_link:
                errors.append(f"linkage_reasoning.{bucket}[{index}] missing keys: {missing_link}")
            unexpected_link = sorted(row_keys - expected_link_keys)
            if unexpected_link:
                errors.append(f"linkage_reasoning.{bucket}[{index}] has unexpected keys: {unexpected_link}")
            link_id = row.get("link_id")
            if not isinstance(link_id, str) or not link_id.startswith("lnk.") or len(link_id) < 6:
                errors.append(f"linkage_reasoning.{bucket}[{index}].link_id must be a string like lnk.<id>")
            peer_project_id = row.get("peer_project_id")
            if not isinstance(peer_project_id, str) or not peer_project_id.strip():
                errors.append(f"linkage_reasoning.{bucket}[{index}].peer_project_id must be a non-empty string")
            elif peer_project_ids and peer_project_id not in peer_project_ids:
                errors.append(
                    f"linkage_reasoning.{bucket}[{index}].peer_project_id must be declared in peer_projects"
                )
            link_kind = row.get("link_kind")
            if not isinstance(link_kind, str) or not link_kind.strip():
                errors.append(f"linkage_reasoning.{bucket}[{index}].link_kind must be a non-empty string")
            direction = row.get("direction")
            if direction not in _DIRECTIONS:
                errors.append(f"linkage_reasoning.{bucket}[{index}].direction must be one of: {list(_DIRECTIONS)}")
            summary = row.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                errors.append(f"linkage_reasoning.{bucket}[{index}].summary must be a non-empty string")
            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list):
                errors.append(f"linkage_reasoning.{bucket}[{index}].evidence_refs must be a list of strings")
            else:
                for ev_index, ev in enumerate(evidence_refs):
                    if not isinstance(ev, str) or not ev.strip():
                        errors.append(
                            f"linkage_reasoning.{bucket}[{index}].evidence_refs[{ev_index}] must be non-empty string"
                        )
            confidence_tag = row.get("confidence_tag")
            if confidence_tag not in _CONFIDENCE_TAGS:
                errors.append(
                    f"linkage_reasoning.{bucket}[{index}].confidence_tag must be one of: {list(_CONFIDENCE_TAGS)}"
                )
            obligations = row.get("interaction_obligations")
            if not isinstance(obligations, list):
                errors.append(f"linkage_reasoning.{bucket}[{index}].interaction_obligations must be a list")
                continue
            for ob_index, obligation in enumerate(obligations):
                if not isinstance(obligation, Mapping):
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}] must be an object"
                    )
                    continue
                expected_ob_keys = {"obligation_id", "obligated_party", "obligation_kind", "summary", "evidence_refs"}
                ob_keys = set(obligation.keys())
                missing_ob = sorted(expected_ob_keys - ob_keys)
                if missing_ob:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}] missing keys: {missing_ob}"
                    )
                unexpected_ob = sorted(ob_keys - expected_ob_keys)
                if unexpected_ob:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}] has unexpected keys: {unexpected_ob}"
                    )
                ob_id = obligation.get("obligation_id")
                if not isinstance(ob_id, str) or not ob_id.startswith("obl.") or len(ob_id) < 6:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].obligation_id must be like obl.<id>"
                    )
                obligated_party = obligation.get("obligated_party")
                if obligated_party not in _OBLIGATED_PARTIES:
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].obligated_party must be one of: {list(_OBLIGATED_PARTIES)}"
                    )
                obligation_kind = obligation.get("obligation_kind")
                if not isinstance(obligation_kind, str) or not obligation_kind.strip():
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].obligation_kind must be a non-empty string"
                    )
                ob_summary = obligation.get("summary")
                if not isinstance(ob_summary, str) or not ob_summary.strip():
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].summary must be a non-empty string"
                    )
                ob_evidence = obligation.get("evidence_refs")
                if not isinstance(ob_evidence, list):
                    errors.append(
                        f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].evidence_refs must be a list of strings"
                    )
                else:
                    for ev_index, ev in enumerate(ob_evidence):
                        if not isinstance(ev, str) or not ev.strip():
                            errors.append(
                                f"linkage_reasoning.{bucket}[{index}].interaction_obligations[{ob_index}].evidence_refs[{ev_index}] must be non-empty string"
                            )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "peer_projects",
            "existing_links",
            "missing_links",
            "proposed_links",
            "interaction_obligations",
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

    return errors


def build_req_030_call_5_sequencing_and_lane_design_reasoning(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-030 payload for Call-5 sequencing and lane design reasoning."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_030_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_030_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")

    target_project = _normalize_target_project(raw.get("target_project"))
    constraints = _normalize_req_030_constraints(raw.get("constraints"))
    recommendations = _normalize_req_030_recommendations(raw.get("recommendations"))
    recommendation_ids = {row["recommendation_id"] for row in recommendations}

    reasoning = _require_mapping(
        raw.get("sequencing_and_lane_design_reasoning"),
        field_name="sequencing_and_lane_design_reasoning",
    )
    lanes = _normalize_req_030_lanes(
        reasoning.get("lanes"),
        target_project_id=target_project["project_id"],
        recommendation_ids=recommendation_ids,
    )
    lanes_by_name = {lane["lane_name"]: lane for lane in lanes}
    sequence = _normalize_req_030_sequence(
        reasoning.get("sequence"),
        target_project_id=target_project["project_id"],
        lanes_by_name=lanes_by_name,
        recommendation_ids=recommendation_ids,
    )
    extra_reasoning = sorted(set(reasoning.keys()) - {"lanes", "sequence"})
    if extra_reasoning:
        raise ValueError(f"sequencing_and_lane_design_reasoning has unexpected keys: {extra_reasoning}")

    lane_deps = sum(len(lane["coordination_dependencies"]) for lane in lanes)
    seq_deps = sum(len(item["coordination_dependencies"]) for item in sequence)
    totals = {
        "recommendations": len(recommendations),
        "lanes": len(lanes),
        "sequence_items": len(sequence),
        "lane_dependencies": lane_deps,
        "sequence_dependencies": seq_deps,
        "total_dependencies": lane_deps + seq_deps,
    }

    output_payload = {
        "ok": True,
        "schema_version": REQ_030_SCHEMA_VERSION,
        "requirement_id": REQ_030_REQUIREMENT_ID,
        "analysis_type": REQ_030_ANALYSIS_TYPE,
        "call_id": REQ_030_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "constraints": constraints,
        "recommendations": recommendations,
        "sequencing_and_lane_design_reasoning": {
            "lanes": lanes,
            "sequence": sequence,
        },
        "totals": totals,
    }

    errors = validate_req_030_call_5_sequencing_and_lane_design_reasoning(output_payload)
    if errors:
        raise ValueError(f"built REQ-030 payload failed validation: {errors}")
    return output_payload


def validate_req_030_call_5_sequencing_and_lane_design_reasoning(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-030 Call-5 sequencing and lane design reasoning payload shape."""
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
        "constraints",
        "recommendations",
        "sequencing_and_lane_design_reasoning",
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
    if payload.get("schema_version") != REQ_030_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_030_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_030_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_030_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_030_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_030_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_030_CALL_ID:
        errors.append(f"call_id must be {REQ_030_CALL_ID}")
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
        project_id = target_project.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            errors.append("target_project.project_id must be a non-empty string")
        else:
            target_project_id = project_id
        root = target_project.get("project_root")
        if not isinstance(root, str) or not root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    constraints = payload.get("constraints")
    if not isinstance(constraints, Mapping):
        errors.append("constraints must be an object")
    else:
        expected_constraint_keys = {"max_parallel_lanes", "max_active_work_items", "notes"}
        constraint_keys = set(constraints.keys())
        missing_constraints = sorted(expected_constraint_keys - constraint_keys)
        if missing_constraints:
            errors.append(f"constraints missing keys: {missing_constraints}")
        unexpected_constraints = sorted(constraint_keys - expected_constraint_keys)
        if unexpected_constraints:
            errors.append(f"constraints has unexpected keys: {unexpected_constraints}")
        for key in ("max_parallel_lanes", "max_active_work_items"):
            value = constraints.get(key)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"constraints.{key} must be a positive integer")
        notes = constraints.get("notes")
        if not isinstance(notes, list):
            errors.append("constraints.notes must be a list of strings")
        else:
            for idx, note in enumerate(notes):
                if not isinstance(note, str) or not note.strip():
                    errors.append(f"constraints.notes[{idx}] must be a non-empty string")

    recommendations = payload.get("recommendations")
    recommendation_ids: set[str] = set()
    if not isinstance(recommendations, list) or not recommendations:
        errors.append("recommendations must be a non-empty list")
    else:
        for idx, rec in enumerate(recommendations):
            if not isinstance(rec, Mapping):
                errors.append(f"recommendations[{idx}] must be an object")
                continue
            expected_rec_keys = {"recommendation_id", "summary", "rationale", "expected_impact", "risk_level"}
            rec_keys = set(rec.keys())
            missing_rec = sorted(expected_rec_keys - rec_keys)
            if missing_rec:
                errors.append(f"recommendations[{idx}] missing keys: {missing_rec}")
            unexpected_rec = sorted(rec_keys - expected_rec_keys)
            if unexpected_rec:
                errors.append(f"recommendations[{idx}] has unexpected keys: {unexpected_rec}")
            rec_id = rec.get("recommendation_id")
            if not isinstance(rec_id, str) or not rec_id.strip():
                errors.append(f"recommendations[{idx}].recommendation_id must be a non-empty string")
            elif rec_id in recommendation_ids:
                errors.append(f"recommendations[{idx}].recommendation_id must be unique (duplicate: {rec_id})")
            else:
                recommendation_ids.add(rec_id)
            for key in ("summary", "rationale", "expected_impact"):
                value = rec.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"recommendations[{idx}].{key} must be a non-empty string")
            risk_level = rec.get("risk_level")
            if risk_level not in _RISK_LEVELS:
                errors.append(f"recommendations[{idx}].risk_level must be one of: {list(_RISK_LEVELS)}")

    reasoning = payload.get("sequencing_and_lane_design_reasoning")
    if not isinstance(reasoning, Mapping):
        errors.append("sequencing_and_lane_design_reasoning must be an object")
        return errors

    expected_reasoning_keys = {"lanes", "sequence"}
    reasoning_keys = set(reasoning.keys())
    missing_reasoning = sorted(expected_reasoning_keys - reasoning_keys)
    if missing_reasoning:
        errors.append(f"sequencing_and_lane_design_reasoning missing keys: {missing_reasoning}")
    unexpected_reasoning = sorted(reasoning_keys - expected_reasoning_keys)
    if unexpected_reasoning:
        errors.append(f"sequencing_and_lane_design_reasoning has unexpected keys: {unexpected_reasoning}")

    lanes = reasoning.get("lanes")
    lanes_by_name: dict[str, Mapping[str, Any]] = {}
    if not isinstance(lanes, list) or not lanes:
        errors.append("sequencing_and_lane_design_reasoning.lanes must be a non-empty list")
        lanes = []
    else:
        for idx, lane in enumerate(lanes):
            if not isinstance(lane, Mapping):
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}] must be an object")
                continue
            expected_lane_keys = {
                "lane_id",
                "lane_name",
                "lane_kind",
                "lane_goal",
                "why_now",
                "recommendation_ids",
                "coordination_dependencies",
            }
            lane_keys = set(lane.keys())
            missing_lane = sorted(expected_lane_keys - lane_keys)
            if missing_lane:
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}] missing keys: {missing_lane}")
            unexpected_lane = sorted(lane_keys - expected_lane_keys)
            if unexpected_lane:
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}] has unexpected keys: {unexpected_lane}")
            lane_id = lane.get("lane_id")
            if not isinstance(lane_id, str) or not lane_id.startswith("lane.") or len(lane_id) < 7:
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].lane_id must be like lane.<id>")
            lane_name = lane.get("lane_name")
            if not isinstance(lane_name, str) or not lane_name.strip():
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].lane_name must be a non-empty string")
            else:
                if lane_name in lanes_by_name:
                    errors.append(
                        f"sequencing_and_lane_design_reasoning.lanes[{idx}].lane_name must be unique (duplicate: {lane_name})"
                    )
                else:
                    lanes_by_name[lane_name] = lane
            for key in ("lane_kind", "lane_goal", "why_now"):
                value = lane.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].{key} must be a non-empty string")
            rec_ids = lane.get("recommendation_ids")
            if not isinstance(rec_ids, list) or not rec_ids:
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].recommendation_ids must be a non-empty list")
            else:
                for ridx, rec_id in enumerate(rec_ids):
                    if not isinstance(rec_id, str) or not rec_id.strip():
                        errors.append(
                            f"sequencing_and_lane_design_reasoning.lanes[{idx}].recommendation_ids[{ridx}] must be a non-empty string"
                        )
                    elif recommendation_ids and rec_id not in recommendation_ids:
                        errors.append(
                            f"sequencing_and_lane_design_reasoning.lanes[{idx}].recommendation_ids[{ridx}] must be declared in recommendations"
                        )
            deps = lane.get("coordination_dependencies")
            if not isinstance(deps, list):
                errors.append(f"sequencing_and_lane_design_reasoning.lanes[{idx}].coordination_dependencies must be a list")
            else:
                for didx, dep in enumerate(deps):
                    _validate_req_030_dependency(
                        dep,
                        errors=errors,
                        field_prefix=f"sequencing_and_lane_design_reasoning.lanes[{idx}].coordination_dependencies[{didx}]",
                    )

    sequence = reasoning.get("sequence")
    orders_seen: set[int] = set()
    recommendation_seen: set[str] = set()
    if not isinstance(sequence, list) or not sequence:
        errors.append("sequencing_and_lane_design_reasoning.sequence must be a non-empty list")
    else:
        for idx, item in enumerate(sequence):
            if not isinstance(item, Mapping):
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}] must be an object")
                continue
            expected_seq_keys = {
                "sequence_id",
                "order",
                "recommendation_id",
                "lane_id",
                "lane_name",
                "why_now",
                "coordination_dependencies",
            }
            seq_keys = set(item.keys())
            missing_seq = sorted(expected_seq_keys - seq_keys)
            if missing_seq:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}] missing keys: {missing_seq}")
            unexpected_seq = sorted(seq_keys - expected_seq_keys)
            if unexpected_seq:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}] has unexpected keys: {unexpected_seq}")
            seq_id = item.get("sequence_id")
            if not isinstance(seq_id, str) or not seq_id.startswith("seq.") or len(seq_id) < 6:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].sequence_id must be like seq.<id>")
            order = item.get("order")
            if not isinstance(order, int) or order <= 0:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].order must be a positive integer")
            elif order in orders_seen:
                errors.append(
                    f"sequencing_and_lane_design_reasoning.sequence[{idx}].order must be unique (duplicate: {order})"
                )
            else:
                orders_seen.add(order)
            rec_id = item.get("recommendation_id")
            if not isinstance(rec_id, str) or not rec_id.strip():
                errors.append(
                    f"sequencing_and_lane_design_reasoning.sequence[{idx}].recommendation_id must be a non-empty string"
                )
            else:
                if recommendation_ids and rec_id not in recommendation_ids:
                    errors.append(
                        f"sequencing_and_lane_design_reasoning.sequence[{idx}].recommendation_id must be declared in recommendations"
                    )
                if rec_id in recommendation_seen:
                    errors.append(
                        f"sequencing_and_lane_design_reasoning.sequence[{idx}].recommendation_id must be unique (duplicate: {rec_id})"
                    )
                else:
                    recommendation_seen.add(rec_id)
            lane_id = item.get("lane_id")
            if not isinstance(lane_id, str) or not lane_id.startswith("lane.") or len(lane_id) < 7:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].lane_id must be like lane.<id>")
            lane_name = item.get("lane_name")
            if not isinstance(lane_name, str) or not lane_name.strip():
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].lane_name must be a non-empty string")
            elif lanes_by_name and lane_name not in lanes_by_name:
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].lane_name must match a declared lane")
            why_now = item.get("why_now")
            if not isinstance(why_now, str) or not why_now.strip():
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].why_now must be a non-empty string")
            deps = item.get("coordination_dependencies")
            if not isinstance(deps, list):
                errors.append(f"sequencing_and_lane_design_reasoning.sequence[{idx}].coordination_dependencies must be a list")
            else:
                for didx, dep in enumerate(deps):
                    _validate_req_030_dependency(
                        dep,
                        errors=errors,
                        field_prefix=f"sequencing_and_lane_design_reasoning.sequence[{idx}].coordination_dependencies[{didx}]",
                    )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "recommendations",
            "lanes",
            "sequence_items",
            "lane_dependencies",
            "sequence_dependencies",
            "total_dependencies",
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

    if target_project_id and not recommendation_ids:
        errors.append("recommendations must be a non-empty list")

    return errors


def _validate_req_030_dependency(raw_value: Any, *, errors: list[str], field_prefix: str) -> None:
    if not isinstance(raw_value, Mapping):
        errors.append(f"{field_prefix} must be an object")
        return
    expected_keys = {"dependency_id", "dependency_kind", "depends_on_type", "depends_on", "summary"}
    keys = set(raw_value.keys())
    missing = sorted(expected_keys - keys)
    if missing:
        errors.append(f"{field_prefix} missing keys: {missing}")
    extra = sorted(keys - expected_keys)
    if extra:
        errors.append(f"{field_prefix} has unexpected keys: {extra}")
    dep_id = raw_value.get("dependency_id")
    if not isinstance(dep_id, str) or not dep_id.startswith("dep.") or len(dep_id) < 6:
        errors.append(f"{field_prefix}.dependency_id must be like dep.<id>")
    dep_kind = raw_value.get("dependency_kind")
    if not isinstance(dep_kind, str) or not dep_kind.strip():
        errors.append(f"{field_prefix}.dependency_kind must be a non-empty string")
    dep_on = raw_value.get("depends_on")
    if not isinstance(dep_on, str) or not dep_on.strip():
        errors.append(f"{field_prefix}.depends_on must be a non-empty string")
    dep_type = raw_value.get("depends_on_type")
    if dep_type not in _DEPENDS_ON_TYPES:
        errors.append(f"{field_prefix}.depends_on_type must be one of: {list(_DEPENDS_ON_TYPES)}")
    summary = raw_value.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append(f"{field_prefix}.summary must be a non-empty string")


def run(payload: dict[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type == REQ_030_ANALYSIS_TYPE:
        return build_req_030_call_5_sequencing_and_lane_design_reasoning(payload)
    if analysis_type and analysis_type != REQ_027_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_027_ANALYSIS_TYPE} or {REQ_030_ANALYSIS_TYPE}")
    return build_req_027_call_2_ecosystem_linkage_reasoning(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strategy LLM pipeline contract surface (REQ-027 Call-2, REQ-030 Call-5)."
    )
    parser.add_argument("--input-json", required=True, help='Input payload path or "-" for stdin.')
    parser.add_argument("--output-json", default="-", help='Output path or "-" for stdout.')
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))

    if args.input_json == "-":
        raw_payload = json.loads(sys.stdin.read())
    else:
        raw_payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    if not isinstance(raw_payload, dict):
        raise SystemExit("input payload must be a JSON object")

    output_payload = run(raw_payload)
    rendered = json.dumps(output_payload, indent=2 if args.json_pretty else None, sort_keys=False)
    if args.output_json == "-":
        print(rendered)
    else:
        target = Path(args.output_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
