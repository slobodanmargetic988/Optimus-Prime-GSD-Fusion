#!/usr/bin/env python3
"""Sweep runtime telemetry artifacts and emit citation-ready source references."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL = "strategy-context-sweep"
TOOL_VERSION = "1.1.0"
ARTIFACT_KEYS = ("runtime_traces", "cycle_summaries")
ANALYSIS_ANCHORS = ("throughput", "blockers", "failure_patterns")
DEFAULT_STALE_AFTER_SECONDS = {
    "runtime_traces": 600,
    "cycle_summaries": 300,
}
DEFAULT_DECISION_POLICY = {"stale": "downgrade", "missing": "exclude"}
ALLOWED_DECISIONS = {"include", "downgrade", "exclude"}
REASON_CODE_BY_FRESHNESS = {
    "fresh": "source_fresh",
    "stale": "stale_source_artifact_detected",
    "missing": "source_artifact_missing",
}
REQ014_ANALYSIS_TYPE = "deficit_and_need_signal_extraction"
REQ014_ANALYSIS_ANCHORS = ("unmet_ecosystem_needs", "high_leverage_fit", "impact", "urgency")
REQ014_DEFAULT_THRESHOLDS = {
    "min_impact_score": 6.0,
    "min_urgency_score": 6.0,
    "min_leverage_ratio": 0.5,
}
REQ014_DEFAULT_MAX_SIGNALS = 5


class SweepError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str = "runtime",
        evidence_refs: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage
        self.evidence_refs = list(evidence_refs or [])


def _as_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _required_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise SweepError("input_error", f"{key} must be an object", stage="input")
    return value


def _required_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise SweepError("input_error", f"{key} must be a list", stage="input")
    return value


def _required_str(payload: dict[str, Any], key: str) -> str:
    text = _as_str(payload.get(key))
    if not text:
        raise SweepError("input_error", f"{key} is required", stage="input")
    return text


def _required_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SweepError("input_error", f"{key} must be a number", stage="input")
    return float(value)


def _parse_input(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise SweepError("input_error", "input must be a JSON object", stage="input")
    return payload


def _parse_now(payload: dict[str, Any]) -> datetime:
    raw = payload.get("now_utc")
    if raw is None:
        return datetime.now(timezone.utc)
    text = _as_str(raw)
    if not text:
        raise SweepError("input_error", "now_utc must be non-empty when provided", stage="input")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SweepError("input_error", f"invalid now_utc timestamp: {exc}", stage="input") from exc
    if dt.tzinfo is None:
        raise SweepError("input_error", "now_utc must include timezone offset", stage="input")
    return dt.astimezone(timezone.utc)


def _to_iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _coerce_threshold_map(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("stale_after_seconds")
    if raw is None:
        return dict(DEFAULT_STALE_AFTER_SECONDS)
    if not isinstance(raw, dict):
        raise SweepError("input_error", "stale_after_seconds must be an object", stage="input")
    out = dict(DEFAULT_STALE_AFTER_SECONDS)
    for key in ARTIFACT_KEYS:
        if key not in raw:
            continue
        value = raw.get(key)
        if not isinstance(value, int) or value < 0:
            raise SweepError(
                "input_error",
                f"stale_after_seconds.{key} must be a non-negative integer",
                stage="input",
            )
        out[key] = value
    return out


def _coerce_decision_policy(payload: dict[str, Any]) -> dict[str, str]:
    raw = payload.get("decision_policy")
    if raw is None:
        return dict(DEFAULT_DECISION_POLICY)
    if not isinstance(raw, dict):
        raise SweepError("input_error", "decision_policy must be an object", stage="input")
    stale = _as_str(raw.get("stale")) or DEFAULT_DECISION_POLICY["stale"]
    missing = _as_str(raw.get("missing")) or DEFAULT_DECISION_POLICY["missing"]
    if stale not in ALLOWED_DECISIONS:
        raise SweepError(
            "input_error",
            "decision_policy.stale must be include|downgrade|exclude",
            stage="input",
        )
    if missing not in ALLOWED_DECISIONS:
        raise SweepError(
            "input_error",
            "decision_policy.missing must be include|downgrade|exclude",
            stage="input",
        )
    return {"stale": stale, "missing": missing}


def _decision_for_freshness(freshness: str, policy: dict[str, str]) -> str:
    if freshness == "fresh":
        return "include"
    if freshness == "stale":
        return policy["stale"]
    return policy["missing"]


def _resolve_artifact_path(project_root: Path, source_path: str) -> Path:
    candidate = Path(source_path).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def _resolve_context_doc_path(raw_path: str, *, base_dir: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def _doc_evidence_ref(kind: str, path: Path, *, project_id: str | None = None) -> str:
    if project_id:
        return f"DOCREF:{kind}:{project_id}:{path}"
    return f"DOCREF:{kind}:{path}"


def _normalize_string_list(values: Any, *, path: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(values, list):
        raise SweepError("input_error", f"{path} must be a list", stage="input")
    out: list[str] = []
    for idx, raw in enumerate(values):
        text = _as_str(raw)
        if not text:
            raise SweepError("input_error", f"{path}[{idx}] must be a non-empty string", stage="input")
        out.append(text)
    if not allow_empty and not out:
        raise SweepError("input_error", f"{path} must be non-empty", stage="input")
    return out


def _normalize_capability_tags(values: Any, *, path: str) -> list[str]:
    tags = _normalize_string_list(values, path=path, allow_empty=False)
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = tag.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _coerce_req014_thresholds(payload: dict[str, Any]) -> dict[str, float]:
    raw = payload.get("thresholds")
    if raw is None:
        return dict(REQ014_DEFAULT_THRESHOLDS)
    if not isinstance(raw, dict):
        raise SweepError("input_error", "thresholds must be an object", stage="input")

    out = dict(REQ014_DEFAULT_THRESHOLDS)
    for key in REQ014_DEFAULT_THRESHOLDS:
        if key not in raw:
            continue
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SweepError("input_error", f"thresholds.{key} must be numeric", stage="input")
        out[key] = float(value)

    if out["min_impact_score"] < 0 or out["min_impact_score"] > 10:
        raise SweepError("input_error", "thresholds.min_impact_score must be between 0 and 10", stage="input")
    if out["min_urgency_score"] < 0 or out["min_urgency_score"] > 10:
        raise SweepError("input_error", "thresholds.min_urgency_score must be between 0 and 10", stage="input")
    if out["min_leverage_ratio"] < 0 or out["min_leverage_ratio"] > 1:
        raise SweepError("input_error", "thresholds.min_leverage_ratio must be between 0 and 1", stage="input")
    return out


def _coerce_req014_max_signals(payload: dict[str, Any]) -> int:
    raw = payload.get("max_signals")
    if raw is None:
        return REQ014_DEFAULT_MAX_SIGNALS
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise SweepError("input_error", "max_signals must be an integer", stage="input")
    if raw <= 0:
        raise SweepError("input_error", "max_signals must be > 0", stage="input")
    return raw


def _validate_req014_target_project(payload: dict[str, Any]) -> dict[str, Any]:
    target = _required_object(payload, "target_project")
    project_id = _required_str(target, "project_id")
    capability_tags = _normalize_capability_tags(target.get("capability_tags"), path="target_project.capability_tags")
    return {
        "project_id": project_id,
        "capability_tags": capability_tags,
    }


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _validate_req014_broad_sweep_context(
    payload: dict[str, Any],
    *,
    target_project_id: str,
) -> dict[str, Any]:
    raw = payload.get("broad_sweep_context")
    if raw is None:
        projects_considered = [target_project_id]
        evidence_refs_by_project = {target_project_id: []}
        cross_project = False
    else:
        if not isinstance(raw, dict):
            raise SweepError("input_error", "broad_sweep_context must be an object", stage="input")

        raw_evidence_refs = raw.get("evidence_refs_by_project")
        if raw_evidence_refs is None:
            raw_evidence_refs = {}
        if not isinstance(raw_evidence_refs, dict):
            raise SweepError("input_error", "broad_sweep_context.evidence_refs_by_project must be an object", stage="input")

        evidence_refs_by_project: dict[str, list[str]] = {}
        for raw_project_id, raw_refs in raw_evidence_refs.items():
            project_id = _as_str(raw_project_id)
            if not project_id:
                raise SweepError(
                    "input_error",
                    "broad_sweep_context.evidence_refs_by_project keys must be non-empty strings",
                    stage="input",
                )
            refs = _normalize_string_list(
                raw_refs,
                path=f"broad_sweep_context.evidence_refs_by_project.{project_id}",
                allow_empty=True,
            )
            evidence_refs_by_project[project_id] = _dedupe_preserve_order(refs)

        raw_projects_considered = raw.get("projects_considered")
        if raw_projects_considered is None:
            projects_considered = list(evidence_refs_by_project.keys())
        else:
            projects_considered = _normalize_string_list(
                raw_projects_considered,
                path="broad_sweep_context.projects_considered",
                allow_empty=True,
            )
            projects_considered = _dedupe_preserve_order(projects_considered)

        for project_id in evidence_refs_by_project:
            if project_id not in projects_considered:
                projects_considered.append(project_id)

        if not projects_considered:
            projects_considered = [target_project_id]
        for project_id in projects_considered:
            evidence_refs_by_project.setdefault(project_id, [])

        raw_cross_project = raw.get("cross_project")
        if raw_cross_project is None:
            cross_project = len(projects_considered) > 1
        elif isinstance(raw_cross_project, bool):
            cross_project = raw_cross_project
        else:
            raise SweepError("input_error", "broad_sweep_context.cross_project must be boolean", stage="input")

    projects_with_evidence_refs = [
        project_id for project_id in projects_considered if evidence_refs_by_project.get(project_id)
    ]
    projects_without_evidence_refs = [
        project_id for project_id in projects_considered if not evidence_refs_by_project.get(project_id)
    ]
    earth_sweep_evidence_refs = _dedupe_preserve_order(
        [
            evidence_ref
            for project_id in projects_considered
            for evidence_ref in evidence_refs_by_project.get(project_id, [])
        ]
    )

    return {
        "cross_project": cross_project,
        "projects_considered": projects_considered,
        "projects_with_evidence_refs": projects_with_evidence_refs,
        "projects_without_evidence_refs": projects_without_evidence_refs,
        "evidence_refs_by_project": evidence_refs_by_project,
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
    }


def _validate_req014_deficits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _required_list(payload, "deficits")
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SweepError("input_error", f"deficits[{idx}] must be an object", stage="input")
        deficit_id = _required_str(row, "deficit_id")
        summary = _required_str(row, "summary")
        impact_score = _required_number(row, "impact_score")
        urgency_score = _required_number(row, "urgency_score")
        if impact_score < 0 or impact_score > 10:
            raise SweepError("input_error", f"deficits[{idx}].impact_score must be between 0 and 10", stage="input")
        if urgency_score < 0 or urgency_score > 10:
            raise SweepError("input_error", f"deficits[{idx}].urgency_score must be between 0 and 10", stage="input")
        required_tags = _normalize_capability_tags(
            row.get("required_capability_tags"),
            path=f"deficits[{idx}].required_capability_tags",
        )
        upstream_refs = _normalize_string_list(
            row.get("evidence_refs"),
            path=f"deficits[{idx}].evidence_refs",
            allow_empty=False,
        )
        out.append(
            {
                "deficit_id": deficit_id,
                "summary": summary,
                "impact_score": impact_score,
                "urgency_score": urgency_score,
                "required_capability_tags": required_tags,
                "upstream_evidence_refs": upstream_refs,
            }
        )
    return out


def _classify_req014_failed_criteria(
    *,
    impact_score: float,
    urgency_score: float,
    leverage_ratio: float,
    thresholds: dict[str, float],
) -> list[str]:
    failed: list[str] = []
    if impact_score < thresholds["min_impact_score"]:
        failed.append("impact_below_threshold")
    if urgency_score < thresholds["min_urgency_score"]:
        failed.append("urgency_below_threshold")
    if leverage_ratio < thresholds["min_leverage_ratio"]:
        failed.append("leverage_below_threshold")
    return failed


def _validate_context_bundle_docs(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get("context_bundle_docs")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SweepError("input_error", "context_bundle_docs must be an object", stage="input")

    base_dir_raw = _as_str(raw.get("base_dir"))
    base_dir = Path(base_dir_raw).expanduser() if base_dir_raw else Path.cwd()
    if not base_dir.is_absolute():
        base_dir = (Path.cwd() / base_dir).resolve()
    else:
        base_dir = base_dir.resolve()

    mission_raw = _as_str(raw.get("mission_path"))
    scope_raw = _as_str(raw.get("scope_path"))
    if not mission_raw or not scope_raw:
        raise SweepError(
            "input_error",
            "context_bundle_docs.mission_path and context_bundle_docs.scope_path are required",
            stage="input",
        )

    mission_path = _resolve_context_doc_path(mission_raw, base_dir=base_dir)
    scope_path = _resolve_context_doc_path(scope_raw, base_dir=base_dir)
    missing_mission_scope_refs: list[str] = []
    if not mission_path.is_file():
        missing_mission_scope_refs.append(_doc_evidence_ref("mission", mission_path))
    if not scope_path.is_file():
        missing_mission_scope_refs.append(_doc_evidence_ref("scope", scope_path))
    if missing_mission_scope_refs:
        raise SweepError(
            "mission_scope_doc_missing",
            "mission/scope context docs must exist for context bundle serialization",
            stage="input",
            evidence_refs=missing_mission_scope_refs,
        )

    peer_docs_raw = raw.get("peer_project_docs")
    if peer_docs_raw is None:
        peer_docs_raw = []
    if not isinstance(peer_docs_raw, list):
        raise SweepError("input_error", "context_bundle_docs.peer_project_docs must be a list", stage="input")
    peer_docs: list[dict[str, str]] = []
    for idx, peer_row in enumerate(peer_docs_raw):
        if not isinstance(peer_row, dict):
            raise SweepError(
                "input_error",
                f"context_bundle_docs.peer_project_docs[{idx}] must be an object",
                stage="input",
            )
        project_id = _as_str(peer_row.get("project_id"))
        peer_path_raw = _as_str(peer_row.get("path"))
        if not project_id or not peer_path_raw:
            raise SweepError(
                "input_error",
                f"context_bundle_docs.peer_project_docs[{idx}] requires project_id and path",
                stage="input",
            )
        peer_path = _resolve_context_doc_path(peer_path_raw, base_dir=base_dir)
        peer_evidence_ref = _doc_evidence_ref("peer", peer_path, project_id=project_id)
        if not peer_path.is_file():
            raise SweepError(
                "peer_project_doc_missing",
                f"peer-project context doc missing for {project_id}: {peer_path}",
                stage="input",
                evidence_refs=[peer_evidence_ref],
            )
        peer_docs.append(
            {
                "project_id": project_id,
                "path": str(peer_path),
                "evidence_ref": peer_evidence_ref,
            }
        )

    return {
        "mission": {
            "path": str(mission_path),
            "evidence_ref": _doc_evidence_ref("mission", mission_path),
        },
        "scope": {
            "path": str(scope_path),
            "evidence_ref": _doc_evidence_ref("scope", scope_path),
        },
        "peer_project_docs": peer_docs,
    }


def _sorted_citation_refs(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["citation_id"]) for row in rows if isinstance(row.get("citation_id"), str)]


def _validate_project_row(row: Any, index: int) -> tuple[str, Path, dict[str, list[dict[str, str]]]]:
    if not isinstance(row, dict):
        raise SweepError("input_error", f"projects[{index}] must be an object", stage="input")
    project_id = _required_str(row, "project_id")
    root_path = Path(_required_str(row, "root_path")).expanduser().resolve()
    artifacts = _required_object(row, "artifacts")
    out: dict[str, list[dict[str, str]]] = {}
    for key in ARTIFACT_KEYS:
        source_rows = artifacts.get(key)
        if not isinstance(source_rows, list) or not source_rows:
            raise SweepError(
                "input_error",
                f"projects[{index}].artifacts.{key} must be a non-empty list",
                stage="input",
            )
        parsed_rows: list[dict[str, str]] = []
        for source_idx, source_row in enumerate(source_rows):
            if not isinstance(source_row, dict):
                raise SweepError(
                    "input_error",
                    f"projects[{index}].artifacts.{key}[{source_idx}] must be an object",
                    stage="input",
                )
            source_id = _required_str(source_row, "source_id")
            source_path = _required_str(source_row, "path")
            parsed_rows.append({"source_id": source_id, "path": source_path})
        out[key] = parsed_rows
    return project_id, root_path, out


def _build_broad_sweep_context(
    *,
    projects_out: list[dict[str, Any]],
    source_references: list[dict[str, Any]],
) -> dict[str, Any]:
    projects_considered = [str(row["project_id"]) for row in projects_out]
    artifact_coverage_by_project: dict[str, dict[str, int]] = {}
    projects_with_missing_sources: list[str] = []
    projects_with_stale_sources: list[str] = []
    projects_with_includable_sources: list[str] = []

    for project_row in projects_out:
        project_id = str(project_row["project_id"])
        counts = project_row["counts"]
        artifact_coverage_by_project[project_id] = {
            artifact_key: len(project_row["artifacts"][artifact_key]) for artifact_key in ARTIFACT_KEYS
        }
        if counts["missing"] > 0:
            projects_with_missing_sources.append(project_id)
        if counts["stale"] > 0:
            projects_with_stale_sources.append(project_id)
        if (counts["include"] + counts["downgrade"]) > 0:
            projects_with_includable_sources.append(project_id)

    evidence_refs_by_project: dict[str, list[str]] = {}
    for project_id in projects_considered:
        refs = [
            str(ref["citation_id"])
            for ref in source_references
            if ref.get("project_id") == project_id and isinstance(ref.get("citation_id"), str)
        ]
        evidence_refs_by_project[project_id] = refs

    return {
        "cross_project": len(projects_considered) > 1,
        "projects_considered": projects_considered,
        "projects_with_includable_sources": projects_with_includable_sources,
        "projects_with_missing_sources": projects_with_missing_sources,
        "projects_with_stale_sources": projects_with_stale_sources,
        "artifact_coverage_by_project": artifact_coverage_by_project,
        "evidence_refs_by_project": evidence_refs_by_project,
    }


def _append_obligation_or_open_risk(
    *,
    obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
    obligation_id: str,
    summary: str,
    evidence_refs: list[str],
    risk_id: str,
    risk_summary: str,
) -> None:
    if evidence_refs:
        obligations.append(
            {
                "obligation_id": obligation_id,
                "summary": summary,
                "evidence_refs": evidence_refs,
            }
        )
        return
    open_risks.append(
        {
            "risk_id": risk_id,
            "summary": risk_summary,
            "evidence_refs": [],
        }
    )


def _build_unhappy_path_rows(source_references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in source_references:
        freshness = _as_str(row.get("freshness"))
        if freshness == "fresh":
            continue
        citation_id = _as_str(row.get("citation_id"))
        reason_code = REASON_CODE_BY_FRESHNESS.get(freshness) or "source_state_unknown"
        out.append(
            {
                "reason_code": reason_code,
                "project_id": _as_str(row.get("project_id")),
                "artifact_type": _as_str(row.get("artifact_type")),
                "source_id": _as_str(row.get("source_id")),
                "evidence_refs": [citation_id] if citation_id else [],
            }
        )
    return out


def _build_context_bundle(
    *,
    checked_at_utc: str,
    broad_sweep_context: dict[str, Any],
    recommendation: dict[str, Any],
    source_references: list[dict[str, Any]],
    unhappy_paths: list[dict[str, Any]],
    context_docs: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "checked_at_utc": checked_at_utc,
        "analysis_anchors": list(ANALYSIS_ANCHORS),
        "broad_sweep_context": broad_sweep_context,
        "recommendation_evidence_refs": list(recommendation.get("evidence_refs") or []),
        "source_reference_ids": _sorted_citation_refs(source_references),
        "unhappy_paths": unhappy_paths,
        "context_docs": context_docs,
    }


def _serialize_context_bundle(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"))


def _build_recommendation(
    *,
    totals: dict[str, int],
    projects_out: list[dict[str, Any]],
    source_references: list[dict[str, Any]],
    broad_sweep_context: dict[str, Any],
) -> dict[str, Any]:
    usable_refs = [ref for ref in source_references if ref.get("exists") is True]
    all_evidence_refs = _sorted_citation_refs(usable_refs)
    stale_refs = _sorted_citation_refs([ref for ref in source_references if ref.get("freshness") == "stale"])
    missing_refs = _sorted_citation_refs([ref for ref in source_references if ref.get("freshness") == "missing"])
    projects_considered = [str(row["project_id"]) for row in projects_out]

    if totals["include"] == 0 and totals["downgrade"] == 0:
        decision = "hold"
    elif totals["missing"] > 0 or totals["stale"] > 0:
        decision = "proceed_with_caution"
    else:
        decision = "proceed"

    rationale = (
        f"Telemetry sweep across {totals['projects']} project(s) produced "
        f"{totals['include']} include, {totals['downgrade']} downgrade, and {totals['exclude']} exclude decisions."
    )

    obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    if stale_refs:
        _append_obligation_or_open_risk(
            obligations=obligations,
            open_risks=open_risks,
            obligation_id="OBL-0001",
            summary="Refresh stale runtime telemetry sources before throughput/blocker trend calls.",
            evidence_refs=stale_refs,
            risk_id="RISK-0001",
            risk_summary="Stale telemetry exists, but no evidence refs were available for follow-up obligations.",
        )
    if missing_refs:
        _append_obligation_or_open_risk(
            obligations=obligations,
            open_risks=open_risks,
            obligation_id="OBL-0002",
            summary="Restore missing runtime telemetry sources to reduce failure-pattern blind spots.",
            evidence_refs=missing_refs,
            risk_id="RISK-0002",
            risk_summary="Missing telemetry exists, but no evidence refs were available for follow-up obligations.",
        )

    if len(projects_considered) > 1:
        under_observed_projects = [
            str(project_row["project_id"])
            for project_row in projects_out
            if (project_row["counts"]["include"] + project_row["counts"]["downgrade"]) == 0
        ]
        if under_observed_projects:
            cross_project_refs = _sorted_citation_refs(
                [
                    ref
                    for ref in source_references
                    if ref.get("project_id") in under_observed_projects and isinstance(ref.get("citation_id"), str)
                ]
            )
            _append_obligation_or_open_risk(
                obligations=obligations,
                open_risks=open_risks,
                obligation_id="OBL-0003",
                summary=(
                    "Close cross-project telemetry coverage gaps before committing Earth-wide throughput conclusions."
                ),
                evidence_refs=cross_project_refs,
                risk_id="RISK-0003",
                risk_summary=(
                    "Cross-project coverage imbalance was detected but had no Earth-sweep evidence refs."
                ),
            )
    else:
        open_risks.append(
            {
                "risk_id": "RISK-0004",
                "summary": (
                    "Cross-project inference is unresolved because sweep input contains fewer than two projects."
                ),
                "evidence_refs": [],
            }
        )

    return {
        "decision": decision,
        "rationale": rationale,
        "evidence_refs": all_evidence_refs,
        "cross_project_context": broad_sweep_context,
        "obligations": obligations,
        "open_risks": open_risks,
    }


def sweep_runtime_telemetry_artifacts(payload: dict[str, Any]) -> dict[str, Any]:
    now_utc = _parse_now(payload)
    thresholds = _coerce_threshold_map(payload)
    decision_policy = _coerce_decision_policy(payload)
    context_docs = _validate_context_bundle_docs(payload)
    projects_in = _required_list(payload, "projects")

    projects_out: list[dict[str, Any]] = []
    source_references: list[dict[str, Any]] = []
    citation_counter = 0
    totals = {
        "projects": 0,
        "sources": 0,
        "fresh": 0,
        "stale": 0,
        "missing": 0,
        "include": 0,
        "downgrade": 0,
        "exclude": 0,
    }

    for index, row in enumerate(projects_in):
        project_id, project_root, artifacts_in = _validate_project_row(row, index)
        project_counts = {
            "sources": 0,
            "fresh": 0,
            "stale": 0,
            "missing": 0,
            "include": 0,
            "downgrade": 0,
            "exclude": 0,
        }
        project_artifacts: dict[str, list[dict[str, Any]]] = {}

        for artifact_key in ARTIFACT_KEYS:
            threshold = thresholds[artifact_key]
            rows_out: list[dict[str, Any]] = []
            for source_row in artifacts_in[artifact_key]:
                source_id = source_row["source_id"]
                resolved_path = _resolve_artifact_path(project_root, source_row["path"])
                exists = resolved_path.is_file()
                if exists:
                    modified = datetime.fromtimestamp(resolved_path.stat().st_mtime, tz=timezone.utc)
                    age_seconds = max(0, int((now_utc - modified).total_seconds()))
                    freshness = "fresh" if age_seconds <= threshold else "stale"
                    last_modified_utc: str | None = _to_iso_utc(modified)
                else:
                    age_seconds = None
                    freshness = "missing"
                    last_modified_utc = None
                decision = _decision_for_freshness(freshness, decision_policy)
                citation_counter += 1
                citation_id = f"SRC-{citation_counter:04d}"
                reason_code = REASON_CODE_BY_FRESHNESS.get(freshness) or "source_state_unknown"
                source_reference = {
                    "citation_id": citation_id,
                    "project_id": project_id,
                    "artifact_type": artifact_key,
                    "source_id": source_id,
                    "path": str(resolved_path),
                    "analysis_anchors": list(ANALYSIS_ANCHORS),
                    "reason_code": reason_code,
                }
                rows_out.append(
                    {
                        "source_id": source_id,
                        "path": str(resolved_path),
                        "exists": exists,
                        "last_modified_utc": last_modified_utc,
                        "age_seconds": age_seconds,
                        "stale_after_seconds": threshold,
                        "freshness": freshness,
                        "decision": decision,
                        "reason_code": reason_code,
                        "evidence_refs": [citation_id],
                        "source_reference": source_reference,
                    }
                )
                source_references.append(
                    {
                        "citation_id": citation_id,
                        "project_id": project_id,
                        "artifact_type": artifact_key,
                        "source_id": source_id,
                        "path": str(resolved_path),
                        "exists": exists,
                        "freshness": freshness,
                        "decision": decision,
                        "reason_code": reason_code,
                    }
                )
                project_counts["sources"] += 1
                project_counts[freshness] += 1
                project_counts[decision] += 1
                totals["sources"] += 1
                totals[freshness] += 1
                totals[decision] += 1
            project_artifacts[artifact_key] = rows_out

        totals["projects"] += 1
        projects_out.append(
            {
                "project_id": project_id,
                "root_path": str(project_root),
                "artifacts": project_artifacts,
                "counts": project_counts,
            }
        )

    broad_sweep_context = _build_broad_sweep_context(
        projects_out=projects_out,
        source_references=source_references,
    )
    recommendation = _build_recommendation(
        totals=totals,
        projects_out=projects_out,
        source_references=source_references,
        broad_sweep_context=broad_sweep_context,
    )
    unhappy_paths = _build_unhappy_path_rows(source_references)
    checked_at_utc = _to_iso_utc(now_utc)
    context_bundle = _build_context_bundle(
        checked_at_utc=checked_at_utc,
        broad_sweep_context=broad_sweep_context,
        recommendation=recommendation,
        source_references=source_references,
        unhappy_paths=unhappy_paths,
        context_docs=context_docs,
    )
    context_bundle_serialized = _serialize_context_bundle(context_bundle)

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "checked_at_utc": checked_at_utc,
        "decision_policy": decision_policy,
        "stale_after_seconds": thresholds,
        "projects": projects_out,
        "source_references": source_references,
        "broad_sweep_context": broad_sweep_context,
        "unhappy_paths": unhappy_paths,
        "context_bundle": context_bundle,
        "context_bundle_serialized": context_bundle_serialized,
        "recommendation": recommendation,
        "totals": totals,
    }


def extract_deficit_and_need_signals(payload: dict[str, Any]) -> dict[str, Any]:
    now_utc = _parse_now(payload)
    checked_at_utc = _to_iso_utc(now_utc)
    thresholds = _coerce_req014_thresholds(payload)
    max_signals = _coerce_req014_max_signals(payload)
    target_project = _validate_req014_target_project(payload)
    broad_sweep_context = _validate_req014_broad_sweep_context(
        payload,
        target_project_id=target_project["project_id"],
    )
    deficits = _validate_req014_deficits(payload)

    target_tags = set(target_project["capability_tags"])
    scored_rows: list[dict[str, Any]] = []
    for row in deficits:
        matched_tags = [tag for tag in row["required_capability_tags"] if tag in target_tags]
        leverage_ratio = round(len(matched_tags) / len(row["required_capability_tags"]), 4)
        priority_score = round(row["impact_score"] * row["urgency_score"], 4)
        failed_criteria = _classify_req014_failed_criteria(
            impact_score=row["impact_score"],
            urgency_score=row["urgency_score"],
            leverage_ratio=leverage_ratio,
            thresholds=thresholds,
        )
        scored_rows.append(
            {
                **row,
                "matched_capability_tags": matched_tags,
                "leverage_ratio": leverage_ratio,
                "priority_score": priority_score,
                "failed_criteria": failed_criteria,
                "eligible": not failed_criteria,
            }
        )

    eligible_rows = sorted(
        [row for row in scored_rows if row["eligible"]],
        key=lambda row: (
            -float(row["priority_score"]),
            -float(row["impact_score"]),
            -float(row["urgency_score"]),
            str(row["deficit_id"]),
        ),
    )

    selected_rows = eligible_rows[:max_signals]
    selected_ids = {str(row["deficit_id"]) for row in selected_rows}

    need_signals: list[dict[str, Any]] = []
    evidence_references: list[dict[str, Any]] = []
    citation_counter = 0
    for idx, row in enumerate(selected_rows, start=1):
        signal_id = f"NEED-{idx:04d}"
        signal_evidence_refs: list[str] = []
        for upstream_ref in row["upstream_evidence_refs"]:
            citation_counter += 1
            citation_id = f"EVD-{citation_counter:04d}"
            signal_evidence_refs.append(citation_id)
            evidence_references.append(
                {
                    "citation_id": citation_id,
                    "signal_id": signal_id,
                    "deficit_id": row["deficit_id"],
                    "upstream_evidence_ref": upstream_ref,
                    "reason_code": "need_signal_supporting_evidence",
                }
            )
        need_signals.append(
            {
                "signal_id": signal_id,
                "deficit_id": row["deficit_id"],
                "summary": row["summary"],
                "impact_score": row["impact_score"],
                "urgency_score": row["urgency_score"],
                "priority_score": row["priority_score"],
                "required_capability_tags": row["required_capability_tags"],
                "matched_capability_tags": row["matched_capability_tags"],
                "leverage_ratio": row["leverage_ratio"],
                "evidence_refs": signal_evidence_refs,
                "reason_code": "eligible_need_signal",
            }
        )

    excluded_deficits: list[dict[str, Any]] = []
    for row in scored_rows:
        deficit_id = str(row["deficit_id"])
        if deficit_id in selected_ids:
            continue
        if row["eligible"]:
            failed_criteria = ["max_signals_cap_reached"]
            reason_code = "max_signals_cap_reached"
        else:
            failed_criteria = list(row["failed_criteria"])
            reason_code = failed_criteria[0] if len(failed_criteria) == 1 else "multiple_threshold_failures"
        excluded_deficits.append(
            {
                "deficit_id": deficit_id,
                "summary": row["summary"],
                "impact_score": row["impact_score"],
                "urgency_score": row["urgency_score"],
                "leverage_ratio": row["leverage_ratio"],
                "failed_criteria": failed_criteria,
                "reason_code": reason_code,
            }
        )

    all_evidence_refs = [str(row["citation_id"]) for row in evidence_references]
    cross_project_evidence_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    recommendation_evidence_refs = _dedupe_preserve_order(all_evidence_refs + cross_project_evidence_refs)
    recommendation_decision = "prioritize_need_signals" if need_signals else "hold"

    obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    if broad_sweep_context["cross_project"]:
        _append_obligation_or_open_risk(
            obligations=obligations,
            open_risks=open_risks,
            obligation_id="OBL-NEED-0001",
            summary="Validate prioritized need signals against Earth-sweep cross-project evidence before execution.",
            evidence_refs=cross_project_evidence_refs,
            risk_id="RISK-NEED-0001",
            risk_summary="Cross-project need validation is unresolved because Earth-sweep evidence refs are missing.",
        )
        missing_projects = list(broad_sweep_context["projects_without_evidence_refs"])
        if missing_projects:
            open_risks.append(
                {
                    "risk_id": "RISK-NEED-0002",
                    "summary": (
                        "Earth-sweep evidence refs are missing for cross-project context rows: "
                        + ", ".join(missing_projects)
                    ),
                    "evidence_refs": [],
                }
            )
    else:
        open_risks.append(
            {
                "risk_id": "RISK-NEED-0003",
                "summary": "Cross-project inference is unresolved because fewer than two projects were provided.",
                "evidence_refs": [],
            }
        )

    recommendation = {
        "decision": recommendation_decision,
        "rationale": (
            f"Need-signal extraction evaluated {len(scored_rows)} deficit(s), "
            f"selected {len(need_signals)} high-leverage signal(s), and excluded "
            f"{len(excluded_deficits)} deficit(s)."
        ),
        "top_signal_id": need_signals[0]["signal_id"] if need_signals else None,
        "evidence_refs": recommendation_evidence_refs,
        "cross_project_context": broad_sweep_context,
        "obligations": obligations,
        "open_risks": open_risks,
    }

    totals = {
        "deficits": len(scored_rows),
        "eligible": len(eligible_rows),
        "signals": len(need_signals),
        "excluded": len(excluded_deficits),
        "evidence_references": len(evidence_references),
    }

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "analysis_type": REQ014_ANALYSIS_TYPE,
        "checked_at_utc": checked_at_utc,
        "analysis_anchors": list(REQ014_ANALYSIS_ANCHORS),
        "target_project": target_project,
        "thresholds": thresholds,
        "max_signals": max_signals,
        "need_signals": need_signals,
        "excluded_deficits": excluded_deficits,
        "evidence_references": evidence_references,
        "recommendation": recommendation,
        "totals": totals,
    }


def run(payload: dict[str, Any]) -> dict[str, Any]:
    analysis_type = _as_str(payload.get("analysis_type"))
    if (
        analysis_type == REQ014_ANALYSIS_TYPE
        or isinstance(payload.get("deficits"), list)
        or isinstance(payload.get("target_project"), dict)
    ):
        return extract_deficit_and_need_signals(payload)
    return sweep_runtime_telemetry_artifacts(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep runtime telemetry artifacts across projects")
    parser.add_argument("--input-json", required=True, help="JSON payload path or '-' for stdin")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _print(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    try:
        payload = _parse_input(args.input_json)
        out = run(payload)
        _print(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except SweepError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "reason_code": exc.code,
            "evidence_refs": exc.evidence_refs,
            "error": {"code": exc.code, "message": exc.message, "stage": exc.stage},
        }
        _print(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "reason_code": "input_error",
            "evidence_refs": [],
            "error": {"code": "input_error", "message": f"invalid JSON input: {exc}", "stage": "input"},
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
