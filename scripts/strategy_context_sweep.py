#!/usr/bin/env python3
"""REQ-001 and REQ-009 contract surfaces for strategy context sweep processing."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.strategy_context_workers import w02 as _worker_w02
    from scripts.strategy_context_workers import w03 as _worker_w03
    from scripts.strategy_context_workers import w04 as _worker_w04
    from scripts.strategy_context_workers import w05 as _worker_w05
    from scripts.strategy_context_workers import w06 as _worker_w06
    from scripts.strategy_context_workers import w07 as _worker_w07
    from scripts.strategy_context_workers import w08 as _worker_w08
except ModuleNotFoundError:
    _repo_root = Path(__file__).resolve().parents[1]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))
    from scripts.strategy_context_workers import w02 as _worker_w02
    from scripts.strategy_context_workers import w03 as _worker_w03
    from scripts.strategy_context_workers import w04 as _worker_w04
    from scripts.strategy_context_workers import w05 as _worker_w05
    from scripts.strategy_context_workers import w06 as _worker_w06
    from scripts.strategy_context_workers import w07 as _worker_w07
    from scripts.strategy_context_workers import w08 as _worker_w08

SCHEMA_VERSION = "req-001.llm-first-strategy-runtime-entrypoint.v1"
REQUIREMENT_ID = "REQ-001"
RUNTIME_MODE = "llm-first"
EXECUTION_MODE = "long-thinking"
REQ_009_SCHEMA_VERSION = "req-009.prior-strategy-revision-ingestion.v1"
REQ_009_REQUIREMENT_ID = "REQ-009"
REQ_013_SCHEMA_VERSION = "req-013.capability-catalog-extraction.v1"
REQ_013_REQUIREMENT_ID = "REQ-013"


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


def _normalize_capability_status(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "missing"
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    status = raw_value.strip().lower()
    if status not in {"provided", "missing"}:
        raise ValueError(f"{field_name} must be either 'provided' or 'missing'")
    return status


def _normalize_capability_catalog_entries(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("capability_catalog_entries must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"capability_catalog_entries[{index}] must be an object")

        project_id = _require_nonempty_text(
            item.get("project_id"),
            field_name=f"capability_catalog_entries[{index}].project_id",
        )
        project_root = _normalize_root(
            item.get("project_root"),
            field_name=f"capability_catalog_entries[{index}].project_root",
        )
        capability_id = _require_nonempty_text(
            item.get("capability_id"),
            field_name=f"capability_catalog_entries[{index}].capability_id",
        )
        capability_summary = _require_nonempty_text(
            item.get("capability_summary")
            if item.get("capability_summary") is not None
            else capability_id,
            field_name=f"capability_catalog_entries[{index}].capability_summary",
        )
        status = _normalize_capability_status(
            item.get("status"),
            field_name=f"capability_catalog_entries[{index}].status",
        )
        source_version = _require_nonempty_text(
            item.get("source_version"),
            field_name=f"capability_catalog_entries[{index}].source_version",
        )
        source_artifact_ref = _require_nonempty_text(
            item.get("source_artifact_ref"),
            field_name=f"capability_catalog_entries[{index}].source_artifact_ref",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"capability_catalog_entries[{index}].evidence_refs",
        )

        normalized.append(
            {
                "project_id": project_id,
                "project_root": project_root,
                "capability_id": capability_id,
                "capability_summary": capability_summary,
                "status": status,
                "source_version": source_version,
                "source_artifact_ref": source_artifact_ref,
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(
        key=lambda row: (
            row["project_id"],
            row["capability_id"],
            row["status"],
            row["source_version"],
            row["source_artifact_ref"],
        )
    )
    return normalized


def _capability_entry_refs(entry: Mapping[str, Any]) -> list[str]:
    return _collect_unique_refs([str(entry["source_artifact_ref"])], list(entry["evidence_refs"]))


def _build_capability_catalog(entries: list[dict[str, Any]]) -> dict[str, Any]:
    provided = [row for row in entries if row["status"] == "provided"]
    missing = [row for row in entries if row["status"] == "missing"]
    catalog_refs = _collect_unique_refs(*[_capability_entry_refs(row) for row in entries])
    return {
        "catalog_strategy": "project-capability-catalog",
        "projects_considered": sorted({row["project_id"] for row in entries}),
        "entries": entries,
        "provided_capability_ids": sorted({row["capability_id"] for row in provided}),
        "missing_capability_ids": sorted({row["capability_id"] for row in missing}),
        "source_versions": sorted({row["source_version"] for row in entries}),
        "evidence_refs": catalog_refs,
    }


def _canonical_req_013_processing_input(
    *,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
    capability_catalog_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical = _canonical_processing_input(
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        candidate_recommendations=candidate_recommendations,
        earth_sweep_source_artifacts=earth_sweep_source_artifacts,
        required_context_documents=required_context_documents,
    )
    if capability_catalog_entries:
        canonical["capability_catalog_entries"] = capability_catalog_entries
    return canonical


def _build_req_013_processing_behavior(
    *,
    target_project_root: str,
    earth_root: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
    capability_catalog_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    base_behavior = _build_processing_behavior(
        target_project_root=target_project_root,
        earth_root=earth_root,
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        candidate_recommendations=candidate_recommendations,
        earth_sweep_source_artifacts=earth_sweep_source_artifacts,
        required_context_documents=required_context_documents,
    )
    capability_catalog = _build_capability_catalog(capability_catalog_entries)
    provided_entries = [row for row in capability_catalog_entries if row["status"] == "provided"]
    provided_refs_by_capability: dict[str, list[str]] = {}
    for row in provided_entries:
        provided_refs_by_capability[row["capability_id"]] = _collect_unique_refs(
            provided_refs_by_capability.get(row["capability_id"], []),
            _capability_entry_refs(row),
        )

    base_recommendation = dict(base_behavior["recommendation"])
    base_open_risks = list(base_recommendation["open_risks"])
    base_recommended_actions = list(base_recommendation["recommended_actions"])
    base_obligations = list(base_recommendation["cross_project_obligations"])

    recommended_actions: list[dict[str, Any]] = []
    suppressed_actions: list[dict[str, Any]] = []
    for action in base_recommended_actions:
        action_id = action["action_id"]
        if action_id in provided_refs_by_capability:
            suppressed_actions.append(
                {
                    "action_id": action_id,
                    "reason_code": "capability_already_provided",
                    "summary": f"Suppressed '{action_id}' because capability catalog marks it as already provided.",
                    "evidence_refs": provided_refs_by_capability[action_id],
                }
            )
            continue
        recommended_actions.append(action)

    suppressed_ids = {row["action_id"] for row in suppressed_actions}
    cross_project_obligations = [
        row
        for row in base_obligations
        if str(row.get("obligation_id", "")).removeprefix("obligation-") not in suppressed_ids
    ]

    catalog_refs = capability_catalog["evidence_refs"]
    recommendation_refs = _collect_unique_refs(
        base_recommendation["evidence_refs"],
        catalog_refs,
        *[row["evidence_refs"] for row in suppressed_actions],
    )
    decision = _recommendation_decision(recommended_actions=recommended_actions, open_risks=base_open_risks)
    recommendation = {
        "decision": decision,
        "rationale": _recommendation_rationale(decision=decision),
        "confidence": _recommendation_confidence(evidence_refs=recommendation_refs, open_risks=base_open_risks),
        "evidence_refs": recommendation_refs,
        "recommended_actions": recommended_actions,
        "cross_project_obligations": cross_project_obligations,
        "open_risks": base_open_risks,
        "suppressed_actions": suppressed_actions,
    }

    context_inputs = dict(base_behavior["context_inputs"])
    if capability_catalog_entries:
        context_inputs["capability_catalog_entries"] = capability_catalog_entries

    context_usage = dict(base_behavior["context_usage"])
    context_usage["capability_catalog_used"] = bool(capability_catalog_entries)
    context_usage["capability_catalog_projects_considered"] = capability_catalog["projects_considered"]
    context_usage["capability_catalog_refs_used"] = catalog_refs
    context_usage["capability_catalog_source_versions_used"] = capability_catalog["source_versions"]
    context_usage["capabilities_provided_ids"] = capability_catalog["provided_capability_ids"]
    context_usage["capabilities_missing_ids"] = capability_catalog["missing_capability_ids"]
    context_usage["suppressed_completed_action_ids"] = sorted(suppressed_ids)
    context_usage["evidence_refs_used"] = recommendation_refs

    return {
        "strategy": "capability-catalog-broad-sweep",
        "reasoning_mode": EXECUTION_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": context_inputs,
        "context_usage": context_usage,
        "capability_catalog": capability_catalog,
        "recommendation": recommendation,
    }


def build_req_013_capability_catalog_extraction(
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
    capability_catalog_entries: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
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
    normalized_capability_catalog = _normalize_capability_catalog_entries(capability_catalog_entries)

    canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    digest = _canonical_input_digest(canonical_input)
    canonical_processing_input = _canonical_req_013_processing_input(
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        capability_catalog_entries=normalized_capability_catalog,
    )
    processing_digest = _canonical_input_digest(canonical_processing_input)
    processing_behavior = _build_req_013_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        capability_catalog_entries=normalized_capability_catalog,
    )

    return {
        "schema_version": REQ_013_SCHEMA_VERSION,
        "requirement_id": REQ_013_REQUIREMENT_ID,
        "capability_catalog_extraction": {
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
            "reproducible_call_id": f"req013-{digest[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_digest,
            "processing_call_id": f"req013-processing-{processing_digest[:16]}",
            "canonical_processing_input": canonical_processing_input,
        },
    }


def validate_req_013_capability_catalog_extraction(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    top_keys = set(payload.keys())
    required_top = {
        "schema_version",
        "requirement_id",
        "capability_catalog_extraction",
        "processing_behavior",
        "call_metadata",
    }
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_013_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_013_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_013_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_013_REQUIREMENT_ID}")

    extraction = payload.get("capability_catalog_extraction")
    if not isinstance(extraction, Mapping):
        errors.append("capability_catalog_extraction must be an object")
        return errors

    required_extraction = {
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
    }
    extraction_keys = set(extraction.keys())
    missing_extraction = sorted(required_extraction - extraction_keys)
    if missing_extraction:
        errors.append(f"capability_catalog_extraction missing keys: {missing_extraction}")
    unexpected_extraction = sorted(extraction_keys - required_extraction)
    if unexpected_extraction:
        errors.append(f"capability_catalog_extraction has unexpected keys: {unexpected_extraction}")

    if extraction.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"runtime_mode must be {RUNTIME_MODE}")
    if extraction.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"execution_mode must be {EXECUTION_MODE}")

    for root_field in ("target_project_root", "earth_root", "output_root"):
        value = extraction.get(root_field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{root_field} must be non-empty string")
        elif not value.startswith("/"):
            errors.append(f"{root_field} must be absolute path")

    revision_identity = extraction.get("revision_identity")
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
        "capability_catalog",
        "recommendation",
    }
    processing_keys = set(processing_behavior.keys())
    missing_processing = sorted(required_processing_behavior - processing_keys)
    if missing_processing:
        errors.append(f"processing_behavior missing keys: {missing_processing}")
    unexpected_processing = sorted(processing_keys - required_processing_behavior)
    if unexpected_processing:
        errors.append(f"processing_behavior has unexpected keys: {unexpected_processing}")

    if processing_behavior.get("strategy") != "capability-catalog-broad-sweep":
        errors.append("processing_behavior.strategy must be capability-catalog-broad-sweep")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        return errors

    target_project_context = context_inputs.get("target_project")
    earth_context = context_inputs.get("earth_sweep")
    if not isinstance(target_project_context, Mapping):
        errors.append("processing_behavior.context_inputs.target_project must be an object")
        return errors
    if not isinstance(earth_context, Mapping):
        errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
        return errors

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
            "suppressed_actions",
        ):
            if required_field not in recommendation:
                errors.append(f"processing_behavior.recommendation missing {required_field}")

    capability_catalog = processing_behavior.get("capability_catalog")
    if not isinstance(capability_catalog, Mapping):
        errors.append("processing_behavior.capability_catalog must be an object")
    else:
        for required_field in (
            "catalog_strategy",
            "projects_considered",
            "entries",
            "provided_capability_ids",
            "missing_capability_ids",
            "source_versions",
            "evidence_refs",
        ):
            if required_field not in capability_catalog:
                errors.append(f"processing_behavior.capability_catalog missing {required_field}")

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

    try:
        normalized_target_root = _normalize_root(
            extraction.get("target_project_root"),
            field_name="capability_catalog_extraction.target_project_root",
        )
        normalized_earth_root = _normalize_root(
            extraction.get("earth_root"),
            field_name="capability_catalog_extraction.earth_root",
        )
        normalized_output_root = _normalize_root(
            extraction.get("output_root"),
            field_name="capability_catalog_extraction.output_root",
        )
        normalized_revision_identity = _require_nonempty_text(
            extraction.get("revision_identity"),
            field_name="capability_catalog_extraction.revision_identity",
        )
        normalized_target_refs = _normalize_string_list(
            target_project_context.get("evidence_refs"),
            field_name="processing_behavior.context_inputs.target_project.evidence_refs",
        )
        normalized_earth_refs = _normalize_string_list(
            earth_context.get("evidence_refs"),
            field_name="processing_behavior.context_inputs.earth_sweep.evidence_refs",
        )
        normalized_cross_context = _normalize_cross_project_context(context_inputs.get("cross_project_context"))
        normalized_candidates = _normalize_candidate_recommendations(context_inputs.get("candidate_recommendations"))
        normalized_earth_source_artifacts = _normalize_earth_sweep_source_artifacts(
            context_inputs.get("earth_sweep_source_artifacts")
        )
        normalized_required_documents = _normalize_required_context_documents(
            context_inputs.get("required_context_documents")
        )
        normalized_capability_catalog = _normalize_capability_catalog_entries(
            context_inputs.get("capability_catalog_entries")
        )
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    expected_canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized extraction anchors")

    expected_digest = _canonical_input_digest(expected_canonical_input)
    expected_call_id = f"req013-{expected_digest[:16]}"
    if metadata.get("canonical_input_sha256") != expected_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != expected_call_id:
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    expected_processing_behavior = _build_req_013_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        capability_catalog_entries=normalized_capability_catalog,
    )
    if dict(processing_behavior) != expected_processing_behavior:
        errors.append("processing_behavior must mirror deterministic capability catalog processing output")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors

    expected_canonical_processing_input = _canonical_req_013_processing_input(
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        capability_catalog_entries=normalized_capability_catalog,
    )
    if dict(canonical_processing_input) != expected_canonical_processing_input:
        errors.append("call_metadata.canonical_processing_input must mirror normalized processing input")

    expected_processing_digest = _canonical_input_digest(expected_canonical_processing_input)
    expected_processing_call_id = f"req013-processing-{expected_processing_digest[:16]}"
    if metadata.get("processing_input_sha256") != expected_processing_digest:
        errors.append("call_metadata.processing_input_sha256 does not match processing input")
    if metadata.get("processing_call_id") != expected_processing_call_id:
        errors.append("call_metadata.processing_call_id does not match processing digest")

    return errors


def _normalize_change_type(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "updated"
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    change_type = raw_value.strip().lower()
    if change_type not in {"added", "updated", "removed"}:
        raise ValueError(f"{field_name} must be one of: added, updated, removed")
    return change_type


def _normalize_prior_strategy_revisions(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("prior_strategy_revisions must be a list")

    normalized: list[dict[str, Any]] = []
    seen_revision_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"prior_strategy_revisions[{index}] must be an object")

        revision_identity = _require_nonempty_text(
            item.get("revision_identity"),
            field_name=f"prior_strategy_revisions[{index}].revision_identity",
        )
        if revision_identity in seen_revision_ids:
            raise ValueError(f"prior_strategy_revisions[{index}].revision_identity must be unique")
        seen_revision_ids.add(revision_identity)

        summary = _normalize_context_note(
            item.get("summary"),
            field_name=f"prior_strategy_revisions[{index}].summary",
        )
        recommended_action_ids = _normalize_string_list(
            item.get("recommended_action_ids"),
            field_name=f"prior_strategy_revisions[{index}].recommended_action_ids",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"prior_strategy_revisions[{index}].evidence_refs",
        )
        normalized.append(
            {
                "revision_identity": revision_identity,
                "summary": summary,
                "recommended_action_ids": recommended_action_ids,
                "evidence_refs": evidence_refs,
            }
        )

    return normalized


def _normalize_changelog_history(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("changelog_history must be a list")

    normalized: list[dict[str, Any]] = []
    seen_change_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"changelog_history[{index}] must be an object")

        change_id = _require_nonempty_text(item.get("change_id"), field_name=f"changelog_history[{index}].change_id")
        if change_id in seen_change_ids:
            raise ValueError(f"changelog_history[{index}].change_id must be unique")
        seen_change_ids.add(change_id)

        revision_identity = _require_nonempty_text(
            item.get("revision_identity"),
            field_name=f"changelog_history[{index}].revision_identity",
        )
        action_id = _normalize_context_note(item.get("action_id"), field_name=f"changelog_history[{index}].action_id")
        change_type = _normalize_change_type(
            item.get("change_type"),
            field_name=f"changelog_history[{index}].change_type",
        )
        change_summary = _require_nonempty_text(
            item.get("change_summary"),
            field_name=f"changelog_history[{index}].change_summary",
        )
        changed_at = _normalize_context_note(item.get("changed_at"), field_name=f"changelog_history[{index}].changed_at")
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"changelog_history[{index}].evidence_refs",
        )
        normalized.append(
            {
                "change_id": change_id,
                "revision_identity": revision_identity,
                "action_id": action_id,
                "change_type": change_type,
                "change_summary": change_summary,
                "changed_at": changed_at,
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(
        key=lambda row: (
            row["revision_identity"],
            row["changed_at"],
            row["change_id"],
            row["action_id"],
            row["change_type"],
        )
    )
    return normalized


def _canonical_req_009_input(
    *,
    current_revision_identity: str,
    prior_strategy_revisions: list[dict[str, Any]],
    changelog_history: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "current_revision_identity": current_revision_identity,
        "prior_strategy_revisions": prior_strategy_revisions,
        "changelog_history": changelog_history,
    }


def _canonical_req_009_processing_input(
    *,
    current_revision_identity: str,
    prior_strategy_revisions: list[dict[str, Any]],
    changelog_history: list[dict[str, Any]],
    analysis: dict[str, Any],
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical = _canonical_processing_input(
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        candidate_recommendations=candidate_recommendations,
        earth_sweep_source_artifacts=earth_sweep_source_artifacts,
        required_context_documents=required_context_documents,
    )
    canonical["current_revision_identity"] = current_revision_identity
    canonical["prior_strategy_revisions"] = prior_strategy_revisions
    canonical["changelog_history"] = changelog_history
    canonical["analysis"] = analysis
    return canonical


def _build_req_009_analysis(
    *,
    prior_strategy_revisions: list[dict[str, Any]],
    changelog_history: list[dict[str, Any]],
) -> dict[str, Any]:
    revision_ids = [row["revision_identity"] for row in prior_strategy_revisions]
    latest_prior_revision_id = revision_ids[-1] if revision_ids else ""

    latest_actions: set[str] = set()
    historical_actions: set[str] = set()
    for index, row in enumerate(prior_strategy_revisions):
        action_ids = set(row["recommended_action_ids"])
        if index == len(prior_strategy_revisions) - 1:
            latest_actions = action_ids
        else:
            historical_actions.update(action_ids)

    all_prior_action_ids = sorted(historical_actions | latest_actions)
    continuing_action_ids = sorted(latest_actions & historical_actions)
    new_action_ids = sorted(latest_actions - historical_actions)
    retired_action_ids = sorted(historical_actions - latest_actions)

    changelog_change_ids = [row["change_id"] for row in changelog_history]
    changelog_action_ids = sorted({row["action_id"] for row in changelog_history if row["action_id"]})
    changelog_added_action_ids = sorted(
        {row["action_id"] for row in changelog_history if row["change_type"] == "added" and row["action_id"]}
    )
    changelog_updated_action_ids = sorted(
        {row["action_id"] for row in changelog_history if row["change_type"] == "updated" and row["action_id"]}
    )
    changelog_removed_action_ids = sorted(
        {row["action_id"] for row in changelog_history if row["change_type"] == "removed" and row["action_id"]}
    )
    changelog_only_action_ids = sorted(set(changelog_action_ids) - set(all_prior_action_ids))

    drift_action_ids = sorted(set(new_action_ids) | set(retired_action_ids) | set(changelog_action_ids))
    recommendation_anchor_action_ids = sorted(
        set(continuing_action_ids) | set(new_action_ids) | set(retired_action_ids) | set(changelog_action_ids)
    )

    return {
        "continuity": {
            "latest_prior_revision_id": latest_prior_revision_id,
            "ingested_revision_ids": revision_ids,
            "continuing_action_ids": continuing_action_ids,
            "retired_action_ids": retired_action_ids,
        },
        "drift": {
            "new_action_ids": new_action_ids,
            "drift_action_ids": drift_action_ids,
            "changelog_change_ids": changelog_change_ids,
            "changelog_action_ids": changelog_action_ids,
            "changelog_added_action_ids": changelog_added_action_ids,
            "changelog_updated_action_ids": changelog_updated_action_ids,
            "changelog_removed_action_ids": changelog_removed_action_ids,
            "changelog_only_action_ids": changelog_only_action_ids,
        },
        "composition_context": {
            "prior_revision_count": len(prior_strategy_revisions),
            "changelog_entry_count": len(changelog_history),
            "recommendation_anchor_action_ids": recommendation_anchor_action_ids,
        },
    }


def _req_009_action_state(*, action_id: str, analysis: Mapping[str, Any]) -> str:
    continuity = analysis.get("continuity")
    drift = analysis.get("drift")
    if not isinstance(continuity, Mapping) or not isinstance(drift, Mapping):
        return "untracked"

    continuing_action_ids = set(continuity.get("continuing_action_ids", []))
    retired_action_ids = set(continuity.get("retired_action_ids", []))
    new_action_ids = set(drift.get("new_action_ids", []))
    changelog_only_action_ids = set(drift.get("changelog_only_action_ids", []))

    if action_id in continuing_action_ids:
        return "continuing"
    if action_id in new_action_ids:
        return "new"
    if action_id in retired_action_ids:
        return "retired"
    if action_id in changelog_only_action_ids:
        return "changelog-only"
    return "untracked"


def _build_req_009_action_evidence_maps(
    *,
    prior_strategy_revisions: list[dict[str, Any]],
    changelog_history: list[dict[str, Any]],
) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str], list[str]]:
    prior_refs_by_action: dict[str, set[str]] = {}
    for revision in prior_strategy_revisions:
        revision_refs = revision["evidence_refs"]
        for action_id in revision["recommended_action_ids"]:
            bucket = prior_refs_by_action.setdefault(action_id, set())
            bucket.update(revision_refs)

    changelog_refs_by_action: dict[str, set[str]] = {}
    for change in changelog_history:
        action_id = change["action_id"]
        if not action_id:
            continue
        bucket = changelog_refs_by_action.setdefault(action_id, set())
        bucket.update(change["evidence_refs"])

    normalized_prior_refs_by_action = {
        action_id: sorted(refs) for action_id, refs in prior_refs_by_action.items()
    }
    normalized_changelog_refs_by_action = {
        action_id: sorted(refs) for action_id, refs in changelog_refs_by_action.items()
    }

    prior_evidence_refs = _collect_unique_refs(*[row["evidence_refs"] for row in prior_strategy_revisions])
    changelog_evidence_refs = _collect_unique_refs(*[row["evidence_refs"] for row in changelog_history])
    return (
        normalized_prior_refs_by_action,
        normalized_changelog_refs_by_action,
        prior_evidence_refs,
        changelog_evidence_refs,
    )


def _compose_req_009_candidate_recommendations(
    *,
    analysis: Mapping[str, Any],
    candidate_recommendations: list[dict[str, Any]],
    prior_strategy_revisions: list[dict[str, Any]],
    changelog_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prior_refs_by_action, changelog_refs_by_action, _, _ = _build_req_009_action_evidence_maps(
        prior_strategy_revisions=prior_strategy_revisions,
        changelog_history=changelog_history,
    )

    seed_candidates = list(candidate_recommendations)
    if not seed_candidates:
        anchor_action_ids = []
        composition_context = analysis.get("composition_context")
        if isinstance(composition_context, Mapping):
            anchor_action_ids = list(composition_context.get("recommendation_anchor_action_ids", []))
        for action_id in anchor_action_ids:
            state = _req_009_action_state(action_id=action_id, analysis=analysis)
            seed_candidates.append(
                {
                    "action_id": action_id,
                    "summary": f"Carry forward action '{action_id}' with explicit continuity/drift checks.",
                    "rationale": (
                        "Composed from ingested prior strategy revisions and changelog history "
                        f"(state={state})."
                    ),
                    "action_scope": "local",
                    "requires_earth_evidence": False,
                    "project_id": "",
                    "evidence_refs": _collect_unique_refs(
                        prior_refs_by_action.get(action_id, []),
                        changelog_refs_by_action.get(action_id, []),
                    ),
                    "next_step": f"Validate '{action_id}' against current revision objectives.",
                }
            )

    composed: list[dict[str, Any]] = []
    for candidate in seed_candidates:
        action_id = candidate["action_id"]
        composed.append(
            {
                "action_id": action_id,
                "summary": candidate["summary"],
                "rationale": candidate["rationale"],
                "action_scope": candidate["action_scope"],
                "requires_earth_evidence": candidate["requires_earth_evidence"],
                "project_id": candidate["project_id"],
                "evidence_refs": _collect_unique_refs(
                    candidate["evidence_refs"],
                    prior_refs_by_action.get(action_id, []),
                    changelog_refs_by_action.get(action_id, []),
                ),
                "next_step": candidate["next_step"],
            }
        )

    composed.sort(key=lambda row: row["action_id"])
    return composed


def _build_req_009_processing_behavior(
    *,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
    prior_strategy_revisions: list[dict[str, Any]],
    changelog_history: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    composed_candidates = _compose_req_009_candidate_recommendations(
        analysis=analysis,
        candidate_recommendations=candidate_recommendations,
        prior_strategy_revisions=prior_strategy_revisions,
        changelog_history=changelog_history,
    )
    _, _, prior_revision_evidence_refs, changelog_evidence_refs = _build_req_009_action_evidence_maps(
        prior_strategy_revisions=prior_strategy_revisions,
        changelog_history=changelog_history,
    )
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

    for candidate in composed_candidates:
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
        prior_revision_evidence_refs,
        changelog_evidence_refs,
        *[row["evidence_refs"] for row in recommended_actions],
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    decision = _recommendation_decision(recommended_actions=recommended_actions, open_risks=open_risks)

    context_inputs: dict[str, Any] = {
        "target_project": {
            "evidence_refs": target_project_evidence_refs,
        },
        "earth_sweep": {
            "evidence_refs": earth_sweep_evidence_refs,
        },
        "cross_project_context": cross_project_context,
        "candidate_recommendations": composed_candidates,
        "prior_strategy_revisions": prior_strategy_revisions,
        "changelog_history": changelog_history,
        "analysis": analysis,
    }
    if earth_sweep_source_artifacts:
        context_inputs["earth_sweep_source_artifacts"] = earth_sweep_source_artifacts
    if required_context_documents:
        context_inputs["required_context_documents"] = required_context_documents

    context_usage: dict[str, Any] = {
        "target_project_context_used": bool(target_project_evidence_refs),
        "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
        "cross_project_context_used": bool(cross_project_context),
        "prior_strategy_revisions_used": bool(prior_strategy_revisions),
        "changelog_history_used": bool(changelog_history),
        "target_project_refs_used": target_project_evidence_refs,
        "earth_sweep_refs_used": earth_sweep_evidence_refs,
        "cross_project_refs_used": cross_project_refs,
        "prior_revision_refs_used": prior_revision_evidence_refs,
        "changelog_refs_used": changelog_evidence_refs,
        "cross_project_projects_considered": sorted({row["project_id"] for row in cross_project_context}),
        "prior_revision_ids_used": [row["revision_identity"] for row in prior_strategy_revisions],
        "changelog_change_ids_used": [row["change_id"] for row in changelog_history],
        "continuity_action_ids_used": list(analysis["continuity"]["continuing_action_ids"]),
        "drift_action_ids_used": list(analysis["drift"]["drift_action_ids"]),
        "evidence_refs_used": recommendation_refs,
    }
    if earth_sweep_source_artifacts:
        context_usage["earth_sweep_source_artifacts_used"] = True
        context_usage["earth_sweep_source_artifact_refs_used"] = source_artifact_refs
    if required_context_documents:
        context_usage["required_context_documents_used"] = True
        context_usage["required_context_document_refs_used"] = required_doc_refs

    return {
        "strategy": "prior-revision-aware-broad-sweep",
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


def build_req_009_prior_strategy_revision_ingestion(
    *,
    current_revision_identity: str,
    prior_strategy_revisions: list[Mapping[str, Any]] | None = None,
    changelog_history: list[Mapping[str, Any]] | None = None,
    target_project_evidence_refs: list[str] | None = None,
    earth_sweep_evidence_refs: list[str] | None = None,
    cross_project_context: list[Mapping[str, Any]] | None = None,
    candidate_recommendations: list[Mapping[str, Any]] | None = None,
    earth_sweep_source_artifacts: list[Mapping[str, Any]] | None = None,
    required_context_documents: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the REQ-009 prior strategy revision ingestion contract payload."""
    normalized_current_revision_identity = _require_nonempty_text(
        current_revision_identity,
        field_name="current_revision_identity",
    )
    normalized_prior_strategy_revisions = _normalize_prior_strategy_revisions(prior_strategy_revisions)
    normalized_changelog_history = _normalize_changelog_history(changelog_history)
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

    canonical_input = _canonical_req_009_input(
        current_revision_identity=normalized_current_revision_identity,
        prior_strategy_revisions=normalized_prior_strategy_revisions,
        changelog_history=normalized_changelog_history,
    )
    digest = _canonical_input_digest(canonical_input)
    analysis = _build_req_009_analysis(
        prior_strategy_revisions=normalized_prior_strategy_revisions,
        changelog_history=normalized_changelog_history,
    )
    processing_behavior = _build_req_009_processing_behavior(
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        prior_strategy_revisions=normalized_prior_strategy_revisions,
        changelog_history=normalized_changelog_history,
        analysis=analysis,
    )
    canonical_processing_input = _canonical_req_009_processing_input(
        current_revision_identity=normalized_current_revision_identity,
        prior_strategy_revisions=normalized_prior_strategy_revisions,
        changelog_history=normalized_changelog_history,
        analysis=analysis,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=list(processing_behavior["context_inputs"]["candidate_recommendations"]),
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
    )
    processing_digest = _canonical_input_digest(canonical_processing_input)

    return {
        "schema_version": REQ_009_SCHEMA_VERSION,
        "requirement_id": REQ_009_REQUIREMENT_ID,
        "prior_strategy_revision_ingestion": {
            "current_revision_identity": normalized_current_revision_identity,
            "prior_strategy_revisions": normalized_prior_strategy_revisions,
            "changelog_history": normalized_changelog_history,
            "analysis": analysis,
        },
        "processing_behavior": processing_behavior,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": digest,
            "reproducible_call_id": f"req009-{digest[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_digest,
            "processing_call_id": f"req009-processing-{processing_digest[:16]}",
            "canonical_processing_input": canonical_processing_input,
        },
    }


