#!/usr/bin/env python3
"""REQ-001 contract surface for the LLM-first strategy runtime entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "req-001.llm-first-strategy-runtime-entrypoint.v1"
REQUIREMENT_ID = "REQ-001"
RUNTIME_MODE = "llm-first"
EXECUTION_MODE = "long-thinking"


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _normalize_root(raw_path: str, *, field_name: str) -> str:
    normalized = str(Path(_require_nonempty_text(raw_path, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


def _canonical_call_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
) -> dict[str, str]:
    return {
        "earth_root": earth_root,
        "execution_mode": EXECUTION_MODE,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "runtime_mode": RUNTIME_MODE,
        "target_project_root": target_project_root,
    }


def _canonical_input_digest(canonical_input: Mapping[str, Any]) -> str:
    raw = json.dumps(canonical_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_string_list(raw_value: Any, *, field_name: str) -> list[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: set[str] = set()
    for index, item in enumerate(raw_value):
        text = _require_nonempty_text(item, field_name=f"{field_name}[{index}]")
        normalized.add(text)
    return sorted(normalized)


def _normalize_context_note(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return ""
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    return raw_value.strip()


def _stable_id_fragment(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _normalize_cross_project_context(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("cross_project_context must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"cross_project_context[{index}] must be an object")
        project_id = _require_nonempty_text(item.get("project_id"), field_name=f"cross_project_context[{index}].project_id")
        project_root = _normalize_root(item.get("project_root"), field_name=f"cross_project_context[{index}].project_root")
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"cross_project_context[{index}].evidence_refs",
        )
        context_note = _normalize_context_note(item.get("context_note"), field_name=f"cross_project_context[{index}].context_note")
        normalized.append(
            {
                "project_id": project_id,
                "project_root": project_root,
                "evidence_refs": evidence_refs,
                "context_note": context_note,
            }
        )

    normalized.sort(key=lambda row: (row["project_id"], row["project_root"]))
    return normalized


def _normalize_source_artifact_status(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "fresh"
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    status = raw_value.strip().lower()
    if status not in {"fresh", "stale"}:
        raise ValueError(f"{field_name} must be either 'fresh' or 'stale'")
    return status


def _normalize_earth_sweep_source_artifacts(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("earth_sweep_source_artifacts must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"earth_sweep_source_artifacts[{index}] must be an object")
        artifact_ref = _require_nonempty_text(
            item.get("artifact_ref"),
            field_name=f"earth_sweep_source_artifacts[{index}].artifact_ref",
        )
        status = _normalize_source_artifact_status(
            item.get("status"),
            field_name=f"earth_sweep_source_artifacts[{index}].status",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"earth_sweep_source_artifacts[{index}].evidence_refs",
        )
        normalized.append(
            {
                "artifact_ref": artifact_ref,
                "status": status,
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(key=lambda row: (row["artifact_ref"], row["status"]))
    return normalized


def _normalize_required_doc_kind(raw_value: Any, *, field_name: str) -> str:
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string")
    doc_kind = raw_value.strip().lower()
    if doc_kind not in {"mission", "scope", "peer-project"}:
        raise ValueError(f"{field_name} must be one of: mission, scope, peer-project")
    return doc_kind


def _normalize_required_doc_status(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "present"
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    status = raw_value.strip().lower()
    if status not in {"present", "missing"}:
        raise ValueError(f"{field_name} must be either 'present' or 'missing'")
    return status


def _normalize_required_context_documents(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("required_context_documents must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"required_context_documents[{index}] must be an object")
        doc_kind = _normalize_required_doc_kind(
            item.get("doc_kind"),
            field_name=f"required_context_documents[{index}].doc_kind",
        )
        doc_ref = _require_nonempty_text(
            item.get("doc_ref"),
            field_name=f"required_context_documents[{index}].doc_ref",
        )
        status = _normalize_required_doc_status(
            item.get("status"),
            field_name=f"required_context_documents[{index}].status",
        )
        project_id = _normalize_context_note(
            item.get("project_id"),
            field_name=f"required_context_documents[{index}].project_id",
        )
        if doc_kind == "peer-project" and not project_id:
            raise ValueError(f"required_context_documents[{index}].project_id must be set for peer-project docs")
        if doc_kind != "peer-project":
            project_id = ""
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"required_context_documents[{index}].evidence_refs",
        )
        normalized.append(
            {
                "doc_kind": doc_kind,
                "doc_ref": doc_ref,
                "status": status,
                "project_id": project_id,
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(key=lambda row: (row["doc_kind"], row["project_id"], row["doc_ref"], row["status"]))
    return normalized


def _normalize_action_scope(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "local"
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    scope = raw_value.strip().lower()
    if scope not in {"local", "cross-project"}:
        raise ValueError(f"{field_name} must be either 'local' or 'cross-project'")
    return scope


def _normalize_candidate_recommendations(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("candidate_recommendations must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"candidate_recommendations[{index}] must be an object")
        raw_action_id = item.get("action_id")
        action_id = (
            _require_nonempty_text(raw_action_id, field_name=f"candidate_recommendations[{index}].action_id")
            if raw_action_id is not None
            else f"action-{index + 1:02d}"
        )
        summary = _require_nonempty_text(item.get("summary"), field_name=f"candidate_recommendations[{index}].summary")
        rationale = _require_nonempty_text(
            item.get("rationale") if item.get("rationale") is not None else "No rationale supplied.",
            field_name=f"candidate_recommendations[{index}].rationale",
        )
        scope = _normalize_action_scope(
            item.get("action_scope"),
            field_name=f"candidate_recommendations[{index}].action_scope",
        )
        requires_earth_evidence = bool(item.get("requires_earth_evidence", scope == "cross-project"))
        project_id = _normalize_context_note(item.get("project_id"), field_name=f"candidate_recommendations[{index}].project_id")
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"candidate_recommendations[{index}].evidence_refs",
        )
        next_step = _normalize_context_note(item.get("next_step"), field_name=f"candidate_recommendations[{index}].next_step")
        normalized.append(
            {
                "action_id": action_id,
                "summary": summary,
                "rationale": rationale,
                "action_scope": scope,
                "requires_earth_evidence": requires_earth_evidence,
                "project_id": project_id,
                "evidence_refs": evidence_refs,
                "next_step": next_step or f"Validate '{action_id}' via LLM-first long-thinking execution.",
            }
        )

    normalized.sort(key=lambda row: row["action_id"])
    return normalized


def _canonical_processing_input(
    *,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]] | None = None,
    required_context_documents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    canonical: dict[str, Any] = {
        "target_project_evidence_refs": target_project_evidence_refs,
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
        "cross_project_context": cross_project_context,
        "candidate_recommendations": candidate_recommendations,
    }
    if earth_sweep_source_artifacts:
        canonical["earth_sweep_source_artifacts"] = earth_sweep_source_artifacts
    if required_context_documents:
        canonical["required_context_documents"] = required_context_documents
    return canonical


def _collect_unique_refs(*ref_groups: list[str]) -> list[str]:
    out: set[str] = set()
    for refs in ref_groups:
        out.update(refs)
    return sorted(out)


def _recommendation_decision(*, recommended_actions: list[dict[str, Any]], open_risks: list[dict[str, Any]]) -> str:
    if recommended_actions and not open_risks:
        return "proceed"
    if recommended_actions and open_risks:
        return "proceed-with-open-risks"
    if open_risks:
        if any(str(row.get("reason_code")) != "missing_earth_sweep_evidence_refs" for row in open_risks):
            return "resolve-context-gaps"
        return "collect-earth-evidence"
    return "insufficient-context"


def _recommendation_rationale(*, decision: str) -> str:
    if decision == "proceed":
        return "Broad-sweep context evidence is sufficient for immediate LLM-first execution."
    if decision == "proceed-with-open-risks":
        return "Some actions are evidence-backed, while unresolved cross-project ideas remain open risks."
    if decision == "collect-earth-evidence":
        return "Cross-project ideas require Earth-sweep evidence refs before obligations can be committed."
    if decision == "resolve-context-gaps":
        return "Stale or missing context artifacts were detected; refresh required evidence before runtime replay."
    return "No actionable evidence-backed strategy actions were found in the provided context sweep."


def _recommendation_confidence(*, evidence_refs: list[str], open_risks: list[dict[str, Any]]) -> str:
    if not evidence_refs:
        return "low"
    if open_risks:
        return "medium"
    return "high"


def _build_processing_behavior(
    *,
    target_project_root: str,
    earth_root: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    cross_project_refs = _collect_unique_refs(*[row["evidence_refs"] for row in cross_project_context])
    source_artifact_refs = _collect_unique_refs(
        *[_collect_unique_refs([row["artifact_ref"]], row["evidence_refs"]) for row in earth_sweep_source_artifacts]
    )
    required_doc_refs = _collect_unique_refs(
        *[_collect_unique_refs([row["doc_ref"]], row["evidence_refs"]) for row in required_context_documents]
    )

    recommended_actions: list[dict[str, Any]] = []
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []

    for source_artifact in earth_sweep_source_artifacts:
        if source_artifact["status"] != "stale":
            continue
        open_risks.append(
            {
                "risk_id": f"risk-earth-source-{_stable_id_fragment(source_artifact['artifact_ref'])}",
                "summary": f"Earth sweep source artifact is stale: {source_artifact['artifact_ref']}",
                "reason_code": "stale_earth_sweep_source_artifact",
                "required_evidence_refs": _collect_unique_refs(
                    [source_artifact["artifact_ref"]],
                    source_artifact["evidence_refs"],
                ),
            }
        )

    for required_doc in required_context_documents:
        if required_doc["status"] != "missing":
            continue
        reason_code = {
            "mission": "missing_mission_doc",
            "scope": "missing_scope_doc",
            "peer-project": "missing_peer_project_doc",
        }[required_doc["doc_kind"]]
        summary = (
            f"Required peer-project document is missing for '{required_doc['project_id']}': {required_doc['doc_ref']}"
            if required_doc["doc_kind"] == "peer-project"
            else f"Required {required_doc['doc_kind']} document is missing: {required_doc['doc_ref']}"
        )
        open_risks.append(
            {
                "risk_id": f"risk-context-doc-{_stable_id_fragment(required_doc['doc_kind'], required_doc['project_id'], required_doc['doc_ref'])}",
                "summary": summary,
                "reason_code": reason_code,
                "required_evidence_refs": _collect_unique_refs(
                    [required_doc["doc_ref"]],
                    required_doc["evidence_refs"],
                ),
            }
        )

    for candidate in candidate_recommendations:
        action = {
            "action_id": candidate["action_id"],
            "summary": candidate["summary"],
            "rationale": candidate["rationale"],
            "action_scope": candidate["action_scope"],
            "next_step": candidate["next_step"],
            "evidence_refs": candidate["evidence_refs"],
        }
        if candidate["requires_earth_evidence"]:
            if earth_sweep_evidence_refs:
                obligation_project_id = candidate["project_id"] or (
                    cross_project_context[0]["project_id"] if cross_project_context else "earth"
                )
                cross_project_obligations.append(
                    {
                        "obligation_id": f"obligation-{candidate['action_id']}",
                        "project_id": obligation_project_id,
                        "summary": candidate["summary"],
                        "evidence_refs": _collect_unique_refs(candidate["evidence_refs"], earth_sweep_evidence_refs),
                    }
                )
                recommended_actions.append(action)
            else:
                open_risks.append(
                    {
                        "risk_id": f"risk-{candidate['action_id']}",
                        "summary": candidate["summary"],
                        "reason_code": "missing_earth_sweep_evidence_refs",
                        "required_evidence_refs": candidate["evidence_refs"],
                    }
                )
        else:
            recommended_actions.append(action)

    recommendation_refs = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        cross_project_refs,
        source_artifact_refs,
        required_doc_refs,
        *[row["evidence_refs"] for row in recommended_actions],
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    decision = _recommendation_decision(recommended_actions=recommended_actions, open_risks=open_risks)

    context_inputs: dict[str, Any] = {
        "target_project": {
            "project_root": target_project_root,
            "evidence_refs": target_project_evidence_refs,
        },
        "earth_sweep": {
            "earth_root": earth_root,
            "evidence_refs": earth_sweep_evidence_refs,
        },
        "cross_project_context": cross_project_context,
        "candidate_recommendations": candidate_recommendations,
    }
    if earth_sweep_source_artifacts:
        context_inputs["earth_sweep_source_artifacts"] = earth_sweep_source_artifacts
    if required_context_documents:
        context_inputs["required_context_documents"] = required_context_documents

    context_usage: dict[str, Any] = {
        "target_project_context_used": bool(target_project_evidence_refs),
        "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
        "cross_project_context_used": bool(cross_project_context),
        "target_project_refs_used": target_project_evidence_refs,
        "earth_sweep_refs_used": earth_sweep_evidence_refs,
        "cross_project_refs_used": cross_project_refs,
        "cross_project_projects_considered": sorted({row["project_id"] for row in cross_project_context}),
        "evidence_refs_used": recommendation_refs,
    }
    if earth_sweep_source_artifacts:
        context_usage["earth_sweep_source_artifacts_used"] = True
        context_usage["earth_sweep_source_artifact_refs_used"] = source_artifact_refs
    if required_context_documents:
        context_usage["required_context_documents_used"] = True
        context_usage["required_context_document_refs_used"] = required_doc_refs

    return {
        "strategy": "llm-first-broad-sweep",
        "reasoning_mode": EXECUTION_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": context_inputs,
        "context_usage": context_usage,
        "recommendation": {
            "decision": decision,
            "rationale": _recommendation_rationale(decision=decision),
            "confidence": _recommendation_confidence(evidence_refs=recommendation_refs, open_risks=open_risks),
            "evidence_refs": recommendation_refs,
            "recommended_actions": recommended_actions,
            "cross_project_obligations": cross_project_obligations,
            "open_risks": open_risks,
        },
    }


def build_req_001_runtime_entrypoint(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    target_project_evidence_refs: list[str] | None = None,
    earth_sweep_evidence_refs: list[str] | None = None,
    cross_project_context: list[Mapping[str, Any]] | None = None,
    candidate_recommendations: list[Mapping[str, Any]] | None = None,
    earth_sweep_source_artifacts: list[Mapping[str, Any]] | None = None,
    required_context_documents: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the REQ-001 runtime entrypoint payload."""
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_nonempty_text(revision_identity, field_name="revision_identity")
    normalized_target_refs = _normalize_string_list(
        target_project_evidence_refs,
        field_name="target_project_evidence_refs",
    )
    normalized_earth_refs = _normalize_string_list(
        earth_sweep_evidence_refs,
        field_name="earth_sweep_evidence_refs",
    )
    normalized_cross_context = _normalize_cross_project_context(cross_project_context)
    normalized_candidates = _normalize_candidate_recommendations(candidate_recommendations)
    normalized_earth_source_artifacts = _normalize_earth_sweep_source_artifacts(earth_sweep_source_artifacts)
    normalized_required_documents = _normalize_required_context_documents(required_context_documents)

    canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    digest = _canonical_input_digest(canonical_input)
    canonical_processing_input = _canonical_processing_input(
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
    )
    processing_digest = _canonical_input_digest(canonical_processing_input)
    processing_behavior = _build_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "requirement_id": REQUIREMENT_ID,
        "strategy_runtime_entrypoint": {
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
        },
        "processing_behavior": processing_behavior,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": digest,
            "reproducible_call_id": f"req001-{digest[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_digest,
            "processing_call_id": f"req001-processing-{processing_digest[:16]}",
            "canonical_processing_input": canonical_processing_input,
        },
    }


