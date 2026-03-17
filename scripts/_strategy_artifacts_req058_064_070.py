#!/usr/bin/env python3
"""REQ-056, REQ-058, and REQ-064 strategy artifact surfaces."""

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

REQ_058_REQUIREMENT_ID = "REQ-058"
REQ_058_SCHEMA_VERSION = "1.0"
REQ_058_ANALYSIS_TYPE = "ecosystem_obligation_artifact"
REQ_058_CALL_ID = "ecosystem-obligation-artifact"
REQ_058_PROCESSING_STRATEGY = "ecosystem-obligation-broad-sweep"
REQ_058_REASONING_MODE = "llm-first"

REQ_064_REQUIREMENT_ID = "REQ-064"
REQ_064_SCHEMA_VERSION = "1.0"
REQ_064_ANALYSIS_TYPE = "source_traceability_validator"
REQ_064_CALL_ID = "source-traceability-validator"
REQ_064_PROCESSING_STRATEGY = "source-traceability-broad-sweep"
REQ_064_REASONING_MODE = "llm-first"
REQ_064_RECOMMENDATION_REQUIRED_FIELDS = (
    "recommendation_id",
    "summary",
    "evidence_refs",
    "claims",
)

REQ_070_REQUIREMENT_ID = "REQ-070"
REQ_070_SCHEMA_VERSION = "1.0"
REQ_070_ANALYSIS_TYPE = "end_to_end_autonomous_strategy_run_acceptance_packet"
REQ_070_CALL_ID = "end-to-end-autonomous-strategy-run-and-acceptance-packet"

_EXPECTED_DIRECTIONS = {"increase", "decrease", "maintain"}
_CONFIDENCE_LEVELS = {"high", "medium", "low"}
_RESPONSIBILITY_TYPES = {"produce", "consume"}
_REQ_058_OPEN_RISK_REASON_MISSING_EARTH_SWEEP_EVIDENCE = "missing_earth_sweep_evidence_refs"
_REQ_058_OPEN_RISK_REASON_UNRESOLVED_IDEA = "unresolved_idea"


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


def _require_bool(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _normalize_req_070_run_identity(value: Any) -> dict[str, str]:
    raw = _require_mapping(value, field_name="run_identity")
    expected_keys = {"project_id", "run_id", "event_id", "strategy_revision_id", "plan_id"}
    raw_keys = set(raw.keys())
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"run_identity has unexpected keys: {unexpected}")
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"run_identity missing keys: {missing}")

    return {
        "project_id": _require_nonempty_text(raw.get("project_id"), field_name="run_identity.project_id"),
        "run_id": _require_nonempty_text(raw.get("run_id"), field_name="run_identity.run_id"),
        "event_id": _require_nonempty_text(raw.get("event_id"), field_name="run_identity.event_id"),
        "strategy_revision_id": _require_nonempty_text(
            raw.get("strategy_revision_id"),
            field_name="run_identity.strategy_revision_id",
        ),
        "plan_id": _require_nonempty_text(raw.get("plan_id"), field_name="run_identity.plan_id"),
    }


def _normalize_req_070_artifact_row(*, raw_row: Any, field_prefix: str) -> dict[str, Any]:
    raw = _require_mapping(raw_row, field_name=field_prefix)
    expected_keys = {"artifact_id", "path", "status", "evidence_refs"}
    raw_keys = set(raw.keys())
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"{field_prefix} has unexpected keys: {unexpected}")
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"{field_prefix} missing keys: {missing}")

    return {
        "artifact_id": _require_nonempty_text(raw.get("artifact_id"), field_name=f"{field_prefix}.artifact_id"),
        "path": _require_nonempty_text(raw.get("path"), field_name=f"{field_prefix}.path"),
        "status": _require_nonempty_text(raw.get("status"), field_name=f"{field_prefix}.status").lower(),
        "evidence_refs": _normalize_text_list(
            raw.get("evidence_refs"),
            field_name=f"{field_prefix}.evidence_refs",
            min_items=1,
        ),
    }


def _normalize_req_070_artifact_rows(value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if not value:
        raise ValueError(f"{field_name} must include at least one row")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        field_prefix = f"{field_name}[{index}]"
        normalized_row = _normalize_req_070_artifact_row(raw_row=row, field_prefix=field_prefix)
        artifact_id = str(normalized_row["artifact_id"])
        if artifact_id in seen_ids:
            raise ValueError(f"{field_prefix}.artifact_id must be unique")
        seen_ids.add(artifact_id)
        normalized.append(normalized_row)

    return sorted(normalized, key=lambda row: row["artifact_id"])


def _normalize_req_070_planner_consumability(value: Any) -> dict[str, Any]:
    raw = _require_mapping(value, field_name="planner_consumability")
    expected_keys = {
        "ready_for_planner",
        "recommendation_mapping_complete",
        "consumability_verdict",
        "recommendation_ids",
        "recommendation_mapping_refs",
        "evidence_refs",
    }
    raw_keys = set(raw.keys())
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"planner_consumability has unexpected keys: {unexpected}")
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"planner_consumability missing keys: {missing}")

    ready_for_planner = _require_bool(
        raw.get("ready_for_planner"),
        field_name="planner_consumability.ready_for_planner",
    )
    if not ready_for_planner:
        raise ValueError("planner_consumability.ready_for_planner must be true")

    recommendation_mapping_complete = _require_bool(
        raw.get("recommendation_mapping_complete"),
        field_name="planner_consumability.recommendation_mapping_complete",
    )
    if not recommendation_mapping_complete:
        raise ValueError("planner_consumability.recommendation_mapping_complete must be true")

    consumability_verdict = _require_nonempty_text(
        raw.get("consumability_verdict"),
        field_name="planner_consumability.consumability_verdict",
    ).lower()
    recommendation_ids = _normalize_text_list(
        raw.get("recommendation_ids"),
        field_name="planner_consumability.recommendation_ids",
        min_items=1,
    )
    recommendation_mapping_refs = _normalize_text_list(
        raw.get("recommendation_mapping_refs"),
        field_name="planner_consumability.recommendation_mapping_refs",
        min_items=1,
    )
    evidence_refs = _normalize_text_list(
        raw.get("evidence_refs"),
        field_name="planner_consumability.evidence_refs",
        min_items=1,
    )

    return {
        "ready_for_planner": ready_for_planner,
        "recommendation_mapping_complete": recommendation_mapping_complete,
        "consumability_verdict": consumability_verdict,
        "recommendation_ids": recommendation_ids,
        "recommendation_mapping_refs": recommendation_mapping_refs,
        "evidence_refs": evidence_refs,
    }


def _normalize_req_070_ecosystem_awareness(*, value: Any, target_project_id: str) -> dict[str, Any]:
    raw = _require_mapping(value, field_name="ecosystem_awareness")
    expected_keys = {
        "ecosystem_aware",
        "context_project_ids",
        "peer_project_ids",
        "earth_sweep_evidence_refs",
    }
    raw_keys = set(raw.keys())
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"ecosystem_awareness has unexpected keys: {unexpected}")
    missing = sorted(expected_keys - raw_keys)
    if missing:
        raise ValueError(f"ecosystem_awareness missing keys: {missing}")

    ecosystem_aware = _require_bool(
        raw.get("ecosystem_aware"),
        field_name="ecosystem_awareness.ecosystem_aware",
    )
    if not ecosystem_aware:
        raise ValueError("ecosystem_awareness.ecosystem_aware must be true")

    context_project_ids = _normalize_text_list(
        raw.get("context_project_ids"),
        field_name="ecosystem_awareness.context_project_ids",
        min_items=2,
    )
    peer_project_ids = _normalize_text_list(
        raw.get("peer_project_ids"),
        field_name="ecosystem_awareness.peer_project_ids",
        min_items=1,
    )
    earth_sweep_evidence_refs = _normalize_text_list(
        raw.get("earth_sweep_evidence_refs"),
        field_name="ecosystem_awareness.earth_sweep_evidence_refs",
        min_items=1,
    )

    if target_project_id not in context_project_ids:
        raise ValueError("ecosystem_awareness.context_project_ids must include target_project.project_id")
    if any(project_id == target_project_id for project_id in peer_project_ids):
        raise ValueError("ecosystem_awareness.peer_project_ids must reference external Earth apps only")
    if any(project_id not in context_project_ids for project_id in peer_project_ids):
        raise ValueError("ecosystem_awareness.peer_project_ids must be a subset of context_project_ids")

    return {
        "ecosystem_aware": ecosystem_aware,
        "context_project_ids": context_project_ids,
        "peer_project_ids": peer_project_ids,
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
    }


