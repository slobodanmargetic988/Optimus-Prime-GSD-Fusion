#!/usr/bin/env python3
"""REQ-056 and REQ-057 strategy artifact handoff surfaces."""

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

REQ_057_REQUIREMENT_ID = "REQ-057"
REQ_057_SCHEMA_VERSION = "1.0"
REQ_057_ANALYSIS_TYPE = "blocker_handling_policy_artifact"
REQ_057_CALL_ID = "blocker-handling-policy-artifact"

_EXPECTED_DIRECTIONS = {"increase", "decrease", "maintain"}
_CONFIDENCE_LEVELS = {"high", "medium", "low"}
_ESCALATION_TRIGGER_TYPES = {
    "attempts_exhausted",
    "dependency_timeout",
    "guardrail_violation",
}
_ESCALATION_WINDOWS = {"attempts", "cycles", "minutes"}


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


def _require_positive_int(value: Any, *, field_name: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


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


def _normalize_escalation_trigger(value: Any, *, field_name: str) -> dict[str, Any]:
    raw = _require_mapping(value, field_name=field_name)
    expected_keys = {"trigger_type", "threshold", "window"}
    raw_keys = set(raw.keys())
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"{field_name} missing keys: {missing}")

    trigger_type = _require_nonempty_text(raw.get("trigger_type"), field_name=f"{field_name}.trigger_type").lower()
    if trigger_type not in _ESCALATION_TRIGGER_TYPES:
        raise ValueError(f"{field_name}.trigger_type must be one of: {sorted(_ESCALATION_TRIGGER_TYPES)}")

    threshold = _require_positive_int(raw.get("threshold"), field_name=f"{field_name}.threshold")
    window = _require_nonempty_text(raw.get("window"), field_name=f"{field_name}.window").lower()
    if window not in _ESCALATION_WINDOWS:
        raise ValueError(f"{field_name}.window must be one of: {sorted(_ESCALATION_WINDOWS)}")

    return {
        "trigger_type": trigger_type,
        "threshold": threshold,
        "window": window,
    }


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


