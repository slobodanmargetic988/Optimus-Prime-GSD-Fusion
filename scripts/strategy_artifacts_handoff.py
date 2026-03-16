#!/usr/bin/env python3
"""REQ-056 and REQ-059 strategy artifact surfaces."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REQ_056_REQUIREMENT_ID = "REQ-056"
REQ_056_SCHEMA_VERSION = "1.0"
REQ_056_ANALYSIS_TYPE = "kpi_target_artifact"
REQ_056_CALL_ID = "kpi-target-artifact"

REQ_059_REQUIREMENT_ID = "REQ-059"
REQ_059_SCHEMA_VERSION = "1.0"
REQ_059_ANALYSIS_TYPE = "strategy_quality_report_artifact"
REQ_059_CALL_ID = "strategy-quality-report-artifact"

_EXPECTED_DIRECTIONS = {"increase", "decrease", "maintain"}
_CONFIDENCE_LEVELS = {"high", "medium", "low"}
_REQ_059_GATE_IDS = ("citation_coverage", "contradiction_status", "confidence_distribution")


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalize_text_list(value: Any, *, field_name: str, min_items: int = 0) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    normalized: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(value):
        item = _require_nonempty_text(row, field_name=f"{field_name}[{index}]")
        if item not in seen:
            normalized.append(item)
            seen.add(item)

    normalized_sorted = sorted(normalized)
    if len(normalized_sorted) < min_items:
        raise ValueError(f"{field_name} must include at least {min_items} value(s)")
    return normalized_sorted


def _normalize_target_project(value: Any) -> dict[str, str]:
    raw = _require_mapping(value, field_name="target_project")
    expected_keys = {"project_id", "project_root"}
    raw_keys = set(raw.keys())
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"target_project has unexpected keys: {unexpected}")
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"target_project missing keys: {missing}")

    project_id = _require_nonempty_text(raw.get("project_id"), field_name="target_project.project_id")
    project_root = _require_nonempty_text(raw.get("project_root"), field_name="target_project.project_root")
    normalized_root = str(Path(project_root).expanduser())
    if not normalized_root.startswith("/"):
        raise ValueError("target_project.project_root must be an absolute path")
    return {
        "project_id": project_id,
        "project_root": normalized_root,
    }


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_ratio_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0


def _require_nonnegative_int(value: Any, *, field_name: str) -> int:
    if not _is_nonnegative_int(value):
        raise ValueError(f"{field_name} must be a non-negative integer")
    return int(value)


def _require_ratio(value: Any, *, field_name: str) -> float:
    if not _is_ratio_number(value):
        raise ValueError(f"{field_name} must be a number between 0 and 1")
    return float(value)


def _rounded_ratio(*, numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _normalize_kpi_targets(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("kpi_targets must be a list")
    if not value:
        raise ValueError("kpi_targets must include at least one row")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        field_prefix = f"kpi_targets[{index}]"
        raw = _require_mapping(row, field_name=field_prefix)
        expected_keys = {
            "target_id",
            "metric_name",
            "expected_direction",
            "baseline_reference",
            "confidence_level",
            "originating_recommendation_ids",
            "assumption_ids",
            "rationale",
            "evidence_refs",
        }
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{field_prefix} has unexpected keys: {unexpected}")
        missing = sorted(expected_keys - row_keys)
        if missing:
            raise ValueError(f"{field_prefix} missing keys: {missing}")

        target_id = _require_nonempty_text(raw.get("target_id"), field_name=f"{field_prefix}.target_id")
        if target_id in seen_ids:
            raise ValueError(f"{field_prefix}.target_id must be unique")
        seen_ids.add(target_id)

        metric_name = _require_nonempty_text(raw.get("metric_name"), field_name=f"{field_prefix}.metric_name")
        expected_direction = _require_nonempty_text(
            raw.get("expected_direction"),
            field_name=f"{field_prefix}.expected_direction",
        ).lower()
        if expected_direction not in _EXPECTED_DIRECTIONS:
            raise ValueError(f"{field_prefix}.expected_direction must be one of: {sorted(_EXPECTED_DIRECTIONS)}")

        baseline_reference = _require_nonempty_text(
            raw.get("baseline_reference"),
            field_name=f"{field_prefix}.baseline_reference",
        )

        confidence_level = _require_nonempty_text(
            raw.get("confidence_level"),
            field_name=f"{field_prefix}.confidence_level",
        ).lower()
        if confidence_level not in _CONFIDENCE_LEVELS:
            raise ValueError(f"{field_prefix}.confidence_level must be one of: {sorted(_CONFIDENCE_LEVELS)}")

        originating_recommendation_ids = _normalize_text_list(
            raw.get("originating_recommendation_ids"),
            field_name=f"{field_prefix}.originating_recommendation_ids",
            min_items=1,
        )
        assumption_ids = _normalize_text_list(
            raw.get("assumption_ids"),
            field_name=f"{field_prefix}.assumption_ids",
            min_items=1,
        )
        rationale = _require_nonempty_text(raw.get("rationale"), field_name=f"{field_prefix}.rationale")
        evidence_refs = _normalize_text_list(
            raw.get("evidence_refs"),
            field_name=f"{field_prefix}.evidence_refs",
            min_items=1,
        )

        normalized.append(
            {
                "target_id": target_id,
                "metric_name": metric_name,
                "expected_direction": expected_direction,
                "baseline_reference": baseline_reference,
                "confidence_level": confidence_level,
                "originating_recommendation_ids": originating_recommendation_ids,
                "assumption_ids": assumption_ids,
                "rationale": rationale,
                "evidence_refs": evidence_refs,
            }
        )

    return sorted(normalized, key=lambda row: row["target_id"])


def build_req_056_kpi_target_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-056 payload for KPI target artifact handoff."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_056_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_056_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    kpi_targets = _normalize_kpi_targets(raw.get("kpi_targets"))

    linked_recommendations = sorted(
        {recommendation_id for row in kpi_targets for recommendation_id in row["originating_recommendation_ids"]}
    )
    linked_assumptions = sorted({assumption_id for row in kpi_targets for assumption_id in row["assumption_ids"]})

    built = {
        "ok": True,
        "schema_version": REQ_056_SCHEMA_VERSION,
        "requirement_id": REQ_056_REQUIREMENT_ID,
        "analysis_type": REQ_056_ANALYSIS_TYPE,
        "call_id": REQ_056_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "kpi_target_artifact": {
            "kpi_targets": kpi_targets,
        },
        "totals": {
            "kpi_targets": len(kpi_targets),
            "unique_recommendations_linked": len(linked_recommendations),
            "unique_assumptions_linked": len(linked_assumptions),
        },
    }

    errors = validate_req_056_kpi_target_artifact(built)
    if errors:
        raise ValueError(f"built REQ-056 payload failed validation: {errors}")
    return built


def _validate_nonempty_string_list(
    *,
    value: Any,
    field_name: str,
    min_items: int,
    require_sorted_unique: bool = True,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    normalized: list[str] = []
    if not isinstance(value, list):
        return [f"{field_name} must be a list"], normalized

    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field_name}[{index}] must be a non-empty string")
            continue
        normalized.append(item.strip())

    if len(normalized) < min_items:
        errors.append(f"{field_name} must include at least {min_items} value(s)")

    unique_sorted = sorted(set(normalized))
    if require_sorted_unique:
        if len(unique_sorted) != len(normalized):
            errors.append(f"{field_name} must not contain duplicates")
        if normalized != unique_sorted:
            errors.append(f"{field_name} must be sorted")
        return errors, unique_sorted

    ordered_unique: list[str] = []
    seen: set[str] = set()
    for item in normalized:
        if item in seen:
            errors.append(f"{field_name} must not contain duplicates")
            continue
        seen.add(item)
        ordered_unique.append(item)

    return errors, ordered_unique


def _validate_kpi_target_row(
    *,
    row: Any,
    index: int,
    seen_target_ids: set[str],
) -> tuple[list[str], set[str], set[str]]:
    errors: list[str] = []
    recommendation_ids: set[str] = set()
    assumption_ids: set[str] = set()
    row_path = f"kpi_target_artifact.kpi_targets[{index}]"
    if not isinstance(row, Mapping):
        return [f"{row_path} must be an object"], recommendation_ids, assumption_ids

    expected_keys = {
        "target_id",
        "metric_name",
        "expected_direction",
        "baseline_reference",
        "confidence_level",
        "originating_recommendation_ids",
        "assumption_ids",
        "rationale",
        "evidence_refs",
    }
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{row_path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{row_path} has unexpected keys: {unexpected}")

    target_id = row.get("target_id")
    if not isinstance(target_id, str) or not target_id.strip():
        errors.append(f"{row_path}.target_id must be a non-empty string")
    elif target_id in seen_target_ids:
        errors.append(f"{row_path}.target_id must be unique")
    else:
        seen_target_ids.add(target_id)

    metric_name = row.get("metric_name")
    if not isinstance(metric_name, str) or not metric_name.strip():
        errors.append(f"{row_path}.metric_name must be a non-empty string")

    expected_direction = row.get("expected_direction")
    if expected_direction not in _EXPECTED_DIRECTIONS:
        errors.append(f"{row_path}.expected_direction must be one of: {sorted(_EXPECTED_DIRECTIONS)}")

    baseline_reference = row.get("baseline_reference")
    if not isinstance(baseline_reference, str) or not baseline_reference.strip():
        errors.append(f"{row_path}.baseline_reference must be a non-empty string")

    confidence_level = row.get("confidence_level")
    if confidence_level not in _CONFIDENCE_LEVELS:
        errors.append(f"{row_path}.confidence_level must be one of: {sorted(_CONFIDENCE_LEVELS)}")

    rationale = row.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        errors.append(f"{row_path}.rationale must be a non-empty string")

    recommendation_errors, recommendation_list = _validate_nonempty_string_list(
        value=row.get("originating_recommendation_ids"),
        field_name=f"{row_path}.originating_recommendation_ids",
        min_items=1,
    )
    errors.extend(recommendation_errors)
    recommendation_ids.update(recommendation_list)

    assumption_errors, assumption_list = _validate_nonempty_string_list(
        value=row.get("assumption_ids"),
        field_name=f"{row_path}.assumption_ids",
        min_items=1,
    )
    errors.extend(assumption_errors)
    assumption_ids.update(assumption_list)

    evidence_errors, _ = _validate_nonempty_string_list(
        value=row.get("evidence_refs"),
        field_name=f"{row_path}.evidence_refs",
        min_items=1,
    )
    errors.extend(evidence_errors)

    return errors, recommendation_ids, assumption_ids


def validate_req_056_kpi_target_artifact(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-056 KPI target artifact payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    expected_top = {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "target_project",
        "kpi_target_artifact",
        "totals",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(expected_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - expected_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_056_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_056_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_056_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_056_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_056_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_056_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_056_CALL_ID:
        errors.append(f"call_id must be {REQ_056_CALL_ID}")
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
        elif not str(project_root).startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    kpi_artifact = payload.get("kpi_target_artifact")
    linked_recommendation_ids: set[str] = set()
    linked_assumption_ids: set[str] = set()
    target_count = 0
    if not isinstance(kpi_artifact, Mapping):
        errors.append("kpi_target_artifact must be an object")
    else:
        expected_artifact_keys = {"kpi_targets"}
        artifact_keys = set(kpi_artifact.keys())
        missing_artifact = sorted(expected_artifact_keys - artifact_keys)
        if missing_artifact:
            errors.append(f"kpi_target_artifact missing keys: {missing_artifact}")
        unexpected_artifact = sorted(artifact_keys - expected_artifact_keys)
        if unexpected_artifact:
            errors.append(f"kpi_target_artifact has unexpected keys: {unexpected_artifact}")

        kpi_targets = kpi_artifact.get("kpi_targets")
        if not isinstance(kpi_targets, list):
            errors.append("kpi_target_artifact.kpi_targets must be a list")
        elif not kpi_targets:
            errors.append("kpi_target_artifact.kpi_targets must include at least one row")
        else:
            target_count = len(kpi_targets)
            seen_target_ids: set[str] = set()
            for index, row in enumerate(kpi_targets):
                row_errors, recommendation_ids, assumption_ids = _validate_kpi_target_row(
                    row=row,
                    index=index,
                    seen_target_ids=seen_target_ids,
                )
                errors.extend(row_errors)
                linked_recommendation_ids.update(recommendation_ids)
                linked_assumption_ids.update(assumption_ids)

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "kpi_targets",
            "unique_recommendations_linked",
            "unique_assumptions_linked",
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

        if totals.get("kpi_targets") != target_count:
            errors.append("totals.kpi_targets must equal kpi_target_artifact.kpi_targets count")
        if totals.get("unique_recommendations_linked") != len(linked_recommendation_ids):
            errors.append("totals.unique_recommendations_linked must equal unique linked recommendation count")
        if totals.get("unique_assumptions_linked") != len(linked_assumption_ids):
            errors.append("totals.unique_assumptions_linked must equal unique linked assumption count")

    return errors


def _normalize_req_059_citation_coverage(value: Any) -> dict[str, Any]:
    raw = _require_mapping(value, field_name="citation_coverage")
    expected_keys = {"cited_claims", "uncited_claims"}
    raw_keys = set(raw.keys())
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"citation_coverage missing keys: {missing}")
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"citation_coverage has unexpected keys: {unexpected}")

    cited_claims = _require_nonnegative_int(raw.get("cited_claims"), field_name="citation_coverage.cited_claims")
    uncited_claims = _require_nonnegative_int(
        raw.get("uncited_claims"),
        field_name="citation_coverage.uncited_claims",
    )
    total_claims = cited_claims + uncited_claims
    if total_claims < 1:
        raise ValueError("citation_coverage must include at least one evaluated claim")

    return {
        "cited_claims": cited_claims,
        "uncited_claims": uncited_claims,
        "total_claims": total_claims,
        "coverage_ratio": _rounded_ratio(numerator=cited_claims, denominator=total_claims),
    }


def _normalize_req_059_contradiction_status(value: Any) -> dict[str, Any]:
    raw = _require_mapping(value, field_name="contradiction_status")
    expected_keys = {"unresolved_contradiction_ids"}
    raw_keys = set(raw.keys())
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"contradiction_status missing keys: {missing}")
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"contradiction_status has unexpected keys: {unexpected}")

    unresolved_contradiction_ids = _normalize_text_list(
        raw.get("unresolved_contradiction_ids"),
        field_name="contradiction_status.unresolved_contradiction_ids",
        min_items=0,
    )
    unresolved_count = len(unresolved_contradiction_ids)
    return {
        "has_unresolved_contradictions": unresolved_count > 0,
        "unresolved_contradiction_count": unresolved_count,
        "unresolved_contradiction_ids": unresolved_contradiction_ids,
    }


def _normalize_req_059_confidence_distribution(value: Any) -> dict[str, Any]:
    raw = _require_mapping(value, field_name="confidence_distribution")
    expected_keys = {"high", "medium", "low"}
    raw_keys = set(raw.keys())
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"confidence_distribution missing keys: {missing}")
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"confidence_distribution has unexpected keys: {unexpected}")

    high = _require_nonnegative_int(raw.get("high"), field_name="confidence_distribution.high")
    medium = _require_nonnegative_int(raw.get("medium"), field_name="confidence_distribution.medium")
    low = _require_nonnegative_int(raw.get("low"), field_name="confidence_distribution.low")
    total = high + medium + low
    if total < 1:
        raise ValueError("confidence_distribution must include at least one scored item")

    return {
        "high": high,
        "medium": medium,
        "low": low,
        "total": total,
        "high_ratio": _rounded_ratio(numerator=high, denominator=total),
        "medium_ratio": _rounded_ratio(numerator=medium, denominator=total),
        "low_ratio": _rounded_ratio(numerator=low, denominator=total),
    }


def _normalize_req_059_gate_policy(value: Any) -> dict[str, Any]:
    raw = _require_mapping(value, field_name="gate_policy")
    expected_keys = {
        "min_citation_coverage_ratio",
        "max_unresolved_contradictions",
        "min_high_confidence_ratio",
    }
    raw_keys = set(raw.keys())
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"gate_policy missing keys: {missing}")
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"gate_policy has unexpected keys: {unexpected}")

    return {
        "min_citation_coverage_ratio": _require_ratio(
            raw.get("min_citation_coverage_ratio"),
            field_name="gate_policy.min_citation_coverage_ratio",
        ),
        "max_unresolved_contradictions": _require_nonnegative_int(
            raw.get("max_unresolved_contradictions"),
            field_name="gate_policy.max_unresolved_contradictions",
        ),
        "min_high_confidence_ratio": _require_ratio(
            raw.get("min_high_confidence_ratio"),
            field_name="gate_policy.min_high_confidence_ratio",
        ),
    }


def _compute_req_059_gate_verdicts(
    *,
    citation_coverage: Mapping[str, Any],
    contradiction_status: Mapping[str, Any],
    confidence_distribution: Mapping[str, Any],
    gate_policy: Mapping[str, Any],
) -> dict[str, Any]:
    citation_coverage_pass = (
        float(citation_coverage["coverage_ratio"]) >= float(gate_policy["min_citation_coverage_ratio"])
    )
    contradiction_pass = (
        int(contradiction_status["unresolved_contradiction_count"]) <= int(gate_policy["max_unresolved_contradictions"])
    )
    confidence_distribution_pass = (
        float(confidence_distribution["high_ratio"]) >= float(gate_policy["min_high_confidence_ratio"])
    )

    failed_gate_ids: list[str] = []
    if not citation_coverage_pass:
        failed_gate_ids.append("citation_coverage")
    if not contradiction_pass:
        failed_gate_ids.append("contradiction_status")
    if not confidence_distribution_pass:
        failed_gate_ids.append("confidence_distribution")

    return {
        "citation_coverage_pass": citation_coverage_pass,
        "contradiction_pass": contradiction_pass,
        "confidence_distribution_pass": confidence_distribution_pass,
        "overall_pass": not failed_gate_ids,
        "failed_gate_ids": failed_gate_ids,
    }


def build_req_059_strategy_quality_report_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-059 payload for strategy quality report artifact handoff."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_059_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_059_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    citation_coverage = _normalize_req_059_citation_coverage(raw.get("citation_coverage"))
    contradiction_status = _normalize_req_059_contradiction_status(raw.get("contradiction_status"))
    confidence_distribution = _normalize_req_059_confidence_distribution(raw.get("confidence_distribution"))
    gate_policy = _normalize_req_059_gate_policy(raw.get("gate_policy"))
    gate_verdicts = _compute_req_059_gate_verdicts(
        citation_coverage=citation_coverage,
        contradiction_status=contradiction_status,
        confidence_distribution=confidence_distribution,
        gate_policy=gate_policy,
    )

    built = {
        "ok": True,
        "schema_version": REQ_059_SCHEMA_VERSION,
        "requirement_id": REQ_059_REQUIREMENT_ID,
        "analysis_type": REQ_059_ANALYSIS_TYPE,
        "call_id": REQ_059_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "strategy_quality_report_artifact": {
            "citation_coverage": citation_coverage,
            "contradiction_status": contradiction_status,
            "confidence_distribution": confidence_distribution,
            "gate_verdicts": gate_verdicts,
        },
        "gate_policy": gate_policy,
        "totals": {
            "quality_gates": len(_REQ_059_GATE_IDS),
            "failed_quality_gates": len(gate_verdicts["failed_gate_ids"]),
        },
    }

    errors = validate_req_059_strategy_quality_report_artifact(built)
    if errors:
        raise ValueError(f"built REQ-059 payload failed validation: {errors}")
    return built


def validate_req_059_strategy_quality_report_artifact(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-059 strategy quality report artifact payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    expected_top = {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "target_project",
        "strategy_quality_report_artifact",
        "gate_policy",
        "totals",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(expected_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - expected_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_059_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_059_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_059_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_059_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_059_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_059_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_059_CALL_ID:
        errors.append(f"call_id must be {REQ_059_CALL_ID}")
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
        elif not str(project_root).startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    gate_policy = payload.get("gate_policy")
    normalized_gate_policy: dict[str, Any] | None = None
    if not isinstance(gate_policy, Mapping):
        errors.append("gate_policy must be an object")
    else:
        expected_gate_policy = {
            "min_citation_coverage_ratio",
            "max_unresolved_contradictions",
            "min_high_confidence_ratio",
        }
        gate_policy_keys = set(gate_policy.keys())
        missing_gate_policy = sorted(expected_gate_policy - gate_policy_keys)
        if missing_gate_policy:
            errors.append(f"gate_policy missing keys: {missing_gate_policy}")
        unexpected_gate_policy = sorted(gate_policy_keys - expected_gate_policy)
        if unexpected_gate_policy:
            errors.append(f"gate_policy has unexpected keys: {unexpected_gate_policy}")

        min_citation_coverage_ratio = gate_policy.get("min_citation_coverage_ratio")
        if not _is_ratio_number(min_citation_coverage_ratio):
            errors.append("gate_policy.min_citation_coverage_ratio must be a number between 0 and 1")

        max_unresolved_contradictions = gate_policy.get("max_unresolved_contradictions")
        if not _is_nonnegative_int(max_unresolved_contradictions):
            errors.append("gate_policy.max_unresolved_contradictions must be a non-negative integer")

        min_high_confidence_ratio = gate_policy.get("min_high_confidence_ratio")
        if not _is_ratio_number(min_high_confidence_ratio):
            errors.append("gate_policy.min_high_confidence_ratio must be a number between 0 and 1")

        if not errors:
            normalized_gate_policy = {
                "min_citation_coverage_ratio": float(min_citation_coverage_ratio),
                "max_unresolved_contradictions": int(max_unresolved_contradictions),
                "min_high_confidence_ratio": float(min_high_confidence_ratio),
            }

    quality_report = payload.get("strategy_quality_report_artifact")
    normalized_citation_coverage: dict[str, Any] | None = None
    normalized_contradiction_status: dict[str, Any] | None = None
    normalized_confidence_distribution: dict[str, Any] | None = None
    normalized_gate_verdicts: dict[str, Any] | None = None
    if not isinstance(quality_report, Mapping):
        errors.append("strategy_quality_report_artifact must be an object")
    else:
        expected_quality_report = {
            "citation_coverage",
            "contradiction_status",
            "confidence_distribution",
            "gate_verdicts",
        }
        quality_report_keys = set(quality_report.keys())
        missing_quality_report = sorted(expected_quality_report - quality_report_keys)
        if missing_quality_report:
            errors.append(f"strategy_quality_report_artifact missing keys: {missing_quality_report}")
        unexpected_quality_report = sorted(quality_report_keys - expected_quality_report)
        if unexpected_quality_report:
            errors.append(f"strategy_quality_report_artifact has unexpected keys: {unexpected_quality_report}")

        citation_coverage = quality_report.get("citation_coverage")
        if not isinstance(citation_coverage, Mapping):
            errors.append("strategy_quality_report_artifact.citation_coverage must be an object")
        else:
            expected_citation_coverage = {"cited_claims", "uncited_claims", "total_claims", "coverage_ratio"}
            citation_coverage_keys = set(citation_coverage.keys())
            missing_citation_coverage = sorted(expected_citation_coverage - citation_coverage_keys)
            if missing_citation_coverage:
                errors.append(f"citation_coverage missing keys: {missing_citation_coverage}")
            unexpected_citation_coverage = sorted(citation_coverage_keys - expected_citation_coverage)
            if unexpected_citation_coverage:
                errors.append(f"citation_coverage has unexpected keys: {unexpected_citation_coverage}")

            cited_claims = citation_coverage.get("cited_claims")
            if not _is_nonnegative_int(cited_claims):
                errors.append("citation_coverage.cited_claims must be a non-negative integer")

            uncited_claims = citation_coverage.get("uncited_claims")
            if not _is_nonnegative_int(uncited_claims):
                errors.append("citation_coverage.uncited_claims must be a non-negative integer")

            total_claims = citation_coverage.get("total_claims")
            if not _is_nonnegative_int(total_claims):
                errors.append("citation_coverage.total_claims must be a non-negative integer")

            coverage_ratio = citation_coverage.get("coverage_ratio")
            if not _is_ratio_number(coverage_ratio):
                errors.append("citation_coverage.coverage_ratio must be a number between 0 and 1")

            if (
                _is_nonnegative_int(cited_claims)
                and _is_nonnegative_int(uncited_claims)
                and _is_nonnegative_int(total_claims)
            ):
                expected_total_claims = int(cited_claims) + int(uncited_claims)
                if int(total_claims) != expected_total_claims:
                    errors.append("citation_coverage.total_claims must equal cited_claims + uncited_claims")
                if int(total_claims) < 1:
                    errors.append("citation_coverage.total_claims must be at least 1")

            if (
                _is_nonnegative_int(cited_claims)
                and _is_nonnegative_int(total_claims)
                and int(total_claims) > 0
                and _is_ratio_number(coverage_ratio)
            ):
                expected_coverage_ratio = _rounded_ratio(numerator=int(cited_claims), denominator=int(total_claims))
                if round(float(coverage_ratio), 4) != expected_coverage_ratio:
                    errors.append(
                        "citation_coverage.coverage_ratio must equal cited_claims / total_claims rounded to 4 decimals"
                    )

            if not errors and _is_nonnegative_int(cited_claims) and _is_nonnegative_int(uncited_claims):
                normalized_citation_coverage = {
                    "cited_claims": int(cited_claims),
                    "uncited_claims": int(uncited_claims),
                    "total_claims": int(total_claims),
                    "coverage_ratio": float(coverage_ratio),
                }

        contradiction_status = quality_report.get("contradiction_status")
        if not isinstance(contradiction_status, Mapping):
            errors.append("strategy_quality_report_artifact.contradiction_status must be an object")
        else:
            expected_contradiction_status = {
                "has_unresolved_contradictions",
                "unresolved_contradiction_count",
                "unresolved_contradiction_ids",
            }
            contradiction_status_keys = set(contradiction_status.keys())
            missing_contradiction_status = sorted(expected_contradiction_status - contradiction_status_keys)
            if missing_contradiction_status:
                errors.append(f"contradiction_status missing keys: {missing_contradiction_status}")
            unexpected_contradiction_status = sorted(contradiction_status_keys - expected_contradiction_status)
            if unexpected_contradiction_status:
                errors.append(f"contradiction_status has unexpected keys: {unexpected_contradiction_status}")

            has_unresolved_contradictions = contradiction_status.get("has_unresolved_contradictions")
            if not isinstance(has_unresolved_contradictions, bool):
                errors.append("contradiction_status.has_unresolved_contradictions must be a boolean")

            unresolved_contradiction_count = contradiction_status.get("unresolved_contradiction_count")
            if not _is_nonnegative_int(unresolved_contradiction_count):
                errors.append("contradiction_status.unresolved_contradiction_count must be a non-negative integer")

            contradiction_id_errors, unresolved_contradiction_ids = _validate_nonempty_string_list(
                value=contradiction_status.get("unresolved_contradiction_ids"),
                field_name="contradiction_status.unresolved_contradiction_ids",
                min_items=0,
            )
            errors.extend(contradiction_id_errors)

            if _is_nonnegative_int(unresolved_contradiction_count):
                if int(unresolved_contradiction_count) != len(unresolved_contradiction_ids):
                    errors.append(
                        "contradiction_status.unresolved_contradiction_count must equal unresolved_contradiction_ids count"
                    )
                if isinstance(has_unresolved_contradictions, bool):
                    expected_has_unresolved = int(unresolved_contradiction_count) > 0
                    if has_unresolved_contradictions != expected_has_unresolved:
                        errors.append(
                            "contradiction_status.has_unresolved_contradictions must match unresolved_contradiction_count"
                        )

            if (
                isinstance(has_unresolved_contradictions, bool)
                and _is_nonnegative_int(unresolved_contradiction_count)
                and not contradiction_id_errors
            ):
                normalized_contradiction_status = {
                    "has_unresolved_contradictions": has_unresolved_contradictions,
                    "unresolved_contradiction_count": int(unresolved_contradiction_count),
                    "unresolved_contradiction_ids": unresolved_contradiction_ids,
                }

        confidence_distribution = quality_report.get("confidence_distribution")
        if not isinstance(confidence_distribution, Mapping):
            errors.append("strategy_quality_report_artifact.confidence_distribution must be an object")
        else:
            expected_confidence_distribution = {
                "high",
                "medium",
                "low",
                "total",
                "high_ratio",
                "medium_ratio",
                "low_ratio",
            }
            confidence_distribution_keys = set(confidence_distribution.keys())
            missing_confidence_distribution = sorted(expected_confidence_distribution - confidence_distribution_keys)
            if missing_confidence_distribution:
                errors.append(f"confidence_distribution missing keys: {missing_confidence_distribution}")
            unexpected_confidence_distribution = sorted(confidence_distribution_keys - expected_confidence_distribution)
            if unexpected_confidence_distribution:
                errors.append(f"confidence_distribution has unexpected keys: {unexpected_confidence_distribution}")

            high = confidence_distribution.get("high")
            if not _is_nonnegative_int(high):
                errors.append("confidence_distribution.high must be a non-negative integer")

            medium = confidence_distribution.get("medium")
            if not _is_nonnegative_int(medium):
                errors.append("confidence_distribution.medium must be a non-negative integer")

            low = confidence_distribution.get("low")
            if not _is_nonnegative_int(low):
                errors.append("confidence_distribution.low must be a non-negative integer")

            total = confidence_distribution.get("total")
            if not _is_nonnegative_int(total):
                errors.append("confidence_distribution.total must be a non-negative integer")

            high_ratio = confidence_distribution.get("high_ratio")
            if not _is_ratio_number(high_ratio):
                errors.append("confidence_distribution.high_ratio must be a number between 0 and 1")

            medium_ratio = confidence_distribution.get("medium_ratio")
            if not _is_ratio_number(medium_ratio):
                errors.append("confidence_distribution.medium_ratio must be a number between 0 and 1")

            low_ratio = confidence_distribution.get("low_ratio")
            if not _is_ratio_number(low_ratio):
                errors.append("confidence_distribution.low_ratio must be a number between 0 and 1")

            if _is_nonnegative_int(high) and _is_nonnegative_int(medium) and _is_nonnegative_int(low) and _is_nonnegative_int(total):
                expected_total = int(high) + int(medium) + int(low)
                if int(total) != expected_total:
                    errors.append("confidence_distribution.total must equal high + medium + low")
                if int(total) < 1:
                    errors.append("confidence_distribution.total must be at least 1")

            if _is_nonnegative_int(high) and _is_nonnegative_int(total) and int(total) > 0 and _is_ratio_number(high_ratio):
                expected_high_ratio = _rounded_ratio(numerator=int(high), denominator=int(total))
                if round(float(high_ratio), 4) != expected_high_ratio:
                    errors.append("confidence_distribution.high_ratio must equal high / total rounded to 4 decimals")
            if _is_nonnegative_int(medium) and _is_nonnegative_int(total) and int(total) > 0 and _is_ratio_number(medium_ratio):
                expected_medium_ratio = _rounded_ratio(numerator=int(medium), denominator=int(total))
                if round(float(medium_ratio), 4) != expected_medium_ratio:
                    errors.append("confidence_distribution.medium_ratio must equal medium / total rounded to 4 decimals")
            if _is_nonnegative_int(low) and _is_nonnegative_int(total) and int(total) > 0 and _is_ratio_number(low_ratio):
                expected_low_ratio = _rounded_ratio(numerator=int(low), denominator=int(total))
                if round(float(low_ratio), 4) != expected_low_ratio:
                    errors.append("confidence_distribution.low_ratio must equal low / total rounded to 4 decimals")

            if (
                _is_nonnegative_int(high)
                and _is_nonnegative_int(medium)
                and _is_nonnegative_int(low)
                and _is_nonnegative_int(total)
                and _is_ratio_number(high_ratio)
                and _is_ratio_number(medium_ratio)
                and _is_ratio_number(low_ratio)
            ):
                normalized_confidence_distribution = {
                    "high": int(high),
                    "medium": int(medium),
                    "low": int(low),
                    "total": int(total),
                    "high_ratio": float(high_ratio),
                    "medium_ratio": float(medium_ratio),
                    "low_ratio": float(low_ratio),
                }

        gate_verdicts = quality_report.get("gate_verdicts")
        if not isinstance(gate_verdicts, Mapping):
            errors.append("strategy_quality_report_artifact.gate_verdicts must be an object")
        else:
            expected_gate_verdicts = {
                "citation_coverage_pass",
                "contradiction_pass",
                "confidence_distribution_pass",
                "overall_pass",
                "failed_gate_ids",
            }
            gate_verdict_keys = set(gate_verdicts.keys())
            missing_gate_verdicts = sorted(expected_gate_verdicts - gate_verdict_keys)
            if missing_gate_verdicts:
                errors.append(f"gate_verdicts missing keys: {missing_gate_verdicts}")
            unexpected_gate_verdicts = sorted(gate_verdict_keys - expected_gate_verdicts)
            if unexpected_gate_verdicts:
                errors.append(f"gate_verdicts has unexpected keys: {unexpected_gate_verdicts}")

            citation_coverage_pass = gate_verdicts.get("citation_coverage_pass")
            contradiction_pass = gate_verdicts.get("contradiction_pass")
            confidence_distribution_pass = gate_verdicts.get("confidence_distribution_pass")
            overall_pass = gate_verdicts.get("overall_pass")
            for key, value in (
                ("citation_coverage_pass", citation_coverage_pass),
                ("contradiction_pass", contradiction_pass),
                ("confidence_distribution_pass", confidence_distribution_pass),
                ("overall_pass", overall_pass),
            ):
                if not isinstance(value, bool):
                    errors.append(f"gate_verdicts.{key} must be a boolean")

            failed_gate_id_errors, failed_gate_ids = _validate_nonempty_string_list(
                value=gate_verdicts.get("failed_gate_ids"),
                field_name="gate_verdicts.failed_gate_ids",
                min_items=0,
                require_sorted_unique=False,
            )
            errors.extend(failed_gate_id_errors)
            unknown_gate_ids = sorted(set(failed_gate_ids) - set(_REQ_059_GATE_IDS))
            if unknown_gate_ids:
                errors.append(f"gate_verdicts.failed_gate_ids has unknown gate ids: {unknown_gate_ids}")

            if (
                isinstance(citation_coverage_pass, bool)
                and isinstance(contradiction_pass, bool)
                and isinstance(confidence_distribution_pass, bool)
                and isinstance(overall_pass, bool)
                and not failed_gate_id_errors
                and not unknown_gate_ids
            ):
                normalized_gate_verdicts = {
                    "citation_coverage_pass": citation_coverage_pass,
                    "contradiction_pass": contradiction_pass,
                    "confidence_distribution_pass": confidence_distribution_pass,
                    "overall_pass": overall_pass,
                    "failed_gate_ids": failed_gate_ids,
                }

    if (
        normalized_citation_coverage is not None
        and normalized_contradiction_status is not None
        and normalized_confidence_distribution is not None
        and normalized_gate_policy is not None
        and normalized_gate_verdicts is not None
    ):
        expected_gate_verdicts = _compute_req_059_gate_verdicts(
            citation_coverage=normalized_citation_coverage,
            contradiction_status=normalized_contradiction_status,
            confidence_distribution=normalized_confidence_distribution,
            gate_policy=normalized_gate_policy,
        )
        if normalized_gate_verdicts["citation_coverage_pass"] != expected_gate_verdicts["citation_coverage_pass"]:
            errors.append("gate_verdicts.citation_coverage_pass must match computed gate verdict")
        if normalized_gate_verdicts["contradiction_pass"] != expected_gate_verdicts["contradiction_pass"]:
            errors.append("gate_verdicts.contradiction_pass must match computed gate verdict")
        if (
            normalized_gate_verdicts["confidence_distribution_pass"]
            != expected_gate_verdicts["confidence_distribution_pass"]
        ):
            errors.append("gate_verdicts.confidence_distribution_pass must match computed gate verdict")
        if normalized_gate_verdicts["overall_pass"] != expected_gate_verdicts["overall_pass"]:
            errors.append("gate_verdicts.overall_pass must match computed gate verdict")
        if normalized_gate_verdicts["failed_gate_ids"] != expected_gate_verdicts["failed_gate_ids"]:
            errors.append("gate_verdicts.failed_gate_ids must match computed failed gate ids")

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {"quality_gates", "failed_quality_gates"}
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")

        quality_gates = totals.get("quality_gates")
        failed_quality_gates = totals.get("failed_quality_gates")
        if not _is_nonnegative_int(quality_gates):
            errors.append("totals.quality_gates must be a non-negative integer")
        if not _is_nonnegative_int(failed_quality_gates):
            errors.append("totals.failed_quality_gates must be a non-negative integer")

        if _is_nonnegative_int(quality_gates) and int(quality_gates) != len(_REQ_059_GATE_IDS):
            errors.append("totals.quality_gates must equal 3")

        if _is_nonnegative_int(failed_quality_gates) and normalized_gate_verdicts is not None:
            if int(failed_quality_gates) != len(normalized_gate_verdicts["failed_gate_ids"]):
                errors.append("totals.failed_quality_gates must equal gate_verdicts.failed_gate_ids count")

    return errors


def build_strategy_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a strategy handoff artifact based on payload analysis_type."""
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type in ("", REQ_056_ANALYSIS_TYPE):
        return build_req_056_kpi_target_artifact(payload)
    if analysis_type == REQ_059_ANALYSIS_TYPE:
        return build_req_059_strategy_quality_report_artifact(payload)
    raise ValueError(
        "analysis_type must be one of: "
        f"{sorted((REQ_056_ANALYSIS_TYPE, REQ_059_ANALYSIS_TYPE))}"
    )


def _load_input_payload(path_value: str) -> dict[str, Any]:
    if path_value == "-":
        raw_text = sys.stdin.read()
    else:
        raw_text = Path(path_value).read_text(encoding="utf-8")
    loaded = json.loads(raw_text)
    if not isinstance(loaded, dict):
        raise ValueError("input payload must be a JSON object")
    return loaded


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit strategy handoff artifact payload.")
    parser.add_argument(
        "--input-json",
        required=True,
        help="Path to strategy artifact input JSON (or '-' for stdin).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_input_payload(args.input_json)
        built = build_strategy_artifact(payload)
    except Exception as exc:  # pragma: no cover - CLI guardrail
        sys.stderr.write(f"[{_utc_timestamp()}] strategy artifact CLI failed: {exc}\n")
        return 1

    sys.stdout.write(json.dumps(built, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
