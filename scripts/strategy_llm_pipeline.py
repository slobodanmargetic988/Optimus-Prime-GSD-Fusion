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
PROCESSING_STRATEGY = "call-1-situational-analysis"
REASONING_MODE = "deterministic-broad-sweep"
ALLOWED_PLANNING_STATUSES = {"ready", "partial", "blocked"}
ALLOWED_RUNTIME_STATUSES = {"healthy", "degraded", "blocked"}
ALLOWED_RECOMMENDATION_SCOPES = {"local", "cross-project"}

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


def _dedupe_preserving_order(rows: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        deduped.append(row)
    return deduped


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


def _normalize_cross_project_context(
    value: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    rows = _require_sequence(value, field_name=field_name)
    normalized: list[dict[str, Any]] = []
    seen_project_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        project_id = _require_nonempty_text(row.get("project_id"), field_name=f"{field_name}[{index}].project_id")
        if project_id in seen_project_ids:
            raise Req026Error(f"{field_name}[{index}].project_id must be unique")
        seen_project_ids.add(project_id)
        normalized.append(
            {
                "project_id": project_id,
                "project_root": _require_nonempty_text(
                    row.get("project_root"),
                    field_name=f"{field_name}[{index}].project_root",
                ),
                "evidence_refs": _normalize_string_list(
                    row.get("evidence_refs", []),
                    field_name=f"{field_name}[{index}].evidence_refs",
                    min_items=0,
                ),
                "context_note": _require_nonempty_text(
                    row.get("context_note"),
                    field_name=f"{field_name}[{index}].context_note",
                ),
            }
        )
    return normalized


def _normalize_candidate_recommendations(
    value: Any,
    *,
    field_name: str,
) -> list[dict[str, Any]]:
    rows = _require_sequence(value, field_name=field_name)
    normalized: list[dict[str, Any]] = []
    seen_recommendation_ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, field_name=f"{field_name}[{index}]")
        recommendation_id = _require_nonempty_text(
            row.get("recommendation_id"),
            field_name=f"{field_name}[{index}].recommendation_id",
        )
        if recommendation_id in seen_recommendation_ids:
            raise Req026Error(f"{field_name}[{index}].recommendation_id must be unique")
        seen_recommendation_ids.add(recommendation_id)

        recommendation_scope = _require_nonempty_text(
            row.get("recommendation_scope"),
            field_name=f"{field_name}[{index}].recommendation_scope",
        ).lower()
        if recommendation_scope not in ALLOWED_RECOMMENDATION_SCOPES:
            raise Req026Error(
                f"{field_name}[{index}].recommendation_scope must be one of {sorted(ALLOWED_RECOMMENDATION_SCOPES)}"
            )

        project_id = _as_text(row.get("project_id"))
        if recommendation_scope == "cross-project":
            project_id = _require_nonempty_text(
                project_id,
                field_name=f"{field_name}[{index}].project_id",
            )
        else:
            project_id = ""

        requires_earth_evidence = row.get("requires_earth_evidence")
        if requires_earth_evidence is None:
            requires_earth_evidence = recommendation_scope == "cross-project"
        if not isinstance(requires_earth_evidence, bool):
            raise Req026Error(f"{field_name}[{index}].requires_earth_evidence must be a boolean")

        normalized.append(
            {
                "recommendation_id": recommendation_id,
                "summary": _require_nonempty_text(
                    row.get("summary"),
                    field_name=f"{field_name}[{index}].summary",
                ),
                "rationale": _require_nonempty_text(
                    row.get("rationale"),
                    field_name=f"{field_name}[{index}].rationale",
                ),
                "recommendation_scope": recommendation_scope,
                "project_id": project_id,
                "requires_earth_evidence": requires_earth_evidence,
                "evidence_refs": _normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"{field_name}[{index}].evidence_refs",
                    min_items=1,
                ),
                "next_step": _require_nonempty_text(
                    row.get("next_step"),
                    field_name=f"{field_name}[{index}].next_step",
                ),
            }
        )
    return normalized