def validate_req_009_prior_strategy_revision_ingestion(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-009 payload shape and deterministic call metadata."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    top_keys = set(payload.keys())
    required_top = {
        "schema_version",
        "requirement_id",
        "prior_strategy_revision_ingestion",
        "processing_behavior",
        "call_metadata",
    }
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_009_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_009_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_009_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_009_REQUIREMENT_ID}")

    ingestion = payload.get("prior_strategy_revision_ingestion")
    if not isinstance(ingestion, Mapping):
        errors.append("prior_strategy_revision_ingestion must be an object")
        return errors

    required_ingestion = {"current_revision_identity", "prior_strategy_revisions", "changelog_history", "analysis"}
    ingestion_keys = set(ingestion.keys())
    missing_ingestion = sorted(required_ingestion - ingestion_keys)
    if missing_ingestion:
        errors.append(f"prior_strategy_revision_ingestion missing keys: {missing_ingestion}")
    unexpected_ingestion = sorted(ingestion_keys - required_ingestion)
    if unexpected_ingestion:
        errors.append(f"prior_strategy_revision_ingestion has unexpected keys: {unexpected_ingestion}")

    current_revision_identity = ingestion.get("current_revision_identity")
    if not isinstance(current_revision_identity, str) or not current_revision_identity.strip():
        errors.append("prior_strategy_revision_ingestion.current_revision_identity must be non-empty string")

    prior_strategy_revisions = ingestion.get("prior_strategy_revisions")
    if not isinstance(prior_strategy_revisions, list):
        errors.append("prior_strategy_revision_ingestion.prior_strategy_revisions must be a list")
    else:
        for index, row in enumerate(prior_strategy_revisions):
            if not isinstance(row, Mapping):
                errors.append(f"prior_strategy_revision_ingestion.prior_strategy_revisions[{index}] must be an object")
                continue
            for required_field in ("revision_identity", "summary", "recommended_action_ids", "evidence_refs"):
                if required_field not in row:
                    errors.append(
                        "prior_strategy_revision_ingestion.prior_strategy_revisions"
                        f"[{index}] missing {required_field}"
                    )

    changelog_history = ingestion.get("changelog_history")
    if not isinstance(changelog_history, list):
        errors.append("prior_strategy_revision_ingestion.changelog_history must be a list")
    else:
        for index, row in enumerate(changelog_history):
            if not isinstance(row, Mapping):
                errors.append(f"prior_strategy_revision_ingestion.changelog_history[{index}] must be an object")
                continue
            for required_field in (
                "change_id",
                "revision_identity",
                "action_id",
                "change_type",
                "change_summary",
                "changed_at",
                "evidence_refs",
            ):
                if required_field not in row:
                    errors.append(f"prior_strategy_revision_ingestion.changelog_history[{index}] missing {required_field}")

    analysis = ingestion.get("analysis")
    if not isinstance(analysis, Mapping):
        errors.append("prior_strategy_revision_ingestion.analysis must be an object")
    else:
        continuity = analysis.get("continuity")
        drift = analysis.get("drift")
        composition_context = analysis.get("composition_context")
        if not isinstance(continuity, Mapping):
            errors.append("prior_strategy_revision_ingestion.analysis.continuity must be an object")
        else:
            for required_field in (
                "latest_prior_revision_id",
                "ingested_revision_ids",
                "continuing_action_ids",
                "retired_action_ids",
            ):
                if required_field not in continuity:
                    errors.append(f"prior_strategy_revision_ingestion.analysis.continuity missing {required_field}")
        if not isinstance(drift, Mapping):
            errors.append("prior_strategy_revision_ingestion.analysis.drift must be an object")
        else:
            for required_field in (
                "new_action_ids",
                "drift_action_ids",
                "changelog_change_ids",
                "changelog_action_ids",
                "changelog_added_action_ids",
                "changelog_updated_action_ids",
                "changelog_removed_action_ids",
                "changelog_only_action_ids",
            ):
                if required_field not in drift:
                    errors.append(f"prior_strategy_revision_ingestion.analysis.drift missing {required_field}")
        if not isinstance(composition_context, Mapping):
            errors.append("prior_strategy_revision_ingestion.analysis.composition_context must be an object")
        else:
            for required_field in ("prior_revision_count", "changelog_entry_count", "recommendation_anchor_action_ids"):
                if required_field not in composition_context:
                    errors.append(
                        "prior_strategy_revision_ingestion.analysis.composition_context "
                        f"missing {required_field}"
                    )

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

    if processing_behavior.get("strategy") != "prior-revision-aware-broad-sweep":
        errors.append("processing_behavior.strategy must be prior-revision-aware-broad-sweep")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
    else:
        for required_field in (
            "target_project",
            "earth_sweep",
            "cross_project_context",
            "candidate_recommendations",
            "prior_strategy_revisions",
            "changelog_history",
            "analysis",
        ):
            if required_field not in context_inputs:
                errors.append(f"processing_behavior.context_inputs missing {required_field}")

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        for required_field in (
            "target_project_context_used",
            "earth_sweep_context_used",
            "cross_project_context_used",
            "prior_strategy_revisions_used",
            "changelog_history_used",
            "target_project_refs_used",
            "earth_sweep_refs_used",
            "cross_project_refs_used",
            "prior_revision_refs_used",
            "changelog_refs_used",
            "cross_project_projects_considered",
            "prior_revision_ids_used",
            "changelog_change_ids_used",
            "continuity_action_ids_used",
            "drift_action_ids_used",
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

    try:
        normalized_current_revision_identity = _require_nonempty_text(
            ingestion.get("current_revision_identity"),
            field_name="prior_strategy_revision_ingestion.current_revision_identity",
        )
        normalized_prior_strategy_revisions = _normalize_prior_strategy_revisions(
            list(ingestion.get("prior_strategy_revisions", []))
        )
        normalized_changelog_history = _normalize_changelog_history(list(ingestion.get("changelog_history", [])))
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    expected_analysis = _build_req_009_analysis(
        prior_strategy_revisions=normalized_prior_strategy_revisions,
        changelog_history=normalized_changelog_history,
    )
    if ingestion.get("analysis") != expected_analysis:
        errors.append("prior_strategy_revision_ingestion.analysis must mirror deterministic ingestion analysis")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        return errors

    target_project_context = context_inputs.get("target_project")
    earth_context = context_inputs.get("earth_sweep")
    if not isinstance(target_project_context, Mapping):
        errors.append("processing_behavior.context_inputs.target_project must be an object")
        return errors
    if not isinstance(earth_context, Mapping):
        errors.append("processing_behavior.context_inputs.earth_sweep must be an object")
        return errors

    try:
        normalized_target_refs = _normalize_string_list(
            target_project_context.get("evidence_refs"),
            field_name="processing_behavior.context_inputs.target_project.evidence_refs",
        )
        normalized_earth_refs = _normalize_string_list(
            earth_context.get("evidence_refs"),
            field_name="processing_behavior.context_inputs.earth_sweep.evidence_refs",
        )
        normalized_cross_context = _normalize_cross_project_context(context_inputs.get("cross_project_context"))
        normalized_candidates = _normalize_candidate_recommendations(context_inputs.get("candidate_recommendations"))
        normalized_earth_source_artifacts = _normalize_earth_sweep_source_artifacts(
            context_inputs.get("earth_sweep_source_artifacts")
        )
        normalized_required_documents = _normalize_required_context_documents(
            context_inputs.get("required_context_documents")
        )
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    expected_canonical_input = _canonical_req_009_input(
        current_revision_identity=normalized_current_revision_identity,
        prior_strategy_revisions=normalized_prior_strategy_revisions,
        changelog_history=normalized_changelog_history,
    )
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized ingestion input")

    expected_digest = _canonical_input_digest(expected_canonical_input)
    expected_call_id = f"req009-{expected_digest[:16]}"
    if metadata.get("canonical_input_sha256") != expected_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != expected_call_id:
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    expected_processing_behavior = _build_req_009_processing_behavior(
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        prior_strategy_revisions=normalized_prior_strategy_revisions,
        changelog_history=normalized_changelog_history,
        analysis=expected_analysis,
    )
    if payload.get("processing_behavior") != expected_processing_behavior:
        errors.append("processing_behavior must mirror deterministic broad-sweep processing output")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors

    expected_canonical_processing_input = _canonical_req_009_processing_input(
        current_revision_identity=normalized_current_revision_identity,
        prior_strategy_revisions=normalized_prior_strategy_revisions,
        changelog_history=normalized_changelog_history,
        analysis=expected_analysis,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=list(expected_processing_behavior["context_inputs"]["candidate_recommendations"]),
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
    )
    if dict(canonical_processing_input) != expected_canonical_processing_input:
        errors.append("call_metadata.canonical_processing_input must mirror normalized processing input")

    expected_processing_digest = _canonical_input_digest(expected_canonical_processing_input)
    expected_processing_call_id = f"req009-processing-{expected_processing_digest[:16]}"
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


def _main_req001(argv: list[str] | None = None) -> int:
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


# Re-export worker-surface functions to preserve merged requirement contracts.
utc_now_iso = _worker_w08.utc_now_iso
build_earth_repository_discovery_context_bundle = _worker_w02.build_earth_repository_discovery_context_bundle
serialize_earth_repository_discovery_context_bundle = _worker_w02.serialize_earth_repository_discovery_context_bundle
build_earth_repository_discovery_manifest = _worker_w02.build_earth_repository_discovery_manifest
validate_earth_repository_discovery_manifest = _worker_w02.validate_earth_repository_discovery_manifest
build_change_detection_since_previous_strategy_revision = _worker_w02.build_change_detection_since_previous_strategy_revision
validate_change_detection_since_previous_strategy_revision = _worker_w02.validate_change_detection_since_previous_strategy_revision
extract_deficit_and_need_signals = _worker_w02.extract_deficit_and_need_signals
ingest_target_project_mission_scope = _worker_w03.ingest_target_project_mission_scope
extract_interface_contracts = _worker_w04.extract_interface_contracts
extract_interface_contracts_file = _worker_w04.extract_interface_contracts_file
ingest_peer_project_mission_and_scope = _worker_w04.ingest_peer_project_mission_and_scope
ingest_peer_project_mission_and_scope_file = _worker_w04.ingest_peer_project_mission_and_scope_file
sweep_runtime_telemetry_artifacts = _worker_w06.sweep_runtime_telemetry_artifacts
load_ground_graph_snapshot = _worker_w07.load_ground_graph_snapshot
load_json_object = _worker_w07.load_json_object
ingest_ground_graph_snapshot = _worker_w07.ingest_ground_graph_snapshot
process_ground_graph_snapshot = _worker_w07.process_ground_graph_snapshot
detect_integration_opportunities = _worker_w07.detect_integration_opportunities
serialize_integration_opportunity_context_bundle = _worker_w07.serialize_integration_opportunity_context_bundle
detect_reuse_opportunities = _worker_w07.detect_reuse_opportunities
serialize_ground_graph_context_bundle = _worker_w07.serialize_ground_graph_context_bundle
serialize_req_008_context_bundle = _worker_w08.serialize_req_008_context_bundle
build_req_008_research_packet_ingestion_and_normalization = (
    _worker_w08.build_req_008_research_packet_ingestion_and_normalization
)
validate_req_008_research_packet_ingestion_and_normalization = (
    _worker_w08.validate_req_008_research_packet_ingestion_and_normalization
)
serialize_req_015_integration_opportunity_bundle = _worker_w08.serialize_req_015_integration_opportunity_bundle
build_req_015_integration_opportunity_detection = _worker_w08.build_req_015_integration_opportunity_detection
validate_req_015_integration_opportunity_detection = _worker_w08.validate_req_015_integration_opportunity_detection
ALLOWED_RISK_LEVELS = _worker_w08.ALLOWED_RISK_LEVELS
REASON_CODE_EARTH_SWEEP_STALE_SOURCE_ARTIFACT = _worker_w08.REASON_CODE_EARTH_SWEEP_STALE_SOURCE_ARTIFACT
REASON_CODE_CONTEXT_DOC_MISSING = _worker_w08.REASON_CODE_CONTEXT_DOC_MISSING
REASON_CODE_PEER_PROJECT_DOC_MISSING = _worker_w08.REASON_CODE_PEER_PROJECT_DOC_MISSING


def _looks_like_req008_builder_input(payload: Mapping[str, Any]) -> bool:
    required = {"research_packet", "recommendations", "normalized_at_utc"}
    return required.issubset(payload.keys())


def run(payload: dict[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type", "")).strip()
    if analysis_type == "deficit_and_need_signal_extraction":
        return _worker_w02.run(payload)

    projects = payload.get("projects")
    if isinstance(projects, list) and projects:
        artifacts = projects[0].get("artifacts") if isinstance(projects[0], dict) else None
        if isinstance(artifacts, dict):
            if "runtime_traces" in artifacts or "cycle_summaries" in artifacts:
                return _worker_w06.run(payload)
            if {"plan_packets", "state", "roadmap", "requirements"} & set(artifacts.keys()):
                return _worker_w05.run(payload)

    if "deficits" in payload and "target_project" in payload:
        return _worker_w02.run(payload)

    raise ValueError(
        "unable to route run payload: expected deficit/need extraction, planning artifact sweep, or runtime telemetry sweep input"
    )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if any(
        arg in argv
        for arg in (
            "--target-project-root",
            "--earth-root",
            "--output-root",
            "--revision-identity",
            "--context-input-path",
            "--output-path",
        )
    ):
        return _main_req001(argv)

    parser = argparse.ArgumentParser(description="Unified strategy context sweep CLI.")
    parser.add_argument("--input-json", required=True, help='Input payload path or "-" for stdin.')
    parser.add_argument("--output-json", default="-", help='Output path or "-" for stdout.')
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    if args.input_json == "-":
        payload = json.loads(sys.stdin.read())
    else:
        payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("input payload must be a JSON object")

    try:
        if _looks_like_req008_builder_input(payload):
            output_payload = build_req_008_research_packet_ingestion_and_normalization(**payload)
        else:
            output_payload = run(payload)
    except Exception as exc:
        if hasattr(exc, "code") and hasattr(exc, "message"):
            error_payload = {
                "ok": False,
                "analysis_type": str(payload.get("analysis_type") or ""),
                "reason_code": str(getattr(exc, "code", "runtime_error")),
                "evidence_refs": list(getattr(exc, "evidence_refs", []) or []),
                "errors": [
                    {
                        "stage": str(getattr(exc, "stage", "runtime")),
                        "message": str(getattr(exc, "message", str(exc))),
                    }
                ],
            }
            rendered_error = json.dumps(error_payload, indent=2 if args.json_pretty else None, sort_keys=False)
            if args.output_json == "-":
                print(rendered_error)
            else:
                target = Path(args.output_json)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(rendered_error + "\n", encoding="utf-8")
            return 1
        raise

    rendered = json.dumps(output_payload, indent=2 if args.json_pretty else None, sort_keys=False)
    if args.output_json == "-":
        print(rendered)
    else:
        target = Path(args.output_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