def validate_req_001_runtime_entrypoint(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-001 payload shape and deterministic call metadata."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    top_keys = set(payload.keys())
    required_top = {"schema_version", "requirement_id", "strategy_runtime_entrypoint", "processing_behavior", "call_metadata"}
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQUIREMENT_ID}")

    entrypoint = payload.get("strategy_runtime_entrypoint")
    if not isinstance(entrypoint, Mapping):
        errors.append("strategy_runtime_entrypoint must be an object")
        return errors

    required_entrypoint = {
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
    }
    entrypoint_keys = set(entrypoint.keys())
    missing_entrypoint = sorted(required_entrypoint - entrypoint_keys)
    if missing_entrypoint:
        errors.append(f"strategy_runtime_entrypoint missing keys: {missing_entrypoint}")
    unexpected_entrypoint = sorted(entrypoint_keys - required_entrypoint)
    if unexpected_entrypoint:
        errors.append(f"strategy_runtime_entrypoint has unexpected keys: {unexpected_entrypoint}")

    if entrypoint.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"runtime_mode must be {RUNTIME_MODE}")
    if entrypoint.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"execution_mode must be {EXECUTION_MODE}")

    for root_field in ("target_project_root", "earth_root", "output_root"):
        value = entrypoint.get(root_field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{root_field} must be non-empty string")
        elif not value.startswith("/"):
            errors.append(f"{root_field} must be absolute path")

    revision_identity = entrypoint.get("revision_identity")
    if not isinstance(revision_identity, str) or not revision_identity.strip():
        errors.append("revision_identity must be non-empty string")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        return errors

    required_processing_behavior = {
        "strategy",
        "reasoning_mode",
        "heuristic_summarization_only",
        "context_inputs",
        "context_usage",
        "recommendation",
    }
    processing_keys = set(processing_behavior.keys())
    missing_processing = sorted(required_processing_behavior - processing_keys)
    if missing_processing:
        errors.append(f"processing_behavior missing keys: {missing_processing}")
    unexpected_processing = sorted(processing_keys - required_processing_behavior)
    if unexpected_processing:
        errors.append(f"processing_behavior has unexpected keys: {unexpected_processing}")

    if processing_behavior.get("strategy") != "llm-first-broad-sweep":
        errors.append("processing_behavior.strategy must be llm-first-broad-sweep")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        target_project_context = context_inputs.get("target_project")
        if not isinstance(target_project_context, Mapping):
            errors.append("processing_behavior.context_inputs.target_project must be an object")
        else:
            if target_project_context.get("project_root") != entrypoint.get("target_project_root"):
                errors.append("target project root mismatch between entrypoint and processing context")
            target_refs = target_project_context.get("evidence_refs")
            if not isinstance(target_refs, list):
                errors.append("processing_behavior.context_inputs.target_project.evidence_refs must be a list")

        earth_context = context_inputs.get("earth_sweep")
        if not isinstance(earth_context, Mapping):
            errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
        else:
            if earth_context.get("earth_root") != entrypoint.get("earth_root"):
                errors.append("earth root mismatch between entrypoint and processing context")
            earth_refs = earth_context.get("evidence_refs")
            if not isinstance(earth_refs, list):
                errors.append("processing_behavior.context_inputs.earth_sweep.evidence_refs must be a list")

        cross_context = context_inputs.get("cross_project_context")
        if not isinstance(cross_context, list):
            errors.append("processing_behavior.context_inputs.cross_project_context must be a list")
        else:
            for index, row in enumerate(cross_context):
                if not isinstance(row, Mapping):
                    errors.append(f"processing_behavior.context_inputs.cross_project_context[{index}] must be an object")
                    continue
                for req_field in ("project_id", "project_root", "evidence_refs", "context_note"):
                    if req_field not in row:
                        errors.append(
                            f"processing_behavior.context_inputs.cross_project_context[{index}] missing {req_field}"
                        )

        candidates = context_inputs.get("candidate_recommendations")
        if not isinstance(candidates, list):
            errors.append("processing_behavior.context_inputs.candidate_recommendations must be a list")
        else:
            for index, row in enumerate(candidates):
                if not isinstance(row, Mapping):
                    errors.append(
                        f"processing_behavior.context_inputs.candidate_recommendations[{index}] must be an object"
                    )
                    continue
                for req_field in (
                    "action_id",
                    "summary",
                    "rationale",
                    "action_scope",
                    "requires_earth_evidence",
                    "project_id",
                    "evidence_refs",
                    "next_step",
                ):
                    if req_field not in row:
                        errors.append(
                            f"processing_behavior.context_inputs.candidate_recommendations[{index}] missing {req_field}"
                        )

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        for required_field in (
            "target_project_context_used",
            "earth_sweep_context_used",
            "cross_project_context_used",
            "target_project_refs_used",
            "earth_sweep_refs_used",
            "cross_project_refs_used",
            "cross_project_projects_considered",
            "evidence_refs_used",
        ):
            if required_field not in context_usage:
                errors.append(f"processing_behavior.context_usage missing {required_field}")

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        for required_field in (
            "decision",
            "rationale",
            "confidence",
            "evidence_refs",
            "recommended_actions",
            "cross_project_obligations",
            "open_risks",
        ):
            if required_field not in recommendation:
                errors.append(f"processing_behavior.recommendation missing {required_field}")

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors

    required_metadata = {
        "reproducibility",
        "canonical_input_sha256",
        "reproducible_call_id",
        "canonical_input",
        "processing_input_sha256",
        "processing_call_id",
        "canonical_processing_input",
    }
    metadata_keys = set(metadata.keys())
    missing_metadata = sorted(required_metadata - metadata_keys)
    if missing_metadata:
        errors.append(f"call_metadata missing keys: {missing_metadata}")
    unexpected_metadata = sorted(metadata_keys - required_metadata)
    if unexpected_metadata:
        errors.append(f"call_metadata has unexpected keys: {unexpected_metadata}")

    if metadata.get("reproducibility") != "deterministic-input-fingerprint":
        errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")

    canonical_input = metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
        return errors

    expected_canonical_input = _canonical_call_input(
        target_project_root=str(entrypoint.get("target_project_root", "")),
        earth_root=str(entrypoint.get("earth_root", "")),
        output_root=str(entrypoint.get("output_root", "")),
        revision_identity=str(entrypoint.get("revision_identity", "")),
    )
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")

    expected_digest = _canonical_input_digest(expected_canonical_input)
    expected_call_id = f"req001-{expected_digest[:16]}"
    if metadata.get("canonical_input_sha256") != expected_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != expected_call_id:
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    expected_canonical_processing_input = _canonical_processing_input(
        target_project_evidence_refs=list(
            processing_behavior.get("context_inputs", {})
            .get("target_project", {})
            .get("evidence_refs", [])
        )
        if isinstance(processing_behavior.get("context_inputs", {}), Mapping)
        else [],
        earth_sweep_evidence_refs=list(
            processing_behavior.get("context_inputs", {})
            .get("earth_sweep", {})
            .get("evidence_refs", [])
        )
        if isinstance(processing_behavior.get("context_inputs", {}), Mapping)
        else [],
        cross_project_context=list(
            processing_behavior.get("context_inputs", {})
            .get("cross_project_context", [])
        )
        if isinstance(processing_behavior.get("context_inputs", {}), Mapping)
        else [],
        candidate_recommendations=list(
            processing_behavior.get("context_inputs", {})
            .get("candidate_recommendations", [])
        )
        if isinstance(processing_behavior.get("context_inputs", {}), Mapping)
        else [],
        earth_sweep_source_artifacts=list(
            processing_behavior.get("context_inputs", {})
            .get("earth_sweep_source_artifacts", [])
        )
        if isinstance(processing_behavior.get("context_inputs", {}), Mapping)
        else [],
        required_context_documents=list(
            processing_behavior.get("context_inputs", {})
            .get("required_context_documents", [])
        )
        if isinstance(processing_behavior.get("context_inputs", {}), Mapping)
        else [],
    )
    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors
    if dict(canonical_processing_input) != expected_canonical_processing_input:
        errors.append("call_metadata.canonical_processing_input must mirror normalized processing input")

    expected_processing_digest = _canonical_input_digest(expected_canonical_processing_input)
    expected_processing_call_id = f"req001-processing-{expected_processing_digest[:16]}"
    if metadata.get("processing_input_sha256") != expected_processing_digest:
        errors.append("call_metadata.processing_input_sha256 does not match processing input")
    if metadata.get("processing_call_id") != expected_processing_call_id:
        errors.append("call_metadata.processing_call_id does not match processing digest")

    return errors


def _write_payload(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit REQ-001 LLM-first strategy runtime entrypoint payload.")
    parser.add_argument("--target-project-root", required=True)
    parser.add_argument("--earth-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--revision-identity", required=True)
    parser.add_argument(
        "--context-input-path",
        default=None,
        help="Optional JSON file containing context sweep inputs for deterministic processing behavior.",
    )
    parser.add_argument(
        "--output-path",
        default="-",
        help='Output path for payload JSON. Use "-" for stdout (default).',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    context_input: dict[str, Any] = {}
    if args.context_input_path:
        try:
            context_input = json.loads(Path(args.context_input_path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"validation_error: context input path not found: {args.context_input_path}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as exc:
            print(f"validation_error: invalid context input json: {exc}", file=sys.stderr)
            return 2
        if not isinstance(context_input, dict):
            print("validation_error: context input JSON must be an object", file=sys.stderr)
            return 2

    payload = build_req_001_runtime_entrypoint(
        target_project_root=args.target_project_root,
        earth_root=args.earth_root,
        output_root=args.output_root,
        revision_identity=args.revision_identity,
        target_project_evidence_refs=context_input.get("target_project_evidence_refs"),
        earth_sweep_evidence_refs=context_input.get("earth_sweep_evidence_refs"),
        cross_project_context=context_input.get("cross_project_context"),
        candidate_recommendations=context_input.get("candidate_recommendations"),
        earth_sweep_source_artifacts=context_input.get("earth_sweep_source_artifacts"),
        required_context_documents=context_input.get("required_context_documents"),
    )
    errors = validate_req_001_runtime_entrypoint(payload)
    if errors:
        for error in errors:
            print(f"validation_error: {error}", file=sys.stderr)
        return 2

    if args.output_path == "-":
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        _write_payload(Path(args.output_path), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
