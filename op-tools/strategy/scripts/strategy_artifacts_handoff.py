#!/usr/bin/env python3
"""Deterministic strategy artifact helpers for handoff-oriented reports."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REQUIRED_RECOMMENDATION_FIELDS = (
    "recommendation_id",
    "priority",
    "summary",
    "rationale",
    "expected_impact",
    "risk_level",
)
REQUIRED_AUTONOMOUS_ARTIFACT_GROUPS = ("current", "history", "validators")
PASS_STATUSES = {"resolved", "closed", "cleared", "none"}
CONFIDENCE_LEVELS = ("high", "medium", "low", "unknown")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def _unique_sorted_strings(values: Iterable[Any]) -> list[str]:
    normalized = {
        str(item).strip()
        for item in values
        if item is not None and str(item).strip()
    }
    return sorted(normalized)


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _project_id_from_item(item: Any) -> str | None:
    if isinstance(item, dict):
        for key in ("project_id", "id", "project", "repo", "name"):
            value = item.get(key)
            if value:
                return str(value)
        return None
    if isinstance(item, str) and item.strip():
        return item.strip()
    return None


def _looks_like_reference(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and ("/" in text or "#" in text)


def _normalize_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _coalesce(
        payload.get("recommendations"),
        _as_dict(payload.get("strategy_packet")).get("recommendations"),
        _as_dict(payload.get("strategy")).get("recommendations"),
    )
    recommendations = []
    for index, item in enumerate(_as_list(raw), start=1):
        record = _as_dict(item).copy()
        if not record:
            continue
        record.setdefault("recommendation_id", f"rec.generated-{index:03d}")
        recommendations.append(record)
    recommendations.sort(key=lambda item: item["recommendation_id"])
    return recommendations


def _build_evidence_index(payload: dict[str, Any]) -> dict[str, list[str]]:
    index: dict[str, set[str]] = {}

    candidates = []
    candidates.extend(_as_list(payload.get("evidence_provenance")))
    candidates.extend(_as_list(payload.get("source_traceability")))
    candidates.extend(_as_list(_as_dict(payload.get("context_bundle")).get("evidence_provenance")))
    candidates.extend(_as_list(_as_dict(payload.get("reasoning_trace")).get("evidence_provenance")))

    for candidate in candidates:
        record = _as_dict(candidate)
        recommendation_id = _coalesce(
            record.get("recommendation_id"),
            record.get("ref"),
            record.get("id"),
        )
        if not recommendation_id:
            continue
        refs = _unique_sorted_strings(
            _as_list(record.get("evidence_refs"))
            + _as_list(record.get("refs"))
            + _as_list(record.get("evidence"))
        )
        if refs:
            index.setdefault(str(recommendation_id), set()).update(refs)

    return {key: sorted(values) for key, values in sorted(index.items())}


def _recommendation_evidence_refs(
    recommendation: dict[str, Any],
    evidence_index: dict[str, list[str]],
) -> list[str]:
    recommendation_id = str(recommendation.get("recommendation_id", "")).strip()
    refs = _unique_sorted_strings(
        _as_list(recommendation.get("evidence_refs"))
        + _as_list(recommendation.get("evidence"))
        + _as_list(recommendation.get("source_refs"))
        + evidence_index.get(recommendation_id, [])
    )
    return refs


def _normalize_contradictions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    candidates.extend(_as_list(payload.get("contradictions")))
    candidates.extend(_as_list(_as_dict(payload.get("reasoning_trace")).get("contradictions")))

    for call in _as_list(payload.get("reasoning_calls")):
        record = _as_dict(call)
        if "contradiction_status" in record:
            candidates.append(record["contradiction_status"])

    normalized = []
    for index, item in enumerate(candidates, start=1):
        record = _as_dict(item).copy()
        if not record:
            continue
        status = str(_coalesce(record.get("status"), record.get("verdict"), "open")).strip().lower()
        contradiction_id = str(_coalesce(record.get("id"), record.get("contradiction_id"), f"contradiction-{index:03d}"))
        normalized.append(
            {
                "contradiction_id": contradiction_id,
                "status": status,
                "summary": str(_coalesce(record.get("summary"), record.get("detail"), contradiction_id)),
                "evidence_refs": _unique_sorted_strings(
                    _as_list(record.get("evidence_refs")) + _as_list(record.get("evidence"))
                ),
            }
        )

    normalized.sort(key=lambda item: item["contradiction_id"])
    return normalized


def _confidence_distribution(
    recommendations: list[dict[str, Any]],
    payload: dict[str, Any],
) -> dict[str, int]:
    counts = {level: 0 for level in CONFIDENCE_LEVELS}

    for recommendation in recommendations:
        raw = str(
            _coalesce(
                recommendation.get("confidence"),
                recommendation.get("confidence_level"),
                recommendation.get("context_confidence"),
                "unknown",
            )
        ).strip().lower()
        level = raw if raw in counts else "unknown"
        counts[level] += 1

    if sum(counts.values()) == 0:
        for item in _as_list(payload.get("context_confidence")):
            raw = str(item).strip().lower()
            counts[raw if raw in counts else "unknown"] += 1

    return counts


def _collect_projects(payload: dict[str, Any]) -> list[str]:
    project_ids: set[str] = set()
    for source in (
        payload.get("earth_sweep"),
        payload.get("broad_sweep"),
        payload.get("ecosystem_context"),
        _as_dict(payload.get("context_bundle")).get("earth_sweep"),
    ):
        for item in _as_list(_as_dict(source).get("projects")):
            project_id = _project_id_from_item(item)
            if project_id:
                project_ids.add(project_id)

    for source in (
        payload.get("cross_project_context"),
        _as_dict(payload.get("context_bundle")).get("cross_project_context"),
    ):
        for item in _as_list(source):
            project_id = _project_id_from_item(item)
            if project_id:
                project_ids.add(project_id)

    target_project_id = _coalesce(
        _as_dict(payload.get("identity")).get("project_id"),
        _as_dict(_as_dict(payload.get("strategy_packet")).get("identity")).get("project_id"),
        payload.get("project_id"),
    )
    if target_project_id:
        project_ids.add(str(target_project_id))

    return sorted(project_ids)


def _project_evidence_index(payload: dict[str, Any]) -> dict[str, list[str]]:
    index: dict[str, set[str]] = {}

    project_sources = [
        ("earth_sweep", _as_list(_as_dict(payload.get("earth_sweep")).get("projects"))),
        ("broad_sweep", _as_list(_as_dict(payload.get("broad_sweep")).get("projects"))),
        ("ecosystem_context", _as_list(_as_dict(payload.get("ecosystem_context")).get("projects"))),
        (
            "context_bundle.earth_sweep",
            _as_list(_as_dict(_as_dict(payload.get("context_bundle")).get("earth_sweep")).get("projects")),
        ),
    ]
    context_sources = [
        ("cross_project_context", _as_list(payload.get("cross_project_context"))),
        ("context_bundle.cross_project_context", _as_list(_as_dict(payload.get("context_bundle")).get("cross_project_context"))),
    ]

    for _source_name, candidates in project_sources + context_sources:
        for item in candidates:
            project_id = _project_id_from_item(item)
            if not project_id:
                continue
            refs = _collect_nested_evidence_refs(item)
            if refs:
                index.setdefault(project_id, set()).update(refs)

    return {key: sorted(values) for key, values in sorted(index.items())}


def _collect_obligation_risks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    open_risks = []
    obligations = []
    obligations.extend(_as_list(payload.get("ecosystem_obligations")))
    obligations.extend(_as_list(payload.get("obligations")))
    obligations.extend(_as_list(_as_dict(payload.get("context_bundle")).get("ecosystem_obligations")))
    project_evidence_index = _project_evidence_index(payload)

    for index, item in enumerate(obligations, start=1):
        record = _as_dict(item)
        if not record:
            continue
        evidence_refs = _unique_sorted_strings(
            _as_list(record.get("evidence_refs")) + _as_list(record.get("evidence"))
        )
        if evidence_refs:
            continue
        project_id = _project_id_from_item(record) or f"project-{index:03d}"
        required_evidence_refs = project_evidence_index.get(project_id, [])
        open_risks.append(
            {
                "risk_id": f"risk.unsupported-cross-project-obligation.{index:03d}",
                "severity": "medium",
                "category": "open_risk",
                "reason_code": "missing_earth_sweep_evidence_refs",
                "summary": f"Cross-project obligation for {project_id} has no Earth-sweep evidence refs.",
                "project_id": project_id,
                "linked_recommendation_ids": _unique_sorted_strings(
                    _as_list(record.get("recommendation_ids")) + _as_list(record.get("linked_recommendation_ids"))
                ),
                "evidence_refs": required_evidence_refs,
                "required_evidence_refs": required_evidence_refs,
                "recommendation": "Keep this as an open risk until Earth-sweep evidence refs exist.",
            }
        )

    open_risks.sort(key=lambda item: item["risk_id"])
    return open_risks


def _collect_nested_evidence_refs(value: Any) -> list[str]:
    refs: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key in ("evidence_refs", "evidence", "source_refs", "context_refs", "refs"):
                refs.update(
                    text
                    for text in _unique_sorted_strings(_as_list(item.get(key)))
                    if _looks_like_reference(text)
                )
            for nested in item.values():
                visit(nested)
            return
        if isinstance(item, (list, tuple)):
            for nested in item:
                visit(nested)

    visit(value)
    return sorted(refs)


def _normalize_artifact_group(
    payload: dict[str, Any],
    *,
    group_name: str,
    aliases: tuple[str, ...],
) -> dict[str, Any]:
    sources_used: set[str] = set()
    candidates: list[Any] = []

    artifacts = _as_dict(payload.get("artifacts"))
    context_bundle = _as_dict(payload.get("context_bundle"))
    context_artifacts = _as_dict(context_bundle.get("artifacts"))

    for alias in aliases:
        if alias in payload:
            sources_used.add(alias)
            candidates.extend(_as_list(payload.get(alias)))
        if alias in artifacts:
            sources_used.add(f"artifacts.{alias}")
            candidates.extend(_as_list(artifacts.get(alias)))
        if alias in context_bundle:
            sources_used.add(f"context_bundle.{alias}")
            candidates.extend(_as_list(context_bundle.get(alias)))
        if alias in context_artifacts:
            sources_used.add(f"context_bundle.artifacts.{alias}")
            candidates.extend(_as_list(context_artifacts.get(alias)))

    normalized = []
    for index, item in enumerate(candidates, start=1):
        record = _as_dict(item)
        artifact_id = str(
            _coalesce(
                record.get("artifact_id"),
                record.get("id"),
                record.get("name"),
                f"{group_name}-artifact-{index:03d}",
            )
        ).strip()
        artifact_ref = str(
            _coalesce(
                record.get("artifact_ref"),
                record.get("path"),
                record.get("artifact_path"),
                record.get("output_path"),
                record.get("ref"),
                record.get("file"),
                record.get("location"),
                item if isinstance(item, str) else None,
            )
            or ""
        ).strip()
        evidence_refs = _collect_nested_evidence_refs(record)
        normalized.append(
            {
                "artifact_id": artifact_id,
                "artifact_ref": artifact_ref,
                "status": str(
                    _coalesce(record.get("status"), record.get("verdict"), "produced")
                ).strip().lower(),
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(key=lambda item: item["artifact_id"])
    artifact_refs = sorted(
        {
            item["artifact_ref"]
            for item in normalized
            if item["artifact_ref"]
        }
    )
    missing_artifact_ids = sorted(
        item["artifact_id"]
        for item in normalized
        if not item["artifact_ref"]
    )

    return {
        "group_name": group_name,
        "artifact_count": len(normalized),
        "artifact_refs": artifact_refs,
        "missing_artifact_ids": missing_artifact_ids,
        "sources_used": sorted(sources_used),
        "artifacts": normalized,
        "group_complete": bool(normalized) and not missing_artifact_ids,
    }


def _collect_context_usage(payload: dict[str, Any]) -> dict[str, Any]:
    source_map = {
        "earth_sweep": payload.get("earth_sweep"),
        "broad_sweep": payload.get("broad_sweep"),
        "ecosystem_context": payload.get("ecosystem_context"),
        "cross_project_context": payload.get("cross_project_context"),
        "context_bundle.earth_sweep": _as_dict(payload.get("context_bundle")).get("earth_sweep"),
        "context_bundle.cross_project_context": _as_dict(payload.get("context_bundle")).get(
            "cross_project_context"
        ),
    }
    sources_used = sorted(
        key
        for key, value in source_map.items()
        if value not in (None, "", [], {})
    )
    return {
        "sources_used": sources_used,
        "evidence_refs": _collect_nested_evidence_refs(
            [value for value in source_map.values() if value not in (None, "", [], {})]
        ),
    }


def _build_planner_hook(
    payload: dict[str, Any],
    recommendations: list[dict[str, Any]],
    evidence_index: dict[str, list[str]],
    artifact_refs: list[str],
) -> dict[str, Any]:
    planner_hook_payload = _as_dict(payload.get("planner_hook"))
    sources_used: set[str] = set()
    rows_by_recommendation_id: dict[str, dict[str, Any]] = {}

    explicit_rows = []
    for field_name in ("recommendation_mapping", "recommendation_readiness"):
        if field_name in planner_hook_payload:
            sources_used.add(f"planner_hook.{field_name}")
            value = planner_hook_payload.get(field_name)
            if isinstance(value, dict):
                explicit_rows.extend(value.values())
            else:
                explicit_rows.extend(_as_list(value))

    for item in explicit_rows:
        record = _as_dict(item)
        recommendation_id = str(
            _coalesce(record.get("recommendation_id"), record.get("id"), record.get("recommendation"))
            or ""
        ).strip()
        if not recommendation_id:
            continue
        rows_by_recommendation_id[recommendation_id] = {
            "recommendation_id": recommendation_id,
            "recommendation_key": str(
                _coalesce(record.get("recommendation_key"), record.get("key"), recommendation_id) or recommendation_id
            ).strip(),
            "status": str(_coalesce(record.get("status"), "ready")).strip().lower(),
            "priority": str(_coalesce(record.get("priority"), "") or "").strip(),
            "summary": str(_coalesce(record.get("summary"), "") or "").strip(),
            "artifact_refs": _unique_sorted_strings(
                _as_list(record.get("artifact_refs")) + _as_list(record.get("artifacts"))
            ),
            "evidence_refs": _collect_nested_evidence_refs(record),
        }

    for recommendation in recommendations:
        recommendation_id = recommendation["recommendation_id"]
        row = rows_by_recommendation_id.setdefault(
            recommendation_id,
            {
                "recommendation_id": recommendation_id,
                "recommendation_key": recommendation_id,
                "status": "ready",
                "priority": "",
                "summary": "",
                "artifact_refs": [],
                "evidence_refs": [],
            },
        )
        row["recommendation_key"] = str(
            _coalesce(
                row.get("recommendation_key"),
                recommendation.get("recommendation_key"),
                recommendation_id,
            )
        ).strip()
        row["priority"] = str(_coalesce(row.get("priority"), recommendation.get("priority"), "")).strip()
        row["summary"] = str(_coalesce(row.get("summary"), recommendation.get("summary"), recommendation_id)).strip()
        row["artifact_refs"] = _unique_sorted_strings(row.get("artifact_refs", []) + artifact_refs)
        row["evidence_refs"] = _unique_sorted_strings(
            row.get("evidence_refs", []) + _recommendation_evidence_refs(recommendation, evidence_index)
        )

    recommendation_ids = sorted(
        recommendation["recommendation_id"] for recommendation in recommendations
    )
    mapped_recommendation_ids = sorted(
        recommendation_id
        for recommendation_id in rows_by_recommendation_id
        if recommendation_id in recommendation_ids
    )
    missing_recommendation_ids = sorted(
        recommendation_id
        for recommendation_id in recommendation_ids
        if recommendation_id not in mapped_recommendation_ids
    )
    sources_used.add("generated_from_recommendations")

    return {
        "recommendation_ids": recommendation_ids,
        "mapped_recommendation_ids": mapped_recommendation_ids,
        "missing_recommendation_ids": missing_recommendation_ids,
        "mapping_complete": bool(recommendation_ids) and not missing_recommendation_ids,
        "sources_used": sorted(sources_used),
        "recommendation_mapping": {
            recommendation_id: rows_by_recommendation_id[recommendation_id]
            for recommendation_id in mapped_recommendation_ids
        },
        "evidence_refs": _unique_sorted_strings(
            _collect_nested_evidence_refs(planner_hook_payload)
            + [
                ref
                for recommendation_id in mapped_recommendation_ids
                for ref in rows_by_recommendation_id[recommendation_id]["evidence_refs"]
            ]
        ),
    }


def build_strategy_quality_report(payload: dict[str, Any]) -> dict[str, Any]:
    recommendations = _normalize_recommendations(payload)
    evidence_index = _build_evidence_index(payload)

    recommendation_rows = []
    missing_evidence = []
    missing_fields: dict[str, list[str]] = {}
    all_evidence_refs: set[str] = set()

    for recommendation in recommendations:
        recommendation_id = recommendation["recommendation_id"]
        evidence_refs = _recommendation_evidence_refs(recommendation, evidence_index)
        missing = [
            field
            for field in REQUIRED_RECOMMENDATION_FIELDS
            if str(recommendation.get(field, "")).strip() == ""
        ]

        if not evidence_refs:
            missing_evidence.append(recommendation_id)
        if missing:
            missing_fields[recommendation_id] = missing

        all_evidence_refs.update(evidence_refs)
        recommendation_rows.append(
            {
                "recommendation_id": recommendation_id,
                "evidence_refs": evidence_refs,
                "missing_required_fields": missing,
                "confidence": str(
                    _coalesce(
                        recommendation.get("confidence"),
                        recommendation.get("confidence_level"),
                        recommendation.get("context_confidence"),
                        "unknown",
                    )
                ).strip().lower(),
            }
        )

    contradictions = _normalize_contradictions(payload)
    open_contradictions = [
        item for item in contradictions if item["status"] not in PASS_STATUSES
    ]
    for contradiction in contradictions:
        all_evidence_refs.update(contradiction["evidence_refs"])

    project_ids = _collect_projects(payload)
    target_project_id = _coalesce(
        _as_dict(payload.get("identity")).get("project_id"),
        _as_dict(_as_dict(payload.get("strategy_packet")).get("identity")).get("project_id"),
        payload.get("project_id"),
    )
    peer_project_ids = [
        project_id for project_id in project_ids if project_id != target_project_id
    ]

    open_risks = _collect_obligation_risks(payload)
    confidence_distribution = _confidence_distribution(recommendations, payload)

    citation_coverage_pass = bool(recommendations) and not missing_evidence
    contradiction_pass = not open_contradictions
    recommendation_fields_pass = not missing_fields
    cross_project_context_pass = bool(peer_project_ids)
    open_risk_blockers = [risk["risk_id"] for risk in open_risks]

    blocking_reasons = []
    if not citation_coverage_pass:
        blocking_reasons.append("missing_evidence_refs")
    if not contradiction_pass:
        blocking_reasons.append("open_contradictions")
    if not recommendation_fields_pass:
        blocking_reasons.append("incomplete_recommendations")
    if not cross_project_context_pass:
        blocking_reasons.append("missing_cross_project_context")
    if open_risk_blockers:
        blocking_reasons.append("unsupported_cross_project_obligations")

    verdict = "pass" if not blocking_reasons else "fail"

    return {
        "artifact_type": "strategy_quality_report",
        "requirement_id": "REQ-059",
        "quality_report_version": "1.0",
        "recommendations_analyzed": len(recommendations),
        "evidence_refs": sorted(all_evidence_refs),
        "citation_coverage": {
            "recommendations_total": len(recommendations),
            "recommendations_with_evidence_refs": len(recommendations) - len(missing_evidence),
            "coverage_ratio": (
                0.0
                if not recommendations
                else round((len(recommendations) - len(missing_evidence)) / len(recommendations), 4)
            ),
            "missing_recommendation_ids": sorted(missing_evidence),
        },
        "recommendation_field_completeness": {
            "required_fields": list(REQUIRED_RECOMMENDATION_FIELDS),
            "complete_recommendations": len(recommendations) - len(missing_fields),
            "incomplete_recommendations": len(missing_fields),
            "missing_by_recommendation": {
                key: value for key, value in sorted(missing_fields.items())
            },
        },
        "contradiction_status": {
            "has_open_contradictions": bool(open_contradictions),
            "open_count": len(open_contradictions),
            "resolved_count": len(contradictions) - len(open_contradictions),
            "items": contradictions,
        },
        "confidence_distribution": confidence_distribution,
        "cross_project_context": {
            "target_project_id": target_project_id,
            "project_ids": project_ids,
            "peer_project_ids": peer_project_ids,
            "project_count": len(project_ids),
            "peer_project_count": len(peer_project_ids),
            "used_in_quality_report": bool(peer_project_ids),
        },
        "recommendations": recommendation_rows,
        "open_risks": open_risks,
        "gate_verdict": {
            "verdict": verdict,
            "ready_for_build": verdict == "pass",
            "citation_coverage_pass": citation_coverage_pass,
            "contradiction_pass": contradiction_pass,
            "recommendation_fields_pass": recommendation_fields_pass,
            "cross_project_context_pass": cross_project_context_pass,
            "blocking_reasons": blocking_reasons,
            "warning_reasons": [],
        },
    }


def write_strategy_quality_report(
    payload: dict[str, Any],
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_strategy_quality_report(payload)
    if output_path is not None:
        _write_json(output_path, report)
    return report


def build_end_to_end_autonomous_strategy_acceptance_packet(
    payload: dict[str, Any],
) -> dict[str, Any]:
    quality_report = build_strategy_quality_report(payload)
    context_usage = _collect_context_usage(payload)
    recommendations = _normalize_recommendations(payload)
    evidence_index = _build_evidence_index(payload)
    target_project_id = quality_report["cross_project_context"]["target_project_id"]

    artifact_groups = {
        "current": _normalize_artifact_group(
            payload,
            group_name="current",
            aliases=("current_artifacts", "current_outputs", "current"),
        ),
        "history": _normalize_artifact_group(
            payload,
            group_name="history",
            aliases=("history_artifacts", "history_outputs", "revision_history_artifacts", "history"),
        ),
        "validators": _normalize_artifact_group(
            payload,
            group_name="validators",
            aliases=("validator_artifacts", "validator_outputs", "validation_artifacts", "validators"),
        ),
    }

    missing_artifact_groups = sorted(
        name
        for name in REQUIRED_AUTONOMOUS_ARTIFACT_GROUPS
        if not artifact_groups[name]["group_complete"]
    )
    artifact_refs = sorted(
        {
            ref
            for group in artifact_groups.values()
            for ref in group["artifact_refs"]
        }
    )
    artifact_evidence_refs = sorted(
        {
            ref
            for group in artifact_groups.values()
            for artifact in group["artifacts"]
            for ref in artifact["evidence_refs"]
        }
    )
    planner_hook = _build_planner_hook(
        payload=payload,
        recommendations=recommendations,
        evidence_index=evidence_index,
        artifact_refs=artifact_refs,
    )
    open_risks = _collect_obligation_risks(payload)

    recommendation_fields_pass = quality_report["gate_verdict"]["recommendation_fields_pass"]
    citation_coverage_pass = quality_report["gate_verdict"]["citation_coverage_pass"]
    contradiction_pass = quality_report["gate_verdict"]["contradiction_pass"]
    cross_project_context_pass = bool(quality_report["cross_project_context"]["peer_project_ids"])
    artifacts_complete = not missing_artifact_groups

    blocking_reasons = []
    if not artifacts_complete:
        blocking_reasons.append("missing_required_artifacts")
    if not citation_coverage_pass:
        blocking_reasons.append("missing_evidence_refs")
    if not recommendation_fields_pass:
        blocking_reasons.append("incomplete_recommendations")
    if not contradiction_pass:
        blocking_reasons.append("open_contradictions")
    if not cross_project_context_pass:
        blocking_reasons.append("missing_cross_project_context")

    warning_reasons = []
    if open_risks:
        warning_reasons.append("open_risks_present")

    verdict = "pass" if not blocking_reasons else "fail"
    planner_consumable = verdict == "pass"
    ecosystem_aware = cross_project_context_pass and bool(context_usage["sources_used"])

    evidence_refs = sorted(
        {
            *quality_report["evidence_refs"],
            *context_usage["evidence_refs"],
            *artifact_evidence_refs,
            *planner_hook["evidence_refs"],
        }
    )

    cross_project_context = _json_copy(quality_report["cross_project_context"])
    cross_project_context.update(
        {
            "context_sources_used": context_usage["sources_used"],
            "evidence_refs": context_usage["evidence_refs"],
            "used_in_acceptance_packet": ecosystem_aware,
        }
    )

    return {
        "artifact_type": "end_to_end_autonomous_strategy_acceptance_packet",
        "requirement_id": "REQ-070",
        "acceptance_packet_version": "1.0",
        "target_project_id": target_project_id,
        "run_identity": {
            "project_id": target_project_id,
            "run_id": _coalesce(_as_dict(payload.get("identity")).get("run_id"), payload.get("run_id")),
            "event_id": _coalesce(
                _as_dict(payload.get("identity")).get("event_id"),
                payload.get("event_id"),
            ),
            "revision_id": _coalesce(
                _as_dict(payload.get("strategy")).get("revision_id"),
                payload.get("revision_id"),
            ),
        },
        "artifacts": artifact_groups,
        "artifact_refs": artifact_refs,
        "evidence_refs": evidence_refs,
        "recommendations_analyzed": quality_report["recommendations_analyzed"],
        "recommendation_field_completeness": _json_copy(
            quality_report["recommendation_field_completeness"]
        ),
        "planner_hook": planner_hook,
        "cross_project_context": cross_project_context,
        "open_risks": open_risks,
        "consumability_verdict": {
            "verdict": verdict,
            "planner_consumable": planner_consumable,
            "ecosystem_aware": ecosystem_aware,
            "artifacts_complete": artifacts_complete,
            "citation_coverage_pass": citation_coverage_pass,
            "recommendation_fields_pass": recommendation_fields_pass,
            "contradiction_pass": contradiction_pass,
            "ready_for_autonomous_planning": planner_consumable and ecosystem_aware,
            "missing_artifact_groups": missing_artifact_groups,
            "blocking_reasons": blocking_reasons,
            "warning_reasons": warning_reasons,
        },
    }


def write_end_to_end_autonomous_strategy_acceptance_packet(
    payload: dict[str, Any],
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    packet = build_end_to_end_autonomous_strategy_acceptance_packet(payload)
    if output_path is not None:
        _write_json(output_path, packet)
    return packet


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _print_status(message: str) -> None:
    print(f"[{_timestamp()}] {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic strategy quality reports.")
    parser.add_argument("--input", required=True, help="Path to JSON payload used to build the report.")
    parser.add_argument(
        "--output",
        help="Optional output path. When omitted, the report is printed to stdout.",
    )
    args = parser.parse_args(argv)

    _print_status(f"Loading strategy quality-report input from {args.input}.")
    payload = _load_json(args.input)
    report = write_strategy_quality_report(payload, args.output)

    if args.output:
        _print_status(f"Wrote strategy quality report to {args.output}.")
    else:
        _print_status("Printing strategy quality report to stdout.")
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
