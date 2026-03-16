#!/usr/bin/env python3
"""Strategy artifact handoff contract surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REQ_056_REQUIREMENT_ID = "REQ-056"
REQ_056_SCHEMA_VERSION = "1.0"
REQ_056_ANALYSIS_TYPE = "kpi_target_artifact"
REQ_056_CALL_ID = "kpi-target-artifact"
REQ_056_PROCESSING_STRATEGY = "kpi-target-broad-sweep"
REQ_056_REASONING_MODE = "deterministic-broad-sweep"
REQ_062_REQUIREMENT_ID = "REQ-062"
REQ_062_SCHEMA_VERSION = "1.0"
REQ_062_ANALYSIS_TYPE = "recommendation_id_uniqueness_validator"
REQ_062_CALL_ID = "recommendation-id-uniqueness-validator"
REQ_062_PROCESSING_STRATEGY = "recommendation-id-uniqueness-broad-sweep"
REQ_062_REASONING_MODE = "deterministic-broad-sweep"

_EXPECTED_DIRECTIONS = {"increase", "decrease", "maintain"}
_CONFIDENCE_LEVELS = {"high", "medium", "low"}
_EARTH_SWEEP_PREFIX = "reports/earth/sweeps/"
_MISSING_EARTH_SWEEP_EVIDENCE = "missing_earth_sweep_evidence_refs"
_UNRESOLVED_CROSS_PROJECT_IDEA = "unresolved_cross_project_idea"
_REQ_056_RECOMMENDATION_FIELDS = [
    "decision",
    "rationale",
    "confidence",
    "evidence_refs",
    "linked_kpi_target_ids",
    "cross_project_obligations",
    "open_risks",
]
_REQ_062_RECOMMENDATION_FIELDS = [
    "decision",
    "rationale",
    "confidence",
    "evidence_refs",
    "cross_project_obligations",
    "open_risks",
]


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stable_id_fragment(*parts: Any) -> str:
    joined = "||".join(str(part).strip() for part in parts if str(part).strip())
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalize_reference(value: Any, *, field_name: str) -> str:
    text = _require_nonempty_text(value, field_name=field_name)
    base, anchor = text.split("#", 1) if "#" in text else (text, "")
    normalized_base = base.replace("\\", "/")
    while normalized_base.startswith("./"):
        normalized_base = normalized_base[2:]
    normalized_base = normalized_base.replace("/./", "/")
    normalized_base = normalized_base.strip()
    normalized = normalized_base if not anchor else f"{normalized_base}#{anchor.strip()}"
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalized


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


def _normalize_ref_list(value: Any, *, field_name: str, min_items: int = 0) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    normalized: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(value):
        item = _normalize_reference(row, field_name=f"{field_name}[{index}]")
        if item not in seen:
            normalized.append(item)
            seen.add(item)

    normalized_sorted = sorted(normalized)
    if len(normalized_sorted) < min_items:
        raise ValueError(f"{field_name} must include at least {min_items} value(s)")
    return normalized_sorted


def _collect_unique_refs(*groups: Any) -> list[str]:
    refs: set[str] = set()
    for group in groups:
        if isinstance(group, str):
            refs.add(_normalize_reference(group, field_name="reference"))
            continue
        if not isinstance(group, list):
            continue
        for item in group:
            if isinstance(item, str) and item.strip():
                refs.add(_normalize_reference(item, field_name="reference"))
    return sorted(refs)


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

        baseline_reference = _normalize_reference(
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
        evidence_refs = _normalize_ref_list(
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


def _normalize_req_056_obligations(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("broad_sweep_context.cross_project_obligations must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        field_prefix = f"broad_sweep_context.cross_project_obligations[{index}]"
        row = _require_mapping(item, field_name=field_prefix)
        project_raw = row.get("project_id", row.get("target_project_id"))
        if project_raw is None:
            raise ValueError(f"{field_prefix}.project_id is required")
        normalized.append(
            {
                "project_id": _require_nonempty_text(project_raw, field_name=f"{field_prefix}.project_id"),
                "recommendation_ids": _normalize_text_list(
                    row.get("recommendation_ids"),
                    field_name=f"{field_prefix}.recommendation_ids",
                    min_items=1,
                ),
                "earth_sweep_evidence_refs": _normalize_ref_list(
                    row.get("earth_sweep_evidence_refs", []),
                    field_name=f"{field_prefix}.earth_sweep_evidence_refs",
                ),
            }
        )

    return sorted(
        normalized,
        key=lambda row: (
            row["project_id"],
            row["recommendation_ids"],
            row["earth_sweep_evidence_refs"],
        ),
    )


def _normalize_req_056_unresolved_ideas(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("broad_sweep_context.unresolved_ideas must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        field_prefix = f"broad_sweep_context.unresolved_ideas[{index}]"
        row = _require_mapping(item, field_name=field_prefix)
        project_raw = row.get("project_id", row.get("target_project_id"))
        if project_raw is None:
            raise ValueError(f"{field_prefix}.project_id is required")
        summary_raw = row.get("summary", row.get("idea"))
        if summary_raw is None:
            raise ValueError(f"{field_prefix}.summary is required")
        idea_id = row.get("idea_id") or f"idea.{_stable_id_fragment(project_raw, summary_raw)}"
        normalized.append(
            {
                "idea_id": _require_nonempty_text(idea_id, field_name=f"{field_prefix}.idea_id"),
                "summary": _require_nonempty_text(summary_raw, field_name=f"{field_prefix}.summary"),
                "project_id": _require_nonempty_text(project_raw, field_name=f"{field_prefix}.project_id"),
                "recommendation_ids": _normalize_text_list(
                    row.get("recommendation_ids", []),
                    field_name=f"{field_prefix}.recommendation_ids",
                ),
                "earth_sweep_evidence_refs": _normalize_ref_list(
                    row.get("earth_sweep_evidence_refs", []),
                    field_name=f"{field_prefix}.earth_sweep_evidence_refs",
                ),
            }
        )

    return sorted(
        normalized,
        key=lambda row: (
            row["project_id"],
            row["idea_id"],
            row["recommendation_ids"],
            row["earth_sweep_evidence_refs"],
        ),
    )


def _normalize_broad_sweep_context(value: Any) -> dict[str, Any]:
    if value is None:
        return {
            "earth_sweep_evidence_refs": [],
            "projects_considered": [],
            "cross_project_obligations": [],
            "unresolved_ideas": [],
        }

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

    return {
        "earth_sweep_evidence_refs": _normalize_ref_list(
            raw.get("earth_sweep_evidence_refs", []),
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
        ),
        "projects_considered": _normalize_text_list(
            raw.get("projects_considered", []),
            field_name="broad_sweep_context.projects_considered",
        ),
        "cross_project_obligations": _normalize_req_056_obligations(raw.get("cross_project_obligations", [])),
        "unresolved_ideas": _normalize_req_056_unresolved_ideas(raw.get("unresolved_ideas", [])),
    }


def _req_056_target_earth_refs(row: Mapping[str, Any]) -> list[str]:
    refs = list(row.get("evidence_refs", []))
    baseline_reference = str(row.get("baseline_reference") or "")
    if baseline_reference.startswith(_EARTH_SWEEP_PREFIX):
        refs.append(baseline_reference)
    return sorted({ref for ref in refs if ref.startswith(_EARTH_SWEEP_PREFIX)})


def _req_056_linked_target_ids_for_recommendations(
    *,
    recommendation_ids: list[str],
    kpi_targets: list[dict[str, Any]],
) -> list[str]:
    matched_target_ids: list[str] = []
    recommendation_id_set = set(recommendation_ids)
    for row in kpi_targets:
        if recommendation_id_set.intersection(row["originating_recommendation_ids"]):
            matched_target_ids.append(str(row["target_id"]))
    return sorted(set(matched_target_ids))


def _req_056_earth_refs_for_recommendations(
    *,
    recommendation_ids: list[str],
    kpi_targets: list[dict[str, Any]],
) -> list[str]:
    refs: list[str] = []
    recommendation_id_set = set(recommendation_ids)
    for row in kpi_targets:
        if recommendation_id_set.intersection(row["originating_recommendation_ids"]):
            refs.extend(_req_056_target_earth_refs(row))
    return sorted(set(refs))


def _req_056_recommendation_decision(
    *,
    cross_project_obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
    has_cross_project_targets: bool,
) -> str:
    if open_risks and not cross_project_obligations and has_cross_project_targets:
        missing_earth_risks = [
            row for row in open_risks if row.get("reason_code") == _MISSING_EARTH_SWEEP_EVIDENCE
        ]
        if missing_earth_risks:
            return "collect-earth-evidence"
    if open_risks:
        return "proceed-with-open-risks"
    return "proceed"


def _req_056_recommendation_confidence(
    *,
    kpi_targets: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
    decision: str,
) -> str:
    confidence_values = [str(row["confidence_level"]) for row in kpi_targets]
    if decision == "collect-earth-evidence":
        return "low"
    if "low" in confidence_values:
        return "low"
    if open_risks or "medium" in confidence_values:
        return "medium"
    return "high"


def _req_056_recommendation_rationale(
    *,
    linked_kpi_target_ids: list[str],
    cross_project_obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
) -> str:
    return (
        f"KPI targets={len(linked_kpi_target_ids)} "
        f"supported_cross_project_obligations={len(cross_project_obligations)} "
        f"open_risks={len(open_risks)}"
    )


def _build_req_056_processing_behavior(
    *,
    target_project: dict[str, str],
    kpi_targets: list[dict[str, Any]],
    broad_sweep_context: dict[str, Any],
) -> dict[str, Any]:
    linked_recommendation_ids = sorted(
        {recommendation_id for row in kpi_targets for recommendation_id in row["originating_recommendation_ids"]}
    )
    linked_assumption_ids = sorted({assumption_id for row in kpi_targets for assumption_id in row["assumption_ids"]})
    linked_kpi_target_ids = [str(row["target_id"]) for row in kpi_targets]

    target_level_earth_refs = _collect_unique_refs(*[_req_056_target_earth_refs(row) for row in kpi_targets])
    context_earth_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    cross_project_recommendation_ids: set[str] = set()
    for row in kpi_targets:
        if _req_056_target_earth_refs(row):
            cross_project_recommendation_ids.update(row["originating_recommendation_ids"])

    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    for row in broad_sweep_context["cross_project_obligations"]:
        linked_ids = sorted(set(row["recommendation_ids"]).intersection(linked_recommendation_ids))
        if not linked_ids:
            continue
        cross_project_recommendation_ids.update(linked_ids)
        obligation_refs = list(row["earth_sweep_evidence_refs"])
        target_ids = _req_056_linked_target_ids_for_recommendations(recommendation_ids=linked_ids, kpi_targets=kpi_targets)
        if obligation_refs:
            cross_project_obligations.append(
                {
                    "obligation_id": f"obligation.{_stable_id_fragment(row['project_id'], linked_ids)}",
                    "project_id": row["project_id"],
                    "linked_kpi_target_ids": target_ids,
                    "recommendation_ids": linked_ids,
                    "evidence_refs": obligation_refs,
                }
            )
            continue

        open_risks.append(
            {
                "risk_id": f"risk.{_stable_id_fragment(row['project_id'], linked_ids, 'missing-earth-evidence')}",
                "summary": f"Cross-project KPI dependency for {row['project_id']} lacks Earth-sweep evidence refs.",
                "reason_code": _MISSING_EARTH_SWEEP_EVIDENCE,
                "project_id": row["project_id"],
                "linked_kpi_target_ids": target_ids,
                "linked_recommendation_ids": linked_ids,
                "evidence_refs": [],
                "required_evidence_refs": _req_056_earth_refs_for_recommendations(
                    recommendation_ids=linked_ids,
                    kpi_targets=kpi_targets,
                )
                or ["missing:earth-sweep-evidence-ref"],
            }
        )

    for row in broad_sweep_context["unresolved_ideas"]:
        if row["recommendation_ids"]:
            linked_ids = sorted(set(row["recommendation_ids"]).intersection(linked_recommendation_ids))
            if not linked_ids:
                continue
        else:
            linked_ids = []
        cross_project_recommendation_ids.update(linked_ids)
        target_ids = _req_056_linked_target_ids_for_recommendations(recommendation_ids=linked_ids, kpi_targets=kpi_targets)
        required_refs = _collect_unique_refs(
            row["earth_sweep_evidence_refs"],
            _req_056_earth_refs_for_recommendations(recommendation_ids=linked_ids, kpi_targets=kpi_targets),
        ) or ["missing:earth-sweep-evidence-ref"]
        open_risks.append(
            {
                "risk_id": f"risk.{_stable_id_fragment(row['idea_id'], row['project_id'])}",
                "summary": row["summary"],
                "reason_code": _UNRESOLVED_CROSS_PROJECT_IDEA,
                "project_id": row["project_id"],
                "linked_kpi_target_ids": target_ids,
                "linked_recommendation_ids": linked_ids,
                "evidence_refs": row["earth_sweep_evidence_refs"],
                "required_evidence_refs": required_refs,
            }
        )

    cross_project_obligations = sorted(
        cross_project_obligations,
        key=lambda row: (row["project_id"], row["recommendation_ids"], row["linked_kpi_target_ids"]),
    )
    open_risks = sorted(open_risks, key=lambda row: (row["project_id"], row["reason_code"], row["risk_id"]))

    projects_considered = sorted(
        set(broad_sweep_context["projects_considered"])
        | {row["project_id"] for row in broad_sweep_context["cross_project_obligations"]}
        | {row["project_id"] for row in broad_sweep_context["unresolved_ideas"]}
    )
    earth_refs_used = _collect_unique_refs(
        context_earth_refs,
        target_level_earth_refs,
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["evidence_refs"] for row in open_risks],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    recommendation_refs = _collect_unique_refs(
        [row["baseline_reference"] for row in kpi_targets],
        *[row["evidence_refs"] for row in kpi_targets],
        earth_refs_used,
    )

    has_cross_project_targets = bool(cross_project_recommendation_ids)
    decision = _req_056_recommendation_decision(
        cross_project_obligations=cross_project_obligations,
        open_risks=open_risks,
        has_cross_project_targets=has_cross_project_targets,
    )
    recommendation = {
        "decision": decision,
        "rationale": _req_056_recommendation_rationale(
            linked_kpi_target_ids=linked_kpi_target_ids,
            cross_project_obligations=cross_project_obligations,
            open_risks=open_risks,
        ),
        "confidence": _req_056_recommendation_confidence(
            kpi_targets=kpi_targets,
            open_risks=open_risks,
            decision=decision,
        ),
        "evidence_refs": recommendation_refs,
        "linked_kpi_target_ids": linked_kpi_target_ids,
        "cross_project_obligations": cross_project_obligations,
        "open_risks": open_risks,
    }
    recommendation_generation = {
        "recommendation_fields_complete": set(recommendation.keys()) == set(_REQ_056_RECOMMENDATION_FIELDS),
        "required_recommendation_fields": list(_REQ_056_RECOMMENDATION_FIELDS),
        "cross_project_context_used": bool(projects_considered or cross_project_obligations or open_risks),
        "evidence_refs_used": recommendation_refs,
    }

    return {
        "strategy": REQ_056_PROCESSING_STRATEGY,
        "reasoning_mode": REQ_056_REASONING_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "target_project": target_project,
            "kpi_targets": kpi_targets,
            "broad_sweep_context": broad_sweep_context,
        },
        "context_usage": {
            "target_project_context_used": True,
            "broad_sweep_context_used": bool(
                projects_considered
                or broad_sweep_context["earth_sweep_evidence_refs"]
                or broad_sweep_context["cross_project_obligations"]
                or broad_sweep_context["unresolved_ideas"]
            ),
            "cross_project_context_used": recommendation_generation["cross_project_context_used"],
            "earth_sweep_context_used": bool(earth_refs_used),
            "projects_considered": projects_considered,
            "earth_sweep_evidence_refs_used": earth_refs_used,
            "linked_recommendation_ids_used": linked_recommendation_ids,
            "linked_assumption_ids_used": linked_assumption_ids,
            "linked_kpi_target_ids_used": linked_kpi_target_ids,
            "evidence_refs_used": recommendation_refs,
        },
        "recommendation_generation": recommendation_generation,
        "recommendation": recommendation,
    }


def build_req_056_kpi_target_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-056 payload for KPI target artifact handoff."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_056_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_056_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc") or raw.get("checked_at_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    kpi_targets = _normalize_kpi_targets(raw.get("kpi_targets"))

    linked_recommendations = sorted(
        {recommendation_id for row in kpi_targets for recommendation_id in row["originating_recommendation_ids"]}
    )
    linked_assumptions = sorted({assumption_id for row in kpi_targets for assumption_id in row["assumption_ids"]})

    built: dict[str, Any] = {
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

    if "broad_sweep_context" in raw:
        broad_sweep_context = _normalize_broad_sweep_context(raw.get("broad_sweep_context"))
        built["processing_behavior"] = _build_req_056_processing_behavior(
            target_project=target_project,
            kpi_targets=kpi_targets,
            broad_sweep_context=broad_sweep_context,
        )

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


def _validate_req_056_processing_behavior(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["processing_behavior must be an object"]

    expected_keys = {
        "strategy",
        "reasoning_mode",
        "heuristic_summarization_only",
        "context_inputs",
        "context_usage",
        "recommendation_generation",
        "recommendation",
    }
    payload_keys = set(payload.keys())
    missing_keys = sorted(expected_keys - payload_keys)
    if missing_keys:
        errors.append(f"processing_behavior missing keys: {missing_keys}")
    unexpected_keys = sorted(payload_keys - expected_keys)
    if unexpected_keys:
        errors.append(f"processing_behavior has unexpected keys: {unexpected_keys}")

    if payload.get("strategy") != REQ_056_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_056_PROCESSING_STRATEGY}")
    if payload.get("reasoning_mode") != REQ_056_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_056_REASONING_MODE}")
    if payload.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    context_inputs = payload.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        for key in ("target_project", "kpi_targets", "broad_sweep_context"):
            if key not in context_inputs:
                errors.append(f"processing_behavior.context_inputs missing {key}")

    context_usage = payload.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        expected_usage_fields = {
            "target_project_context_used",
            "broad_sweep_context_used",
            "cross_project_context_used",
            "earth_sweep_context_used",
            "projects_considered",
            "earth_sweep_evidence_refs_used",
            "linked_recommendation_ids_used",
            "linked_assumption_ids_used",
            "linked_kpi_target_ids_used",
            "evidence_refs_used",
        }
        missing_usage = sorted(expected_usage_fields - set(context_usage.keys()))
        if missing_usage:
            errors.append(f"processing_behavior.context_usage missing keys: {missing_usage}")
        for key in (
            "target_project_context_used",
            "broad_sweep_context_used",
            "cross_project_context_used",
            "earth_sweep_context_used",
        ):
            if key in context_usage and not isinstance(context_usage.get(key), bool):
                errors.append(f"processing_behavior.context_usage.{key} must be a boolean")
        for key in (
            "projects_considered",
            "earth_sweep_evidence_refs_used",
            "linked_recommendation_ids_used",
            "linked_assumption_ids_used",
            "linked_kpi_target_ids_used",
            "evidence_refs_used",
        ):
            if key in context_usage and not isinstance(context_usage.get(key), list):
                errors.append(f"processing_behavior.context_usage.{key} must be a list")

    recommendation_generation = payload.get("recommendation_generation")
    if not isinstance(recommendation_generation, Mapping):
        errors.append("processing_behavior.recommendation_generation must be an object")
    else:
        expected_generation_fields = {
            "recommendation_fields_complete",
            "required_recommendation_fields",
            "cross_project_context_used",
            "evidence_refs_used",
        }
        missing_generation = sorted(expected_generation_fields - set(recommendation_generation.keys()))
        if missing_generation:
            errors.append(f"processing_behavior.recommendation_generation missing keys: {missing_generation}")
        if (
            "recommendation_fields_complete" in recommendation_generation
            and not isinstance(recommendation_generation.get("recommendation_fields_complete"), bool)
        ):
            errors.append(
                "processing_behavior.recommendation_generation.recommendation_fields_complete must be a boolean"
            )
        for key in ("required_recommendation_fields", "evidence_refs_used"):
            if key in recommendation_generation and not isinstance(recommendation_generation.get(key), list):
                errors.append(f"processing_behavior.recommendation_generation.{key} must be a list")
        if (
            "cross_project_context_used" in recommendation_generation
            and not isinstance(recommendation_generation.get("cross_project_context_used"), bool)
        ):
            errors.append("processing_behavior.recommendation_generation.cross_project_context_used must be a boolean")

    recommendation = payload.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        recommendation_keys = set(recommendation.keys())
        expected_recommendation_keys = set(_REQ_056_RECOMMENDATION_FIELDS)
        missing_recommendation = sorted(expected_recommendation_keys - recommendation_keys)
        if missing_recommendation:
            errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
        unexpected_recommendation = sorted(recommendation_keys - expected_recommendation_keys)
        if unexpected_recommendation:
            errors.append(f"processing_behavior.recommendation has unexpected keys: {unexpected_recommendation}")
        if recommendation.get("decision") not in {"proceed", "proceed-with-open-risks", "collect-earth-evidence"}:
            errors.append(
                "processing_behavior.recommendation.decision must be one of: "
                "['collect-earth-evidence', 'proceed', 'proceed-with-open-risks']"
            )
        if recommendation.get("confidence") not in _CONFIDENCE_LEVELS:
            errors.append(
                f"processing_behavior.recommendation.confidence must be one of: {sorted(_CONFIDENCE_LEVELS)}"
            )
        for key in ("rationale",):
            if key in recommendation and (
                not isinstance(recommendation.get(key), str) or not str(recommendation.get(key)).strip()
            ):
                errors.append(f"processing_behavior.recommendation.{key} must be a non-empty string")
        for key in ("evidence_refs", "linked_kpi_target_ids", "cross_project_obligations", "open_risks"):
            if key in recommendation and not isinstance(recommendation.get(key), list):
                errors.append(f"processing_behavior.recommendation.{key} must be a list")

        if isinstance(recommendation_generation, Mapping):
            expected_complete = recommendation_keys == expected_recommendation_keys
            if recommendation_generation.get("recommendation_fields_complete") != expected_complete:
                errors.append(
                    "processing_behavior.recommendation_generation.recommendation_fields_complete "
                    "must match recommendation field completeness"
                )
            if recommendation_generation.get("required_recommendation_fields") != _REQ_056_RECOMMENDATION_FIELDS:
                errors.append(
                    "processing_behavior.recommendation_generation.required_recommendation_fields "
                    "must match REQ-056 recommendation fields"
                )
            if recommendation_generation.get("evidence_refs_used") != recommendation.get("evidence_refs"):
                errors.append(
                    "processing_behavior.recommendation_generation.evidence_refs_used must match "
                    "processing_behavior.recommendation.evidence_refs"
                )

        if isinstance(context_usage, Mapping):
            if context_usage.get("cross_project_context_used") != bool(
                recommendation.get("cross_project_obligations") or recommendation.get("open_risks")
            ):
                errors.append(
                    "processing_behavior.context_usage.cross_project_context_used must match "
                    "cross-project recommendation output usage"
                )
            if context_usage.get("evidence_refs_used") != recommendation.get("evidence_refs"):
                errors.append(
                    "processing_behavior.context_usage.evidence_refs_used must match "
                    "processing_behavior.recommendation.evidence_refs"
                )

    return errors


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
        "processing_behavior",
    }
    top_keys = set(payload.keys())
    missing_top = sorted((expected_top - {"processing_behavior"}) - top_keys)
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

    if "processing_behavior" in payload:
        errors.extend(_validate_req_056_processing_behavior(payload.get("processing_behavior")))

    return errors


def _normalize_req_062_recommendations(value: Any, *, field_name: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    normalized: list[dict[str, str]] = []
    for index, item in enumerate(value):
        row_path = f"{field_name}[{index}]"
        row = _require_mapping(item, field_name=row_path)
        expected_keys = {"recommendation_key", "recommendation_id"}
        row_keys = set(row.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{row_path} has unexpected keys: {unexpected}")
        missing = sorted(expected_keys - row_keys)
        if missing:
            raise ValueError(f"{row_path} missing keys: {missing}")

        normalized.append(
            {
                "recommendation_key": _require_nonempty_text(
                    row.get("recommendation_key"),
                    field_name=f"{row_path}.recommendation_key",
                ),
                "recommendation_id": _require_nonempty_text(
                    row.get("recommendation_id"),
                    field_name=f"{row_path}.recommendation_id",
                ),
            }
        )

    return sorted(normalized, key=lambda row: (row["recommendation_key"], row["recommendation_id"]))


def _normalize_req_062_revision(value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(value, field_name=field_name)
    expected_keys = {"revision_id", "recommendations"}
    row_keys = set(row.keys())
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    missing = sorted(expected_keys - row_keys)
    if missing:
        raise ValueError(f"{field_name} missing keys: {missing}")

    return {
        "revision_id": _require_nonempty_text(row.get("revision_id"), field_name=f"{field_name}.revision_id"),
        "recommendations": _normalize_req_062_recommendations(
            row.get("recommendations"),
            field_name=f"{field_name}.recommendations",
        ),
    }


def _build_req_062_revision_index(recommendations: list[dict[str, str]]) -> dict[str, Any]:
    id_to_keys_all: dict[str, list[str]] = {}
    key_to_ids: dict[str, set[str]] = {}
    for row in recommendations:
        recommendation_id = row["recommendation_id"]
        recommendation_key = row["recommendation_key"]
        id_to_keys_all.setdefault(recommendation_id, []).append(recommendation_key)
        key_to_ids.setdefault(recommendation_key, set()).add(recommendation_id)

    id_to_row_count = {recommendation_id: len(keys) for recommendation_id, keys in id_to_keys_all.items()}
    id_to_keys = {
        recommendation_id: sorted(set(keys))
        for recommendation_id, keys in id_to_keys_all.items()
    }
    normalized_key_to_ids = {recommendation_key: sorted(ids) for recommendation_key, ids in key_to_ids.items()}

    return {
        "row_count": len(recommendations),
        "unique_ids": sorted(id_to_row_count.keys()),
        "id_to_row_count": id_to_row_count,
        "id_to_keys": id_to_keys,
        "key_to_ids": normalized_key_to_ids,
    }


def _build_req_062_id_collisions(*, revision_id: str, index: Mapping[str, Any]) -> list[dict[str, Any]]:
    collisions: list[dict[str, Any]] = []
    id_to_row_count = index.get("id_to_row_count", {})
    id_to_keys = index.get("id_to_keys", {})
    for recommendation_id in sorted(id_to_row_count.keys()):
        occurrence_count = int(id_to_row_count[recommendation_id])
        if occurrence_count < 2:
            continue
        recommendation_keys = list(id_to_keys.get(recommendation_id, []))
        collisions.append(
            {
                "diagnostic_id": (
                    f"collision.{_stable_id_fragment(revision_id, recommendation_id, occurrence_count, recommendation_keys)}"
                ),
                "revision_id": revision_id,
                "recommendation_id": recommendation_id,
                "occurrence_count": occurrence_count,
                "recommendation_keys": recommendation_keys,
            }
        )
    return collisions


def _req_062_diagnostic_base_refs() -> list[str]:
    sample_path = "strategy/current/samples/REQ-062_recommendation-id-uniqueness-validator.sample.json"
    return [
        f"{sample_path}#revision_snapshots.previous.recommendation_ids",
        f"{sample_path}#revision_snapshots.current.recommendation_ids",
        f"{sample_path}#diagnostics.id_collisions",
        f"{sample_path}#diagnostics.id_drift",
        f"{sample_path}#diagnostics.added_ids",
        f"{sample_path}#diagnostics.removed_ids",
    ]


def _req_062_linked_recommendation_ids(
    *,
    previous_revision: Mapping[str, Any],
    current_revision: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> list[str]:
    linked_ids: set[str] = set()
    for revision in (previous_revision, current_revision):
        for row in revision.get("recommendations", []):
            if isinstance(row, Mapping) and isinstance(row.get("recommendation_id"), str):
                recommendation_id = str(row["recommendation_id"]).strip()
                if recommendation_id:
                    linked_ids.add(recommendation_id)
    for row in diagnostics.get("id_collisions", []):
        if isinstance(row, Mapping):
            recommendation_id = str(row.get("recommendation_id") or "").strip()
            if recommendation_id:
                linked_ids.add(recommendation_id)
    for row in diagnostics.get("id_drift", []):
        if not isinstance(row, Mapping):
            continue
        for key in ("previous_recommendation_ids", "current_recommendation_ids"):
            for recommendation_id in row.get(key, []):
                if isinstance(recommendation_id, str) and recommendation_id.strip():
                    linked_ids.add(recommendation_id.strip())
    for key in ("added_ids", "removed_ids"):
        for recommendation_id in diagnostics.get(key, []):
            if isinstance(recommendation_id, str) and recommendation_id.strip():
                linked_ids.add(recommendation_id.strip())
    return sorted(linked_ids)


def _req_062_recommendation_decision(
    *,
    open_risks: list[dict[str, Any]],
    cross_project_obligations: list[dict[str, Any]],
) -> str:
    missing_earth_risks = [row for row in open_risks if row.get("reason_code") == _MISSING_EARTH_SWEEP_EVIDENCE]
    if missing_earth_risks and not cross_project_obligations:
        return "collect-earth-evidence"
    if open_risks:
        return "proceed-with-open-risks"
    return "proceed"


def _req_062_recommendation_confidence(
    *,
    diagnostics: Mapping[str, Any],
    open_risks: list[dict[str, Any]],
) -> str:
    if open_risks:
        return "low"
    if diagnostics.get("id_collisions") or diagnostics.get("id_drift"):
        return "medium"
    return "high"


def _req_062_recommendation_rationale(
    *,
    diagnostics: Mapping[str, Any],
    cross_project_obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
) -> str:
    return (
        f"id_collisions={len(diagnostics.get('id_collisions', []))} "
        f"id_drift={len(diagnostics.get('id_drift', []))} "
        f"cross_project_obligations={len(cross_project_obligations)} "
        f"open_risks={len(open_risks)}"
    )


def _build_req_062_processing_behavior(
    *,
    previous_revision: dict[str, Any],
    current_revision: dict[str, Any],
    diagnostics: Mapping[str, Any],
    broad_sweep_context: dict[str, Any],
) -> dict[str, Any]:
    linked_recommendation_ids = _req_062_linked_recommendation_ids(
        previous_revision=previous_revision,
        current_revision=current_revision,
        diagnostics=diagnostics,
    )
    linked_diagnostic_ids = sorted(
        {
            str(row.get("diagnostic_id"))
            for key in ("id_collisions", "id_drift")
            for row in diagnostics.get(key, [])
            if isinstance(row, Mapping) and str(row.get("diagnostic_id") or "").strip()
        }
    )
    diagnostic_base_refs = _req_062_diagnostic_base_refs()
    context_earth_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])

    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    for row in diagnostics.get("id_collisions", []):
        if not isinstance(row, Mapping):
            continue
        recommendation_id = str(row.get("recommendation_id") or "").strip()
        diagnostic_id = str(row.get("diagnostic_id") or "").strip()
        open_risks.append(
            {
                "risk_id": f"risk.{_stable_id_fragment('collision', recommendation_id, diagnostic_id)}",
                "summary": (
                    f"Recommendation ID '{recommendation_id}' collides within revision "
                    f"'{str(row.get('revision_id') or '').strip()}'."
                ),
                "reason_code": "recommendation_id_collision",
                "project_id": "",
                "linked_recommendation_ids": [recommendation_id] if recommendation_id else [],
                "linked_diagnostic_ids": [diagnostic_id] if diagnostic_id else [],
                "evidence_refs": _collect_unique_refs(diagnostic_base_refs),
                "required_evidence_refs": _collect_unique_refs(diagnostic_base_refs),
            }
        )

    for row in diagnostics.get("id_drift", []):
        if not isinstance(row, Mapping):
            continue
        recommendation_key = str(row.get("recommendation_key") or "").strip()
        diagnostic_id = str(row.get("diagnostic_id") or "").strip()
        linked_ids = _normalize_text_list(
            list(row.get("previous_recommendation_ids", [])) + list(row.get("current_recommendation_ids", [])),
            field_name="diagnostics.id_drift.linked_recommendation_ids",
        )
        open_risks.append(
            {
                "risk_id": f"risk.{_stable_id_fragment('drift', recommendation_key, diagnostic_id)}",
                "summary": f"Recommendation key '{recommendation_key}' drifted across revisions.",
                "reason_code": "recommendation_id_drift",
                "project_id": "",
                "linked_recommendation_ids": linked_ids,
                "linked_diagnostic_ids": [diagnostic_id] if diagnostic_id else [],
                "evidence_refs": _collect_unique_refs(diagnostic_base_refs),
                "required_evidence_refs": _collect_unique_refs(diagnostic_base_refs),
            }
        )

    for row in broad_sweep_context["cross_project_obligations"]:
        linked_ids = sorted(set(row["recommendation_ids"]).intersection(linked_recommendation_ids))
        if not linked_ids:
            continue
        obligation_refs = sorted(
            {ref for ref in row["earth_sweep_evidence_refs"] if ref.startswith(_EARTH_SWEEP_PREFIX)}
        )
        if obligation_refs:
            cross_project_obligations.append(
                {
                    "obligation_id": f"obligation.{_stable_id_fragment(row['project_id'], linked_ids)}",
                    "project_id": row["project_id"],
                    "recommendation_ids": linked_ids,
                    "linked_diagnostic_ids": linked_diagnostic_ids,
                    "evidence_refs": obligation_refs,
                }
            )
            continue
        open_risks.append(
            {
                "risk_id": f"risk.{_stable_id_fragment(row['project_id'], linked_ids, 'missing-earth-evidence')}",
                "summary": f"Cross-project recommendation dependency for {row['project_id']} lacks Earth-sweep evidence refs.",
                "reason_code": _MISSING_EARTH_SWEEP_EVIDENCE,
                "project_id": row["project_id"],
                "linked_recommendation_ids": linked_ids,
                "linked_diagnostic_ids": linked_diagnostic_ids,
                "evidence_refs": [],
                "required_evidence_refs": context_earth_refs or ["missing:earth-sweep-evidence-ref"],
            }
        )

    for row in broad_sweep_context["unresolved_ideas"]:
        if row["recommendation_ids"]:
            linked_ids = sorted(set(row["recommendation_ids"]).intersection(linked_recommendation_ids))
            if not linked_ids:
                continue
        else:
            linked_ids = []
        required_refs = _collect_unique_refs(row["earth_sweep_evidence_refs"], context_earth_refs) or [
            "missing:earth-sweep-evidence-ref"
        ]
        open_risks.append(
            {
                "risk_id": f"risk.{_stable_id_fragment(row['idea_id'], row['project_id'])}",
                "summary": row["summary"],
                "reason_code": _UNRESOLVED_CROSS_PROJECT_IDEA,
                "project_id": row["project_id"],
                "linked_recommendation_ids": linked_ids,
                "linked_diagnostic_ids": [],
                "evidence_refs": row["earth_sweep_evidence_refs"],
                "required_evidence_refs": required_refs,
            }
        )

    cross_project_obligations = sorted(
        cross_project_obligations,
        key=lambda row: (row["project_id"], row["recommendation_ids"], row["evidence_refs"]),
    )
    open_risks = sorted(
        open_risks,
        key=lambda row: (row["project_id"], row["reason_code"], row["risk_id"]),
    )

    projects_considered = sorted(
        set(broad_sweep_context["projects_considered"])
        | {row["project_id"] for row in broad_sweep_context["cross_project_obligations"]}
        | {row["project_id"] for row in broad_sweep_context["unresolved_ideas"]}
    )
    context_refs_used = _collect_unique_refs(
        context_earth_refs,
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["evidence_refs"] for row in open_risks],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    earth_refs_used = sorted({ref for ref in context_refs_used if ref.startswith(_EARTH_SWEEP_PREFIX)})
    recommendation_refs = _collect_unique_refs(
        diagnostic_base_refs,
        context_refs_used,
    )
    cross_project_context_used = bool(
        projects_considered or cross_project_obligations or [row for row in open_risks if row.get("project_id")]
    )
    decision = _req_062_recommendation_decision(
        open_risks=open_risks,
        cross_project_obligations=cross_project_obligations,
    )
    recommendation = {
        "decision": decision,
        "rationale": _req_062_recommendation_rationale(
            diagnostics=diagnostics,
            cross_project_obligations=cross_project_obligations,
            open_risks=open_risks,
        ),
        "confidence": _req_062_recommendation_confidence(
            diagnostics=diagnostics,
            open_risks=open_risks,
        ),
        "evidence_refs": recommendation_refs,
        "cross_project_obligations": cross_project_obligations,
        "open_risks": open_risks,
    }
    recommendation_generation = {
        "recommendation_fields_complete": set(recommendation.keys()) == set(_REQ_062_RECOMMENDATION_FIELDS),
        "required_recommendation_fields": list(_REQ_062_RECOMMENDATION_FIELDS),
        "cross_project_context_used": cross_project_context_used,
        "evidence_refs_used": recommendation_refs,
    }

    return {
        "strategy": REQ_062_PROCESSING_STRATEGY,
        "reasoning_mode": REQ_062_REASONING_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "previous_revision": previous_revision,
            "current_revision": current_revision,
            "broad_sweep_context": broad_sweep_context,
        },
        "context_usage": {
            "previous_revision_context_used": True,
            "current_revision_context_used": True,
            "broad_sweep_context_used": bool(
                projects_considered
                or broad_sweep_context["earth_sweep_evidence_refs"]
                or broad_sweep_context["cross_project_obligations"]
                or broad_sweep_context["unresolved_ideas"]
            ),
            "cross_project_context_used": cross_project_context_used,
            "earth_sweep_context_used": bool(earth_refs_used),
            "projects_considered": projects_considered,
            "earth_sweep_evidence_refs_used": earth_refs_used,
            "linked_recommendation_ids_used": linked_recommendation_ids,
            "linked_diagnostic_ids_used": linked_diagnostic_ids,
            "evidence_refs_used": recommendation_refs,
        },
        "recommendation_generation": recommendation_generation,
        "recommendation": recommendation,
    }


def build_req_062_recommendation_id_uniqueness_validator(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-062 payload for recommendation ID uniqueness/stability validation."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_062_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_062_ANALYSIS_TYPE}")

    checked_at_utc = _require_nonempty_text(raw.get("now_utc") or raw.get("checked_at_utc"), field_name="now_utc")
    previous_revision = _normalize_req_062_revision(raw.get("previous_revision"), field_name="previous_revision")
    current_revision = _normalize_req_062_revision(raw.get("current_revision"), field_name="current_revision")
    broad_sweep_context = _normalize_broad_sweep_context(raw.get("broad_sweep_context"))

    previous_index = _build_req_062_revision_index(previous_revision["recommendations"])
    current_index = _build_req_062_revision_index(current_revision["recommendations"])

    id_collisions = _build_req_062_id_collisions(
        revision_id=previous_revision["revision_id"],
        index=previous_index,
    ) + _build_req_062_id_collisions(
        revision_id=current_revision["revision_id"],
        index=current_index,
    )

    id_drift: list[dict[str, Any]] = []
    previous_key_to_ids = previous_index["key_to_ids"]
    current_key_to_ids = current_index["key_to_ids"]
    shared_keys = sorted(set(previous_key_to_ids.keys()).intersection(current_key_to_ids.keys()))
    for recommendation_key in shared_keys:
        previous_recommendation_ids = list(previous_key_to_ids[recommendation_key])
        current_recommendation_ids = list(current_key_to_ids[recommendation_key])
        if previous_recommendation_ids == current_recommendation_ids:
            continue
        id_drift.append(
            {
                "diagnostic_id": f"drift.{_stable_id_fragment(recommendation_key, previous_recommendation_ids, current_recommendation_ids)}",
                "recommendation_key": recommendation_key,
                "previous_recommendation_ids": previous_recommendation_ids,
                "current_recommendation_ids": current_recommendation_ids,
            }
        )

    previous_unique_ids = set(previous_index["unique_ids"])
    current_unique_ids = set(current_index["unique_ids"])
    added_ids = sorted(current_unique_ids - previous_unique_ids)
    removed_ids = sorted(previous_unique_ids - current_unique_ids)

    is_unique_within_revision = not id_collisions
    ids_stable_across_revisions = not id_drift

    built: dict[str, Any] = {
        "ok": True,
        "schema_version": REQ_062_SCHEMA_VERSION,
        "requirement_id": REQ_062_REQUIREMENT_ID,
        "analysis_type": REQ_062_ANALYSIS_TYPE,
        "call_id": REQ_062_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "revision_pair": {
            "previous_revision_id": previous_revision["revision_id"],
            "current_revision_id": current_revision["revision_id"],
        },
        "revision_snapshots": {
            "previous": {
                "revision_id": previous_revision["revision_id"],
                "recommendation_ids": sorted(previous_unique_ids),
            },
            "current": {
                "revision_id": current_revision["revision_id"],
                "recommendation_ids": sorted(current_unique_ids),
            },
        },
        "diagnostics": {
            "id_collisions": id_collisions,
            "id_drift": id_drift,
            "added_ids": added_ids,
            "removed_ids": removed_ids,
        },
        "totals": {
            "previous_recommendation_rows": previous_index["row_count"],
            "current_recommendation_rows": current_index["row_count"],
            "previous_unique_recommendation_ids": len(previous_unique_ids),
            "current_unique_recommendation_ids": len(current_unique_ids),
            "added_ids": len(added_ids),
            "removed_ids": len(removed_ids),
            "id_collisions": len(id_collisions),
            "id_drift": len(id_drift),
        },
        "verdict": {
            "is_unique_within_revision": is_unique_within_revision,
            "ids_stable_across_revisions": ids_stable_across_revisions,
            "passed": is_unique_within_revision and ids_stable_across_revisions,
        },
        "processing_behavior": _build_req_062_processing_behavior(
            previous_revision=previous_revision,
            current_revision=current_revision,
            diagnostics={
                "id_collisions": id_collisions,
                "id_drift": id_drift,
                "added_ids": added_ids,
                "removed_ids": removed_ids,
            },
            broad_sweep_context=broad_sweep_context,
        ),
    }

    errors = validate_req_062_recommendation_id_uniqueness_validator(built)
    if errors:
        raise ValueError(f"built REQ-062 payload failed validation: {errors}")
    return built


def _validate_req_062_revision_snapshot(*, payload: Any, field_name: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    recommendation_ids: list[str] = []
    if not isinstance(payload, Mapping):
        return [f"{field_name} must be an object"], recommendation_ids

    expected_keys = {"revision_id", "recommendation_ids"}
    payload_keys = set(payload.keys())
    missing = sorted(expected_keys - payload_keys)
    if missing:
        errors.append(f"{field_name} missing keys: {missing}")
    unexpected = sorted(payload_keys - expected_keys)
    if unexpected:
        errors.append(f"{field_name} has unexpected keys: {unexpected}")

    revision_id = payload.get("revision_id")
    if not isinstance(revision_id, str) or not revision_id.strip():
        errors.append(f"{field_name}.revision_id must be a non-empty string")

    recommendation_errors, recommendation_ids = _validate_nonempty_string_list(
        value=payload.get("recommendation_ids"),
        field_name=f"{field_name}.recommendation_ids",
        min_items=0,
    )
    errors.extend(recommendation_errors)
    return errors, recommendation_ids


def _validate_req_062_id_collision_row(*, row: Any, index: int) -> list[str]:
    errors: list[str] = []
    row_path = f"diagnostics.id_collisions[{index}]"
    if not isinstance(row, Mapping):
        return [f"{row_path} must be an object"]

    expected_keys = {
        "diagnostic_id",
        "revision_id",
        "recommendation_id",
        "occurrence_count",
        "recommendation_keys",
    }
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{row_path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{row_path} has unexpected keys: {unexpected}")

    for key in ("diagnostic_id", "revision_id", "recommendation_id"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{row_path}.{key} must be a non-empty string")

    occurrence_count = row.get("occurrence_count")
    if not isinstance(occurrence_count, int) or occurrence_count < 2:
        errors.append(f"{row_path}.occurrence_count must be an integer >= 2")

    recommendation_key_errors, recommendation_keys = _validate_nonempty_string_list(
        value=row.get("recommendation_keys"),
        field_name=f"{row_path}.recommendation_keys",
        min_items=1,
    )
    errors.extend(recommendation_key_errors)
    if isinstance(occurrence_count, int) and isinstance(row.get("recommendation_keys"), list):
        if occurrence_count < len(recommendation_keys):
            errors.append(
                f"{row_path}.occurrence_count must be >= diagnostics.id_collisions[{index}].recommendation_keys size"
            )

    return errors


def _validate_req_062_id_drift_row(*, row: Any, index: int) -> list[str]:
    errors: list[str] = []
    row_path = f"diagnostics.id_drift[{index}]"
    if not isinstance(row, Mapping):
        return [f"{row_path} must be an object"]

    expected_keys = {
        "diagnostic_id",
        "recommendation_key",
        "previous_recommendation_ids",
        "current_recommendation_ids",
    }
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{row_path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{row_path} has unexpected keys: {unexpected}")

    for key in ("diagnostic_id", "recommendation_key"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{row_path}.{key} must be a non-empty string")

    previous_errors, previous_ids = _validate_nonempty_string_list(
        value=row.get("previous_recommendation_ids"),
        field_name=f"{row_path}.previous_recommendation_ids",
        min_items=1,
    )
    current_errors, current_ids = _validate_nonempty_string_list(
        value=row.get("current_recommendation_ids"),
        field_name=f"{row_path}.current_recommendation_ids",
        min_items=1,
    )
    errors.extend(previous_errors)
    errors.extend(current_errors)

    if previous_ids == current_ids:
        errors.append(f"{row_path} must represent differing previous/current recommendation IDs")

    return errors


def _validate_req_062_processing_behavior(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["processing_behavior must be an object"]

    expected_keys = {
        "strategy",
        "reasoning_mode",
        "heuristic_summarization_only",
        "context_inputs",
        "context_usage",
        "recommendation_generation",
        "recommendation",
    }
    payload_keys = set(payload.keys())
    missing_keys = sorted(expected_keys - payload_keys)
    if missing_keys:
        errors.append(f"processing_behavior missing keys: {missing_keys}")
    unexpected_keys = sorted(payload_keys - expected_keys)
    if unexpected_keys:
        errors.append(f"processing_behavior has unexpected keys: {unexpected_keys}")

    if payload.get("strategy") != REQ_062_PROCESSING_STRATEGY:
        errors.append(f"processing_behavior.strategy must be {REQ_062_PROCESSING_STRATEGY}")
    if payload.get("reasoning_mode") != REQ_062_REASONING_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {REQ_062_REASONING_MODE}")
    if payload.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    context_inputs = payload.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        for key in ("previous_revision", "current_revision", "broad_sweep_context"):
            if key not in context_inputs:
                errors.append(f"processing_behavior.context_inputs missing {key}")

    context_usage = payload.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        expected_usage_fields = {
            "previous_revision_context_used",
            "current_revision_context_used",
            "broad_sweep_context_used",
            "cross_project_context_used",
            "earth_sweep_context_used",
            "projects_considered",
            "earth_sweep_evidence_refs_used",
            "linked_recommendation_ids_used",
            "linked_diagnostic_ids_used",
            "evidence_refs_used",
        }
        missing_usage = sorted(expected_usage_fields - set(context_usage.keys()))
        if missing_usage:
            errors.append(f"processing_behavior.context_usage missing keys: {missing_usage}")
        for key in (
            "previous_revision_context_used",
            "current_revision_context_used",
            "broad_sweep_context_used",
            "cross_project_context_used",
            "earth_sweep_context_used",
        ):
            if key in context_usage and not isinstance(context_usage.get(key), bool):
                errors.append(f"processing_behavior.context_usage.{key} must be a boolean")
        for key in (
            "projects_considered",
            "earth_sweep_evidence_refs_used",
            "linked_recommendation_ids_used",
            "linked_diagnostic_ids_used",
            "evidence_refs_used",
        ):
            if key in context_usage and not isinstance(context_usage.get(key), list):
                errors.append(f"processing_behavior.context_usage.{key} must be a list")

    recommendation_generation = payload.get("recommendation_generation")
    if not isinstance(recommendation_generation, Mapping):
        errors.append("processing_behavior.recommendation_generation must be an object")
    else:
        expected_generation_fields = {
            "recommendation_fields_complete",
            "required_recommendation_fields",
            "cross_project_context_used",
            "evidence_refs_used",
        }
        missing_generation = sorted(expected_generation_fields - set(recommendation_generation.keys()))
        if missing_generation:
            errors.append(f"processing_behavior.recommendation_generation missing keys: {missing_generation}")
        if (
            "recommendation_fields_complete" in recommendation_generation
            and not isinstance(recommendation_generation.get("recommendation_fields_complete"), bool)
        ):
            errors.append(
                "processing_behavior.recommendation_generation.recommendation_fields_complete must be a boolean"
            )
        if (
            "cross_project_context_used" in recommendation_generation
            and not isinstance(recommendation_generation.get("cross_project_context_used"), bool)
        ):
            errors.append("processing_behavior.recommendation_generation.cross_project_context_used must be a boolean")
        for key in ("required_recommendation_fields", "evidence_refs_used"):
            if key in recommendation_generation and not isinstance(recommendation_generation.get(key), list):
                errors.append(f"processing_behavior.recommendation_generation.{key} must be a list")

    recommendation = payload.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        recommendation_keys = set(recommendation.keys())
        expected_recommendation_keys = set(_REQ_062_RECOMMENDATION_FIELDS)
        missing_recommendation = sorted(expected_recommendation_keys - recommendation_keys)
        if missing_recommendation:
            errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
        unexpected_recommendation = sorted(recommendation_keys - expected_recommendation_keys)
        if unexpected_recommendation:
            errors.append(f"processing_behavior.recommendation has unexpected keys: {unexpected_recommendation}")
        if recommendation.get("decision") not in {"proceed", "proceed-with-open-risks", "collect-earth-evidence"}:
            errors.append(
                "processing_behavior.recommendation.decision must be one of: "
                "['collect-earth-evidence', 'proceed', 'proceed-with-open-risks']"
            )
        if recommendation.get("confidence") not in _CONFIDENCE_LEVELS:
            errors.append(
                f"processing_behavior.recommendation.confidence must be one of: {sorted(_CONFIDENCE_LEVELS)}"
            )
        if not isinstance(recommendation.get("rationale"), str) or not str(recommendation.get("rationale")).strip():
            errors.append("processing_behavior.recommendation.rationale must be a non-empty string")
        for key in ("evidence_refs", "cross_project_obligations", "open_risks"):
            if key in recommendation and not isinstance(recommendation.get(key), list):
                errors.append(f"processing_behavior.recommendation.{key} must be a list")

        if isinstance(recommendation_generation, Mapping):
            expected_complete = recommendation_keys == expected_recommendation_keys
            if recommendation_generation.get("recommendation_fields_complete") != expected_complete:
                errors.append(
                    "processing_behavior.recommendation_generation.recommendation_fields_complete "
                    "must match recommendation field completeness"
                )
            if recommendation_generation.get("required_recommendation_fields") != _REQ_062_RECOMMENDATION_FIELDS:
                errors.append(
                    "processing_behavior.recommendation_generation.required_recommendation_fields "
                    "must match REQ-062 recommendation fields"
                )
            if recommendation_generation.get("evidence_refs_used") != recommendation.get("evidence_refs"):
                errors.append(
                    "processing_behavior.recommendation_generation.evidence_refs_used must match "
                    "processing_behavior.recommendation.evidence_refs"
                )

        if isinstance(context_usage, Mapping):
            if context_usage.get("evidence_refs_used") != recommendation.get("evidence_refs"):
                errors.append(
                    "processing_behavior.context_usage.evidence_refs_used must match "
                    "processing_behavior.recommendation.evidence_refs"
                )
        if isinstance(recommendation_generation, Mapping) and isinstance(context_usage, Mapping):
            if recommendation_generation.get("cross_project_context_used") != context_usage.get(
                "cross_project_context_used"
            ):
                errors.append(
                    "processing_behavior.recommendation_generation.cross_project_context_used must match "
                    "processing_behavior.context_usage.cross_project_context_used"
                )

    return errors


def validate_req_062_recommendation_id_uniqueness_validator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-062 recommendation ID uniqueness/stability payload shape."""
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
        "revision_pair",
        "revision_snapshots",
        "diagnostics",
        "totals",
        "verdict",
        "processing_behavior",
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
    if payload.get("schema_version") != REQ_062_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_062_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_062_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_062_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_062_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_062_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_062_CALL_ID:
        errors.append(f"call_id must be {REQ_062_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    revision_pair = payload.get("revision_pair")
    previous_pair_revision_id = ""
    current_pair_revision_id = ""
    if not isinstance(revision_pair, Mapping):
        errors.append("revision_pair must be an object")
    else:
        expected_pair_keys = {"previous_revision_id", "current_revision_id"}
        pair_keys = set(revision_pair.keys())
        missing_pair = sorted(expected_pair_keys - pair_keys)
        if missing_pair:
            errors.append(f"revision_pair missing keys: {missing_pair}")
        unexpected_pair = sorted(pair_keys - expected_pair_keys)
        if unexpected_pair:
            errors.append(f"revision_pair has unexpected keys: {unexpected_pair}")
        previous_pair_revision_id = str(revision_pair.get("previous_revision_id") or "").strip()
        current_pair_revision_id = str(revision_pair.get("current_revision_id") or "").strip()
        if not previous_pair_revision_id:
            errors.append("revision_pair.previous_revision_id must be a non-empty string")
        if not current_pair_revision_id:
            errors.append("revision_pair.current_revision_id must be a non-empty string")

    previous_snapshot_ids: list[str] = []
    current_snapshot_ids: list[str] = []
    revision_snapshots = payload.get("revision_snapshots")
    if not isinstance(revision_snapshots, Mapping):
        errors.append("revision_snapshots must be an object")
    else:
        expected_snapshot_keys = {"previous", "current"}
        snapshot_keys = set(revision_snapshots.keys())
        missing_snapshot = sorted(expected_snapshot_keys - snapshot_keys)
        if missing_snapshot:
            errors.append(f"revision_snapshots missing keys: {missing_snapshot}")
        unexpected_snapshot = sorted(snapshot_keys - expected_snapshot_keys)
        if unexpected_snapshot:
            errors.append(f"revision_snapshots has unexpected keys: {unexpected_snapshot}")

        previous_errors, previous_snapshot_ids = _validate_req_062_revision_snapshot(
            payload=revision_snapshots.get("previous"),
            field_name="revision_snapshots.previous",
        )
        current_errors, current_snapshot_ids = _validate_req_062_revision_snapshot(
            payload=revision_snapshots.get("current"),
            field_name="revision_snapshots.current",
        )
        errors.extend(previous_errors)
        errors.extend(current_errors)

        previous_snapshot = revision_snapshots.get("previous")
        if isinstance(previous_snapshot, Mapping) and previous_pair_revision_id:
            if previous_snapshot.get("revision_id") != previous_pair_revision_id:
                errors.append("revision_pair.previous_revision_id must match revision_snapshots.previous.revision_id")
        current_snapshot = revision_snapshots.get("current")
        if isinstance(current_snapshot, Mapping) and current_pair_revision_id:
            if current_snapshot.get("revision_id") != current_pair_revision_id:
                errors.append("revision_pair.current_revision_id must match revision_snapshots.current.revision_id")

    diagnostics = payload.get("diagnostics")
    id_collisions: list[Any] = []
    id_drift: list[Any] = []
    added_ids: list[str] = []
    removed_ids: list[str] = []
    if not isinstance(diagnostics, Mapping):
        errors.append("diagnostics must be an object")
    else:
        expected_diag_keys = {"id_collisions", "id_drift", "added_ids", "removed_ids"}
        diag_keys = set(diagnostics.keys())
        missing_diag = sorted(expected_diag_keys - diag_keys)
        if missing_diag:
            errors.append(f"diagnostics missing keys: {missing_diag}")
        unexpected_diag = sorted(diag_keys - expected_diag_keys)
        if unexpected_diag:
            errors.append(f"diagnostics has unexpected keys: {unexpected_diag}")

        id_collisions_raw = diagnostics.get("id_collisions")
        if not isinstance(id_collisions_raw, list):
            errors.append("diagnostics.id_collisions must be a list")
        else:
            id_collisions = id_collisions_raw
            for index, row in enumerate(id_collisions):
                errors.extend(_validate_req_062_id_collision_row(row=row, index=index))

        id_drift_raw = diagnostics.get("id_drift")
        if not isinstance(id_drift_raw, list):
            errors.append("diagnostics.id_drift must be a list")
        else:
            id_drift = id_drift_raw
            for index, row in enumerate(id_drift):
                errors.extend(_validate_req_062_id_drift_row(row=row, index=index))

        added_errors, added_ids = _validate_nonempty_string_list(
            value=diagnostics.get("added_ids"),
            field_name="diagnostics.added_ids",
            min_items=0,
        )
        removed_errors, removed_ids = _validate_nonempty_string_list(
            value=diagnostics.get("removed_ids"),
            field_name="diagnostics.removed_ids",
            min_items=0,
        )
        errors.extend(added_errors)
        errors.extend(removed_errors)

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "previous_recommendation_rows",
            "current_recommendation_rows",
            "previous_unique_recommendation_ids",
            "current_unique_recommendation_ids",
            "added_ids",
            "removed_ids",
            "id_collisions",
            "id_drift",
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

        if totals.get("previous_unique_recommendation_ids") != len(previous_snapshot_ids):
            errors.append(
                "totals.previous_unique_recommendation_ids must equal revision_snapshots.previous.recommendation_ids count"
            )
        if totals.get("current_unique_recommendation_ids") != len(current_snapshot_ids):
            errors.append(
                "totals.current_unique_recommendation_ids must equal revision_snapshots.current.recommendation_ids count"
            )
        if totals.get("added_ids") != len(added_ids):
            errors.append("totals.added_ids must equal diagnostics.added_ids count")
        if totals.get("removed_ids") != len(removed_ids):
            errors.append("totals.removed_ids must equal diagnostics.removed_ids count")
        if totals.get("id_collisions") != len(id_collisions):
            errors.append("totals.id_collisions must equal diagnostics.id_collisions count")
        if totals.get("id_drift") != len(id_drift):
            errors.append("totals.id_drift must equal diagnostics.id_drift count")
        if totals.get("previous_recommendation_rows", 0) < totals.get("previous_unique_recommendation_ids", 0):
            errors.append("totals.previous_recommendation_rows must be >= totals.previous_unique_recommendation_ids")
        if totals.get("current_recommendation_rows", 0) < totals.get("current_unique_recommendation_ids", 0):
            errors.append("totals.current_recommendation_rows must be >= totals.current_unique_recommendation_ids")

    previous_ids_set = set(previous_snapshot_ids)
    current_ids_set = set(current_snapshot_ids)
    if added_ids and added_ids != sorted(current_ids_set - previous_ids_set):
        errors.append(
            "diagnostics.added_ids must equal revision_snapshots.current.recommendation_ids minus "
            "revision_snapshots.previous.recommendation_ids"
        )
    if removed_ids and removed_ids != sorted(previous_ids_set - current_ids_set):
        errors.append(
            "diagnostics.removed_ids must equal revision_snapshots.previous.recommendation_ids minus "
            "revision_snapshots.current.recommendation_ids"
        )
    if not added_ids and sorted(current_ids_set - previous_ids_set):
        errors.append(
            "diagnostics.added_ids must include revision_snapshots.current.recommendation_ids minus "
            "revision_snapshots.previous.recommendation_ids"
        )
    if not removed_ids and sorted(previous_ids_set - current_ids_set):
        errors.append(
            "diagnostics.removed_ids must include revision_snapshots.previous.recommendation_ids minus "
            "revision_snapshots.current.recommendation_ids"
        )

    verdict = payload.get("verdict")
    if not isinstance(verdict, Mapping):
        errors.append("verdict must be an object")
    else:
        expected_verdict_keys = {"is_unique_within_revision", "ids_stable_across_revisions", "passed"}
        verdict_keys = set(verdict.keys())
        missing_verdict = sorted(expected_verdict_keys - verdict_keys)
        if missing_verdict:
            errors.append(f"verdict missing keys: {missing_verdict}")
        unexpected_verdict = sorted(verdict_keys - expected_verdict_keys)
        if unexpected_verdict:
            errors.append(f"verdict has unexpected keys: {unexpected_verdict}")

        expected_unique = not bool(id_collisions)
        expected_stable = not bool(id_drift)
        if verdict.get("is_unique_within_revision") not in {True, False}:
            errors.append("verdict.is_unique_within_revision must be a boolean")
        elif verdict.get("is_unique_within_revision") != expected_unique:
            errors.append("verdict.is_unique_within_revision must match diagnostics.id_collisions")

        if verdict.get("ids_stable_across_revisions") not in {True, False}:
            errors.append("verdict.ids_stable_across_revisions must be a boolean")
        elif verdict.get("ids_stable_across_revisions") != expected_stable:
            errors.append("verdict.ids_stable_across_revisions must match diagnostics.id_drift")

        expected_passed = expected_unique and expected_stable
        if verdict.get("passed") not in {True, False}:
            errors.append("verdict.passed must be a boolean")
        elif verdict.get("passed") != expected_passed:
            errors.append("verdict.passed must equal is_unique_within_revision and ids_stable_across_revisions")

    errors.extend(_validate_req_062_processing_behavior(payload.get("processing_behavior")))

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
    parser = argparse.ArgumentParser(description="Emit REQ-056 KPI target artifact payload.")
    parser.add_argument(
        "--input-json",
        required=True,
        help="Path to REQ-056 input JSON (or '-' for stdin).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_input_payload(args.input_json)
        built = build_req_056_kpi_target_artifact(payload)
    except Exception as exc:  # pragma: no cover - CLI guardrail
        sys.stderr.write(f"[{_utc_timestamp()}] REQ-056 CLI failed: {exc}\n")
        return 1

    sys.stdout.write(json.dumps(built, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