def _normalize_blocker_policies(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("blocker_policies must be a list")
    if not value:
        raise ValueError("blocker_policies must include at least one row")

    normalized: list[dict[str, Any]] = []
    seen_policy_ids: set[str] = set()
    for index, row in enumerate(value):
        field_prefix = f"blocker_policies[{index}]"
        raw = _require_mapping(row, field_name=field_prefix)
        expected_keys = {
            "policy_id",
            "blocker_code",
            "escalation_trigger",
            "owner_hints",
            "fallback_paths",
        }
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{field_prefix} has unexpected keys: {unexpected}")
        missing = sorted(expected_keys - row_keys)
        if missing:
            raise ValueError(f"{field_prefix} missing keys: {missing}")

        policy_id = _require_nonempty_text(raw.get("policy_id"), field_name=f"{field_prefix}.policy_id")
        if policy_id in seen_policy_ids:
            raise ValueError(f"{field_prefix}.policy_id must be unique")
        seen_policy_ids.add(policy_id)

        blocker_code = _require_nonempty_text(raw.get("blocker_code"), field_name=f"{field_prefix}.blocker_code")
        escalation_trigger = _normalize_escalation_trigger(
            raw.get("escalation_trigger"),
            field_name=f"{field_prefix}.escalation_trigger",
        )
        owner_hints = _normalize_text_list(
            raw.get("owner_hints"),
            field_name=f"{field_prefix}.owner_hints",
            min_items=1,
        )
        fallback_paths = _normalize_text_list(
            raw.get("fallback_paths"),
            field_name=f"{field_prefix}.fallback_paths",
            min_items=1,
        )

        normalized.append(
            {
                "policy_id": policy_id,
                "blocker_code": blocker_code,
                "escalation_trigger": escalation_trigger,
                "owner_hints": owner_hints,
                "fallback_paths": fallback_paths,
            }
        )

    return sorted(normalized, key=lambda row: row["policy_id"])


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


def build_req_057_blocker_handling_policy_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-057 payload for blocker handling policy artifact handoff."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_057_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_057_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    policies = _normalize_blocker_policies(raw.get("blocker_policies"))

    linked_blocker_codes = sorted({row["blocker_code"] for row in policies})
    linked_owner_hints = sorted({owner for row in policies for owner in row["owner_hints"]})
    linked_fallback_paths = sorted({path for row in policies for path in row["fallback_paths"]})

    built = {
        "ok": True,
        "schema_version": REQ_057_SCHEMA_VERSION,
        "requirement_id": REQ_057_REQUIREMENT_ID,
        "analysis_type": REQ_057_ANALYSIS_TYPE,
        "call_id": REQ_057_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "blocker_handling_policy_artifact": {
            "policies": policies,
        },
        "totals": {
            "policies": len(policies),
            "unique_blocker_codes": len(linked_blocker_codes),
            "unique_owner_hints": len(linked_owner_hints),
            "unique_fallback_paths": len(linked_fallback_paths),
        },
    }

    errors = validate_req_057_blocker_handling_policy_artifact(built)
    if errors:
        raise ValueError(f"built REQ-057 payload failed validation: {errors}")
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


def _validate_escalation_trigger(*, value: Any, field_name: str) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"{field_name} must be an object"]

    errors: list[str] = []
    expected_keys = {"trigger_type", "threshold", "window"}
    trigger_keys = set(value.keys())
    missing = sorted(expected_keys - trigger_keys)
    if missing:
        errors.append(f"{field_name} missing keys: {missing}")
    unexpected = sorted(trigger_keys - expected_keys)
    if unexpected:
        errors.append(f"{field_name} has unexpected keys: {unexpected}")

    trigger_type = value.get("trigger_type")
    if trigger_type not in _ESCALATION_TRIGGER_TYPES:
        errors.append(f"{field_name}.trigger_type must be one of: {sorted(_ESCALATION_TRIGGER_TYPES)}")

    threshold = value.get("threshold")
    if not isinstance(threshold, int) or threshold <= 0:
        errors.append(f"{field_name}.threshold must be a positive integer")

    window = value.get("window")
    if window not in _ESCALATION_WINDOWS:
        errors.append(f"{field_name}.window must be one of: {sorted(_ESCALATION_WINDOWS)}")

    return errors


