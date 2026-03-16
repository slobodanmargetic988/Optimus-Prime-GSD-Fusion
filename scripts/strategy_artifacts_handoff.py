#!/usr/bin/env python3
"""REQ-055 constraint classification artifact surface."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REQ_055_REQUIREMENT_ID = "REQ-055"
REQ_055_SCHEMA_VERSION = "1.0"
REQ_055_ANALYSIS_TYPE = "constraint_classification_artifact"
REQ_055_CALL_ID = "constraint-classification-artifact"

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
    parser = argparse.ArgumentParser(description="Emit REQ-055 constraint classification artifact payload.")
    parser.add_argument(
        "--input-json",
        required=True,
        help="Path to REQ-055 input JSON (or '-' for stdin).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_input_payload(args.input_json)
        built = build_req_055_constraint_classification_artifact(payload)
    except Exception as exc:  # pragma: no cover - CLI guardrail
        sys.stderr.write(f"[{_utc_timestamp()}] REQ-055 CLI failed: {exc}\n")
        return 1

    sys.stdout.write(json.dumps(built, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
