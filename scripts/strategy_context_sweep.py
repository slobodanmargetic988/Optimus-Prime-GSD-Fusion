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


class SweepError(Exception):
    def __init__(self, code: str, message: str, *, stage: str = "runtime") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


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
                source_reference = {
                    "citation_id": citation_id,
                    "project_id": project_id,
                    "artifact_type": artifact_key,
                    "source_id": source_id,
                    "path": str(resolved_path),
                    "analysis_anchors": list(ANALYSIS_ANCHORS),
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

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "checked_at_utc": _to_iso_utc(now_utc),
        "decision_policy": decision_policy,
        "stale_after_seconds": thresholds,
        "projects": projects_out,
        "source_references": source_references,
        "broad_sweep_context": broad_sweep_context,
        "recommendation": recommendation,
        "totals": totals,
    }


def run(payload: dict[str, Any]) -> dict[str, Any]:
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
            "error": {"code": "input_error", "message": f"invalid JSON input: {exc}", "stage": "input"},
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