def _validate_blocker_policy_row(
    *,
    row: Any,
    index: int,
    seen_policy_ids: set[str],
) -> tuple[list[str], set[str], set[str], set[str]]:
    errors: list[str] = []
    blocker_codes: set[str] = set()
    owner_hints: set[str] = set()
    fallback_paths: set[str] = set()
    row_path = f"blocker_handling_policy_artifact.policies[{index}]"

    if not isinstance(row, Mapping):
        return [f"{row_path} must be an object"], blocker_codes, owner_hints, fallback_paths

    expected_keys = {
        "policy_id",
        "blocker_code",
        "escalation_trigger",
        "owner_hints",
        "fallback_paths",
    }
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{row_path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{row_path} has unexpected keys: {unexpected}")

    policy_id = row.get("policy_id")
    if not isinstance(policy_id, str) or not policy_id.strip():
        errors.append(f"{row_path}.policy_id must be a non-empty string")
    elif policy_id in seen_policy_ids:
        errors.append(f"{row_path}.policy_id must be unique")
    else:
        seen_policy_ids.add(policy_id)

    blocker_code = row.get("blocker_code")
    if not isinstance(blocker_code, str) or not blocker_code.strip():
        errors.append(f"{row_path}.blocker_code must be a non-empty string")
    else:
        blocker_codes.add(blocker_code.strip())

    errors.extend(
        _validate_escalation_trigger(
            value=row.get("escalation_trigger"),
            field_name=f"{row_path}.escalation_trigger",
        )
    )

    owner_errors, owner_list = _validate_nonempty_string_list(
        value=row.get("owner_hints"),
        field_name=f"{row_path}.owner_hints",
        min_items=1,
    )
    errors.extend(owner_errors)
    owner_hints.update(owner_list)

    fallback_errors, fallback_list = _validate_nonempty_string_list(
        value=row.get("fallback_paths"),
        field_name=f"{row_path}.fallback_paths",
        min_items=1,
    )
    errors.extend(fallback_errors)
    fallback_paths.update(fallback_list)

    return errors, blocker_codes, owner_hints, fallback_paths


def validate_req_057_blocker_handling_policy_artifact(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-057 blocker handling policy artifact payload shape."""
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
        "blocker_handling_policy_artifact",
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
    if payload.get("schema_version") != REQ_057_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_057_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_057_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_057_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_057_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_057_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_057_CALL_ID:
        errors.append(f"call_id must be {REQ_057_CALL_ID}")
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

    policy_artifact = payload.get("blocker_handling_policy_artifact")
    linked_blocker_codes: set[str] = set()
    linked_owner_hints: set[str] = set()
    linked_fallback_paths: set[str] = set()
    policy_count = 0
    if not isinstance(policy_artifact, Mapping):
        errors.append("blocker_handling_policy_artifact must be an object")
    else:
        expected_artifact_keys = {"policies"}
        artifact_keys = set(policy_artifact.keys())
        missing_artifact = sorted(expected_artifact_keys - artifact_keys)
        if missing_artifact:
            errors.append(f"blocker_handling_policy_artifact missing keys: {missing_artifact}")
        unexpected_artifact = sorted(artifact_keys - expected_artifact_keys)
        if unexpected_artifact:
            errors.append(f"blocker_handling_policy_artifact has unexpected keys: {unexpected_artifact}")

        policy_rows = policy_artifact.get("policies")
        if not isinstance(policy_rows, list):
            errors.append("blocker_handling_policy_artifact.policies must be a list")
        elif not policy_rows:
            errors.append("blocker_handling_policy_artifact.policies must include at least one row")
        else:
            policy_count = len(policy_rows)
            seen_policy_ids: set[str] = set()
            for index, row in enumerate(policy_rows):
                row_errors, blocker_codes, owner_hints, fallback_paths = _validate_blocker_policy_row(
                    row=row,
                    index=index,
                    seen_policy_ids=seen_policy_ids,
                )
                errors.extend(row_errors)
                linked_blocker_codes.update(blocker_codes)
                linked_owner_hints.update(owner_hints)
                linked_fallback_paths.update(fallback_paths)

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "policies",
            "unique_blocker_codes",
            "unique_owner_hints",
            "unique_fallback_paths",
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

        if totals.get("policies") != policy_count:
            errors.append("totals.policies must equal blocker_handling_policy_artifact.policies count")
        if totals.get("unique_blocker_codes") != len(linked_blocker_codes):
            errors.append("totals.unique_blocker_codes must equal unique blocker code count")
        if totals.get("unique_owner_hints") != len(linked_owner_hints):
            errors.append("totals.unique_owner_hints must equal unique owner hint count")
        if totals.get("unique_fallback_paths") != len(linked_fallback_paths):
            errors.append("totals.unique_fallback_paths must equal unique fallback path count")

    return errors


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
    parser = argparse.ArgumentParser(description="Emit REQ-056/REQ-057 strategy artifact payload.")
    parser.add_argument(
        "--input-json",
        required=True,
        help="Path to REQ-056/REQ-057 input JSON (or '-' for stdin).",
    )
    return parser


def _build_strategy_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type == REQ_056_ANALYSIS_TYPE:
        return build_req_056_kpi_target_artifact(payload)
    if analysis_type == REQ_057_ANALYSIS_TYPE:
        return build_req_057_blocker_handling_policy_artifact(payload)
    raise ValueError(
        "analysis_type must be one of: "
        f"{sorted([REQ_056_ANALYSIS_TYPE, REQ_057_ANALYSIS_TYPE])}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_input_payload(args.input_json)
        built = _build_strategy_artifact(payload)
    except Exception as exc:  # pragma: no cover - CLI guardrail
        sys.stderr.write(f"[{_utc_timestamp()}] Strategy artifact CLI failed: {exc}\n")
        return 1

    sys.stdout.write(json.dumps(built, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