def _normalize_broad_sweep_context(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        container: Mapping[str, Any] = {}
    else:
        container = _require_mapping(value, field_name=field_name)
    return {
        "earth_sweep_evidence_refs": _normalize_string_list(
            container.get("earth_sweep_evidence_refs", []),
            field_name=f"{field_name}.earth_sweep_evidence_refs",
            min_items=0,
        ),
        "cross_project_context": _normalize_cross_project_context(
            container.get("cross_project_context", []),
            field_name=f"{field_name}.cross_project_context",
        ),
        "candidate_recommendations": _normalize_candidate_recommendations(
            container.get("candidate_recommendations", []),
            field_name=f"{field_name}.candidate_recommendations",
        ),
    }


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


def _build_cross_project_context_summary(
    *,
    earth_sweep_evidence_refs: Sequence[str],
    cross_project_context: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    projects_considered = [str(row["project_id"]) for row in cross_project_context]
    projects_with_evidence_refs = [
        str(row["project_id"]) for row in cross_project_context if row.get("evidence_refs")
    ]
    projects_without_evidence_refs = [
        str(row["project_id"]) for row in cross_project_context if not row.get("evidence_refs")
    ]
    evidence_refs_by_project = {
        str(row["project_id"]): list(row.get("evidence_refs", []))
        for row in cross_project_context
    }
    return {
        "cross_project": bool(cross_project_context),
        "projects_considered": projects_considered,
        "projects_with_evidence_refs": projects_with_evidence_refs,
        "projects_without_evidence_refs": projects_without_evidence_refs,
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "evidence_refs_by_project": evidence_refs_by_project,
    }


def _build_processing_behavior(
    *,
    broad_sweep_context: Mapping[str, Any],
    planning_refs: Sequence[str],
    runtime_refs: Sequence[str],
    assessment_status: str,
    unknowns: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    earth_sweep_evidence_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    cross_project_context = list(broad_sweep_context["cross_project_context"])
    candidate_recommendations = list(broad_sweep_context["candidate_recommendations"])
    context_by_project = {
        str(row["project_id"]): row for row in cross_project_context
    }

    recommended_next_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    for row in candidate_recommendations:
        recommendation_id = str(row["recommendation_id"])
        if row["recommendation_scope"] == "local":
            recommended_next_actions.append(
                {
                    "recommendation_id": recommendation_id,
                    "summary": row["summary"],
                    "rationale": row["rationale"],
                    "next_step": row["next_step"],
                    "evidence_refs": list(row["evidence_refs"]),
                }
            )
            continue

        project_id = str(row["project_id"])
        project_context = context_by_project.get(project_id)
        project_evidence_refs = list(project_context.get("evidence_refs", [])) if project_context else []

        missing_reason_codes: list[str] = []
        if row["requires_earth_evidence"] and not earth_sweep_evidence_refs:
            missing_reason_codes.append("missing_earth_sweep_evidence_refs")
        if project_context is None:
            missing_reason_codes.append("missing_cross_project_context")
        elif not project_evidence_refs:
            missing_reason_codes.append("missing_cross_project_context_evidence_refs")

        if missing_reason_codes:
            open_risks.append(
                {
                    "risk_id": f"risk-{recommendation_id}",
                    "reason_code": ",".join(missing_reason_codes),
                    "summary": row["summary"],
                    "required_evidence_refs": _dedupe_preserving_order(
                        list(row["evidence_refs"]) + project_evidence_refs
                    ),
                }
            )
            continue

        cross_project_obligations.append(
            {
                "obligation_id": f"obligation-{recommendation_id}",
                "project_id": project_id,
                "summary": row["summary"],
                "rationale": row["rationale"],
                "next_step": row["next_step"],
                "evidence_refs": _dedupe_preserving_order(
                    list(earth_sweep_evidence_refs) + project_evidence_refs + list(row["evidence_refs"])
                ),
            }
        )

    if assessment_status == "blocked":
        decision = "hold"
        confidence = "low"
    elif open_risks:
        decision = "proceed-with-open-risks"
        confidence = "low" if assessment_status == "needs-follow-up" else "medium"
    elif assessment_status == "needs-follow-up":
        decision = "proceed-with-caution"
        confidence = "medium"
    else:
        decision = "proceed"
        confidence = "high"

    evidence_refs = _dedupe_preserving_order(
        list(planning_refs)
        + list(runtime_refs)
        + list(earth_sweep_evidence_refs)
        + [ref for row in recommended_next_actions for ref in row["evidence_refs"]]
        + [ref for row in cross_project_obligations for ref in row["evidence_refs"]]
        + [ref for row in open_risks for ref in row["required_evidence_refs"]]
    )

    return {
        "strategy": PROCESSING_STRATEGY,
        "reasoning_mode": REASONING_MODE,
        "context_inputs": {
            "broad_sweep_context": {
                "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
                "cross_project_context": cross_project_context,
                "candidate_recommendations": candidate_recommendations,
            }
        },
        "context_usage": {
            "broad_sweep_context_used": bool(
                earth_sweep_evidence_refs or cross_project_context or candidate_recommendations
            ),
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
            "cross_project_context_used": bool(cross_project_context),
            "earth_sweep_evidence_refs_used": earth_sweep_evidence_refs,
            "cross_project_projects_considered": [str(row["project_id"]) for row in cross_project_context],
            "cross_project_projects_with_evidence_refs": [
                str(row["project_id"]) for row in cross_project_context if row.get("evidence_refs")
            ],
            "cross_project_projects_without_evidence_refs": [
                str(row["project_id"]) for row in cross_project_context if not row.get("evidence_refs")
            ],
            "candidate_recommendation_ids_considered": [
                str(row["recommendation_id"]) for row in candidate_recommendations
            ],
            "local_recommendation_ids_emitted": [
                str(row["recommendation_id"]) for row in recommended_next_actions
            ],
            "cross_project_obligation_ids_emitted": [
                str(row["obligation_id"]) for row in cross_project_obligations
            ],
            "open_risk_ids_emitted": [str(row["risk_id"]) for row in open_risks],
            "unknown_ids_for_later_calls": [str(row["unknown_id"]) for row in unknowns],
        },
        "recommendation": {
            "decision": decision,
            "rationale": (
                f"assessment={assessment_status} unknowns={len(unknowns)} "
                f"local={len(recommended_next_actions)} obligations={len(cross_project_obligations)} "
                f"open_risks={len(open_risks)}"
            ),
            "confidence": confidence,
            "evidence_refs": evidence_refs,
            "recommended_next_actions": recommended_next_actions,
            "cross_project_context": _build_cross_project_context_summary(
                earth_sweep_evidence_refs=earth_sweep_evidence_refs,
                cross_project_context=cross_project_context,
            ),
            "cross_project_obligations": cross_project_obligations,
            "open_risks": open_risks,
        },
    }


def build_req_026_call_1_situational_analysis_reasoning(
    *,
    target_project: Mapping[str, Any],
    planning_evidence: Mapping[str, Any],
    runtime_evidence: Mapping[str, Any],
    broad_sweep_context: Mapping[str, Any] | None = None,
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
    normalized_broad_sweep_context = _normalize_broad_sweep_context(
        broad_sweep_context,
        field_name="broad_sweep_context",
    )

    planning_status = _evidence_status(planning_artifacts, category="planning")
    runtime_status = _evidence_status(runtime_artifacts, category="runtime")
    unknowns = _build_unknowns(planning_artifacts=planning_artifacts, runtime_artifacts=runtime_artifacts)
    overall_status = _assessment_status(planning_status=planning_status, runtime_status=runtime_status)

    planning_artifact_ids, planning_refs, planning_signals = _collect_state_details(planning_artifacts)
    runtime_artifact_ids, runtime_refs, runtime_signals = _collect_state_details(runtime_artifacts)
    evidence_basis = planning_artifact_ids + runtime_artifact_ids
    processing_behavior = _build_processing_behavior(
        broad_sweep_context=normalized_broad_sweep_context,
        planning_refs=planning_refs,
        runtime_refs=runtime_refs,
        assessment_status=overall_status,
        unknowns=unknowns,
    )

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
        "processing_behavior": processing_behavior,
        "unknowns": unknowns,
        "source": {
            "planning_artifact_count": len(planning_artifacts),
            "runtime_artifact_count": len(runtime_artifacts),
            "mission_source": mission["source"],
            "scope_source": scope["source"],
            "earth_sweep_evidence_count": len(normalized_broad_sweep_context["earth_sweep_evidence_refs"]),
            "cross_project_context_count": len(normalized_broad_sweep_context["cross_project_context"]),
            "candidate_recommendation_count": len(normalized_broad_sweep_context["candidate_recommendations"]),
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

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        processing_behavior = {}
    if processing_behavior.get("strategy") != PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REASONING_MODE}")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        context_inputs = {}
    broad_sweep_context = context_inputs.get("broad_sweep_context")
    if not isinstance(broad_sweep_context, Mapping):
        errors.append("processing_behavior.context_inputs.broad_sweep_context must be an object")
        broad_sweep_context = {}
    for key in ("earth_sweep_evidence_refs", "cross_project_context", "candidate_recommendations"):
        if not isinstance(broad_sweep_context.get(key), list):
            errors.append(f"processing_behavior.context_inputs.broad_sweep_context.{key} must be an array")

    cross_project_context = broad_sweep_context.get("cross_project_context")
    if isinstance(cross_project_context, list):
        seen_project_ids: set[str] = set()
        for index, row in enumerate(cross_project_context):
            if not isinstance(row, Mapping):
                errors.append(
                    f"processing_behavior.context_inputs.broad_sweep_context.cross_project_context[{index}] must be an object"
                )
                continue
            project_id = _as_text(row.get("project_id"))
            if not project_id:
                errors.append(
                    f"processing_behavior.context_inputs.broad_sweep_context.cross_project_context[{index}].project_id is required"
                )
            elif project_id in seen_project_ids:
                errors.append(f"cross_project_context[{index}].project_id must be unique")
            else:
                seen_project_ids.add(project_id)

    candidate_recommendations = broad_sweep_context.get("candidate_recommendations")
    if isinstance(candidate_recommendations, list):
        seen_recommendation_ids: set[str] = set()
        for index, row in enumerate(candidate_recommendations):
            if not isinstance(row, Mapping):
                errors.append(
                    f"processing_behavior.context_inputs.broad_sweep_context.candidate_recommendations[{index}] must be an object"
                )
                continue
            recommendation_id = _as_text(row.get("recommendation_id"))
            if not recommendation_id:
                errors.append(
                    "processing_behavior.context_inputs.broad_sweep_context."
                    f"candidate_recommendations[{index}].recommendation_id is required"
                )
            elif recommendation_id in seen_recommendation_ids:
                errors.append(f"candidate_recommendations[{index}].recommendation_id must be unique")
            else:
                seen_recommendation_ids.add(recommendation_id)

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
        context_usage = {}
    for key in ("broad_sweep_context_used", "earth_sweep_context_used", "cross_project_context_used"):
        if not isinstance(context_usage.get(key), bool):
            errors.append(f"processing_behavior.context_usage.{key} must be a boolean")
    for key in (
        "earth_sweep_evidence_refs_used",
        "cross_project_projects_considered",
        "cross_project_projects_with_evidence_refs",
        "cross_project_projects_without_evidence_refs",
        "candidate_recommendation_ids_considered",
        "local_recommendation_ids_emitted",
        "cross_project_obligation_ids_emitted",
        "open_risk_ids_emitted",
        "unknown_ids_for_later_calls",
    ):
        value = context_usage.get(key)
        if not isinstance(value, list) or any(not _as_text(item) for item in value):
            errors.append(f"processing_behavior.context_usage.{key} must be a string array")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
        recommendation = {}
    if _as_text(recommendation.get("decision")) not in {
        "proceed",
        "proceed-with-caution",
        "proceed-with-open-risks",
        "hold",
    }:
        errors.append(
            "processing_behavior.recommendation.decision must be proceed, proceed-with-caution, "
            "proceed-with-open-risks, or hold"
        )
    if not _as_text(recommendation.get("rationale")):
        errors.append("processing_behavior.recommendation.rationale is required")
    if _as_text(recommendation.get("confidence")) not in {"high", "medium", "low"}:
        errors.append("processing_behavior.recommendation.confidence must be high, medium, or low")
    recommendation_refs = recommendation.get("evidence_refs")
    if not isinstance(recommendation_refs, list) or not recommendation_refs or any(not _as_text(item) for item in recommendation_refs):
        errors.append("processing_behavior.recommendation.evidence_refs must be a non-empty string array")

    recommended_next_actions = recommendation.get("recommended_next_actions")
    if not isinstance(recommended_next_actions, list):
        errors.append("processing_behavior.recommendation.recommended_next_actions must be an array")
        recommended_next_actions = []
    for index, row in enumerate(recommended_next_actions):
        if not isinstance(row, Mapping):
            errors.append(f"processing_behavior.recommendation.recommended_next_actions[{index}] must be an object")
            continue
        for key in ("recommendation_id", "summary", "rationale", "next_step"):
            if not _as_text(row.get(key)):
                errors.append(
                    f"processing_behavior.recommendation.recommended_next_actions[{index}].{key} is required"
                )
        refs = row.get("evidence_refs")
        if not isinstance(refs, list) or not refs or any(not _as_text(item) for item in refs):
            errors.append(
                f"processing_behavior.recommendation.recommended_next_actions[{index}].evidence_refs "
                "must be a non-empty string array"
            )

    recommendation_cross_project_context = recommendation.get("cross_project_context")
    if not isinstance(recommendation_cross_project_context, Mapping):
        errors.append("processing_behavior.recommendation.cross_project_context must be an object")
        recommendation_cross_project_context = {}
    if not isinstance(recommendation_cross_project_context.get("cross_project"), bool):
        errors.append("processing_behavior.recommendation.cross_project_context.cross_project must be a boolean")
    for key in (
        "projects_considered",
        "projects_with_evidence_refs",
        "projects_without_evidence_refs",
        "earth_sweep_evidence_refs",
    ):
        value = recommendation_cross_project_context.get(key)
        if not isinstance(value, list) or any(not _as_text(item) for item in value):
            errors.append(
                f"processing_behavior.recommendation.cross_project_context.{key} must be a string array"
            )
    evidence_refs_by_project = recommendation_cross_project_context.get("evidence_refs_by_project")
    if not isinstance(evidence_refs_by_project, Mapping):
        errors.append(
            "processing_behavior.recommendation.cross_project_context.evidence_refs_by_project must be an object"
        )
    else:
        for project_id, refs in evidence_refs_by_project.items():
            if not _as_text(project_id):
                errors.append(
                    "processing_behavior.recommendation.cross_project_context.evidence_refs_by_project keys must be non-empty"
                )
            if not isinstance(refs, list) or any(not _as_text(item) for item in refs):
                errors.append(
                    "processing_behavior.recommendation.cross_project_context."
                    f"evidence_refs_by_project.{project_id} must be a string array"
                )

    cross_project_obligations = recommendation.get("cross_project_obligations")
    if not isinstance(cross_project_obligations, list):
        errors.append("processing_behavior.recommendation.cross_project_obligations must be an array")
        cross_project_obligations = []
    for index, row in enumerate(cross_project_obligations):
        if not isinstance(row, Mapping):
            errors.append(f"processing_behavior.recommendation.cross_project_obligations[{index}] must be an object")
            continue
        for key in ("obligation_id", "project_id", "summary", "rationale", "next_step"):
            if not _as_text(row.get(key)):
                errors.append(
                    f"processing_behavior.recommendation.cross_project_obligations[{index}].{key} is required"
                )
        refs = row.get("evidence_refs")
        if not isinstance(refs, list) or not refs or any(not _as_text(item) for item in refs):
            errors.append(
                f"processing_behavior.recommendation.cross_project_obligations[{index}].evidence_refs "
                "must be a non-empty string array"
            )

    open_risks = recommendation.get("open_risks")
    if not isinstance(open_risks, list):
        errors.append("processing_behavior.recommendation.open_risks must be an array")
        open_risks = []
    for index, row in enumerate(open_risks):
        if not isinstance(row, Mapping):
            errors.append(f"processing_behavior.recommendation.open_risks[{index}] must be an object")
            continue
        for key in ("risk_id", "reason_code", "summary"):
            if not _as_text(row.get(key)):
                errors.append(f"processing_behavior.recommendation.open_risks[{index}].{key} is required")
        refs = row.get("required_evidence_refs")
        if not isinstance(refs, list) or any(not _as_text(item) for item in refs):
            errors.append(
                f"processing_behavior.recommendation.open_risks[{index}].required_evidence_refs must be a string array"
            )

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
        value = source.get(key)
        if not isinstance(value, int) or value <= 0:
            errors.append(f"source.{key} must be a positive integer")
    for key in (
        "earth_sweep_evidence_count",
        "cross_project_context_count",
        "candidate_recommendation_count",
    ):
        value = source.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"source.{key} must be a non-negative integer")
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
        broad_sweep_context=payload.get("broad_sweep_context"),
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
