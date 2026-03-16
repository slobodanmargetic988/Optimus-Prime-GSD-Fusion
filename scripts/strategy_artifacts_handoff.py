#!/usr/bin/env python3
"""REQ-055 constraint classification artifact surface."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REQ_055_REQUIREMENT_ID = "REQ-055"
REQ_055_SCHEMA_VERSION = "1.0"
REQ_055_ANALYSIS_TYPE = "constraint_classification_artifact"
REQ_055_CALL_ID = "constraint-classification-artifact"
REQ_061_REQUIREMENT_ID = "REQ-061"
REQ_061_SCHEMA_VERSION = "1.0"
REQ_061_ANALYSIS_TYPE = "recommendation_quality_validator"
REQ_061_CALL_ID = "recommendation-quality-validator"

_CLASSIFICATIONS = {"hard", "soft", "speculative"}
_CLASSIFICATION_BUCKETS = {
    "hard": "hard_constraints",
    "soft": "soft_constraints",
    "speculative": "speculative_constraints",
}
_RECOMMENDATION_REQUIRED_FIELDS = (
    "decision",
    "rationale",
    "confidence",
    "evidence_refs",
    "recommended_actions",
    "cross_project_obligations",
    "open_risks",
)
_CONTEXT_USAGE_REQUIRED_FIELDS = (
    "cross_project_context_provided",
    "cross_project_context_used",
    "earth_sweep_context_used",
    "projects_considered",
    "earth_sweep_evidence_refs_considered",
    "constraint_ids_used",
    "recommendation_mapping",
    "recommendation_fields_complete",
    "required_recommendation_fields",
)
_REQ_061_REQUIRED_RECOMMENDATION_FIELDS = (
    "summary",
    "rationale",
    "packet_kind",
    "lane",
    "priority",
    "sequence_hint",
    "evidence_refs",
)
_REQ_061_ALLOWED_PACKET_KINDS = {"cross-project", "target-project"}
_REQ_061_ALLOWED_PRIORITIES = {"high", "medium", "low"}
_REQ_061_ALLOWED_FAILURE_REASON_CODES = {
    "incomplete_recommendation",
    "low_substance_rationale",
    "insufficient_evidence_citations",
}
_REQ_061_ALLOWED_DECISIONS = {"accepted", "blocked"}
_REQ_061_ALLOWED_COMPLETENESS = {"complete", "incomplete"}
_REQ_061_ALLOWED_RATIONALE_STATUS = {"meets_minimum", "low_substance"}
_REQ_061_ALLOWED_EVIDENCE_STATUS = {"meets_minimum", "below_minimum"}
_REQ_061_ALLOWED_PLANNER_READINESS = {"allow_planner_packet", "block_planner_packet"}
_REQ_061_FAILURE_REASON_ORDER = (
    "incomplete_recommendation",
    "low_substance_rationale",
    "insufficient_evidence_citations",
)
_REQ_061_REASON_CODE_STRATEGY_PACKET_SCHEMA_ROW_INVALID = "strategy_packet_schema_row_invalid"
_REQ_061_REASON_CODE_DUPLICATE_RECOMMENDATION_ID_COLLISION = "duplicate_recommendation_id_collision"
_REQ_061_REASON_CODE_TRACEABILITY_GATE_FAILED = "traceability_gate_failed"
_REQ_061_PROCESSING_RECOMMENDATION_FIELDS = (
    "decision",
    "rationale",
    "confidence",
    "evidence_refs",
    "recommended_actions",
    "cross_project_obligations",
    "open_risks",
)
_REQ_061_PROCESSING_CONTEXT_USAGE_FIELDS = (
    "cross_project_context_provided",
    "cross_project_context_used",
    "earth_sweep_context_used",
    "projects_considered",
    "earth_sweep_evidence_refs_considered",
    "accepted_recommendation_ids",
    "blocked_recommendation_ids",
    "recommendation_mapping",
    "recommendation_fields_complete",
    "required_recommendation_fields",
)
_REQ_061_PROCESSING_ALLOWED_DECISIONS = {
    "allow-planner-packet",
    "allow-planner-packet-with-open-risks",
    "block-planner-packet",
}
_REQ_061_PROCESSING_ALLOWED_CONFIDENCE = {"high", "medium", "low"}
_REQ_061_PROCESSING_ALLOWED_PLANNER_STATUS = {
    "promoted",
    "blocked_by_quality",
    "blocked_by_missing_earth_sweep_evidence",
}


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


def _optional_text(value: Any, *, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip()


def _require_positive_int(value: Any, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _normalize_text_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(value):
        item = _require_nonempty_text(row, field_name=f"{field_name}[{index}]")
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return sorted(normalized)


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


def _count_words(value: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", value))


def _normalize_constraints(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("constraints must be a list")
    if not value:
        raise ValueError("constraints must include at least one row")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        field_prefix = f"constraints[{index}]"
        raw = _require_mapping(row, field_name=field_prefix)
        expected_keys = {"constraint_id", "statement", "classification", "rationale", "evidence_refs", "source_refs"}
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{field_prefix} has unexpected keys: {unexpected}")
        missing = sorted(expected_keys - row_keys)
        if missing:
            raise ValueError(f"{field_prefix} missing keys: {missing}")

        constraint_id = _require_nonempty_text(raw.get("constraint_id"), field_name=f"{field_prefix}.constraint_id")
        if constraint_id in seen_ids:
            raise ValueError(f"{field_prefix}.constraint_id must be unique")
        seen_ids.add(constraint_id)

        statement = _require_nonempty_text(raw.get("statement"), field_name=f"{field_prefix}.statement")
        classification = _require_nonempty_text(
            raw.get("classification"),
            field_name=f"{field_prefix}.classification",
        ).lower()
        if classification not in _CLASSIFICATIONS:
            raise ValueError(
                f"{field_prefix}.classification must be one of: {sorted(_CLASSIFICATIONS)}"
            )
        rationale = _require_nonempty_text(raw.get("rationale"), field_name=f"{field_prefix}.rationale")
        evidence_refs = _normalize_text_list(raw.get("evidence_refs"), field_name=f"{field_prefix}.evidence_refs")
        source_refs = _normalize_text_list(raw.get("source_refs"), field_name=f"{field_prefix}.source_refs")
        if not source_refs:
            raise ValueError(f"{field_prefix}.source_refs must include at least one value")

        normalized.append(
            {
                "constraint_id": constraint_id,
                "statement": statement,
                "classification": classification,
                "rationale": rationale,
                "evidence_refs": evidence_refs,
                "source_refs": source_refs,
                "policy_role": "mandatory_guardrail" if classification == "hard" else "optional_guidance",
            }
        )

    return sorted(normalized, key=lambda row: (row["classification"], row["constraint_id"]))


def _normalize_broad_sweep_obligations(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("broad_sweep_context.cross_project_obligations must be a list")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        field_prefix = f"broad_sweep_context.cross_project_obligations[{index}]"
        raw = _require_mapping(row, field_name=field_prefix)
        expected_keys = {
            "obligation_id",
            "project_id",
            "summary",
            "evidence_refs",
            "earth_sweep_evidence_refs",
            "source_refs",
        }
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{field_prefix} has unexpected keys: {unexpected}")
        missing = sorted({"obligation_id", "project_id", "summary"} - row_keys)
        if missing:
            raise ValueError(f"{field_prefix} missing keys: {missing}")

        obligation_id = _require_nonempty_text(raw.get("obligation_id"), field_name=f"{field_prefix}.obligation_id")
        if obligation_id in seen_ids:
            raise ValueError(f"{field_prefix}.obligation_id must be unique")
        seen_ids.add(obligation_id)

        project_id = _require_nonempty_text(raw.get("project_id"), field_name=f"{field_prefix}.project_id")
        summary = _require_nonempty_text(raw.get("summary"), field_name=f"{field_prefix}.summary")
        evidence_refs_value = raw.get("earth_sweep_evidence_refs")
        if evidence_refs_value is None:
            evidence_refs_value = raw.get("evidence_refs")
        evidence_refs = _normalize_text_list(evidence_refs_value, field_name=f"{field_prefix}.evidence_refs")
        source_refs = _normalize_text_list(raw.get("source_refs"), field_name=f"{field_prefix}.source_refs")
        if not source_refs:
            source_refs = list(evidence_refs)

        normalized.append(
            {
                "obligation_id": obligation_id,
                "project_id": project_id,
                "summary": summary,
                "evidence_refs": evidence_refs,
                "source_refs": source_refs,
            }
        )

    return sorted(normalized, key=lambda row: (row["project_id"], row["obligation_id"]))


def _normalize_broad_sweep_unresolved_ideas(value: Any) -> list[dict[str, Any]]:
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
            "idea_id",
            "summary",
            "evidence_refs",
            "earth_sweep_evidence_refs",
            "source_refs",
        }
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{field_prefix} has unexpected keys: {unexpected}")
        if "summary" not in row_keys:
            raise ValueError(f"{field_prefix} missing keys: ['summary']")

        default_id = f"idea-{index + 1:03d}"
        idea_id = _require_nonempty_text(raw.get("idea_id") or default_id, field_name=f"{field_prefix}.idea_id")
        if idea_id in seen_ids:
            raise ValueError(f"{field_prefix}.idea_id must be unique")
        seen_ids.add(idea_id)

        summary = _require_nonempty_text(raw.get("summary"), field_name=f"{field_prefix}.summary")
        evidence_refs_value = raw.get("earth_sweep_evidence_refs")
        if evidence_refs_value is None:
            evidence_refs_value = raw.get("evidence_refs")
        evidence_refs = _normalize_text_list(evidence_refs_value, field_name=f"{field_prefix}.evidence_refs")
        source_refs = _normalize_text_list(raw.get("source_refs"), field_name=f"{field_prefix}.source_refs")
        if not source_refs:
            source_refs = list(evidence_refs)

        normalized.append(
            {
                "idea_id": idea_id,
                "summary": summary,
                "evidence_refs": evidence_refs,
                "source_refs": source_refs,
            }
        )

    return sorted(normalized, key=lambda row: row["idea_id"])


def _normalize_broad_sweep_context(value: Any) -> dict[str, Any]:
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
        "earth_sweep_evidence_refs": _normalize_text_list(
            raw.get("earth_sweep_evidence_refs"),
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
        ),
        "projects_considered": _normalize_text_list(
            raw.get("projects_considered"),
            field_name="broad_sweep_context.projects_considered",
        ),
        "cross_project_obligations": _normalize_broad_sweep_obligations(raw.get("cross_project_obligations")),
        "unresolved_ideas": _normalize_broad_sweep_unresolved_ideas(raw.get("unresolved_ideas")),
    }


def _build_req_055_processing_behavior(
    *,
    constraints: list[dict[str, Any]],
    broad_sweep_context: dict[str, Any],
) -> dict[str, Any]:
    earth_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    obligations_input = list(broad_sweep_context["cross_project_obligations"])
    unresolved_ideas = list(broad_sweep_context["unresolved_ideas"])
    projects_considered = sorted(
        {
            *broad_sweep_context["projects_considered"],
            *[row["project_id"] for row in obligations_input],
        }
    )

    recommended_actions: list[dict[str, Any]] = []
    recommendation_mapping: list[dict[str, str]] = []
    for row in constraints:
        classification = str(row["classification"])
        action_scope = {
            "hard": "mandatory-guardrail",
            "soft": "optional-guidance",
            "speculative": "investigation",
        }[classification]
        action_id = f"constraint-{row['constraint_id']}"
        recommended_actions.append(
            {
                "action_id": action_id,
                "summary": row["statement"],
                "rationale": row["rationale"],
                "action_scope": action_scope,
                "next_step": f"Apply {classification} constraint handling in planner policy.",
                "evidence_refs": sorted({*row["evidence_refs"], *row["source_refs"]}),
            }
        )
        recommendation_mapping.append(
            {
                "constraint_id": str(row["constraint_id"]),
                "action_id": action_id,
                "classification": classification,
                "policy_role": str(row["policy_role"]),
            }
        )

    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    for row in obligations_input:
        obligation_refs = sorted({*earth_refs, *row["evidence_refs"]})
        if earth_refs:
            cross_project_obligations.append(
                {
                    "obligation_id": row["obligation_id"],
                    "project_id": row["project_id"],
                    "summary": row["summary"],
                    "evidence_refs": obligation_refs,
                }
            )
            continue

        required_refs = list(row["evidence_refs"]) or ["missing:earth-sweep-evidence-ref"]
        open_risks.append(
            {
                "risk_id": f"risk-{row['obligation_id']}",
                "summary": row["summary"],
                "reason_code": "missing_earth_sweep_evidence_refs",
                "evidence_refs": required_refs,
                "required_evidence_refs": required_refs,
            }
        )

    for row in unresolved_ideas:
        required_refs = list(row["evidence_refs"]) or ["missing:earth-sweep-evidence-ref"]
        open_risks.append(
            {
                "risk_id": f"risk-{row['idea_id']}",
                "summary": row["summary"],
                "reason_code": "unresolved_idea_open_risk",
                "evidence_refs": required_refs,
                "required_evidence_refs": required_refs,
            }
        )

    missing_earth_evidence = any(
        row["reason_code"] == "missing_earth_sweep_evidence_refs" for row in open_risks
    )
    decision = "proceed"
    confidence = "high"
    if missing_earth_evidence:
        decision = "collect-earth-evidence"
        confidence = "low"
    elif open_risks:
        decision = "proceed-with-open-risks"
        confidence = "medium"

    recommendation_evidence_refs = sorted(
        {
            *earth_refs,
            *[
                ref
                for row in constraints
                for ref in [*list(row["evidence_refs"]), *list(row["source_refs"])]
            ],
            *[ref for row in cross_project_obligations for ref in row["evidence_refs"]],
            *[ref for row in unresolved_ideas for ref in row["evidence_refs"]],
        }
    )
    recommendation = {
        "decision": decision,
        "rationale": (
            f"Classified {len(constraints)} constraints with "
            f"{len(cross_project_obligations)} evidence-backed cross-project obligation(s) "
            f"and {len(open_risks)} open risk(s)."
        ),
        "confidence": confidence,
        "evidence_refs": recommendation_evidence_refs,
        "recommended_actions": recommended_actions,
        "cross_project_obligations": cross_project_obligations,
        "open_risks": open_risks,
    }

    required_recommendation_fields = list(_RECOMMENDATION_REQUIRED_FIELDS)
    recommendation_fields_complete = set(recommendation.keys()) == set(required_recommendation_fields)

    context_usage = {
        "cross_project_context_provided": bool(
            broad_sweep_context["projects_considered"] or obligations_input or unresolved_ideas or earth_refs
        ),
        "cross_project_context_used": bool(projects_considered or obligations_input or unresolved_ideas),
        "earth_sweep_context_used": bool(earth_refs),
        "projects_considered": projects_considered,
        "earth_sweep_evidence_refs_considered": earth_refs,
        "constraint_ids_used": [row["constraint_id"] for row in constraints],
        "recommendation_mapping": recommendation_mapping,
        "recommendation_fields_complete": recommendation_fields_complete,
        "required_recommendation_fields": required_recommendation_fields,
    }
    return {
        "recommendation": recommendation,
        "context_usage": context_usage,
    }


def build_req_055_constraint_classification_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-055 payload for explicit constraint classification."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_055_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_055_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    constraints = _normalize_constraints(raw.get("constraints"))
    broad_sweep_context: dict[str, Any] | None = None
    if raw.get("broad_sweep_context") is not None:
        broad_sweep_context = _normalize_broad_sweep_context(raw.get("broad_sweep_context"))

    hard_constraints: list[dict[str, Any]] = []
    soft_constraints: list[dict[str, Any]] = []
    speculative_constraints: list[dict[str, Any]] = []
    for row in constraints:
        bucket_key = _CLASSIFICATION_BUCKETS[str(row["classification"])]
        if bucket_key == "hard_constraints":
            hard_constraints.append(row)
        elif bucket_key == "soft_constraints":
            soft_constraints.append(row)
        else:
            speculative_constraints.append(row)

    planner_policy = {
        "hard_constraint_ids": [row["constraint_id"] for row in hard_constraints],
        "soft_constraint_ids": [row["constraint_id"] for row in soft_constraints],
        "speculative_constraint_ids": [row["constraint_id"] for row in speculative_constraints],
        "mandatory_guardrail_ids": [row["constraint_id"] for row in hard_constraints],
        "optional_guidance_ids": [row["constraint_id"] for row in (soft_constraints + speculative_constraints)],
    }

    built = {
        "ok": True,
        "schema_version": REQ_055_SCHEMA_VERSION,
        "requirement_id": REQ_055_REQUIREMENT_ID,
        "analysis_type": REQ_055_ANALYSIS_TYPE,
        "call_id": REQ_055_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "constraint_classification": {
            "hard_constraints": hard_constraints,
            "soft_constraints": soft_constraints,
            "speculative_constraints": speculative_constraints,
            "planner_policy": planner_policy,
        },
        "totals": {
            "constraints": len(constraints),
            "hard_constraints": len(hard_constraints),
            "soft_constraints": len(soft_constraints),
            "speculative_constraints": len(speculative_constraints),
            "mandatory_guardrails": len(planner_policy["mandatory_guardrail_ids"]),
            "optional_guidance": len(planner_policy["optional_guidance_ids"]),
        },
    }
    if broad_sweep_context is not None:
        built["processing_behavior"] = _build_req_055_processing_behavior(
            constraints=constraints,
            broad_sweep_context=broad_sweep_context,
        )
    errors = validate_req_055_constraint_classification_artifact(built)
    if errors:
        raise ValueError(f"built REQ-055 payload failed validation: {errors}")
    return built


def _validate_constraint_row(
    *,
    row: Any,
    index: int,
    bucket: str,
    expected_classification: str,
    seen_ids: set[str],
) -> tuple[list[str], str]:
    errors: list[str] = []
    row_path = f"constraint_classification.{bucket}[{index}]"
    if not isinstance(row, Mapping):
        return [f"{row_path} must be an object"], ""

    expected_keys = {
        "constraint_id",
        "statement",
        "classification",
        "rationale",
        "evidence_refs",
        "source_refs",
        "policy_role",
    }
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{row_path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{row_path} has unexpected keys: {unexpected}")

    constraint_id = row.get("constraint_id")
    if not isinstance(constraint_id, str) or not constraint_id.strip():
        errors.append(f"{row_path}.constraint_id must be a non-empty string")
        constraint_id = ""
    elif constraint_id in seen_ids:
        errors.append(f"{row_path}.constraint_id must be unique across all classifications")
    else:
        seen_ids.add(constraint_id)

    statement = row.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        errors.append(f"{row_path}.statement must be a non-empty string")

    classification = row.get("classification")
    if classification != expected_classification:
        errors.append(f"{row_path}.classification must be {expected_classification}")

    rationale = row.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        errors.append(f"{row_path}.rationale must be a non-empty string")

    for list_key in ("evidence_refs", "source_refs"):
        value = row.get(list_key)
        if not isinstance(value, list):
            errors.append(f"{row_path}.{list_key} must be a list")
            continue
        for item_index, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"{row_path}.{list_key}[{item_index}] must be a non-empty string")
        if list_key == "source_refs" and not value:
            errors.append(f"{row_path}.source_refs must include at least one value")

    policy_role = row.get("policy_role")
    expected_role = "mandatory_guardrail" if expected_classification == "hard" else "optional_guidance"
    if policy_role != expected_role:
        errors.append(f"{row_path}.policy_role must be {expected_role}")

    return errors, str(constraint_id)


def _validate_req_055_recommendation_row(row: Any, *, index: int, kind: str) -> list[str]:
    errors: list[str] = []
    path = f"processing_behavior.recommendation.{kind}[{index}]"
    if not isinstance(row, Mapping):
        return [f"{path} must be an object"]

    if kind == "recommended_actions":
        expected_keys = {"action_id", "summary", "rationale", "action_scope", "next_step", "evidence_refs"}
        required_text = ("action_id", "summary", "rationale", "action_scope", "next_step")
    elif kind == "cross_project_obligations":
        expected_keys = {"obligation_id", "project_id", "summary", "evidence_refs"}
        required_text = ("obligation_id", "project_id", "summary")
    else:
        expected_keys = {"risk_id", "summary", "reason_code", "evidence_refs", "required_evidence_refs"}
        required_text = ("risk_id", "summary", "reason_code")

    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{path} has unexpected keys: {unexpected}")

    for key in required_text:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}.{key} must be a non-empty string")

    list_keys = ("evidence_refs", "required_evidence_refs") if kind == "open_risks" else ("evidence_refs",)
    for list_key in list_keys:
        value = row.get(list_key)
        if not isinstance(value, list):
            errors.append(f"{path}.{list_key} must be a list")
            continue
        for list_index, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"{path}.{list_key}[{list_index}] must be a non-empty string")

    return errors


def _validate_req_055_recommendation_mapping_row(row: Any, *, index: int) -> tuple[list[str], str]:
    errors: list[str] = []
    path = f"processing_behavior.context_usage.recommendation_mapping[{index}]"
    if not isinstance(row, Mapping):
        return [f"{path} must be an object"], ""

    expected_keys = {"constraint_id", "action_id", "classification", "policy_role"}
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{path} has unexpected keys: {unexpected}")

    constraint_id = ""
    for key in ("constraint_id", "action_id", "classification", "policy_role"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}.{key} must be a non-empty string")
            continue
        if key == "constraint_id":
            constraint_id = value

    classification = row.get("classification")
    if isinstance(classification, str) and classification not in _CLASSIFICATIONS:
        errors.append(f"{path}.classification must be one of: {sorted(_CLASSIFICATIONS)}")

    policy_role = row.get("policy_role")
    if isinstance(classification, str) and classification in _CLASSIFICATIONS:
        expected_policy_role = "mandatory_guardrail" if classification == "hard" else "optional_guidance"
        if policy_role != expected_policy_role:
            errors.append(f"{path}.policy_role must be {expected_policy_role}")

    expected_action_id = f"constraint-{constraint_id}" if constraint_id else ""
    action_id = row.get("action_id")
    if expected_action_id and action_id != expected_action_id:
        errors.append(f"{path}.action_id must equal {expected_action_id}")

    return errors, constraint_id


def _validate_req_055_processing_behavior(
    processing_behavior: Any,
    *,
    all_constraint_ids: list[str],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(processing_behavior, Mapping):
        return ["processing_behavior must be an object"]

    expected_keys = {"recommendation", "context_usage"}
    keys = set(processing_behavior.keys())
    missing = sorted(expected_keys - keys)
    if missing:
        errors.append(f"processing_behavior missing keys: {missing}")
    unexpected = sorted(keys - expected_keys)
    if unexpected:
        errors.append(f"processing_behavior has unexpected keys: {unexpected}")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        recommendation_keys = set(recommendation.keys())
        required_recommendation_keys = set(_RECOMMENDATION_REQUIRED_FIELDS)
        missing_recommendation = sorted(required_recommendation_keys - recommendation_keys)
        if missing_recommendation:
            errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
        unexpected_recommendation = sorted(recommendation_keys - required_recommendation_keys)
        if unexpected_recommendation:
            errors.append(
                f"processing_behavior.recommendation has unexpected keys: {unexpected_recommendation}"
            )

        for key in ("decision", "rationale", "confidence"):
            value = recommendation.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"processing_behavior.recommendation.{key} must be a non-empty string")

        evidence_refs = recommendation.get("evidence_refs")
        if not isinstance(evidence_refs, list):
            errors.append("processing_behavior.recommendation.evidence_refs must be a list")
        else:
            for index, item in enumerate(evidence_refs):
                if not isinstance(item, str) or not item.strip():
                    errors.append(
                        f"processing_behavior.recommendation.evidence_refs[{index}] must be a non-empty string"
                    )

        for key in ("recommended_actions", "cross_project_obligations", "open_risks"):
            value = recommendation.get(key)
            if not isinstance(value, list):
                errors.append(f"processing_behavior.recommendation.{key} must be a list")
                continue
            for index, row in enumerate(value):
                errors.extend(_validate_req_055_recommendation_row(row, index=index, kind=key))

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        context_keys = set(context_usage.keys())
        required_context_keys = set(_CONTEXT_USAGE_REQUIRED_FIELDS)
        missing_context = sorted(required_context_keys - context_keys)
        if missing_context:
            errors.append(f"processing_behavior.context_usage missing keys: {missing_context}")
        unexpected_context = sorted(context_keys - required_context_keys)
        if unexpected_context:
            errors.append(f"processing_behavior.context_usage has unexpected keys: {unexpected_context}")

        for key in (
            "cross_project_context_provided",
            "cross_project_context_used",
            "earth_sweep_context_used",
            "recommendation_fields_complete",
        ):
            if not isinstance(context_usage.get(key), bool):
                errors.append(f"processing_behavior.context_usage.{key} must be a boolean")

        for key in ("projects_considered", "earth_sweep_evidence_refs_considered", "constraint_ids_used"):
            value = context_usage.get(key)
            if not isinstance(value, list):
                errors.append(f"processing_behavior.context_usage.{key} must be a list")
                continue
            for index, item in enumerate(value):
                if not isinstance(item, str) or not item.strip():
                    errors.append(
                        f"processing_behavior.context_usage.{key}[{index}] must be a non-empty string"
                    )

        if context_usage.get("constraint_ids_used") != all_constraint_ids:
            errors.append(
                "processing_behavior.context_usage.constraint_ids_used must match classified constraint IDs"
            )

        recommendation_mapping = context_usage.get("recommendation_mapping")
        if not isinstance(recommendation_mapping, list):
            errors.append("processing_behavior.context_usage.recommendation_mapping must be a list")
        else:
            mapped_constraint_ids: list[str] = []
            seen_mapped_constraint_ids: set[str] = set()
            for index, row in enumerate(recommendation_mapping):
                row_errors, constraint_id = _validate_req_055_recommendation_mapping_row(row, index=index)
                errors.extend(row_errors)
                if constraint_id:
                    if constraint_id in seen_mapped_constraint_ids:
                        errors.append(
                            "processing_behavior.context_usage.recommendation_mapping constraint_ids must be unique"
                        )
                    else:
                        seen_mapped_constraint_ids.add(constraint_id)
                        mapped_constraint_ids.append(constraint_id)
            if mapped_constraint_ids != all_constraint_ids:
                errors.append(
                    "processing_behavior.context_usage.recommendation_mapping must cover classified constraint IDs in order"
                )

        if context_usage.get("required_recommendation_fields") != list(_RECOMMENDATION_REQUIRED_FIELDS):
            errors.append(
                "processing_behavior.context_usage.required_recommendation_fields must match required recommendation keys"
            )
        if context_usage.get("recommendation_fields_complete") is not True:
            errors.append("processing_behavior.context_usage.recommendation_fields_complete must be true")

    return errors


def validate_req_055_constraint_classification_artifact(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-055 constraint classification artifact shape."""
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
        "constraint_classification",
        "totals",
    }
    optional_top = {"processing_behavior"}
    expected_top = required_top | optional_top
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - expected_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_055_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_055_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_055_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_055_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_055_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_055_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_055_CALL_ID:
        errors.append(f"call_id must be {REQ_055_CALL_ID}")
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

    classification = payload.get("constraint_classification")
    hard_ids: list[str] = []
    soft_ids: list[str] = []
    speculative_ids: list[str] = []
    if not isinstance(classification, Mapping):
        errors.append("constraint_classification must be an object")
    else:
        expected_classification_keys = {
            "hard_constraints",
            "soft_constraints",
            "speculative_constraints",
            "planner_policy",
        }
        classification_keys = set(classification.keys())
        missing = sorted(expected_classification_keys - classification_keys)
        if missing:
            errors.append(f"constraint_classification missing keys: {missing}")
        unexpected = sorted(classification_keys - expected_classification_keys)
        if unexpected:
            errors.append(f"constraint_classification has unexpected keys: {unexpected}")

        seen_ids: set[str] = set()
        for bucket, expected_class in (
            ("hard_constraints", "hard"),
            ("soft_constraints", "soft"),
            ("speculative_constraints", "speculative"),
        ):
            value = classification.get(bucket)
            if not isinstance(value, list):
                errors.append(f"constraint_classification.{bucket} must be a list")
                continue
            for index, row in enumerate(value):
                row_errors, constraint_id = _validate_constraint_row(
                    row=row,
                    index=index,
                    bucket=bucket,
                    expected_classification=expected_class,
                    seen_ids=seen_ids,
                )
                errors.extend(row_errors)
                if constraint_id:
                    if bucket == "hard_constraints":
                        hard_ids.append(constraint_id)
                    elif bucket == "soft_constraints":
                        soft_ids.append(constraint_id)
                    else:
                        speculative_ids.append(constraint_id)

        planner_policy = classification.get("planner_policy")
        if not isinstance(planner_policy, Mapping):
            errors.append("constraint_classification.planner_policy must be an object")
        else:
            expected_policy = {
                "hard_constraint_ids",
                "soft_constraint_ids",
                "speculative_constraint_ids",
                "mandatory_guardrail_ids",
                "optional_guidance_ids",
            }
            policy_keys = set(planner_policy.keys())
            missing_policy = sorted(expected_policy - policy_keys)
            if missing_policy:
                errors.append(f"constraint_classification.planner_policy missing keys: {missing_policy}")
            unexpected_policy = sorted(policy_keys - expected_policy)
            if unexpected_policy:
                errors.append(f"constraint_classification.planner_policy has unexpected keys: {unexpected_policy}")

            for list_key in expected_policy:
                value = planner_policy.get(list_key)
                if not isinstance(value, list):
                    errors.append(f"constraint_classification.planner_policy.{list_key} must be a list")
                    continue
                for index, item in enumerate(value):
                    if not isinstance(item, str) or not item.strip():
                        errors.append(
                            f"constraint_classification.planner_policy.{list_key}[{index}] must be a non-empty string"
                        )

            if planner_policy.get("hard_constraint_ids") != hard_ids:
                errors.append("constraint_classification.planner_policy.hard_constraint_ids must match hard_constraints")
            if planner_policy.get("soft_constraint_ids") != soft_ids:
                errors.append("constraint_classification.planner_policy.soft_constraint_ids must match soft_constraints")
            if planner_policy.get("speculative_constraint_ids") != speculative_ids:
                errors.append(
                    "constraint_classification.planner_policy.speculative_constraint_ids must match speculative_constraints"
                )
            if planner_policy.get("mandatory_guardrail_ids") != hard_ids:
                errors.append(
                    "constraint_classification.planner_policy.mandatory_guardrail_ids must match hard_constraints"
                )
            expected_optional = soft_ids + speculative_ids
            if planner_policy.get("optional_guidance_ids") != expected_optional:
                errors.append(
                    "constraint_classification.planner_policy.optional_guidance_ids must match soft+speculative constraints"
                )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "constraints",
            "hard_constraints",
            "soft_constraints",
            "speculative_constraints",
            "mandatory_guardrails",
            "optional_guidance",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")

        for total_key in expected_totals:
            value = totals.get(total_key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{total_key} must be a non-negative integer")

        expected_constraints = len(hard_ids) + len(soft_ids) + len(speculative_ids)
        if totals.get("constraints") != expected_constraints:
            errors.append("totals.constraints must equal hard+soft+speculative constraint counts")
        if totals.get("hard_constraints") != len(hard_ids):
            errors.append("totals.hard_constraints must equal hard_constraints count")
        if totals.get("soft_constraints") != len(soft_ids):
            errors.append("totals.soft_constraints must equal soft_constraints count")
        if totals.get("speculative_constraints") != len(speculative_ids):
            errors.append("totals.speculative_constraints must equal speculative_constraints count")
        if totals.get("mandatory_guardrails") != len(hard_ids):
            errors.append("totals.mandatory_guardrails must equal hard_constraints count")
        if totals.get("optional_guidance") != (len(soft_ids) + len(speculative_ids)):
            errors.append("totals.optional_guidance must equal soft+speculative constraints count")

    processing_behavior = payload.get("processing_behavior")
    if processing_behavior is not None:
        errors.extend(
            _validate_req_055_processing_behavior(
                processing_behavior,
                all_constraint_ids=hard_ids + soft_ids + speculative_ids,
            )
        )

    return errors


def _normalize_req_061_thresholds(value: Any) -> dict[str, int]:
    if value is None:
        raw: Mapping[str, Any] = {}
    else:
        raw = _require_mapping(value, field_name="quality_thresholds")

    expected_keys = {"min_rationale_word_count", "min_evidence_citations"}
    raw_keys = set(raw.keys())
    unexpected = sorted(raw_keys - expected_keys)
    if unexpected:
        raise ValueError(f"quality_thresholds has unexpected keys: {unexpected}")

    min_rationale_word_count = _require_positive_int(
        raw.get("min_rationale_word_count", 12),
        field_name="quality_thresholds.min_rationale_word_count",
    )
    min_evidence_citations = _require_positive_int(
        raw.get("min_evidence_citations", 2),
        field_name="quality_thresholds.min_evidence_citations",
    )
    return {
        "required_recommendation_fields": list(_REQ_061_REQUIRED_RECOMMENDATION_FIELDS),
        "min_rationale_word_count": min_rationale_word_count,
        "min_evidence_citations": min_evidence_citations,
    }


def _normalize_req_061_recommendations(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("recommendations must be a list")
    if not value:
        raise ValueError("recommendations must include at least one row")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(value):
        path = f"recommendations[{index}]"
        raw = _require_mapping(row, field_name=path)
        expected_keys = {
            "recommendation_id",
            "summary",
            "rationale",
            "packet_kind",
            "lane",
            "priority",
            "sequence_hint",
            "evidence_refs",
        }
        row_keys = set(raw.keys())
        unexpected = sorted(row_keys - expected_keys)
        if unexpected:
            raise ValueError(f"{path} has unexpected keys: {unexpected}")

        recommendation_id = _require_nonempty_text(
            raw.get("recommendation_id"),
            field_name=f"{path}.recommendation_id",
        )
        if recommendation_id in seen_ids:
            raise ValueError(f"{path}.recommendation_id must be unique")
        seen_ids.add(recommendation_id)

        packet_kind = _optional_text(raw.get("packet_kind"), field_name=f"{path}.packet_kind")
        if packet_kind and packet_kind not in _REQ_061_ALLOWED_PACKET_KINDS:
            raise ValueError(
                f"{path}.packet_kind must be one of: {sorted(_REQ_061_ALLOWED_PACKET_KINDS)}"
            )

        priority = _optional_text(raw.get("priority"), field_name=f"{path}.priority")
        if priority and priority not in _REQ_061_ALLOWED_PRIORITIES:
            raise ValueError(f"{path}.priority must be one of: {sorted(_REQ_061_ALLOWED_PRIORITIES)}")

        sequence_hint_raw = raw.get("sequence_hint")
        if sequence_hint_raw is None:
            sequence_hint = 0
        else:
            sequence_hint = _require_positive_int(sequence_hint_raw, field_name=f"{path}.sequence_hint")

        if "evidence_refs" in raw:
            evidence_refs = _normalize_text_list(raw.get("evidence_refs"), field_name=f"{path}.evidence_refs")
            evidence_refs_present = True
        else:
            evidence_refs = []
            evidence_refs_present = False

        normalized.append(
            {
                "recommendation_id": recommendation_id,
                "summary": _optional_text(raw.get("summary"), field_name=f"{path}.summary"),
                "rationale": _optional_text(raw.get("rationale"), field_name=f"{path}.rationale"),
                "packet_kind": packet_kind,
                "lane": _optional_text(raw.get("lane"), field_name=f"{path}.lane"),
                "priority": priority,
                "sequence_hint": sequence_hint,
                "evidence_refs": evidence_refs,
                "field_presence": {
                    "summary": "summary" in raw and bool(_optional_text(raw.get("summary"), field_name=f"{path}.summary")),
                    "rationale": "rationale" in raw and bool(
                        _optional_text(raw.get("rationale"), field_name=f"{path}.rationale")
                    ),
                    "packet_kind": "packet_kind" in raw and bool(packet_kind),
                    "lane": "lane" in raw and bool(_optional_text(raw.get("lane"), field_name=f"{path}.lane")),
                    "priority": "priority" in raw and bool(priority),
                    "sequence_hint": "sequence_hint" in raw and sequence_hint > 0,
                    "evidence_refs": evidence_refs_present,
                },
            }
        )

    return sorted(normalized, key=lambda row: (row["sequence_hint"], row["recommendation_id"]))


def _build_req_061_assessment_row(
    *,
    recommendation: Mapping[str, Any],
    thresholds: Mapping[str, int],
) -> dict[str, Any]:
    missing_fields = [
        field_name
        for field_name in _REQ_061_REQUIRED_RECOMMENDATION_FIELDS
        if not bool(recommendation["field_presence"][field_name])
    ]
    rationale_word_count = _count_words(str(recommendation["rationale"]))
    evidence_citation_count = len(list(recommendation["evidence_refs"]))

    failure_reason_codes: list[str] = []
    if missing_fields:
        failure_reason_codes.append("incomplete_recommendation")
    if rationale_word_count < int(thresholds["min_rationale_word_count"]):
        failure_reason_codes.append("low_substance_rationale")
    if evidence_citation_count < int(thresholds["min_evidence_citations"]):
        failure_reason_codes.append("insufficient_evidence_citations")

    return {
        "recommendation_id": recommendation["recommendation_id"],
        "summary": recommendation["summary"],
        "packet_kind": recommendation["packet_kind"],
        "lane": recommendation["lane"],
        "priority": recommendation["priority"],
        "sequence_hint": recommendation["sequence_hint"],
        "completeness_status": "incomplete" if missing_fields else "complete",
        "missing_fields": missing_fields,
        "rationale_quality": {
            "status": (
                "meets_minimum"
                if rationale_word_count >= int(thresholds["min_rationale_word_count"])
                else "low_substance"
            ),
            "word_count": rationale_word_count,
            "minimum_required": int(thresholds["min_rationale_word_count"]),
        },
        "evidence_citations": {
            "status": (
                "meets_minimum"
                if evidence_citation_count >= int(thresholds["min_evidence_citations"])
                else "below_minimum"
            ),
            "count": evidence_citation_count,
            "minimum_required": int(thresholds["min_evidence_citations"]),
            "evidence_refs": list(recommendation["evidence_refs"]),
        },
        "decision": "blocked" if failure_reason_codes else "accepted",
        "failure_reason_codes": failure_reason_codes,
    }


def _build_req_061_processing_behavior(
    *,
    assessments: list[dict[str, Any]],
    broad_sweep_context: dict[str, Any],
) -> dict[str, Any]:
    earth_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    earth_ref_set = set(earth_refs)
    obligations_input = list(broad_sweep_context["cross_project_obligations"])
    unresolved_ideas = list(broad_sweep_context["unresolved_ideas"])
    projects_considered = sorted(
        {
            *broad_sweep_context["projects_considered"],
            *[str(row["project_id"]) for row in obligations_input],
        }
    )

    recommended_actions: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    recommendation_mapping: list[dict[str, str]] = []
    accepted_recommendation_ids: list[str] = []
    blocked_recommendation_ids: list[str] = []

    for row in assessments:
        recommendation_id = str(row["recommendation_id"])
        packet_kind = str(row["packet_kind"])
        evidence_refs = list(row["evidence_citations"]["evidence_refs"])
        is_cross_project = packet_kind == "cross-project"
        has_earth_sweep_evidence = bool(earth_ref_set.intersection(evidence_refs))
        planner_status = "blocked_by_quality"

        if row["decision"] == "accepted":
            accepted_recommendation_ids.append(recommendation_id)
            if not is_cross_project or has_earth_sweep_evidence:
                planner_status = "promoted"
                recommended_actions.append(
                    {
                        "action_id": f"recommendation-{recommendation_id}",
                        "recommendation_id": recommendation_id,
                        "summary": str(row["summary"]),
                        "rationale": (
                            f"Completeness={row['completeness_status']}; "
                            f"rationale={row['rationale_quality']['status']}; "
                            f"evidence={row['evidence_citations']['status']}."
                        ),
                        "packet_kind": packet_kind,
                        "lane": str(row["lane"]),
                        "priority": str(row["priority"]),
                        "sequence_hint": int(row["sequence_hint"]),
                        "evidence_refs": evidence_refs,
                    }
                )
            else:
                planner_status = "blocked_by_missing_earth_sweep_evidence"
                required_refs = earth_refs or ["missing:earth-sweep-evidence-ref"]
                open_risks.append(
                    {
                        "risk_id": f"risk-{recommendation_id}",
                        "summary": str(row["summary"]),
                        "reason_code": "missing_earth_sweep_evidence_refs",
                        "evidence_refs": evidence_refs or required_refs,
                        "required_evidence_refs": required_refs,
                    }
                )
        else:
            blocked_recommendation_ids.append(recommendation_id)

        recommendation_mapping.append(
            {
                "recommendation_id": recommendation_id,
                "quality_decision": str(row["decision"]),
                "planner_status": planner_status,
                "packet_kind": packet_kind,
            }
        )

    cross_project_obligations: list[dict[str, Any]] = []
    for row in obligations_input:
        obligation_refs = sorted({*earth_refs, *list(row["evidence_refs"])})
        if earth_refs:
            cross_project_obligations.append(
                {
                    "obligation_id": str(row["obligation_id"]),
                    "project_id": str(row["project_id"]),
                    "summary": str(row["summary"]),
                    "evidence_refs": obligation_refs,
                }
            )
            continue

        required_refs = list(row["evidence_refs"]) or ["missing:earth-sweep-evidence-ref"]
        open_risks.append(
            {
                "risk_id": f"risk-{row['obligation_id']}",
                "summary": str(row["summary"]),
                "reason_code": "missing_earth_sweep_evidence_refs",
                "evidence_refs": required_refs,
                "required_evidence_refs": required_refs,
            }
        )

    for row in unresolved_ideas:
        required_refs = list(row["evidence_refs"]) or ["missing:earth-sweep-evidence-ref"]
        open_risks.append(
            {
                "risk_id": f"risk-{row['idea_id']}",
                "summary": str(row["summary"]),
                "reason_code": "unresolved_idea_open_risk",
                "evidence_refs": required_refs,
                "required_evidence_refs": required_refs,
            }
        )

    missing_earth_evidence = any(
        str(row["reason_code"]) == "missing_earth_sweep_evidence_refs" for row in open_risks
    )
    if recommended_actions:
        decision = "allow-planner-packet-with-open-risks" if open_risks else "allow-planner-packet"
        confidence = "medium" if open_risks else "high"
    else:
        decision = "block-planner-packet"
        confidence = "low" if (missing_earth_evidence or blocked_recommendation_ids or open_risks) else "medium"

    recommendation_evidence_refs = sorted(
        {
            *earth_refs,
            *[
                ref
                for row in assessments
                for ref in list(row["evidence_citations"]["evidence_refs"])
            ],
            *[ref for row in cross_project_obligations for ref in row["evidence_refs"]],
            *[ref for row in unresolved_ideas for ref in row["evidence_refs"]],
        }
    )
    recommendation = {
        "decision": decision,
        "rationale": (
            f"Promoted {len(recommended_actions)} planner-facing recommendation(s), "
            f"kept {len(cross_project_obligations)} cross-project obligation(s), "
            f"and recorded {len(open_risks)} open risk(s) from blocked or unresolved cross-project context."
        ),
        "confidence": confidence,
        "evidence_refs": recommendation_evidence_refs,
        "recommended_actions": recommended_actions,
        "cross_project_obligations": cross_project_obligations,
        "open_risks": sorted(
            open_risks,
            key=lambda row: (str(row["reason_code"]), str(row["risk_id"])),
        ),
    }

    required_recommendation_fields = list(_REQ_061_PROCESSING_RECOMMENDATION_FIELDS)
    recommendation_fields_complete = set(recommendation.keys()) == set(required_recommendation_fields)
    context_usage = {
        "cross_project_context_provided": bool(
            earth_refs or broad_sweep_context["projects_considered"] or obligations_input or unresolved_ideas
        ),
        "cross_project_context_used": bool(
            projects_considered
            or obligations_input
            or unresolved_ideas
            or any(str(row["packet_kind"]) == "cross-project" for row in assessments)
        ),
        "earth_sweep_context_used": bool(earth_refs),
        "projects_considered": projects_considered,
        "earth_sweep_evidence_refs_considered": earth_refs,
        "accepted_recommendation_ids": accepted_recommendation_ids,
        "blocked_recommendation_ids": blocked_recommendation_ids,
        "recommendation_mapping": recommendation_mapping,
        "recommendation_fields_complete": recommendation_fields_complete,
        "required_recommendation_fields": required_recommendation_fields,
    }
    return {
        "recommendation": recommendation,
        "context_usage": context_usage,
    }


def build_req_061_recommendation_quality_validator(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-061 payload for recommendation quality validation."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_061_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_061_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    thresholds = _normalize_req_061_thresholds(raw.get("quality_thresholds"))
    recommendations = _normalize_req_061_recommendations(raw.get("recommendations"))
    broad_sweep_context: dict[str, Any] | None = None
    if raw.get("broad_sweep_context") is not None:
        broad_sweep_context = _normalize_broad_sweep_context(raw.get("broad_sweep_context"))

    assessments = [
        _build_req_061_assessment_row(recommendation=row, thresholds=thresholds)
        for row in recommendations
    ]
    accepted_recommendations = [row for row in assessments if row["decision"] == "accepted"]
    blocked_recommendations = [row for row in assessments if row["decision"] == "blocked"]
    allowed_recommendation_ids = [str(row["recommendation_id"]) for row in accepted_recommendations]
    blocked_recommendation_ids = [str(row["recommendation_id"]) for row in blocked_recommendations]
    blocking_reason_codes = sorted(
        {
            reason_code
            for row in blocked_recommendations
            for reason_code in list(row["failure_reason_codes"])
        }
    )

    built = {
        "ok": True,
        "schema_version": REQ_061_SCHEMA_VERSION,
        "requirement_id": REQ_061_REQUIREMENT_ID,
        "analysis_type": REQ_061_ANALYSIS_TYPE,
        "call_id": REQ_061_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "target_project": target_project,
        "quality_thresholds": thresholds,
        "quality_validation": {
            "accepted_recommendations": accepted_recommendations,
            "blocked_recommendations": blocked_recommendations,
            "planner_readiness": {
                "decision": (
                    "allow_planner_packet"
                    if accepted_recommendations
                    else "block_planner_packet"
                ),
                "allowed_recommendation_ids": allowed_recommendation_ids,
                "blocked_recommendation_ids": blocked_recommendation_ids,
                "blocking_reason_codes": blocking_reason_codes,
            },
        },
        "totals": {
            "candidate_recommendations": len(recommendations),
            "accepted_recommendations": len(accepted_recommendations),
            "blocked_recommendations": len(blocked_recommendations),
            "incomplete_recommendations": sum(
                1 for row in assessments if row["completeness_status"] == "incomplete"
            ),
            "low_substance_recommendations": sum(
                1 for row in assessments if row["rationale_quality"]["status"] == "low_substance"
            ),
            "citation_failures": sum(
                1 for row in assessments if row["evidence_citations"]["status"] == "below_minimum"
            ),
        },
    }
    if broad_sweep_context is not None:
        built["processing_behavior"] = _build_req_061_processing_behavior(
            assessments=assessments,
            broad_sweep_context=broad_sweep_context,
        )
    errors = validate_req_061_recommendation_quality_validator(built)
    if errors:
        raise ValueError(f"built REQ-061 payload failed validation: {errors}")
    return built


def _req_061_append_diagnostic(
    errors: list[str],
    *,
    path: str,
    reason_code: str,
    message: str,
    evidence_refs: list[str],
    diff_details: Mapping[str, str] | None = None,
) -> None:
    diagnostic: dict[str, Any] = {
        "reason_code": reason_code,
        "message": message,
        "evidence_refs": evidence_refs,
    }
    if diff_details:
        diagnostic["diff_details"] = dict(sorted(diff_details.items()))
    errors.append(f"{path} diagnostic {json.dumps(diagnostic, sort_keys=True)}")


def _validate_req_061_traceability_evidence_refs(
    refs: Any,
    *,
    path: str,
    parent_ref_set: set[str],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(refs, list):
        return errors
    for index, item in enumerate(refs):
        if not isinstance(item, str) or not item.strip():
            continue
        evidence_ref = item.strip()
        if evidence_ref in parent_ref_set:
            continue
        ref_path = f"{path}[{index}]"
        errors.append(
            f"{ref_path} must exist in processing_behavior.recommendation.evidence_refs for traceability gate"
        )
        _req_061_append_diagnostic(
            errors,
            path=ref_path,
            reason_code=_REQ_061_REASON_CODE_TRACEABILITY_GATE_FAILED,
            message="broken evidence reference failed traceability gate",
            evidence_refs=[evidence_ref],
            diff_details={
                "expected_ref_set": "processing_behavior.recommendation.evidence_refs",
                "observed_ref": evidence_ref,
            },
        )
    return errors


def _validate_req_061_processing_recommended_action_row(row: Any, *, index: int) -> list[str]:
    errors: list[str] = []
    path = f"processing_behavior.recommendation.recommended_actions[{index}]"
    issue_tokens: set[str] = set()
    if not isinstance(row, Mapping):
        errors.append(f"{path} must be an object")
        _req_061_append_diagnostic(
            errors,
            path=path,
            reason_code=_REQ_061_REASON_CODE_STRATEGY_PACKET_SCHEMA_ROW_INVALID,
            message="strategy packet schema row rejected because row is not an object",
            evidence_refs=[path],
            diff_details={"issue_types": "row_not_object"},
        )
        return errors

    expected_keys = {
        "action_id",
        "recommendation_id",
        "summary",
        "rationale",
        "packet_kind",
        "lane",
        "priority",
        "sequence_hint",
        "evidence_refs",
    }
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{path} missing keys: {missing}")
        issue_tokens.add("missing_keys")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{path} has unexpected keys: {unexpected}")
        issue_tokens.add("unexpected_keys")

    for key in ("action_id", "recommendation_id", "summary", "rationale", "packet_kind", "lane", "priority"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}.{key} must be a non-empty string")
            issue_tokens.add(f"invalid_text:{key}")

    packet_kind = row.get("packet_kind")
    if isinstance(packet_kind, str) and packet_kind not in _REQ_061_ALLOWED_PACKET_KINDS:
        errors.append(f"{path}.packet_kind must be one of: {sorted(_REQ_061_ALLOWED_PACKET_KINDS)}")
        issue_tokens.add("invalid_packet_kind")

    priority = row.get("priority")
    if isinstance(priority, str) and priority not in _REQ_061_ALLOWED_PRIORITIES:
        errors.append(f"{path}.priority must be one of: {sorted(_REQ_061_ALLOWED_PRIORITIES)}")
        issue_tokens.add("invalid_priority")

    sequence_hint = row.get("sequence_hint")
    if not isinstance(sequence_hint, int) or isinstance(sequence_hint, bool) or sequence_hint <= 0:
        errors.append(f"{path}.sequence_hint must be a positive integer")
        issue_tokens.add("invalid_sequence_hint")

    evidence_refs = row.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append(f"{path}.evidence_refs must be a list")
        issue_tokens.add("invalid_evidence_refs_list")
    else:
        for evidence_index, item in enumerate(evidence_refs):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"{path}.evidence_refs[{evidence_index}] must be a non-empty string")
                issue_tokens.add("invalid_evidence_ref_item")

    recommendation_id = row.get("recommendation_id")
    action_id = row.get("action_id")
    if isinstance(recommendation_id, str) and recommendation_id.strip() and action_id != f"recommendation-{recommendation_id}":
        errors.append(f"{path}.action_id must equal recommendation-<recommendation_id>")
        issue_tokens.add("action_id_mismatch")

    if errors:
        _req_061_append_diagnostic(
            errors,
            path=path,
            reason_code=_REQ_061_REASON_CODE_STRATEGY_PACKET_SCHEMA_ROW_INVALID,
            message="strategy packet schema row rejected by deterministic validation gate",
            evidence_refs=[path],
            diff_details={"issue_types": ",".join(sorted(issue_tokens))},
        )

    return errors


def _validate_req_061_processing_mapping_row(row: Any, *, index: int) -> tuple[list[str], str]:
    errors: list[str] = []
    path = f"processing_behavior.context_usage.recommendation_mapping[{index}]"
    if not isinstance(row, Mapping):
        return [f"{path} must be an object"], ""

    expected_keys = {"recommendation_id", "quality_decision", "planner_status", "packet_kind"}
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{path} has unexpected keys: {unexpected}")

    recommendation_id = ""
    for key in ("recommendation_id", "quality_decision", "planner_status", "packet_kind"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}.{key} must be a non-empty string")
            continue
        if key == "recommendation_id":
            recommendation_id = value

    if row.get("quality_decision") not in _REQ_061_ALLOWED_DECISIONS:
        errors.append(f"{path}.quality_decision must be one of: {sorted(_REQ_061_ALLOWED_DECISIONS)}")
    if row.get("planner_status") not in _REQ_061_PROCESSING_ALLOWED_PLANNER_STATUS:
        errors.append(
            f"{path}.planner_status must be one of: {sorted(_REQ_061_PROCESSING_ALLOWED_PLANNER_STATUS)}"
        )
    if row.get("packet_kind") not in _REQ_061_ALLOWED_PACKET_KINDS:
        errors.append(f"{path}.packet_kind must be one of: {sorted(_REQ_061_ALLOWED_PACKET_KINDS)}")

    return errors, recommendation_id


def _validate_req_061_processing_behavior(
    processing_behavior: Any,
    *,
    accepted_ids: list[str],
    blocked_ids: list[str],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(processing_behavior, Mapping):
        return ["processing_behavior must be an object"]

    expected_keys = {"recommendation", "context_usage"}
    keys = set(processing_behavior.keys())
    missing = sorted(expected_keys - keys)
    if missing:
        errors.append(f"processing_behavior missing keys: {missing}")
    unexpected = sorted(keys - expected_keys)
    if unexpected:
        errors.append(f"processing_behavior has unexpected keys: {unexpected}")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        recommendation_keys = set(recommendation.keys())
        required_recommendation_keys = set(_REQ_061_PROCESSING_RECOMMENDATION_FIELDS)
        missing_recommendation = sorted(required_recommendation_keys - recommendation_keys)
        if missing_recommendation:
            errors.append(f"processing_behavior.recommendation missing keys: {missing_recommendation}")
        unexpected_recommendation = sorted(recommendation_keys - required_recommendation_keys)
        if unexpected_recommendation:
            errors.append(
                f"processing_behavior.recommendation has unexpected keys: {unexpected_recommendation}"
            )

        for key in ("decision", "rationale", "confidence"):
            value = recommendation.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"processing_behavior.recommendation.{key} must be a non-empty string")

        if recommendation.get("decision") not in _REQ_061_PROCESSING_ALLOWED_DECISIONS:
            errors.append(
                "processing_behavior.recommendation.decision must be one of: "
                f"{sorted(_REQ_061_PROCESSING_ALLOWED_DECISIONS)}"
            )
        if recommendation.get("confidence") not in _REQ_061_PROCESSING_ALLOWED_CONFIDENCE:
            errors.append(
                "processing_behavior.recommendation.confidence must be one of: "
                f"{sorted(_REQ_061_PROCESSING_ALLOWED_CONFIDENCE)}"
            )

        evidence_refs = recommendation.get("evidence_refs")
        traceability_evidence_ref_set: set[str] = set()
        if not isinstance(evidence_refs, list):
            errors.append("processing_behavior.recommendation.evidence_refs must be a list")
        else:
            for evidence_index, item in enumerate(evidence_refs):
                if not isinstance(item, str) or not item.strip():
                    errors.append(
                        f"processing_behavior.recommendation.evidence_refs[{evidence_index}] must be a non-empty string"
                    )
                    continue
                traceability_evidence_ref_set.add(item.strip())

        recommended_actions = recommendation.get("recommended_actions")
        if not isinstance(recommended_actions, list):
            errors.append("processing_behavior.recommendation.recommended_actions must be a list")
        else:
            for index, row in enumerate(recommended_actions):
                errors.extend(_validate_req_061_processing_recommended_action_row(row, index=index))
                if isinstance(row, Mapping):
                    errors.extend(
                        _validate_req_061_traceability_evidence_refs(
                            row.get("evidence_refs"),
                            path=(
                                "processing_behavior.recommendation."
                                f"recommended_actions[{index}].evidence_refs"
                            ),
                            parent_ref_set=traceability_evidence_ref_set,
                        )
                    )

        for key in ("cross_project_obligations", "open_risks"):
            value = recommendation.get(key)
            if not isinstance(value, list):
                errors.append(f"processing_behavior.recommendation.{key} must be a list")
                continue
            for index, row in enumerate(value):
                errors.extend(_validate_req_055_recommendation_row(row, index=index, kind=key))
                if isinstance(row, Mapping):
                    errors.extend(
                        _validate_req_061_traceability_evidence_refs(
                            row.get("evidence_refs"),
                            path=f"processing_behavior.recommendation.{key}[{index}].evidence_refs",
                            parent_ref_set=traceability_evidence_ref_set,
                        )
                    )

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        context_keys = set(context_usage.keys())
        required_context_keys = set(_REQ_061_PROCESSING_CONTEXT_USAGE_FIELDS)
        missing_context = sorted(required_context_keys - context_keys)
        if missing_context:
            errors.append(f"processing_behavior.context_usage missing keys: {missing_context}")
        unexpected_context = sorted(context_keys - required_context_keys)
        if unexpected_context:
            errors.append(f"processing_behavior.context_usage has unexpected keys: {unexpected_context}")

        for key in (
            "cross_project_context_provided",
            "cross_project_context_used",
            "earth_sweep_context_used",
            "recommendation_fields_complete",
        ):
            if not isinstance(context_usage.get(key), bool):
                errors.append(f"processing_behavior.context_usage.{key} must be a boolean")

        for key in (
            "projects_considered",
            "earth_sweep_evidence_refs_considered",
            "accepted_recommendation_ids",
            "blocked_recommendation_ids",
        ):
            value = context_usage.get(key)
            if not isinstance(value, list):
                errors.append(f"processing_behavior.context_usage.{key} must be a list")
                continue
            for item_index, item in enumerate(value):
                if not isinstance(item, str) or not item.strip():
                    errors.append(
                        f"processing_behavior.context_usage.{key}[{item_index}] must be a non-empty string"
                    )

        if context_usage.get("accepted_recommendation_ids") != accepted_ids:
            errors.append(
                "processing_behavior.context_usage.accepted_recommendation_ids must match quality accepted IDs"
            )
        if context_usage.get("blocked_recommendation_ids") != blocked_ids:
            errors.append(
                "processing_behavior.context_usage.blocked_recommendation_ids must match quality blocked IDs"
            )

        recommendation_mapping = context_usage.get("recommendation_mapping")
        if not isinstance(recommendation_mapping, list):
            errors.append("processing_behavior.context_usage.recommendation_mapping must be a list")
        else:
            mapped_recommendation_ids: list[str] = []
            seen_mapped_recommendation_ids: set[str] = set()
            for index, row in enumerate(recommendation_mapping):
                row_errors, recommendation_id = _validate_req_061_processing_mapping_row(row, index=index)
                errors.extend(row_errors)
                if recommendation_id:
                    if recommendation_id in seen_mapped_recommendation_ids:
                        errors.append(
                            "processing_behavior.context_usage.recommendation_mapping recommendation_ids must be unique"
                        )
                    else:
                        seen_mapped_recommendation_ids.add(recommendation_id)
                        mapped_recommendation_ids.append(recommendation_id)
            if sorted(mapped_recommendation_ids) != sorted([*accepted_ids, *blocked_ids]):
                errors.append(
                    "processing_behavior.context_usage.recommendation_mapping must cover all quality-assessed recommendation IDs"
                )

        if context_usage.get("required_recommendation_fields") != list(_REQ_061_PROCESSING_RECOMMENDATION_FIELDS):
            errors.append(
                "processing_behavior.context_usage.required_recommendation_fields must match required recommendation keys"
            )
        if context_usage.get("recommendation_fields_complete") is not True:
            errors.append("processing_behavior.context_usage.recommendation_fields_complete must be true")

    return errors


def _validate_req_061_assessment_row(
    row: Any,
    *,
    path: str,
    expected_decision: str,
    thresholds: Mapping[str, Any],
) -> tuple[list[str], str]:
    errors: list[str] = []
    if not isinstance(row, Mapping):
        return [f"{path} must be an object"], ""

    expected_keys = {
        "recommendation_id",
        "summary",
        "packet_kind",
        "lane",
        "priority",
        "sequence_hint",
        "completeness_status",
        "missing_fields",
        "rationale_quality",
        "evidence_citations",
        "decision",
        "failure_reason_codes",
    }
    row_keys = set(row.keys())
    missing = sorted(expected_keys - row_keys)
    if missing:
        errors.append(f"{path} missing keys: {missing}")
    unexpected = sorted(row_keys - expected_keys)
    if unexpected:
        errors.append(f"{path} has unexpected keys: {unexpected}")

    recommendation_id = row.get("recommendation_id")
    if not isinstance(recommendation_id, str) or not recommendation_id.strip():
        errors.append(f"{path}.recommendation_id must be a non-empty string")
        recommendation_id = ""

    for key in ("summary", "packet_kind", "lane", "priority"):
        value = row.get(key)
        if not isinstance(value, str):
            errors.append(f"{path}.{key} must be a string")

    packet_kind = row.get("packet_kind")
    if isinstance(packet_kind, str) and packet_kind and packet_kind not in _REQ_061_ALLOWED_PACKET_KINDS:
        errors.append(f"{path}.packet_kind must be one of: {sorted(_REQ_061_ALLOWED_PACKET_KINDS)}")

    priority = row.get("priority")
    if isinstance(priority, str) and priority and priority not in _REQ_061_ALLOWED_PRIORITIES:
        errors.append(f"{path}.priority must be one of: {sorted(_REQ_061_ALLOWED_PRIORITIES)}")

    sequence_hint = row.get("sequence_hint")
    if not isinstance(sequence_hint, int) or isinstance(sequence_hint, bool) or sequence_hint < 0:
        errors.append(f"{path}.sequence_hint must be a non-negative integer")

    completeness_status = row.get("completeness_status")
    if completeness_status not in _REQ_061_ALLOWED_COMPLETENESS:
        errors.append(f"{path}.completeness_status must be one of: {sorted(_REQ_061_ALLOWED_COMPLETENESS)}")

    missing_fields = row.get("missing_fields")
    if not isinstance(missing_fields, list):
        errors.append(f"{path}.missing_fields must be a list")
        missing_fields = []
    else:
        for index, field_name in enumerate(missing_fields):
            if field_name not in _REQ_061_REQUIRED_RECOMMENDATION_FIELDS:
                errors.append(
                    f"{path}.missing_fields[{index}] must be one of: {list(_REQ_061_REQUIRED_RECOMMENDATION_FIELDS)}"
                )
        expected_missing_field_order = [
            field_name
            for field_name in _REQ_061_REQUIRED_RECOMMENDATION_FIELDS
            if field_name in set(missing_fields)
        ]
        if missing_fields != expected_missing_field_order:
            errors.append(f"{path}.missing_fields must follow required_recommendation_fields order")

    rationale_quality = row.get("rationale_quality")
    if not isinstance(rationale_quality, Mapping):
        errors.append(f"{path}.rationale_quality must be an object")
    else:
        expected_rationale_keys = {"status", "word_count", "minimum_required"}
        rationale_keys = set(rationale_quality.keys())
        missing_rationale = sorted(expected_rationale_keys - rationale_keys)
        if missing_rationale:
            errors.append(f"{path}.rationale_quality missing keys: {missing_rationale}")
        unexpected_rationale = sorted(rationale_keys - expected_rationale_keys)
        if unexpected_rationale:
            errors.append(f"{path}.rationale_quality has unexpected keys: {unexpected_rationale}")

        status = rationale_quality.get("status")
        if status not in _REQ_061_ALLOWED_RATIONALE_STATUS:
            errors.append(
                f"{path}.rationale_quality.status must be one of: {sorted(_REQ_061_ALLOWED_RATIONALE_STATUS)}"
            )
        for key in ("word_count", "minimum_required"):
            value = rationale_quality.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"{path}.rationale_quality.{key} must be a non-negative integer")
        if rationale_quality.get("minimum_required") != thresholds.get("min_rationale_word_count"):
            errors.append(
                f"{path}.rationale_quality.minimum_required must match quality_thresholds.min_rationale_word_count"
            )

    evidence_citations = row.get("evidence_citations")
    if not isinstance(evidence_citations, Mapping):
        errors.append(f"{path}.evidence_citations must be an object")
    else:
        expected_evidence_keys = {"status", "count", "minimum_required", "evidence_refs"}
        evidence_keys = set(evidence_citations.keys())
        missing_evidence = sorted(expected_evidence_keys - evidence_keys)
        if missing_evidence:
            errors.append(f"{path}.evidence_citations missing keys: {missing_evidence}")
        unexpected_evidence = sorted(evidence_keys - expected_evidence_keys)
        if unexpected_evidence:
            errors.append(f"{path}.evidence_citations has unexpected keys: {unexpected_evidence}")

        status = evidence_citations.get("status")
        if status not in _REQ_061_ALLOWED_EVIDENCE_STATUS:
            errors.append(
                f"{path}.evidence_citations.status must be one of: {sorted(_REQ_061_ALLOWED_EVIDENCE_STATUS)}"
            )
        for key in ("count", "minimum_required"):
            value = evidence_citations.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"{path}.evidence_citations.{key} must be a non-negative integer")
        refs = evidence_citations.get("evidence_refs")
        if not isinstance(refs, list):
            errors.append(f"{path}.evidence_citations.evidence_refs must be a list")
        else:
            for index, item in enumerate(refs):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"{path}.evidence_citations.evidence_refs[{index}] must be a non-empty string")
            if refs != sorted(set(refs)):
                errors.append(f"{path}.evidence_citations.evidence_refs must be sorted unique strings")
            if evidence_citations.get("count") != len(refs):
                errors.append(f"{path}.evidence_citations.count must equal evidence_refs length")
        if evidence_citations.get("minimum_required") != thresholds.get("min_evidence_citations"):
            errors.append(
                f"{path}.evidence_citations.minimum_required must match quality_thresholds.min_evidence_citations"
            )

    decision = row.get("decision")
    if decision != expected_decision:
        errors.append(f"{path}.decision must be {expected_decision}")

    failure_reason_codes = row.get("failure_reason_codes")
    if not isinstance(failure_reason_codes, list):
        errors.append(f"{path}.failure_reason_codes must be a list")
        failure_reason_codes = []
    else:
        for index, item in enumerate(failure_reason_codes):
            if item not in _REQ_061_ALLOWED_FAILURE_REASON_CODES:
                errors.append(
                    f"{path}.failure_reason_codes[{index}] must be one of: {sorted(_REQ_061_ALLOWED_FAILURE_REASON_CODES)}"
                )
        expected_failure_reason_order = [
            reason_code
            for reason_code in _REQ_061_FAILURE_REASON_ORDER
            if reason_code in set(failure_reason_codes)
        ]
        if failure_reason_codes != expected_failure_reason_order:
            errors.append(f"{path}.failure_reason_codes must follow REQ-061 failure-reason order")

    if completeness_status == "complete" and missing_fields:
        errors.append(f"{path}.missing_fields must be empty when completeness_status is complete")
    if completeness_status == "incomplete" and not missing_fields:
        errors.append(f"{path}.missing_fields must be non-empty when completeness_status is incomplete")

    rationale_status = (
        rationale_quality.get("status") if isinstance(rationale_quality, Mapping) else None
    )
    evidence_status = (
        evidence_citations.get("status") if isinstance(evidence_citations, Mapping) else None
    )
    expected_failure_reason_codes: list[str] = []
    if completeness_status == "incomplete":
        expected_failure_reason_codes.append("incomplete_recommendation")
    if rationale_status == "low_substance":
        expected_failure_reason_codes.append("low_substance_rationale")
    if evidence_status == "below_minimum":
        expected_failure_reason_codes.append("insufficient_evidence_citations")

    if decision == "accepted":
        if expected_failure_reason_codes:
            errors.append(f"{path}.decision cannot be accepted when quality failures are present")
        if failure_reason_codes:
            errors.append(f"{path}.failure_reason_codes must be empty for accepted rows")
    elif decision == "blocked":
        if failure_reason_codes != expected_failure_reason_codes:
            errors.append(f"{path}.failure_reason_codes must match derived quality failures")

    return errors, str(recommendation_id)