def _normalize_req_070_open_risks(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("open_risks must be a list")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        field_prefix = f"open_risks[{index}]"
        raw = _require_mapping(row, field_name=field_prefix)
        expected_keys = {"risk_id", "summary", "reason_code", "required_evidence_refs"}
        raw_keys = set(raw.keys())
        unexpected = sorted(raw_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{field_prefix} has unexpected keys: {unexpected}")
        missing = sorted(expected_keys - raw_keys)
        if missing:
            raise ValueError(f"{field_prefix} missing keys: {missing}")

        risk_id = _require_nonempty_text(raw.get("risk_id"), field_name=f"{field_prefix}.risk_id")
        if risk_id in seen_ids:
            raise ValueError(f"{field_prefix}.risk_id must be unique")
        seen_ids.add(risk_id)

        normalized.append(
            {
                "risk_id": risk_id,
                "summary": _require_nonempty_text(raw.get("summary"), field_name=f"{field_prefix}.summary"),
                "reason_code": _require_nonempty_text(
                    raw.get("reason_code"),
                    field_name=f"{field_prefix}.reason_code",
                ),
                "required_evidence_refs": _normalize_text_list(
                    raw.get("required_evidence_refs"),
                    field_name=f"{field_prefix}.required_evidence_refs",
                    min_items=1,
                ),
            }
        )

    return sorted(normalized, key=lambda row: row["risk_id"])


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


def _normalize_ecosystem_obligation_row(
    *,
    raw_row: Any,
    field_prefix: str,
    min_evidence_refs: int,
    allow_context_evidence_alias: bool = False,
) -> dict[str, Any]:
    raw = _require_mapping(raw_row, field_name=field_prefix)
    expected_keys = {
        "obligation_id",
        "peer_project_id",
        "responsibility",
        "artifact",
        "obligation_summary",
        "dependency_prerequisites",
        "evidence_refs",
    }
    if allow_context_evidence_alias:
        expected_keys.add("earth_sweep_evidence_refs")

    row_keys = set(raw.keys())
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        raise ValueError(f"{field_prefix} has unexpected keys: {unexpected}")

    required_keys = expected_keys - {"earth_sweep_evidence_refs"}
    if allow_context_evidence_alias:
        required_keys = required_keys - {"evidence_refs"}
    missing = sorted(required_keys - row_keys)
    if missing:
        raise ValueError(f"{field_prefix} missing keys: {missing}")
    if allow_context_evidence_alias and "evidence_refs" not in row_keys and "earth_sweep_evidence_refs" not in row_keys:
        raise ValueError(f"{field_prefix} missing keys: ['evidence_refs|earth_sweep_evidence_refs']")

    obligation_id = _require_nonempty_text(raw.get("obligation_id"), field_name=f"{field_prefix}.obligation_id")
    peer_project_id = _require_nonempty_text(raw.get("peer_project_id"), field_name=f"{field_prefix}.peer_project_id")
    responsibility = _require_nonempty_text(raw.get("responsibility"), field_name=f"{field_prefix}.responsibility").lower()
    if responsibility not in _RESPONSIBILITY_TYPES:
        raise ValueError(f"{field_prefix}.responsibility must be one of: {sorted(_RESPONSIBILITY_TYPES)}")

    artifact = _require_nonempty_text(raw.get("artifact"), field_name=f"{field_prefix}.artifact")
    obligation_summary = _require_nonempty_text(raw.get("obligation_summary"), field_name=f"{field_prefix}.obligation_summary")
    dependency_prerequisites = _normalize_text_list(
        raw.get("dependency_prerequisites"),
        field_name=f"{field_prefix}.dependency_prerequisites",
        min_items=1,
    )

    evidence_key = "evidence_refs"
    evidence_value = raw.get("evidence_refs")
    if allow_context_evidence_alias and evidence_value is None and "earth_sweep_evidence_refs" in raw:
        evidence_key = "earth_sweep_evidence_refs"
        evidence_value = raw.get("earth_sweep_evidence_refs")
    if evidence_value is None:
        evidence_value = []
    evidence_refs = _normalize_text_list(
        evidence_value,
        field_name=f"{field_prefix}.{evidence_key}",
        min_items=min_evidence_refs,
    )

    return {
        "obligation_id": obligation_id,
        "peer_project_id": peer_project_id,
        "responsibility": responsibility,
        "artifact": artifact,
        "obligation_summary": obligation_summary,
        "dependency_prerequisites": dependency_prerequisites,
        "evidence_refs": evidence_refs,
    }


def _normalize_ecosystem_obligations(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("ecosystem_obligations must be a list")
    if not value:
        raise ValueError("ecosystem_obligations must include at least one row")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        field_prefix = f"ecosystem_obligations[{index}]"
        normalized_row = _normalize_ecosystem_obligation_row(
            raw_row=row,
            field_prefix=field_prefix,
            min_evidence_refs=1,
        )
        obligation_id = str(normalized_row["obligation_id"])
        if obligation_id in seen_ids:
            raise ValueError(f"{field_prefix}.obligation_id must be unique")
        seen_ids.add(obligation_id)
        normalized.append(normalized_row)

    return sorted(normalized, key=lambda row: row["obligation_id"])


def _normalize_req_058_unresolved_ideas(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("broad_sweep_context.unresolved_ideas must be a list")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        field_prefix = f"broad_sweep_context.unresolved_ideas[{index}]"
        raw = _require_mapping(row, field_name=field_prefix)
        expected_keys = {
            "risk_id",
            "summary",
            "reason_code",
            "required_evidence_refs",
            "earth_sweep_evidence_refs",
        }
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{field_prefix} has unexpected keys: {unexpected}")

        risk_id = _require_nonempty_text(raw.get("risk_id"), field_name=f"{field_prefix}.risk_id")
        if risk_id in seen_ids:
            raise ValueError(f"{field_prefix}.risk_id must be unique")
        seen_ids.add(risk_id)

        summary = _require_nonempty_text(raw.get("summary"), field_name=f"{field_prefix}.summary")
        reason_code = _require_nonempty_text(raw.get("reason_code"), field_name=f"{field_prefix}.reason_code")
        evidence_value = raw.get("required_evidence_refs")
        evidence_field_name = "required_evidence_refs"
        if evidence_value is None and "earth_sweep_evidence_refs" in raw:
            evidence_value = raw.get("earth_sweep_evidence_refs")
            evidence_field_name = "earth_sweep_evidence_refs"
        if evidence_value is None:
            evidence_value = []
        required_evidence_refs = _normalize_text_list(
            evidence_value,
            field_name=f"{field_prefix}.{evidence_field_name}",
            min_items=0,
        )
        normalized.append(
            {
                "risk_id": risk_id,
                "summary": summary,
                "reason_code": reason_code,
                "required_evidence_refs": required_evidence_refs,
            }
        )

    return sorted(normalized, key=lambda row: row["risk_id"])


def _normalize_req_058_broad_sweep_context(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None

    raw = _require_mapping(value, field_name="broad_sweep_context")
    expected_keys = {
        "earth_sweep_evidence_refs",
        "projects_considered",
        "cross_project_obligations",
        "unresolved_ideas",
    }
    raw_keys = set(raw.keys())
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"broad_sweep_context has unexpected keys: {unexpected}")

    earth_sweep_evidence_refs = _normalize_text_list(
        raw.get("earth_sweep_evidence_refs") if "earth_sweep_evidence_refs" in raw else [],
        field_name="broad_sweep_context.earth_sweep_evidence_refs",
        min_items=0,
    )
    projects_considered = _normalize_text_list(
        raw.get("projects_considered") if "projects_considered" in raw else [],
        field_name="broad_sweep_context.projects_considered",
        min_items=0,
    )

    cross_project_obligations_raw = raw.get("cross_project_obligations")
    if cross_project_obligations_raw is None:
        cross_project_obligations_raw = []
    if not isinstance(cross_project_obligations_raw, list):
        raise ValueError("broad_sweep_context.cross_project_obligations must be a list")

    cross_project_obligations: list[dict[str, Any]] = []
    seen_obligation_ids: set[str] = set()
    for index, row in enumerate(cross_project_obligations_raw):
        field_prefix = f"broad_sweep_context.cross_project_obligations[{index}]"
        normalized_row = _normalize_ecosystem_obligation_row(
            raw_row=row,
            field_prefix=field_prefix,
            min_evidence_refs=0,
            allow_context_evidence_alias=True,
        )
        obligation_id = str(normalized_row["obligation_id"])
        if obligation_id in seen_obligation_ids:
            raise ValueError(f"{field_prefix}.obligation_id must be unique")
        seen_obligation_ids.add(obligation_id)
        cross_project_obligations.append(normalized_row)

    unresolved_ideas = _normalize_req_058_unresolved_ideas(raw.get("unresolved_ideas"))

    return {
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
        "projects_considered": projects_considered,
        "cross_project_obligations": sorted(cross_project_obligations, key=lambda row: row["obligation_id"]),
        "unresolved_ideas": unresolved_ideas,
    }


def _merge_req_058_obligation_candidates(
    *,
    explicit_obligations: list[dict[str, Any]],
    context_obligations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in list(explicit_obligations) + list(context_obligations):
        obligation_id = str(row["obligation_id"])
        if obligation_id not in merged:
            merged[obligation_id] = {
                "obligation_id": obligation_id,
                "peer_project_id": str(row["peer_project_id"]),
                "responsibility": str(row["responsibility"]),
                "artifact": str(row["artifact"]),
                "obligation_summary": str(row["obligation_summary"]),
                "dependency_prerequisites": list(row["dependency_prerequisites"]),
                "evidence_refs": list(row["evidence_refs"]),
            }
            continue

        existing = merged[obligation_id]
        for field_name in ("peer_project_id", "responsibility", "artifact", "obligation_summary"):
            if existing[field_name] != row[field_name]:
                raise ValueError(f"obligation_id {obligation_id} has conflicting values for {field_name}")
        existing["dependency_prerequisites"] = sorted(
            set(existing["dependency_prerequisites"]) | set(row["dependency_prerequisites"])
        )
        existing["evidence_refs"] = sorted(set(existing["evidence_refs"]) | set(row["evidence_refs"]))

    return sorted(merged.values(), key=lambda row: row["obligation_id"])


def _merge_req_058_open_risks(*, generated_risks: list[dict[str, Any]], context_risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in list(generated_risks) + list(context_risks):
        risk_id = str(row["risk_id"])
        if risk_id not in merged:
            merged[risk_id] = {
                "risk_id": risk_id,
                "summary": str(row["summary"]),
                "reason_code": str(row["reason_code"]),
                "required_evidence_refs": list(row["required_evidence_refs"]),
            }
            continue

        existing = merged[risk_id]
        if existing["summary"] != row["summary"] or existing["reason_code"] != row["reason_code"]:
            raise ValueError(f"risk_id {risk_id} has conflicting values")
        existing["required_evidence_refs"] = sorted(
            set(existing["required_evidence_refs"]) | set(row["required_evidence_refs"])
        )

    return sorted(merged.values(), key=lambda row: row["risk_id"])


def _partition_req_058_obligations_against_broad_sweep(
    *,
    target_project_id: str,
    candidate_obligations: list[dict[str, Any]],
    broad_sweep_context: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    approved: list[dict[str, Any]] = []
    generated_risks: list[dict[str, Any]] = []

    earth_sweep_evidence_refs: set[str] = set()
    if broad_sweep_context is not None:
        earth_sweep_evidence_refs = set(broad_sweep_context["earth_sweep_evidence_refs"])

    for row in candidate_obligations:
        if row["peer_project_id"] == target_project_id:
            raise ValueError("ecosystem_obligations.peer_project_id must reference an external Earth app")

        if broad_sweep_context is None:
            approved.append(row)
            continue

        obligation_refs = list(row["evidence_refs"])
        matched_refs = sorted(ref for ref in obligation_refs if ref in earth_sweep_evidence_refs)
        if matched_refs:
            approved.append(row)
            continue

        generated_risks.append(
            {
                "risk_id": f"risk.{row['obligation_id']}",
                "summary": (
                    "Cross-project obligation withheld until Earth-sweep evidence refs are attached: "
                    f"{row['obligation_summary']}"
                ),
                "reason_code": _REQ_058_OPEN_RISK_REASON_MISSING_EARTH_SWEEP_EVIDENCE,
                "required_evidence_refs": obligation_refs,
            }
        )

    return sorted(approved, key=lambda row: row["obligation_id"]), sorted(generated_risks, key=lambda row: row["risk_id"])


def _build_req_058_processing_behavior(
    *,
    target_project: Mapping[str, Any],
    broad_sweep_context: Mapping[str, Any],
    candidate_obligations: list[dict[str, Any]],
    approved_obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
) -> dict[str, Any]:
    projects_considered = list(broad_sweep_context["projects_considered"])
    earth_sweep_evidence_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    broad_context_obligation_ids = [str(row["obligation_id"]) for row in broad_sweep_context["cross_project_obligations"]]
    unresolved_idea_ids = [str(row["risk_id"]) for row in broad_sweep_context["unresolved_ideas"]]

    recommendation_evidence_refs = sorted(
        {
            reference
            for reference in (
                list(earth_sweep_evidence_refs)
                + [ref for row in approved_obligations for ref in row["evidence_refs"]]
                + [ref for row in open_risks for ref in row["required_evidence_refs"]]
            )
        }
    )

    if approved_obligations and not open_risks:
        decision = "proceed"
        confidence = "high"
    elif approved_obligations:
        decision = "proceed-with-open-risks"
        confidence = "medium"
    else:
        decision = "resolve-context-gaps"
        confidence = "low"

    rationale = (
        f"candidate_obligations={len(candidate_obligations)} approved={len(approved_obligations)} "
        f"open_risks={len(open_risks)} projects={len(projects_considered)} "
        f"earth_refs={len(earth_sweep_evidence_refs)}"
    )

    return {
        "strategy": REQ_058_PROCESSING_STRATEGY,
        "reasoning_mode": REQ_058_REASONING_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "target_project": dict(target_project),
            "broad_sweep_context": {
                "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
                "projects_considered": projects_considered,
                "cross_project_obligations": list(broad_sweep_context["cross_project_obligations"]),
                "unresolved_ideas": list(broad_sweep_context["unresolved_ideas"]),
            },
        },
        "context_usage": {
            "broad_sweep_context_used": bool(
                earth_sweep_evidence_refs
                or projects_considered
                or broad_context_obligation_ids
                or unresolved_idea_ids
            ),
            "cross_project_context_used": bool(projects_considered),
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
            "projects_considered": projects_considered,
            "candidate_obligations_considered": len(candidate_obligations),
            "obligations_emitted": len(approved_obligations),
            "open_risks_count": len(open_risks),
        },
        "recommendation": {
            "decision": decision,
            "rationale": rationale,
            "confidence": confidence,
            "evidence_refs": recommendation_evidence_refs,
            "context_project_ids": projects_considered,
            "cross_project_context": {
                "projects_considered": projects_considered,
                "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
                "cross_project_obligation_ids": sorted(broad_context_obligation_ids),
                "unresolved_idea_ids": sorted(unresolved_idea_ids),
            },
            "approved_ecosystem_obligations": [
                {
                    "obligation_id": row["obligation_id"],
                    "peer_project_id": row["peer_project_id"],
                    "responsibility": row["responsibility"],
                    "artifact": row["artifact"],
                    "evidence_refs": row["evidence_refs"],
                }
                for row in approved_obligations
            ],
            "open_risks": list(open_risks),
        },
    }


def build_req_058_ecosystem_obligation_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-058 payload for ecosystem obligation artifact handoff."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_058_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_058_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    explicit_obligations: list[dict[str, Any]] = []
    if raw.get("ecosystem_obligations") is not None:
        explicit_obligations = _normalize_ecosystem_obligations(raw.get("ecosystem_obligations"))
    broad_sweep_context = _normalize_req_058_broad_sweep_context(raw.get("broad_sweep_context"))
    context_obligations = list(broad_sweep_context["cross_project_obligations"]) if broad_sweep_context else []
    candidate_obligations = _merge_req_058_obligation_candidates(
        explicit_obligations=explicit_obligations,
        context_obligations=context_obligations,
    )
    if not candidate_obligations:
        raise ValueError("ecosystem_obligations must include at least one row")

    target_project_id = target_project["project_id"]
    ecosystem_obligations, generated_risks = _partition_req_058_obligations_against_broad_sweep(
        target_project_id=target_project_id,
        candidate_obligations=candidate_obligations,
        broad_sweep_context=broad_sweep_context,
    )
    context_open_risks = [
        {
            "risk_id": str(row["risk_id"]),
            "summary": str(row["summary"]),
            "reason_code": _REQ_058_OPEN_RISK_REASON_UNRESOLVED_IDEA,
            "required_evidence_refs": list(row["required_evidence_refs"]),
        }
        for row in (list(broad_sweep_context["unresolved_ideas"]) if broad_sweep_context else [])
    ]
    open_risks = _merge_req_058_open_risks(generated_risks=generated_risks, context_risks=context_open_risks)

    if not ecosystem_obligations:
        raise ValueError("ecosystem_obligations must include at least one Earth-sweep-supported row")

    unique_dependency_prerequisites = sorted(
        {
            prerequisite
            for row in ecosystem_obligations
            for prerequisite in row["dependency_prerequisites"]
        }
    )
    produce_responsibilities = sum(1 for row in ecosystem_obligations if row["responsibility"] == "produce")
    consume_responsibilities = sum(1 for row in ecosystem_obligations if row["responsibility"] == "consume")

    built = {
        "ok": True,
        "schema_version": REQ_058_SCHEMA_VERSION,
        "requirement_id": REQ_058_REQUIREMENT_ID,
        "analysis_type": REQ_058_ANALYSIS_TYPE,
        "call_id": REQ_058_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "ecosystem_obligation_artifact": {
            "ecosystem_obligations": ecosystem_obligations,
        },
        "totals": {
            "ecosystem_obligations": len(ecosystem_obligations),
            "produce_responsibilities": produce_responsibilities,
            "consume_responsibilities": consume_responsibilities,
            "unique_dependency_prerequisites": len(unique_dependency_prerequisites),
        },
    }
    if broad_sweep_context is not None:
        built["processing_behavior"] = _build_req_058_processing_behavior(
            target_project=target_project,
            broad_sweep_context=broad_sweep_context,
            candidate_obligations=candidate_obligations,
            approved_obligations=ecosystem_obligations,
            open_risks=open_risks,
        )

    errors = validate_req_058_ecosystem_obligation_artifact(built)
    if errors:
        raise ValueError(f"built REQ-058 payload failed validation: {errors}")
    return built


def _normalize_req_064_source_references(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("source_references must be a list")
    if not value:
        raise ValueError("source_references must include at least one row")

    normalized: list[dict[str, str]] = []
    seen_evidence_refs: set[str] = set()
    for index, row in enumerate(value):
        row_path = f"source_references[{index}]"
        raw = _require_mapping(row, field_name=row_path)
        expected_keys = {
            "evidence_ref",
            "source_path",
            "source_excerpt",
        }
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{row_path} has unexpected keys: {unexpected}")
        missing = sorted(expected_keys - row_keys)
        if missing:
            raise ValueError(f"{row_path} missing keys: {missing}")

        evidence_ref = _require_nonempty_text(raw.get("evidence_ref"), field_name=f"{row_path}.evidence_ref")
        if evidence_ref in seen_evidence_refs:
            raise ValueError(f"{row_path}.evidence_ref must be unique")
        seen_evidence_refs.add(evidence_ref)

        source_path = _require_nonempty_text(raw.get("source_path"), field_name=f"{row_path}.source_path")
        source_excerpt = _require_nonempty_text(raw.get("source_excerpt"), field_name=f"{row_path}.source_excerpt")
        normalized.append(
            {
                "evidence_ref": evidence_ref,
                "source_path": source_path,
                "source_excerpt": source_excerpt,
            }
        )

    return sorted(normalized, key=lambda row: row["evidence_ref"])


def _normalize_req_064_claims(
    value: Any,
    *,
    field_name: str,
    valid_evidence_refs: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if not value:
        raise ValueError(f"{field_name} must include at least one row")

    normalized: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for index, row in enumerate(value):
        row_path = f"{field_name}[{index}]"
        raw = _require_mapping(row, field_name=row_path)
        expected_keys = {"claim_id", "statement", "evidence_refs"}
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{row_path} has unexpected keys: {unexpected}")
        missing = sorted(expected_keys - row_keys)
        if missing:
            raise ValueError(f"{row_path} missing keys: {missing}")

        claim_id = _require_nonempty_text(raw.get("claim_id"), field_name=f"{row_path}.claim_id")
        if claim_id in seen_claim_ids:
            raise ValueError(f"{row_path}.claim_id must be unique")
        seen_claim_ids.add(claim_id)

        statement = _require_nonempty_text(raw.get("statement"), field_name=f"{row_path}.statement")
        evidence_refs = _normalize_text_list(
            raw.get("evidence_refs"),
            field_name=f"{row_path}.evidence_refs",
            min_items=1,
        )
        broken_refs = sorted(set(evidence_refs) - valid_evidence_refs)
        if broken_refs:
            raise ValueError(f"{row_path}.evidence_refs contains unknown evidence refs: {broken_refs}")
        normalized.append(
            {
                "claim_id": claim_id,
                "statement": statement,
                "evidence_refs": evidence_refs,
            }
        )

    return sorted(normalized, key=lambda row: row["claim_id"])


def _normalize_req_064_recommendations(
    value: Any,
    *,
    valid_evidence_refs: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("recommendations must be a list")
    if not value:
        raise ValueError("recommendations must include at least one row")

    normalized: list[dict[str, Any]] = []
    seen_recommendation_ids: set[str] = set()
    for index, row in enumerate(value):
        row_path = f"recommendations[{index}]"
        raw = _require_mapping(row, field_name=row_path)
        expected_keys = {"recommendation_id", "summary", "evidence_refs", "claims"}
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{row_path} has unexpected keys: {unexpected}")
        missing = sorted(expected_keys - row_keys)
        if missing:
            raise ValueError(f"{row_path} missing keys: {missing}")

        recommendation_id = _require_nonempty_text(raw.get("recommendation_id"), field_name=f"{row_path}.recommendation_id")
        if recommendation_id in seen_recommendation_ids:
            raise ValueError(f"{row_path}.recommendation_id must be unique")
        seen_recommendation_ids.add(recommendation_id)

        summary = _require_nonempty_text(raw.get("summary"), field_name=f"{row_path}.summary")
        evidence_refs = _normalize_text_list(
            raw.get("evidence_refs"),
            field_name=f"{row_path}.evidence_refs",
            min_items=1,
        )
        broken_refs = sorted(set(evidence_refs) - valid_evidence_refs)
        if broken_refs:
            raise ValueError(f"{row_path}.evidence_refs contains unknown evidence refs: {broken_refs}")

        claims = _normalize_req_064_claims(
            raw.get("claims"),
            field_name=f"{row_path}.claims",
            valid_evidence_refs=valid_evidence_refs,
        )
        normalized.append(
            {
                "recommendation_id": recommendation_id,
                "summary": summary,
                "evidence_refs": evidence_refs,
                "claims": claims,
            }
        )

    return sorted(normalized, key=lambda row: row["recommendation_id"])


def _build_req_064_recommendation_field_completeness(
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    missing_by_recommendation: dict[str, list[str]] = {}
    for row in recommendations:
        recommendation_id = str(row["recommendation_id"])
        missing: list[str] = []
        for field_name in REQ_064_RECOMMENDATION_REQUIRED_FIELDS:
            value = row.get(field_name)
            if field_name in {"evidence_refs", "claims"}:
                if not isinstance(value, list) or not value:
                    missing.append(field_name)
            elif not isinstance(value, str) or not value.strip():
                missing.append(field_name)
        if missing:
            missing_by_recommendation[recommendation_id] = sorted(missing)

    return {
        "required_fields": list(REQ_064_RECOMMENDATION_REQUIRED_FIELDS),
        "recommendations_total": len(recommendations),
        "complete_recommendations": len(recommendations) - len(missing_by_recommendation),
        "incomplete_recommendations": len(missing_by_recommendation),
        "missing_by_recommendation": {
            key: value for key, value in sorted(missing_by_recommendation.items())
        },
    }


def _build_req_064_processing_behavior(
    *,
    target_project: Mapping[str, Any],
    source_references: list[dict[str, str]],
    recommendations: list[dict[str, Any]],
    broad_sweep_context: Mapping[str, Any],
    accepted_cross_project_obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
) -> dict[str, Any]:
    projects_considered = list(broad_sweep_context["projects_considered"])
    earth_sweep_evidence_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    context_obligations = list(broad_sweep_context["cross_project_obligations"])
    unresolved_ideas = list(broad_sweep_context["unresolved_ideas"])

    claims = [claim for row in recommendations for claim in row["claims"]]
    recommendation_missing_evidence = [
        str(row["recommendation_id"]) for row in recommendations if not row["evidence_refs"]
    ]
    claim_missing_evidence = [str(claim["claim_id"]) for claim in claims if not claim["evidence_refs"]]
    citation_traceability_pass = not recommendation_missing_evidence and not claim_missing_evidence

    recommendation_field_completeness = _build_req_064_recommendation_field_completeness(recommendations)
    recommendation_fields_pass = recommendation_field_completeness["incomplete_recommendations"] == 0

    recommendation_evidence_refs = sorted(
        {
            evidence_ref
            for evidence_ref in (
                [row["evidence_ref"] for row in source_references]
                + earth_sweep_evidence_refs
                + [ref for row in recommendations for ref in row["evidence_refs"]]
                + [ref for claim in claims for ref in claim["evidence_refs"]]
                + [ref for row in accepted_cross_project_obligations for ref in row["evidence_refs"]]
                + [ref for row in open_risks for ref in row["required_evidence_refs"]]
            )
        }
    )

    accepted_obligation_ids = sorted(str(row["obligation_id"]) for row in accepted_cross_project_obligations)
    context_obligation_ids = sorted(str(row["obligation_id"]) for row in context_obligations)
    withheld_obligation_ids = sorted(set(context_obligation_ids) - set(accepted_obligation_ids))
    unresolved_idea_ids = sorted(str(row["risk_id"]) for row in unresolved_ideas)

    if citation_traceability_pass and recommendation_fields_pass and not open_risks:
        decision = "proceed"
        confidence = "high"
    elif citation_traceability_pass and recommendation_fields_pass:
        decision = "proceed-with-open-risks"
        confidence = "medium"
    else:
        decision = "halt-and-fix-traceability"
        confidence = "low"

    rationale = (
        f"source_refs={len(source_references)} recommendations={len(recommendations)} claims={len(claims)} "
        f"accepted_obligations={len(accepted_cross_project_obligations)} open_risks={len(open_risks)} "
        f"citation_traceability_pass={citation_traceability_pass} recommendation_fields_pass={recommendation_fields_pass}"
    )

    return {
        "strategy": REQ_064_PROCESSING_STRATEGY,
        "reasoning_mode": REQ_064_REASONING_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "target_project": dict(target_project),
            "broad_sweep_context": {
                "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
                "projects_considered": projects_considered,
                "cross_project_obligations": context_obligations,
                "unresolved_ideas": unresolved_ideas,
            },
        },
        "context_usage": {
            "broad_sweep_context_used": bool(
                earth_sweep_evidence_refs
                or projects_considered
                or context_obligation_ids
                or unresolved_idea_ids
            ),
            "cross_project_context_used": bool(projects_considered),
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
            "projects_considered": projects_considered,
            "source_references_considered": len(source_references),
            "recommendations_considered": len(recommendations),
            "claims_considered": len(claims),
            "cross_project_obligations_considered": len(context_obligation_ids),
            "cross_project_obligations_accepted": len(accepted_obligation_ids),
            "open_risks_count": len(open_risks),
            "citation_traceability_pass": citation_traceability_pass,
            "recommendation_field_completeness_pass": recommendation_fields_pass,
            "evidence_refs_used": recommendation_evidence_refs,
        },
        "recommendation": {
            "decision": decision,
            "rationale": rationale,
            "confidence": confidence,
            "evidence_refs": recommendation_evidence_refs,
            "context_project_ids": projects_considered,
            "citation_traceability": {
                "recommendations_total": len(recommendations),
                "recommendations_with_evidence_refs": len(recommendations) - len(recommendation_missing_evidence),
                "claims_total": len(claims),
                "claims_with_evidence_refs": len(claims) - len(claim_missing_evidence),
                "missing_recommendation_ids": recommendation_missing_evidence,
                "missing_claim_ids": claim_missing_evidence,
            },
            "recommendation_field_completeness": recommendation_field_completeness,
            "cross_project_context": {
                "projects_considered": projects_considered,
                "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
                "cross_project_obligation_ids": context_obligation_ids,
                "accepted_cross_project_obligation_ids": accepted_obligation_ids,
                "withheld_cross_project_obligation_ids": withheld_obligation_ids,
                "unresolved_idea_ids": unresolved_idea_ids,
            },
            "accepted_cross_project_obligations": [
                {
                    "obligation_id": row["obligation_id"],
                    "peer_project_id": row["peer_project_id"],
                    "responsibility": row["responsibility"],
                    "artifact": row["artifact"],
                    "evidence_refs": row["evidence_refs"],
                }
                for row in accepted_cross_project_obligations
            ],
            "open_risks": list(open_risks),
        },
    }


def build_req_064_source_traceability_validator(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-064 payload for source traceability validator handoff."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_064_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_064_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    source_references = _normalize_req_064_source_references(raw.get("source_references"))
    source_reference_ids = {row["evidence_ref"] for row in source_references}
    recommendations = _normalize_req_064_recommendations(
        raw.get("recommendations"),
        valid_evidence_refs=source_reference_ids,
    )
    broad_sweep_context = _normalize_req_058_broad_sweep_context(raw.get("broad_sweep_context"))
    accepted_cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    if broad_sweep_context is not None:
        accepted_cross_project_obligations, generated_risks = _partition_req_058_obligations_against_broad_sweep(
            target_project_id=target_project["project_id"],
            candidate_obligations=list(broad_sweep_context["cross_project_obligations"]),
            broad_sweep_context=dict(broad_sweep_context),
        )
        unresolved_idea_risks = [
            {
                "risk_id": str(row["risk_id"]),
                "summary": str(row["summary"]),
                "reason_code": str(row["reason_code"]),
                "required_evidence_refs": list(row["required_evidence_refs"]),
            }
            for row in list(broad_sweep_context["unresolved_ideas"])
        ]
        open_risks = _merge_req_058_open_risks(
            generated_risks=generated_risks,
            context_risks=unresolved_idea_risks,
        )

    claims_count = sum(len(row["claims"]) for row in recommendations)
    recommendation_evidence_links = sum(len(row["evidence_refs"]) for row in recommendations)
    claim_evidence_links = sum(
        len(claim["evidence_refs"])
        for row in recommendations
        for claim in row["claims"]
    )

    built = {
        "ok": True,
        "schema_version": REQ_064_SCHEMA_VERSION,
        "requirement_id": REQ_064_REQUIREMENT_ID,
        "analysis_type": REQ_064_ANALYSIS_TYPE,
        "call_id": REQ_064_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "source_traceability_validator": {
            "source_references": source_references,
            "recommendations": recommendations,
        },
        "totals": {
            "source_references": len(source_references),
            "recommendations": len(recommendations),
            "claims": claims_count,
            "recommendation_evidence_links": recommendation_evidence_links,
            "claim_evidence_links": claim_evidence_links,
        },
    }
    if broad_sweep_context is not None:
        built["processing_behavior"] = _build_req_064_processing_behavior(
            target_project=target_project,
            source_references=source_references,
            recommendations=recommendations,
            broad_sweep_context=broad_sweep_context,
            accepted_cross_project_obligations=accepted_cross_project_obligations,
            open_risks=open_risks,
        )

    errors = validate_req_064_source_traceability_validator(built)
    if errors:
        raise ValueError(f"built REQ-064 payload failed validation: {errors}")
    return built


def build_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build normalized REQ-070 payload for end-to-end strategy acceptance packet handoff."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_070_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_070_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    run_identity = _normalize_req_070_run_identity(raw.get("run_identity"))
    current_artifacts = _normalize_req_070_artifact_rows(
        raw.get("current_artifacts"),
        field_name="current_artifacts",
    )
    history_artifacts = _normalize_req_070_artifact_rows(
        raw.get("history_artifacts"),
        field_name="history_artifacts",
    )
    validator_artifacts = _normalize_req_070_artifact_rows(
        raw.get("validator_artifacts"),
        field_name="validator_artifacts",
    )
    planner_consumability = _normalize_req_070_planner_consumability(raw.get("planner_consumability"))
    ecosystem_awareness = _normalize_req_070_ecosystem_awareness(
        value=raw.get("ecosystem_awareness"),
        target_project_id=target_project["project_id"],
    )
    open_risks = _normalize_req_070_open_risks(raw.get("open_risks"))

    all_evidence_refs = sorted(
        {
            reference
            for reference in (
                [ref for row in current_artifacts for ref in row["evidence_refs"]]
                + [ref for row in history_artifacts for ref in row["evidence_refs"]]
                + [ref for row in validator_artifacts for ref in row["evidence_refs"]]
                + list(planner_consumability["evidence_refs"])
                + list(ecosystem_awareness["earth_sweep_evidence_refs"])
                + [ref for row in open_risks for ref in row["required_evidence_refs"]]
            )
        }
    )

    built = {
        "ok": True,
        "schema_version": REQ_070_SCHEMA_VERSION,
        "requirement_id": REQ_070_REQUIREMENT_ID,
        "analysis_type": REQ_070_ANALYSIS_TYPE,
        "call_id": REQ_070_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "run_identity": run_identity,
        "end_to_end_strategy_run_acceptance_packet": {
            "current_artifacts": current_artifacts,
            "history_artifacts": history_artifacts,
            "validator_artifacts": validator_artifacts,
            "planner_consumability": planner_consumability,
            "ecosystem_awareness": ecosystem_awareness,
            "open_risks": open_risks,
        },
        "totals": {
            "current_artifacts": len(current_artifacts),
            "history_artifacts": len(history_artifacts),
            "validator_artifacts": len(validator_artifacts),
            "planner_recommendations": len(planner_consumability["recommendation_ids"]),
            "peer_projects_considered": len(ecosystem_awareness["peer_project_ids"]),
            "open_risks": len(open_risks),
            "evidence_refs": len(all_evidence_refs),
        },
    }

    errors = validate_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(built)
    if errors:
        raise ValueError(f"built REQ-070 payload failed validation: {errors}")
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


def _validate_ecosystem_obligation_row(
    *,
    row: Any,
    index: int,
    target_project_id: str,
    seen_obligation_ids: set[str],
) -> tuple[list[str], set[str], str | None]:
    errors: list[str] = []
    dependency_prerequisites: set[str] = set()
    responsibility: str | None = None
    row_path = f"ecosystem_obligation_artifact.ecosystem_obligations[{index}]"
    if not isinstance(row, Mapping):
        return [f"{row_path} must be an object"], dependency_prerequisites, responsibility

    expected_keys = {
        "obligation_id",
        "peer_project_id",
        "responsibility",
        "artifact",
        "obligation_summary",
        "dependency_prerequisites",
        "evidence_refs",
    }
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{row_path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{row_path} has unexpected keys: {unexpected}")

    obligation_id = row.get("obligation_id")
    if not isinstance(obligation_id, str) or not obligation_id.strip():
        errors.append(f"{row_path}.obligation_id must be a non-empty string")
    elif obligation_id in seen_obligation_ids:
        errors.append(f"{row_path}.obligation_id must be unique")
    else:
        seen_obligation_ids.add(obligation_id)

    peer_project_id = row.get("peer_project_id")
    if not isinstance(peer_project_id, str) or not peer_project_id.strip():
        errors.append(f"{row_path}.peer_project_id must be a non-empty string")
    elif peer_project_id == target_project_id:
        errors.append(f"{row_path}.peer_project_id must reference an external Earth app")

    responsibility_value = row.get("responsibility")
    if responsibility_value not in _RESPONSIBILITY_TYPES:
        errors.append(f"{row_path}.responsibility must be one of: {sorted(_RESPONSIBILITY_TYPES)}")
    else:
        responsibility = str(responsibility_value)

    artifact = row.get("artifact")
    if not isinstance(artifact, str) or not artifact.strip():
        errors.append(f"{row_path}.artifact must be a non-empty string")

    obligation_summary = row.get("obligation_summary")
    if not isinstance(obligation_summary, str) or not obligation_summary.strip():
        errors.append(f"{row_path}.obligation_summary must be a non-empty string")

    prerequisite_errors, prerequisite_list = _validate_nonempty_string_list(
        value=row.get("dependency_prerequisites"),
        field_name=f"{row_path}.dependency_prerequisites",
        min_items=1,
    )
    errors.extend(prerequisite_errors)
    dependency_prerequisites.update(prerequisite_list)

    evidence_errors, _ = _validate_nonempty_string_list(
        value=row.get("evidence_refs"),
        field_name=f"{row_path}.evidence_refs",
        min_items=1,
    )
    errors.extend(evidence_errors)

    return errors, dependency_prerequisites, responsibility


def _validate_req_058_processing_behavior(
    processing_behavior: Any,
    *,
    obligations: list[Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(processing_behavior, Mapping):
        return ["processing_behavior must be an object"]

    expected_top = {
        "strategy",
        "reasoning_mode",
        "heuristic_summarization_only",
        "context_inputs",
        "context_usage",
        "recommendation",
    }
    top_keys = set(processing_behavior.keys())
    missing_top = sorted(expected_top - top_keys)
    if missing_top:
        errors.append(f"processing_behavior missing keys: {missing_top}")
    unexpected_top = sorted(top_keys - expected_top)
    if unexpected_top:
        errors.append(f"processing_behavior has unexpected keys: {unexpected_top}")

    if processing_behavior.get("strategy") != REQ_058_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_058_PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REQ_058_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_058_REASONING_MODE}")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        target_project = context_inputs.get("target_project")
        if not isinstance(target_project, Mapping):
            errors.append("processing_behavior.context_inputs.target_project must be an object")
        broad_sweep_context = context_inputs.get("broad_sweep_context")
        if not isinstance(broad_sweep_context, Mapping):
            errors.append("processing_behavior.context_inputs.broad_sweep_context must be an object")
        else:
            for key in ("earth_sweep_evidence_refs", "projects_considered", "cross_project_obligations", "unresolved_ideas"):
                if not isinstance(broad_sweep_context.get(key), list):
                    errors.append(f"processing_behavior.context_inputs.broad_sweep_context.{key} must be a list")

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        expected_usage_keys = {
            "broad_sweep_context_used",
            "cross_project_context_used",
            "earth_sweep_context_used",
            "projects_considered",
            "candidate_obligations_considered",
            "obligations_emitted",
            "open_risks_count",
        }
        usage_keys = set(context_usage.keys())
        missing_usage = sorted(expected_usage_keys - usage_keys)
        if missing_usage:
            errors.append(f"processing_behavior.context_usage missing keys: {missing_usage}")
        unexpected_usage = sorted(usage_keys - expected_usage_keys)
        if unexpected_usage:
            errors.append(f"processing_behavior.context_usage has unexpected keys: {unexpected_usage}")
        for key in ("broad_sweep_context_used", "cross_project_context_used", "earth_sweep_context_used"):
            if not isinstance(context_usage.get(key), bool):
                errors.append(f"processing_behavior.context_usage.{key} must be a boolean")
        if not isinstance(context_usage.get("projects_considered"), list):
            errors.append("processing_behavior.context_usage.projects_considered must be a list")
        for key in ("candidate_obligations_considered", "obligations_emitted", "open_risks_count"):
            value = context_usage.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"processing_behavior.context_usage.{key} must be a non-negative integer")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
        return errors

    expected_recommendation_keys = {
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "context_project_ids",
        "cross_project_context",
        "approved_ecosystem_obligations",
        "open_risks",
    }
    recommendation_keys = set(recommendation.keys())
    missing_recommendation = sorted(expected_recommendation_keys - recommendation_keys)
    if missing_recommendation:
        errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
    unexpected_recommendation = sorted(recommendation_keys - expected_recommendation_keys)
    if unexpected_recommendation:
        errors.append(f"processing_behavior.recommendation has unexpected keys: {unexpected_recommendation}")

    if recommendation.get("decision") not in {"proceed", "proceed-with-open-risks", "resolve-context-gaps"}:
        errors.append("processing_behavior.recommendation.decision must be a supported value")
    if recommendation.get("confidence") not in _CONFIDENCE_LEVELS:
        errors.append(f"processing_behavior.recommendation.confidence must be one of: {sorted(_CONFIDENCE_LEVELS)}")
    if not isinstance(recommendation.get("rationale"), str) or not str(recommendation.get("rationale")).strip():
        errors.append("processing_behavior.recommendation.rationale must be a non-empty string")

    evidence_errors, _ = _validate_nonempty_string_list(
        value=recommendation.get("evidence_refs"),
        field_name="processing_behavior.recommendation.evidence_refs",
        min_items=1,
    )
    errors.extend(evidence_errors)

    context_ids_errors, _ = _validate_nonempty_string_list(
        value=recommendation.get("context_project_ids"),
        field_name="processing_behavior.recommendation.context_project_ids",
        min_items=0,
    )
    errors.extend(context_ids_errors)

    cross_project_context = recommendation.get("cross_project_context")
    if not isinstance(cross_project_context, Mapping):
        errors.append("processing_behavior.recommendation.cross_project_context must be an object")
    else:
        for key in ("projects_considered", "earth_sweep_evidence_refs", "cross_project_obligation_ids", "unresolved_idea_ids"):
            if not isinstance(cross_project_context.get(key), list):
                errors.append(f"processing_behavior.recommendation.cross_project_context.{key} must be a list")

    approved_rows = recommendation.get("approved_ecosystem_obligations")
    approved_ids: set[str] = set()
    if not isinstance(approved_rows, list):
        errors.append("processing_behavior.recommendation.approved_ecosystem_obligations must be a list")
    else:
        for index, row in enumerate(approved_rows):
            row_path = f"processing_behavior.recommendation.approved_ecosystem_obligations[{index}]"
            if not isinstance(row, Mapping):
                errors.append(f"{row_path} must be an object")
                continue
            for required in ("obligation_id", "peer_project_id", "responsibility", "artifact", "evidence_refs"):
                if required not in row:
                    errors.append(f"{row_path} missing {required}")
            obligation_id = row.get("obligation_id")
            if not isinstance(obligation_id, str) or not obligation_id.strip():
                errors.append(f"{row_path}.obligation_id must be a non-empty string")
                continue
            approved_ids.add(obligation_id)

    open_risks = recommendation.get("open_risks")
    if not isinstance(open_risks, list):
        errors.append("processing_behavior.recommendation.open_risks must be a list")
    else:
        for index, row in enumerate(open_risks):
            row_path = f"processing_behavior.recommendation.open_risks[{index}]"
            if not isinstance(row, Mapping):
                errors.append(f"{row_path} must be an object")
                continue
            for required in ("risk_id", "summary", "reason_code", "required_evidence_refs"):
                if required not in row:
                    errors.append(f"{row_path} missing {required}")

    obligation_ids = {str(row.get("obligation_id")) for row in obligations}
    if approved_ids != obligation_ids:
        errors.append(
            "processing_behavior.recommendation.approved_ecosystem_obligations must mirror ecosystem_obligation_artifact rows"
        )

    return errors


def validate_req_058_ecosystem_obligation_artifact(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-058 ecosystem obligation artifact payload shape."""
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
        "ecosystem_obligation_artifact",
        "totals",
    }
    optional_top = {"processing_behavior"}
    allowed_top = required_top | optional_top
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - allowed_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_058_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_058_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_058_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_058_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_058_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_058_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_058_CALL_ID:
        errors.append(f"call_id must be {REQ_058_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    target_project_id = ""
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
        else:
            target_project_id = project_id
        project_root = target_project.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not str(project_root).startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    ecosystem_artifact = payload.get("ecosystem_obligation_artifact")
    unique_dependency_prerequisites: set[str] = set()
    obligation_count = 0
    produce_responsibilities = 0
    consume_responsibilities = 0
    obligations_for_processing_behavior: list[Mapping[str, Any]] = []
    if not isinstance(ecosystem_artifact, Mapping):
        errors.append("ecosystem_obligation_artifact must be an object")
    else:
        expected_artifact_keys = {"ecosystem_obligations"}
        artifact_keys = set(ecosystem_artifact.keys())
        missing_artifact = sorted(expected_artifact_keys - artifact_keys)
        if missing_artifact:
            errors.append(f"ecosystem_obligation_artifact missing keys: {missing_artifact}")
        unexpected_artifact = sorted(artifact_keys - expected_artifact_keys)
        if unexpected_artifact:
            errors.append(f"ecosystem_obligation_artifact has unexpected keys: {unexpected_artifact}")

        obligations = ecosystem_artifact.get("ecosystem_obligations")
        if not isinstance(obligations, list):
            errors.append("ecosystem_obligation_artifact.ecosystem_obligations must be a list")
        elif not obligations:
            errors.append("ecosystem_obligation_artifact.ecosystem_obligations must include at least one row")
        else:
            obligations_for_processing_behavior = list(obligations)
            obligation_count = len(obligations)
            seen_obligation_ids: set[str] = set()
            for index, row in enumerate(obligations):
                row_errors, prerequisite_ids, responsibility = _validate_ecosystem_obligation_row(
                    row=row,
                    index=index,
                    target_project_id=target_project_id,
                    seen_obligation_ids=seen_obligation_ids,
                )
                errors.extend(row_errors)
                unique_dependency_prerequisites.update(prerequisite_ids)
                if responsibility == "produce":
                    produce_responsibilities += 1
                elif responsibility == "consume":
                    consume_responsibilities += 1

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "ecosystem_obligations",
            "produce_responsibilities",
            "consume_responsibilities",
            "unique_dependency_prerequisites",
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

        if totals.get("ecosystem_obligations") != obligation_count:
            errors.append(
                "totals.ecosystem_obligations must equal ecosystem_obligation_artifact.ecosystem_obligations count"
            )
        if totals.get("produce_responsibilities") != produce_responsibilities:
            errors.append("totals.produce_responsibilities must equal produce responsibility count")
        if totals.get("consume_responsibilities") != consume_responsibilities:
            errors.append("totals.consume_responsibilities must equal consume responsibility count")
        if totals.get("unique_dependency_prerequisites") != len(unique_dependency_prerequisites):
            errors.append("totals.unique_dependency_prerequisites must equal unique prerequisite count")

    if "processing_behavior" in payload:
        errors.extend(
            _validate_req_058_processing_behavior(
                payload.get("processing_behavior"),
                obligations=obligations_for_processing_behavior,
            )
        )

    return errors


def _validate_req_064_source_reference_row(
    *,
    row: Any,
    index: int,
    seen_evidence_refs: set[str],
) -> tuple[list[str], str | None]:
    errors: list[str] = []
    row_path = f"source_traceability_validator.source_references[{index}]"
    if not isinstance(row, Mapping):
        return [f"{row_path} must be an object"], None

    expected_keys = {"evidence_ref", "source_path", "source_excerpt"}
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{row_path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{row_path} has unexpected keys: {unexpected}")

    evidence_ref = row.get("evidence_ref")
    evidence_ref_value: str | None = None
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        errors.append(f"{row_path}.evidence_ref must be a non-empty string")
    elif evidence_ref in seen_evidence_refs:
        errors.append(f"{row_path}.evidence_ref must be unique")
    else:
        evidence_ref_value = evidence_ref.strip()
        seen_evidence_refs.add(evidence_ref_value)

    source_path = row.get("source_path")
    if not isinstance(source_path, str) or not source_path.strip():
        errors.append(f"{row_path}.source_path must be a non-empty string")

    source_excerpt = row.get("source_excerpt")
    if not isinstance(source_excerpt, str) or not source_excerpt.strip():
        errors.append(f"{row_path}.source_excerpt must be a non-empty string")

    return errors, evidence_ref_value


def _validate_req_064_claim_row(
    *,
    row: Any,
    recommendation_index: int,
    claim_index: int,
    seen_claim_ids: set[str],
    source_reference_ids: set[str],
) -> tuple[list[str], int]:
    errors: list[str] = []
    row_path = f"source_traceability_validator.recommendations[{recommendation_index}].claims[{claim_index}]"
    citations_count = 0
    if not isinstance(row, Mapping):
        return [f"{row_path} must be an object"], citations_count

    expected_keys = {"claim_id", "statement", "evidence_refs"}
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{row_path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{row_path} has unexpected keys: {unexpected}")

    claim_id = row.get("claim_id")
    if not isinstance(claim_id, str) or not claim_id.strip():
        errors.append(f"{row_path}.claim_id must be a non-empty string")
    elif claim_id in seen_claim_ids:
        errors.append(f"{row_path}.claim_id must be unique")
    else:
        seen_claim_ids.add(claim_id)

    statement = row.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        errors.append(f"{row_path}.statement must be a non-empty string")

    evidence_errors, evidence_refs = _validate_nonempty_string_list(
        value=row.get("evidence_refs"),
        field_name=f"{row_path}.evidence_refs",
        min_items=1,
    )
    errors.extend(evidence_errors)
    citations_count = len(evidence_refs)

    broken_refs = sorted(set(evidence_refs) - source_reference_ids)
    if broken_refs:
        errors.append(f"{row_path}.evidence_refs contains unknown evidence refs: {broken_refs}")

    return errors, citations_count


def _req_064_nonempty_sorted_unique_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
    return sorted(set(normalized))


def _req_064_claim_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    claim_ids: list[str] = []
    for row in value:
        if not isinstance(row, Mapping):
            continue
        claim_id = row.get("claim_id")
        if isinstance(claim_id, str) and claim_id.strip():
            claim_ids.append(claim_id.strip())
    return sorted(set(claim_ids))


def _req_064_duplicate_recommendation_collision_details(
    *,
    recommendation_id: str,
    first_index: int,
    duplicate_index: int,
    first_row: Mapping[str, Any],
    duplicate_row: Mapping[str, Any],
) -> dict[str, Any]:
    first_summary = first_row.get("summary")
    duplicate_summary = duplicate_row.get("summary")
    first_summary_value = first_summary.strip() if isinstance(first_summary, str) else ""
    duplicate_summary_value = duplicate_summary.strip() if isinstance(duplicate_summary, str) else ""

    first_evidence_refs = _req_064_nonempty_sorted_unique_strings(first_row.get("evidence_refs"))
    duplicate_evidence_refs = _req_064_nonempty_sorted_unique_strings(duplicate_row.get("evidence_refs"))

    first_claim_ids = _req_064_claim_ids(first_row.get("claims"))
    duplicate_claim_ids = _req_064_claim_ids(duplicate_row.get("claims"))

    return {
        "recommendation_id": recommendation_id,
        "first_index": first_index,
        "duplicate_index": duplicate_index,
        "summary_changed": first_summary_value != duplicate_summary_value,
        "evidence_refs_added": sorted(set(duplicate_evidence_refs) - set(first_evidence_refs)),
        "evidence_refs_removed": sorted(set(first_evidence_refs) - set(duplicate_evidence_refs)),
        "claim_ids_added": sorted(set(duplicate_claim_ids) - set(first_claim_ids)),
        "claim_ids_removed": sorted(set(first_claim_ids) - set(duplicate_claim_ids)),
        "claim_count_delta": len(duplicate_claim_ids) - len(first_claim_ids),
    }


def _validate_req_064_recommendation_row(
    *,
    row: Any,
    index: int,
    seen_recommendation_rows: dict[str, tuple[int, Mapping[str, Any]]],
    source_reference_ids: set[str],
) -> tuple[list[str], int, int, int]:
    errors: list[str] = []
    claims_count = 0
    recommendation_links = 0
    claim_links = 0
    row_path = f"source_traceability_validator.recommendations[{index}]"
    if not isinstance(row, Mapping):
        return [f"{row_path} must be an object"], claims_count, recommendation_links, claim_links

    expected_keys = {"recommendation_id", "summary", "evidence_refs", "claims"}
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{row_path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{row_path} has unexpected keys: {unexpected}")

    recommendation_id = row.get("recommendation_id")
    if not isinstance(recommendation_id, str) or not recommendation_id.strip():
        errors.append(f"{row_path}.recommendation_id must be a non-empty string")
    elif recommendation_id in seen_recommendation_rows:
        errors.append(f"{row_path}.recommendation_id must be unique")
        first_index, first_row = seen_recommendation_rows[recommendation_id]
        collision_details = _req_064_duplicate_recommendation_collision_details(
            recommendation_id=recommendation_id,
            first_index=first_index,
            duplicate_index=index,
            first_row=first_row,
            duplicate_row=row,
        )
        errors.append(
            f"{row_path}.recommendation_id duplicate collision details: "
            f"{json.dumps(collision_details, sort_keys=True)}"
        )
    else:
        seen_recommendation_rows[recommendation_id] = (index, row)

    summary = row.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        errors.append(f"{row_path}.summary must be a non-empty string")

    recommendation_evidence_errors, recommendation_evidence_refs = _validate_nonempty_string_list(
        value=row.get("evidence_refs"),
        field_name=f"{row_path}.evidence_refs",
        min_items=1,
    )
    errors.extend(recommendation_evidence_errors)
    recommendation_links = len(recommendation_evidence_refs)
    broken_recommendation_refs = sorted(set(recommendation_evidence_refs) - source_reference_ids)
    if broken_recommendation_refs:
        errors.append(f"{row_path}.evidence_refs contains unknown evidence refs: {broken_recommendation_refs}")

    claims = row.get("claims")
    if not isinstance(claims, list):
        errors.append(f"{row_path}.claims must be a list")
    elif not claims:
        errors.append(f"{row_path}.claims must include at least one row")
    else:
        claims_count = len(claims)
        seen_claim_ids: set[str] = set()
        for claim_index, claim_row in enumerate(claims):
            claim_errors, claim_citations = _validate_req_064_claim_row(
                row=claim_row,
                recommendation_index=index,
                claim_index=claim_index,
                seen_claim_ids=seen_claim_ids,
                source_reference_ids=source_reference_ids,
            )
            errors.extend(claim_errors)
            claim_links += claim_citations

    return errors, claims_count, recommendation_links, claim_links


def _validate_req_064_processing_behavior(
    *,
    processing_behavior: Any,
    recommendations: list[Mapping[str, Any]],
    source_reference_count: int,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(processing_behavior, Mapping):
        return ["processing_behavior must be an object"]

    expected_top = {
        "strategy",
        "reasoning_mode",
        "heuristic_summarization_only",
        "context_inputs",
        "context_usage",
        "recommendation",
    }
    top_keys = set(processing_behavior.keys())
    missing_top = sorted(expected_top - top_keys)
    if missing_top:
        errors.append(f"processing_behavior missing keys: {missing_top}")
    unexpected_top = sorted(top_keys - expected_top)
    if unexpected_top:
        errors.append(f"processing_behavior has unexpected keys: {unexpected_top}")

    if processing_behavior.get("strategy") != REQ_064_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_064_PROCESSING_STRATEGY}")
    if processing_behavior.get("reasoning_mode") != REQ_064_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_064_REASONING_MODE}")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        if not isinstance(context_inputs.get("target_project"), Mapping):
            errors.append("processing_behavior.context_inputs.target_project must be an object")
        broad_sweep_context = context_inputs.get("broad_sweep_context")
        if not isinstance(broad_sweep_context, Mapping):
            errors.append("processing_behavior.context_inputs.broad_sweep_context must be an object")
        else:
            for key in ("earth_sweep_evidence_refs", "projects_considered", "cross_project_obligations", "unresolved_ideas"):
                if not isinstance(broad_sweep_context.get(key), list):
                    errors.append(f"processing_behavior.context_inputs.broad_sweep_context.{key} must be a list")

    claims_count = sum(len(row.get("claims", [])) for row in recommendations if isinstance(row.get("claims"), list))
    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        expected_usage = {
            "broad_sweep_context_used",
            "cross_project_context_used",
            "earth_sweep_context_used",
            "projects_considered",
            "source_references_considered",
            "recommendations_considered",
            "claims_considered",
            "cross_project_obligations_considered",
            "cross_project_obligations_accepted",
            "open_risks_count",
            "citation_traceability_pass",
            "recommendation_field_completeness_pass",
            "evidence_refs_used",
        }
        usage_keys = set(context_usage.keys())
        missing_usage = sorted(expected_usage - usage_keys)
        if missing_usage:
            errors.append(f"processing_behavior.context_usage missing keys: {missing_usage}")
        unexpected_usage = sorted(usage_keys - expected_usage)
        if unexpected_usage:
            errors.append(f"processing_behavior.context_usage has unexpected keys: {unexpected_usage}")

        for key in (
            "broad_sweep_context_used",
            "cross_project_context_used",
            "earth_sweep_context_used",
            "citation_traceability_pass",
            "recommendation_field_completeness_pass",
        ):
            if not isinstance(context_usage.get(key), bool):
                errors.append(f"processing_behavior.context_usage.{key} must be a boolean")

        for key in (
            "source_references_considered",
            "recommendations_considered",
            "claims_considered",
            "cross_project_obligations_considered",
            "cross_project_obligations_accepted",
            "open_risks_count",
        ):
            value = context_usage.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"processing_behavior.context_usage.{key} must be a non-negative integer")

        projects_errors, _ = _validate_nonempty_string_list(
            value=context_usage.get("projects_considered"),
            field_name="processing_behavior.context_usage.projects_considered",
            min_items=0,
        )
        errors.extend(projects_errors)
        evidence_errors, _ = _validate_nonempty_string_list(
            value=context_usage.get("evidence_refs_used"),
            field_name="processing_behavior.context_usage.evidence_refs_used",
            min_items=1,
        )
        errors.extend(evidence_errors)

        if context_usage.get("source_references_considered") != source_reference_count:
            errors.append(
                "processing_behavior.context_usage.source_references_considered must equal source reference count"
            )
        if context_usage.get("recommendations_considered") != len(recommendations):
            errors.append(
                "processing_behavior.context_usage.recommendations_considered must equal recommendation count"
            )
        if context_usage.get("claims_considered") != claims_count:
            errors.append("processing_behavior.context_usage.claims_considered must equal claim count")

        considered = context_usage.get("cross_project_obligations_considered")
        accepted = context_usage.get("cross_project_obligations_accepted")
        if isinstance(considered, int) and isinstance(accepted, int) and accepted > considered:
            errors.append(
                "processing_behavior.context_usage.cross_project_obligations_accepted cannot exceed considered count"
            )

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        expected_recommendation = {
            "decision",
            "rationale",
            "confidence",
            "evidence_refs",
            "context_project_ids",
            "citation_traceability",
            "recommendation_field_completeness",
            "cross_project_context",
            "accepted_cross_project_obligations",
            "open_risks",
        }
        recommendation_keys = set(recommendation.keys())
        missing_recommendation = sorted(expected_recommendation - recommendation_keys)
        if missing_recommendation:
            errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
        unexpected_recommendation = sorted(recommendation_keys - expected_recommendation)
        if unexpected_recommendation:
            errors.append(f"processing_behavior.recommendation has unexpected keys: {unexpected_recommendation}")

        if recommendation.get("decision") not in {"proceed", "proceed-with-open-risks", "halt-and-fix-traceability"}:
            errors.append("processing_behavior.recommendation.decision must be a supported value")
        if recommendation.get("confidence") not in _CONFIDENCE_LEVELS:
            errors.append(f"processing_behavior.recommendation.confidence must be one of: {sorted(_CONFIDENCE_LEVELS)}")
        if not isinstance(recommendation.get("rationale"), str) or not str(recommendation.get("rationale")).strip():
            errors.append("processing_behavior.recommendation.rationale must be a non-empty string")

        recommendation_evidence_errors, _ = _validate_nonempty_string_list(
            value=recommendation.get("evidence_refs"),
            field_name="processing_behavior.recommendation.evidence_refs",
            min_items=1,
        )
        errors.extend(recommendation_evidence_errors)
        recommendation_projects_errors, _ = _validate_nonempty_string_list(
            value=recommendation.get("context_project_ids"),
            field_name="processing_behavior.recommendation.context_project_ids",
            min_items=0,
        )
        errors.extend(recommendation_projects_errors)

        citation_traceability = recommendation.get("citation_traceability")
        if not isinstance(citation_traceability, Mapping):
            errors.append("processing_behavior.recommendation.citation_traceability must be an object")
        else:
            expected_traceability = {
                "recommendations_total",
                "recommendations_with_evidence_refs",
                "claims_total",
                "claims_with_evidence_refs",
                "missing_recommendation_ids",
                "missing_claim_ids",
            }
            traceability_keys = set(citation_traceability.keys())
            missing_traceability = sorted(expected_traceability - traceability_keys)
            if missing_traceability:
                errors.append(
                    "processing_behavior.recommendation.citation_traceability missing keys: "
                    f"{missing_traceability}"
                )
            unexpected_traceability = sorted(traceability_keys - expected_traceability)
            if unexpected_traceability:
                errors.append(
                    "processing_behavior.recommendation.citation_traceability has unexpected keys: "
                    f"{unexpected_traceability}"
                )
            for key in (
                "recommendations_total",
                "recommendations_with_evidence_refs",
                "claims_total",
                "claims_with_evidence_refs",
            ):
                value = citation_traceability.get(key)
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        f"processing_behavior.recommendation.citation_traceability.{key} must be a non-negative integer"
                    )
            for key in ("missing_recommendation_ids", "missing_claim_ids"):
                list_errors, _ = _validate_nonempty_string_list(
                    value=citation_traceability.get(key),
                    field_name=f"processing_behavior.recommendation.citation_traceability.{key}",
                    min_items=0,
                )
                errors.extend(list_errors)

        recommendation_field_completeness = recommendation.get("recommendation_field_completeness")
        if not isinstance(recommendation_field_completeness, Mapping):
            errors.append("processing_behavior.recommendation.recommendation_field_completeness must be an object")
        else:
            expected_completeness = {
                "required_fields",
                "recommendations_total",
                "complete_recommendations",
                "incomplete_recommendations",
                "missing_by_recommendation",
            }
            completeness_keys = set(recommendation_field_completeness.keys())
            missing_completeness = sorted(expected_completeness - completeness_keys)
            if missing_completeness:
                errors.append(
                    "processing_behavior.recommendation.recommendation_field_completeness missing keys: "
                    f"{missing_completeness}"
                )
            unexpected_completeness = sorted(completeness_keys - expected_completeness)
            if unexpected_completeness:
                errors.append(
                    "processing_behavior.recommendation.recommendation_field_completeness has unexpected keys: "
                    f"{unexpected_completeness}"
                )

            required_fields = recommendation_field_completeness.get("required_fields")
            if required_fields != list(REQ_064_RECOMMENDATION_REQUIRED_FIELDS):
                errors.append(
                    "processing_behavior.recommendation.recommendation_field_completeness.required_fields "
                    "must match REQ-064 required fields"
                )
            for key in ("recommendations_total", "complete_recommendations", "incomplete_recommendations"):
                value = recommendation_field_completeness.get(key)
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        "processing_behavior.recommendation.recommendation_field_completeness."
                        f"{key} must be a non-negative integer"
                    )
            if not isinstance(recommendation_field_completeness.get("missing_by_recommendation"), Mapping):
                errors.append(
                    "processing_behavior.recommendation.recommendation_field_completeness.missing_by_recommendation "
                    "must be an object"
                )

        cross_project_context = recommendation.get("cross_project_context")
        if not isinstance(cross_project_context, Mapping):
            errors.append("processing_behavior.recommendation.cross_project_context must be an object")
        else:
            for key in (
                "projects_considered",
                "earth_sweep_evidence_refs",
                "cross_project_obligation_ids",
                "accepted_cross_project_obligation_ids",
                "withheld_cross_project_obligation_ids",
                "unresolved_idea_ids",
            ):
                if not isinstance(cross_project_context.get(key), list):
                    errors.append(f"processing_behavior.recommendation.cross_project_context.{key} must be a list")

        accepted_cross_project_obligations = recommendation.get("accepted_cross_project_obligations")
        if not isinstance(accepted_cross_project_obligations, list):
            errors.append("processing_behavior.recommendation.accepted_cross_project_obligations must be a list")
        else:
            for index, row in enumerate(accepted_cross_project_obligations):
                row_path = f"processing_behavior.recommendation.accepted_cross_project_obligations[{index}]"
                if not isinstance(row, Mapping):
                    errors.append(f"{row_path} must be an object")
                    continue
                expected_row = {"obligation_id", "peer_project_id", "responsibility", "artifact", "evidence_refs"}
                row_keys = set(row.keys())
                missing_row = sorted(expected_row - row_keys)
                if missing_row:
                    errors.append(f"{row_path} missing keys: {missing_row}")
                unexpected_row = sorted(row_keys - expected_row)
                if unexpected_row:
                    errors.append(f"{row_path} has unexpected keys: {unexpected_row}")
                for key in ("obligation_id", "peer_project_id", "responsibility", "artifact"):
                    value = row.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"{row_path}.{key} must be a non-empty string")
                refs_errors, _ = _validate_nonempty_string_list(
                    value=row.get("evidence_refs"),
                    field_name=f"{row_path}.evidence_refs",
                    min_items=1,
                )
                errors.extend(refs_errors)

        open_risks = recommendation.get("open_risks")
        if not isinstance(open_risks, list):
            errors.append("processing_behavior.recommendation.open_risks must be a list")
        else:
            for index, row in enumerate(open_risks):
                row_path = f"processing_behavior.recommendation.open_risks[{index}]"
                if not isinstance(row, Mapping):
                    errors.append(f"{row_path} must be an object")
                    continue
                expected_row = {"risk_id", "summary", "reason_code", "required_evidence_refs"}
                row_keys = set(row.keys())
                missing_row = sorted(expected_row - row_keys)
                if missing_row:
                    errors.append(f"{row_path} missing keys: {missing_row}")
                unexpected_row = sorted(row_keys - expected_row)
                if unexpected_row:
                    errors.append(f"{row_path} has unexpected keys: {unexpected_row}")
                for key in ("risk_id", "summary", "reason_code"):
                    value = row.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"{row_path}.{key} must be a non-empty string")
                refs_errors, _ = _validate_nonempty_string_list(
                    value=row.get("required_evidence_refs"),
                    field_name=f"{row_path}.required_evidence_refs",
                    min_items=0,
                )
                errors.extend(refs_errors)

    return errors


def validate_req_064_source_traceability_validator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-064 source traceability validator payload shape."""
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
        "source_traceability_validator",
        "totals",
    }
    optional_top = {"processing_behavior"}
    top_keys = set(payload.keys())
    missing_top = sorted(expected_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - expected_top - optional_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_064_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_064_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_064_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_064_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_064_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_064_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_064_CALL_ID:
        errors.append(f"call_id must be {REQ_064_CALL_ID}")
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

    source_traceability_validator = payload.get("source_traceability_validator")
    source_reference_count = 0
    recommendation_count = 0
    claims_count = 0
    recommendation_links_count = 0
    claim_links_count = 0
    source_reference_ids: set[str] = set()
    recommendations_for_processing_behavior: list[Mapping[str, Any]] = []
    if not isinstance(source_traceability_validator, Mapping):
        errors.append("source_traceability_validator must be an object")
    else:
        expected_validator_keys = {"source_references", "recommendations"}
        validator_keys = set(source_traceability_validator.keys())
        missing_validator = sorted(expected_validator_keys - validator_keys)
        if missing_validator:
            errors.append(f"source_traceability_validator missing keys: {missing_validator}")
        unexpected_validator = sorted(validator_keys - expected_validator_keys)
        if unexpected_validator:
            errors.append(f"source_traceability_validator has unexpected keys: {unexpected_validator}")

        source_references = source_traceability_validator.get("source_references")
        if not isinstance(source_references, list):
            errors.append("source_traceability_validator.source_references must be a list")
        elif not source_references:
            errors.append("source_traceability_validator.source_references must include at least one row")
        else:
            source_reference_count = len(source_references)
            seen_evidence_refs: set[str] = set()
            for index, row in enumerate(source_references):
                row_errors, evidence_ref = _validate_req_064_source_reference_row(
                    row=row,
                    index=index,
                    seen_evidence_refs=seen_evidence_refs,
                )
                errors.extend(row_errors)
                if evidence_ref:
                    source_reference_ids.add(evidence_ref)

        recommendations = source_traceability_validator.get("recommendations")
        if not isinstance(recommendations, list):
            errors.append("source_traceability_validator.recommendations must be a list")
        elif not recommendations:
            errors.append("source_traceability_validator.recommendations must include at least one row")
        else:
            recommendations_for_processing_behavior = [row for row in recommendations if isinstance(row, Mapping)]
            recommendation_count = len(recommendations)
            seen_recommendation_rows: dict[str, tuple[int, Mapping[str, Any]]] = {}
            for index, row in enumerate(recommendations):
                row_errors, row_claims_count, row_recommendation_links, row_claim_links = _validate_req_064_recommendation_row(
                    row=row,
                    index=index,
                    seen_recommendation_rows=seen_recommendation_rows,
                    source_reference_ids=source_reference_ids,
                )
                errors.extend(row_errors)
                claims_count += row_claims_count
                recommendation_links_count += row_recommendation_links
                claim_links_count += row_claim_links

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "source_references",
            "recommendations",
            "claims",
            "recommendation_evidence_links",
            "claim_evidence_links",
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

        if totals.get("source_references") != source_reference_count:
            errors.append("totals.source_references must equal source_traceability_validator.source_references count")
        if totals.get("recommendations") != recommendation_count:
            errors.append("totals.recommendations must equal source_traceability_validator.recommendations count")
        if totals.get("claims") != claims_count:
            errors.append("totals.claims must equal source_traceability_validator.recommendations[].claims count")
        if totals.get("recommendation_evidence_links") != recommendation_links_count:
            errors.append("totals.recommendation_evidence_links must equal cited recommendation evidence link count")
        if totals.get("claim_evidence_links") != claim_links_count:
            errors.append("totals.claim_evidence_links must equal cited claim evidence link count")

    if "processing_behavior" in payload:
        errors.extend(
            _validate_req_064_processing_behavior(
                processing_behavior=payload.get("processing_behavior"),
                recommendations=recommendations_for_processing_behavior,
                source_reference_count=source_reference_count,
            )
        )

    return errors


def _validate_req_070_artifact_rows(
    *,
    rows: Any,
    field_name: str,
) -> tuple[list[str], int, int]:
    errors: list[str] = []
    artifact_count = 0
    evidence_refs_count = 0
    if not isinstance(rows, list):
        return [f"{field_name} must be a list"], artifact_count, evidence_refs_count
    if not rows:
        errors.append(f"{field_name} must include at least one row")
        return errors, artifact_count, evidence_refs_count

    seen_ids: set[str] = set()
    artifact_count = len(rows)
    for index, row in enumerate(rows):
        row_name = f"{field_name}[{index}]"
        if not isinstance(row, Mapping):
            errors.append(f"{row_name} must be an object")
            continue

        expected_keys = {"artifact_id", "path", "status", "evidence_refs"}
        row_keys = set(row.keys())
        missing_keys = sorted(expected_keys - row_keys)
        if missing_keys:
            errors.append(f"{row_name} missing keys: {missing_keys}")
        unexpected_keys = sorted(row_keys - expected_keys)
        if unexpected_keys:
            errors.append(f"{row_name} has unexpected keys: {unexpected_keys}")

        artifact_id = row.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            errors.append(f"{row_name}.artifact_id must be a non-empty string")
        else:
            normalized_artifact_id = artifact_id.strip()
            if normalized_artifact_id in seen_ids:
                errors.append(f"{row_name}.artifact_id must be unique")
            seen_ids.add(normalized_artifact_id)

        path_value = row.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            errors.append(f"{row_name}.path must be a non-empty string")

        status_value = row.get("status")
        if not isinstance(status_value, str) or not status_value.strip():
            errors.append(f"{row_name}.status must be a non-empty string")
        elif status_value.strip() != status_value.strip().lower():
            errors.append(f"{row_name}.status must be lowercase")

        refs_errors, refs = _validate_nonempty_string_list(
            value=row.get("evidence_refs"),
            field_name=f"{row_name}.evidence_refs",
            min_items=1,
        )
        errors.extend(refs_errors)
        evidence_refs_count += len(refs)

    return errors, artifact_count, evidence_refs_count


def validate_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(
    payload: Mapping[str, Any],
) -> list[str]:
    """Validate REQ-070 end-to-end acceptance packet payload shape."""
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
        "run_identity",
        "end_to_end_strategy_run_acceptance_packet",
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
    if payload.get("schema_version") != REQ_070_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_070_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_070_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_070_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_070_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_070_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_070_CALL_ID:
        errors.append(f"call_id must be {REQ_070_CALL_ID}")
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

    run_identity = payload.get("run_identity")
    if not isinstance(run_identity, Mapping):
        errors.append("run_identity must be an object")
    else:
        expected_run_identity = {"project_id", "run_id", "event_id", "strategy_revision_id", "plan_id"}
        run_identity_keys = set(run_identity.keys())
        missing_run_identity = sorted(expected_run_identity - run_identity_keys)
        if missing_run_identity:
            errors.append(f"run_identity missing keys: {missing_run_identity}")
        unexpected_run_identity = sorted(run_identity_keys - expected_run_identity)
        if unexpected_run_identity:
            errors.append(f"run_identity has unexpected keys: {unexpected_run_identity}")
        for key in expected_run_identity:
            value = run_identity.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"run_identity.{key} must be a non-empty string")

    artifact_payload = payload.get("end_to_end_strategy_run_acceptance_packet")
    current_artifacts_count = 0
    history_artifacts_count = 0
    validator_artifacts_count = 0
    evidence_refs_total = 0
    planner_recommendations_count = 0
    peer_projects_considered = 0
    open_risks_count = 0
    if not isinstance(artifact_payload, Mapping):
        errors.append("end_to_end_strategy_run_acceptance_packet must be an object")
    else:
        expected_packet_keys = {
            "current_artifacts",
            "history_artifacts",
            "validator_artifacts",
            "planner_consumability",
            "ecosystem_awareness",
            "open_risks",
        }
        packet_keys = set(artifact_payload.keys())
        missing_packet = sorted(expected_packet_keys - packet_keys)
        if missing_packet:
            errors.append(f"end_to_end_strategy_run_acceptance_packet missing keys: {missing_packet}")
        unexpected_packet = sorted(packet_keys - expected_packet_keys)
        if unexpected_packet:
            errors.append(f"end_to_end_strategy_run_acceptance_packet has unexpected keys: {unexpected_packet}")

        row_errors, current_artifacts_count, row_evidence_count = _validate_req_070_artifact_rows(
            rows=artifact_payload.get("current_artifacts"),
            field_name="end_to_end_strategy_run_acceptance_packet.current_artifacts",
        )
        errors.extend(row_errors)
        evidence_refs_total += row_evidence_count

        row_errors, history_artifacts_count, row_evidence_count = _validate_req_070_artifact_rows(
            rows=artifact_payload.get("history_artifacts"),
            field_name="end_to_end_strategy_run_acceptance_packet.history_artifacts",
        )
        errors.extend(row_errors)
        evidence_refs_total += row_evidence_count

        row_errors, validator_artifacts_count, row_evidence_count = _validate_req_070_artifact_rows(
            rows=artifact_payload.get("validator_artifacts"),
            field_name="end_to_end_strategy_run_acceptance_packet.validator_artifacts",
        )
        errors.extend(row_errors)
        evidence_refs_total += row_evidence_count

        planner_consumability = artifact_payload.get("planner_consumability")
        if not isinstance(planner_consumability, Mapping):
            errors.append("end_to_end_strategy_run_acceptance_packet.planner_consumability must be an object")
        else:
            expected_planner = {
                "ready_for_planner",
                "recommendation_mapping_complete",
                "consumability_verdict",
                "recommendation_ids",
                "recommendation_mapping_refs",
                "evidence_refs",
            }
            planner_keys = set(planner_consumability.keys())
            missing_planner = sorted(expected_planner - planner_keys)
            if missing_planner:
                errors.append(f"planner_consumability missing keys: {missing_planner}")
            unexpected_planner = sorted(planner_keys - expected_planner)
            if unexpected_planner:
                errors.append(f"planner_consumability has unexpected keys: {unexpected_planner}")

            if not isinstance(planner_consumability.get("ready_for_planner"), bool):
                errors.append("planner_consumability.ready_for_planner must be a boolean")
            elif planner_consumability.get("ready_for_planner") is not True:
                errors.append("planner_consumability.ready_for_planner must be true")

            if not isinstance(planner_consumability.get("recommendation_mapping_complete"), bool):
                errors.append("planner_consumability.recommendation_mapping_complete must be a boolean")
            elif planner_consumability.get("recommendation_mapping_complete") is not True:
                errors.append("planner_consumability.recommendation_mapping_complete must be true")

            verdict = planner_consumability.get("consumability_verdict")
            if not isinstance(verdict, str) or not verdict.strip():
                errors.append("planner_consumability.consumability_verdict must be a non-empty string")
            elif verdict.strip() != verdict.strip().lower():
                errors.append("planner_consumability.consumability_verdict must be lowercase")

            refs_errors, recommendation_ids = _validate_nonempty_string_list(
                value=planner_consumability.get("recommendation_ids"),
                field_name="planner_consumability.recommendation_ids",
                min_items=1,
            )
            errors.extend(refs_errors)
            planner_recommendations_count = len(recommendation_ids)

            refs_errors, _ = _validate_nonempty_string_list(
                value=planner_consumability.get("recommendation_mapping_refs"),
                field_name="planner_consumability.recommendation_mapping_refs",
                min_items=1,
            )
            errors.extend(refs_errors)

            refs_errors, planner_evidence_refs = _validate_nonempty_string_list(
                value=planner_consumability.get("evidence_refs"),
                field_name="planner_consumability.evidence_refs",
                min_items=1,
            )
            errors.extend(refs_errors)
            evidence_refs_total += len(planner_evidence_refs)

        ecosystem_awareness = artifact_payload.get("ecosystem_awareness")
        if not isinstance(ecosystem_awareness, Mapping):
            errors.append("end_to_end_strategy_run_acceptance_packet.ecosystem_awareness must be an object")
        else:
            expected_ecosystem = {
                "ecosystem_aware",
                "context_project_ids",
                "peer_project_ids",
                "earth_sweep_evidence_refs",
            }
            ecosystem_keys = set(ecosystem_awareness.keys())
            missing_ecosystem = sorted(expected_ecosystem - ecosystem_keys)
            if missing_ecosystem:
                errors.append(f"ecosystem_awareness missing keys: {missing_ecosystem}")
            unexpected_ecosystem = sorted(ecosystem_keys - expected_ecosystem)
            if unexpected_ecosystem:
                errors.append(f"ecosystem_awareness has unexpected keys: {unexpected_ecosystem}")

            if not isinstance(ecosystem_awareness.get("ecosystem_aware"), bool):
                errors.append("ecosystem_awareness.ecosystem_aware must be a boolean")
            elif ecosystem_awareness.get("ecosystem_aware") is not True:
                errors.append("ecosystem_awareness.ecosystem_aware must be true")

            refs_errors, context_project_ids = _validate_nonempty_string_list(
                value=ecosystem_awareness.get("context_project_ids"),
                field_name="ecosystem_awareness.context_project_ids",
                min_items=2,
            )
            errors.extend(refs_errors)
            if target_project_id and target_project_id not in context_project_ids:
                errors.append("ecosystem_awareness.context_project_ids must include target_project.project_id")

            refs_errors, peer_project_ids = _validate_nonempty_string_list(
                value=ecosystem_awareness.get("peer_project_ids"),
                field_name="ecosystem_awareness.peer_project_ids",
                min_items=1,
            )
            errors.extend(refs_errors)
            peer_projects_considered = len(peer_project_ids)
            if target_project_id and any(project_id == target_project_id for project_id in peer_project_ids):
                errors.append("ecosystem_awareness.peer_project_ids must reference external Earth apps only")
            if any(project_id not in context_project_ids for project_id in peer_project_ids):
                errors.append("ecosystem_awareness.peer_project_ids must be a subset of context_project_ids")

            refs_errors, earth_sweep_evidence_refs = _validate_nonempty_string_list(
                value=ecosystem_awareness.get("earth_sweep_evidence_refs"),
                field_name="ecosystem_awareness.earth_sweep_evidence_refs",
                min_items=1,
            )
            errors.extend(refs_errors)
            evidence_refs_total += len(earth_sweep_evidence_refs)

        open_risks = artifact_payload.get("open_risks")
        if not isinstance(open_risks, list):
            errors.append("end_to_end_strategy_run_acceptance_packet.open_risks must be a list")
        else:
            open_risks_count = len(open_risks)
            seen_risk_ids: set[str] = set()
            for index, row in enumerate(open_risks):
                row_name = f"end_to_end_strategy_run_acceptance_packet.open_risks[{index}]"
                if not isinstance(row, Mapping):
                    errors.append(f"{row_name} must be an object")
                    continue

                expected_risk_keys = {"risk_id", "summary", "reason_code", "required_evidence_refs"}
                row_keys = set(row.keys())
                missing_risk_keys = sorted(expected_risk_keys - row_keys)
                if missing_risk_keys:
                    errors.append(f"{row_name} missing keys: {missing_risk_keys}")
                unexpected_risk_keys = sorted(row_keys - expected_risk_keys)
                if unexpected_risk_keys:
                    errors.append(f"{row_name} has unexpected keys: {unexpected_risk_keys}")

                risk_id = row.get("risk_id")
                if not isinstance(risk_id, str) or not risk_id.strip():
                    errors.append(f"{row_name}.risk_id must be a non-empty string")
                else:
                    normalized_risk_id = risk_id.strip()
                    if normalized_risk_id in seen_risk_ids:
                        errors.append(f"{row_name}.risk_id must be unique")
                    seen_risk_ids.add(normalized_risk_id)

                for key in ("summary", "reason_code"):
                    value = row.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"{row_name}.{key} must be a non-empty string")

                refs_errors, risk_refs = _validate_nonempty_string_list(
                    value=row.get("required_evidence_refs"),
                    field_name=f"{row_name}.required_evidence_refs",
                    min_items=1,
                )
                errors.extend(refs_errors)
                evidence_refs_total += len(risk_refs)

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "current_artifacts",
            "history_artifacts",
            "validator_artifacts",
            "planner_recommendations",
            "peer_projects_considered",
            "open_risks",
            "evidence_refs",
        }
        totals_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - totals_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(totals_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")

        for key in expected_totals:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")

        if totals.get("current_artifacts") != current_artifacts_count:
            errors.append("totals.current_artifacts must equal current artifact row count")
        if totals.get("history_artifacts") != history_artifacts_count:
            errors.append("totals.history_artifacts must equal history artifact row count")
        if totals.get("validator_artifacts") != validator_artifacts_count:
            errors.append("totals.validator_artifacts must equal validator artifact row count")
        if totals.get("planner_recommendations") != planner_recommendations_count:
            errors.append("totals.planner_recommendations must equal planner recommendation id count")
        if totals.get("peer_projects_considered") != peer_projects_considered:
            errors.append("totals.peer_projects_considered must equal ecosystem peer project id count")
        if totals.get("open_risks") != open_risks_count:
            errors.append("totals.open_risks must equal open risk row count")
        if totals.get("evidence_refs") != evidence_refs_total:
            errors.append("totals.evidence_refs must equal summed evidence reference count")

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
    parser = argparse.ArgumentParser(
        description="Emit strategy artifact payloads for REQ-056, REQ-058, REQ-064, and REQ-070."
    )
    parser.add_argument(
        "--input-json",
        required=True,
        help="Path to REQ-056/REQ-058/REQ-064/REQ-070 input JSON (or '-' for stdin).",
    )
    return parser


def _build_artifact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    has_kpi_targets = "kpi_targets" in payload
    has_ecosystem_obligations = "ecosystem_obligations" in payload
    has_req_058_context = "broad_sweep_context" in payload
    has_source_references = "source_references" in payload
    has_recommendations = "recommendations" in payload
    has_req_070_artifacts = (
        "current_artifacts" in payload
        or "history_artifacts" in payload
        or "validator_artifacts" in payload
        or "planner_consumability" in payload
        or "ecosystem_awareness" in payload
    )

    if analysis_type == REQ_056_ANALYSIS_TYPE or (not analysis_type and has_kpi_targets and not has_ecosystem_obligations):
        return build_req_056_kpi_target_artifact(payload)
    if analysis_type == REQ_058_ANALYSIS_TYPE or (
        not analysis_type and (has_ecosystem_obligations or has_req_058_context) and not has_kpi_targets
    ):
        return build_req_058_ecosystem_obligation_artifact(payload)
    if analysis_type == REQ_064_ANALYSIS_TYPE or (
        not analysis_type
        and (has_source_references or has_recommendations)
        and not has_kpi_targets
        and not has_ecosystem_obligations
        and not has_req_058_context
    ):
        return build_req_064_source_traceability_validator(payload)
    if analysis_type == REQ_070_ANALYSIS_TYPE or (
        not analysis_type
        and has_req_070_artifacts
        and not has_kpi_targets
        and not has_ecosystem_obligations
        and not has_req_058_context
        and not has_source_references
        and not has_recommendations
    ):
        return build_req_070_end_to_end_autonomous_strategy_run_acceptance_packet(payload)

    expected_types = sorted(
        [
            REQ_056_ANALYSIS_TYPE,
            REQ_058_ANALYSIS_TYPE,
            REQ_064_ANALYSIS_TYPE,
            REQ_070_ANALYSIS_TYPE,
        ]
    )
    raise ValueError(f"analysis_type must be one of: {expected_types}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_input_payload(args.input_json)
        built = _build_artifact_payload(payload)
    except Exception as exc:  # pragma: no cover - CLI guardrail
        sys.stderr.write(f"[{_utc_timestamp()}] strategy_artifacts_handoff CLI failed: {exc}\n")
        return 1

    sys.stdout.write(json.dumps(built, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