def validate_req_061_recommendation_quality_validator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-061 recommendation quality validator shape."""
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
        "quality_thresholds",
        "quality_validation",
        "totals",
    }
    optional_top = {"processing_behavior"}
    expected_top = required_top | optional_top
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - expected_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_061_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_061_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_061_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_061_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_061_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_061_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_061_CALL_ID:
        errors.append(f"call_id must be {REQ_061_CALL_ID}")
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

    quality_thresholds = payload.get("quality_thresholds")
    if not isinstance(quality_thresholds, Mapping):
        errors.append("quality_thresholds must be an object")
        quality_thresholds = {}
    else:
        expected_thresholds = {
            "required_recommendation_fields",
            "min_rationale_word_count",
            "min_evidence_citations",
        }
        threshold_keys = set(quality_thresholds.keys())
        missing_thresholds = sorted(expected_thresholds - threshold_keys)
        if missing_thresholds:
            errors.append(f"quality_thresholds missing keys: {missing_thresholds}")
        unexpected_thresholds = sorted(threshold_keys - expected_thresholds)
        if unexpected_thresholds:
            errors.append(f"quality_thresholds has unexpected keys: {unexpected_thresholds}")

        if quality_thresholds.get("required_recommendation_fields") != list(_REQ_061_REQUIRED_RECOMMENDATION_FIELDS):
            errors.append("quality_thresholds.required_recommendation_fields must match REQ-061 field anchors")
        for key in ("min_rationale_word_count", "min_evidence_citations"):
            value = quality_thresholds.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(f"quality_thresholds.{key} must be a positive integer")

    quality_validation = payload.get("quality_validation")
    accepted_ids: list[str] = []
    blocked_ids: list[str] = []
    blocked_reason_codes: list[str] = []
    if not isinstance(quality_validation, Mapping):
        errors.append("quality_validation must be an object")
    else:
        expected_quality_validation = {
            "accepted_recommendations",
            "blocked_recommendations",
            "planner_readiness",
        }
        quality_validation_keys = set(quality_validation.keys())
        missing_quality_validation = sorted(expected_quality_validation - quality_validation_keys)
        if missing_quality_validation:
            errors.append(f"quality_validation missing keys: {missing_quality_validation}")
        unexpected_quality_validation = sorted(quality_validation_keys - expected_quality_validation)
        if unexpected_quality_validation:
            errors.append(f"quality_validation has unexpected keys: {unexpected_quality_validation}")

        seen_ids: set[str] = set()
        recommendation_id_locations: dict[str, str] = {}
        for bucket_name, expected_decision in (
            ("accepted_recommendations", "accepted"),
            ("blocked_recommendations", "blocked"),
        ):
            value = quality_validation.get(bucket_name)
            if not isinstance(value, list):
                errors.append(f"quality_validation.{bucket_name} must be a list")
                continue
            previous_sort_key: tuple[int, str] | None = None
            for index, row in enumerate(value):
                row_path = f"quality_validation.{bucket_name}[{index}]"
                row_errors, recommendation_id = _validate_req_061_assessment_row(
                    row,
                    path=row_path,
                    expected_decision=expected_decision,
                    thresholds=quality_thresholds,
                )
                errors.extend(row_errors)
                if recommendation_id:
                    row_location = f"quality_validation.{bucket_name}[{index}]"
                    if recommendation_id in seen_ids:
                        errors.append(
                            "quality_validation recommendation_id values must be unique across accepted and blocked rows"
                        )
                        _req_061_append_diagnostic(
                            errors,
                            path=row_location,
                            reason_code=_REQ_061_REASON_CODE_DUPLICATE_RECOMMENDATION_ID_COLLISION,
                            message="duplicate recommendation_id collision detected across quality buckets",
                            evidence_refs=[
                                recommendation_id_locations[recommendation_id],
                                row_location,
                            ],
                            diff_details={
                                "first_seen": recommendation_id_locations[recommendation_id],
                                "duplicate_seen": row_location,
                                "recommendation_id": recommendation_id,
                            },
                        )
                    else:
                        seen_ids.add(recommendation_id)
                        recommendation_id_locations[recommendation_id] = row_location
                        if bucket_name == "accepted_recommendations":
                            accepted_ids.append(recommendation_id)
                        else:
                            blocked_ids.append(recommendation_id)
                            if isinstance(row, Mapping):
                                blocked_reason_codes.extend(list(row.get("failure_reason_codes", [])))
                if isinstance(row, Mapping):
                    sort_key = (
                        int(row.get("sequence_hint", 0)) if isinstance(row.get("sequence_hint"), int) else -1,
                        str(row.get("recommendation_id", "")),
                    )
                    if previous_sort_key is not None and sort_key < previous_sort_key:
                        errors.append(f"{row_path} must preserve deterministic sort order by sequence_hint then recommendation_id")
                    previous_sort_key = sort_key

        planner_readiness = quality_validation.get("planner_readiness")
        if not isinstance(planner_readiness, Mapping):
            errors.append("quality_validation.planner_readiness must be an object")
        else:
            expected_planner_readiness = {
                "decision",
                "allowed_recommendation_ids",
                "blocked_recommendation_ids",
                "blocking_reason_codes",
            }
            readiness_keys = set(planner_readiness.keys())
            missing_readiness = sorted(expected_planner_readiness - readiness_keys)
            if missing_readiness:
                errors.append(f"quality_validation.planner_readiness missing keys: {missing_readiness}")
            unexpected_readiness = sorted(readiness_keys - expected_planner_readiness)
            if unexpected_readiness:
                errors.append(f"quality_validation.planner_readiness has unexpected keys: {unexpected_readiness}")

            decision = planner_readiness.get("decision")
            if decision not in _REQ_061_ALLOWED_PLANNER_READINESS:
                errors.append(
                    "quality_validation.planner_readiness.decision must be "
                    f"one of: {sorted(_REQ_061_ALLOWED_PLANNER_READINESS)}"
                )
            for key, expected_ids in (
                ("allowed_recommendation_ids", accepted_ids),
                ("blocked_recommendation_ids", blocked_ids),
            ):
                value = planner_readiness.get(key)
                if not isinstance(value, list):
                    errors.append(f"quality_validation.planner_readiness.{key} must be a list")
                    continue
                for index, item in enumerate(value):
                    if not isinstance(item, str) or not item.strip():
                        errors.append(
                            f"quality_validation.planner_readiness.{key}[{index}] must be a non-empty string"
                        )
                if value != expected_ids:
                    errors.append(f"quality_validation.planner_readiness.{key} must match assessed recommendation IDs")

            blocking_reason_codes_value = planner_readiness.get("blocking_reason_codes")
            if not isinstance(blocking_reason_codes_value, list):
                errors.append("quality_validation.planner_readiness.blocking_reason_codes must be a list")
            else:
                for index, item in enumerate(blocking_reason_codes_value):
                    if item not in _REQ_061_ALLOWED_FAILURE_REASON_CODES:
                        errors.append(
                            "quality_validation.planner_readiness.blocking_reason_codes"
                            f"[{index}] must be one of: {sorted(_REQ_061_ALLOWED_FAILURE_REASON_CODES)}"
                        )
                expected_blocking_reason_codes = sorted(set(blocked_reason_codes))
                if blocking_reason_codes_value != expected_blocking_reason_codes:
                    errors.append(
                        "quality_validation.planner_readiness.blocking_reason_codes must match blocked recommendation failures"
                    )

            if accepted_ids and planner_readiness.get("decision") != "allow_planner_packet":
                errors.append(
                    "quality_validation.planner_readiness.decision must be allow_planner_packet when accepted recommendations exist"
                )
            if not accepted_ids and planner_readiness.get("decision") != "block_planner_packet":
                errors.append(
                    "quality_validation.planner_readiness.decision must be block_planner_packet when all recommendations are blocked"
                )

    processing_behavior = payload.get("processing_behavior")
    if processing_behavior is not None:
        errors.extend(
            _validate_req_061_processing_behavior(
                processing_behavior,
                accepted_ids=accepted_ids,
                blocked_ids=blocked_ids,
            )
        )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_totals = {
            "candidate_recommendations",
            "accepted_recommendations",
            "blocked_recommendations",
            "incomplete_recommendations",
            "low_substance_recommendations",
            "citation_failures",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_totals - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_totals)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        for total_key in expected_totals:
            value = totals.get(total_key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"totals.{total_key} must be a non-negative integer")

        incomplete_count = 0
        low_substance_count = 0
        citation_failure_count = 0
        assessment_total = 0
        quality_validation_value = payload.get("quality_validation")
        if isinstance(quality_validation_value, Mapping):
            for bucket_name in ("accepted_recommendations", "blocked_recommendations"):
                bucket = quality_validation_value.get(bucket_name)
                if not isinstance(bucket, list):
                    continue
                assessment_total += len(bucket)
                for row in bucket:
                    if not isinstance(row, Mapping):
                        continue
                    if row.get("completeness_status") == "incomplete":
                        incomplete_count += 1
                    rationale_quality = row.get("rationale_quality")
                    if isinstance(rationale_quality, Mapping) and rationale_quality.get("status") == "low_substance":
                        low_substance_count += 1
                    evidence_citations = row.get("evidence_citations")
                    if isinstance(evidence_citations, Mapping) and evidence_citations.get("status") == "below_minimum":
                        citation_failure_count += 1

        if totals.get("candidate_recommendations") != assessment_total:
            errors.append("totals.candidate_recommendations must equal accepted+blocked recommendation counts")
        if totals.get("accepted_recommendations") != len(accepted_ids):
            errors.append("totals.accepted_recommendations must equal accepted recommendation count")
        if totals.get("blocked_recommendations") != len(blocked_ids):
            errors.append("totals.blocked_recommendations must equal blocked recommendation count")
        if totals.get("incomplete_recommendations") != incomplete_count:
            errors.append("totals.incomplete_recommendations must equal incomplete recommendation count")
        if totals.get("low_substance_recommendations") != low_substance_count:
            errors.append("totals.low_substance_recommendations must equal low-substance recommendation count")
        if totals.get("citation_failures") != citation_failure_count:
            errors.append("totals.citation_failures must equal evidence citation failure count")

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
    parser = argparse.ArgumentParser(description="Emit strategy artifact handoff payloads.")
    parser.add_argument(
        "--input-json",
        required=True,
        help="Path to strategy artifact input JSON (or '-' for stdin).",
    )
    return parser


def _build_artifact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type in ("", REQ_055_ANALYSIS_TYPE):
        return build_req_055_constraint_classification_artifact(payload)
    if analysis_type == REQ_061_ANALYSIS_TYPE:
        return build_req_061_recommendation_quality_validator(payload)
    raise ValueError(f"unsupported analysis_type: {analysis_type}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_input_payload(args.input_json)
        built = _build_artifact_payload(payload)
    except Exception as exc:  # pragma: no cover - CLI guardrail
        sys.stderr.write(f"[{_utc_timestamp()}] strategy artifact handoff CLI failed: {exc}\n")
        return 1

    sys.stdout.write(json.dumps(built, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
