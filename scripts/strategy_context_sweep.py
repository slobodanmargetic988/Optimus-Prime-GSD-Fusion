#!/usr/bin/env python3
"""Contract surfaces for strategy context sweep processing."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.strategy_context_workers import w02 as _worker_w02
    from scripts.strategy_context_workers import w03 as _worker_w03
    from scripts.strategy_context_workers import w04 as _worker_w04
    from scripts.strategy_context_workers import w05 as _worker_w05
    from scripts.strategy_context_workers import w06 as _worker_w06
    from scripts.strategy_context_workers import w07 as _worker_w07
    from scripts.strategy_context_workers import w07_req016_bundle as _worker_w07_req016
    from scripts.strategy_context_workers import w08 as _worker_w08
    from scripts import strategy_context_sweep_req021 as _req021
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
    from scripts.strategy_context_workers import w07_req016_bundle as _worker_w07_req016
    from scripts.strategy_context_workers import w08 as _worker_w08
    from scripts import strategy_context_sweep_req021 as _req021

SCHEMA_VERSION = "req-001.llm-first-strategy-runtime-entrypoint.v1"
REQUIREMENT_ID = "REQ-001"
RUNTIME_MODE = "llm-first"
EXECUTION_MODE = "long-thinking"
REQ_009_SCHEMA_VERSION = "req-009.prior-strategy-revision-ingestion.v1"
REQ_009_REQUIREMENT_ID = "REQ-009"
REQ_011_SCHEMA_VERSION = "req-011.cross-project-dependency-extraction.v1"
REQ_011_REQUIREMENT_ID = "REQ-011"
REQ_013_SCHEMA_VERSION = "req-013.capability-catalog-extraction.v1"
REQ_013_REQUIREMENT_ID = "REQ-013"
REQ_019_SCHEMA_VERSION = "req-019.execution-resource-context-ingestion.v1"
REQ_019_REQUIREMENT_ID = "REQ-019"
REQ_021_SCHEMA_VERSION = _req021.REQ_021_SCHEMA_VERSION
REQ_021_REQUIREMENT_ID = _req021.REQ_021_REQUIREMENT_ID
REQ_021_LEDGER_SCOPE = _req021.REQ_021_LEDGER_SCOPE
REQ_021_CLAIM_ID_PATTERN = _req021.REQ_021_CLAIM_ID_PATTERN
REQ_023_SCHEMA_VERSION = "req-023.context-compaction-for-llm-call-budget.v1"
REQ_023_REQUIREMENT_ID = "REQ-023"
REQ_023_DEFAULT_LLM_CALL_BUDGET = {
    "max_context_packets": 3,
    "max_focus_points_per_packet": 2,
    "max_evidence_refs_per_packet": 3,
}
REQ_020_SCHEMA_VERSION = "req-020.risk-signal-normalization.v1"
REQ_020_REQUIREMENT_ID = "REQ-020"
REQ_020_TOOL = "strategy-context-sweep"
REQ_020_TOOL_VERSION = "1.0.0"
REQ_020_FALLBACK_NORMALIZED_AT_UTC = "1970-01-01T00:00:00Z"
REQ_024_SCHEMA_VERSION = "req-024.strategy-context-bundle-serialization.v1"
REQ_024_REQUIREMENT_ID = "REQ-024"
REQ_022_SCHEMA_VERSION = "req-022.context-confidence-scoring.v1"
REQ_022_REQUIREMENT_ID = "REQ-022"
REQ_024_TOOL = "strategy-context-sweep"
REQ_024_TOOL_VERSION = "1.0.0"
REQ_024_BUNDLE_SCHEMA_VERSION = "strategy-context-bundle.v1"
REQ_024_SERIALIZATION_FORMAT = "json-canonical-v1"
REQ_024_FALLBACK_BUNDLE_GENERATED_AT_UTC = "1970-01-01T00:00:00Z"

REQ_020_ALLOWED_SOURCES = {
    "blocker",
    "retry",
    "watchdog_exit",
    "regression_pattern",
}
REQ_020_SOURCE_ALIASES = {
    "blocker": "blocker",
    "blockers": "blocker",
    "retry": "retry",
    "retries": "retry",
    "watchdog_exit": "watchdog_exit",
    "watchdog-exit": "watchdog_exit",
    "watchdog": "watchdog_exit",
    "regression_pattern": "regression_pattern",
    "regression-pattern": "regression_pattern",
    "regression": "regression_pattern",
}
REQ_020_ANALYSIS_ANCHORS = [
    "blockers",
    "retries",
    "watchdog_exits",
    "regression_patterns",
]
REQ_020_ALLOWED_SEVERITIES = {
    "low",
    "medium",
    "high",
    "critical",
}
REQ_020_SEVERITY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}
REQ_020_DEFAULT_REASON_CODE_BY_SOURCE = {
    "blocker": "task_blocked",
    "retry": "retry_limit_reached",
    "watchdog_exit": "stale_base_branch_commit",
    "regression_pattern": "regression_detected",
}
REQ_020_REASON_CODE_ALIASES = {
    "blocker_detected": "task_blocked",
    "blocking_issue_detected": "task_blocked",
    "retry_exhausted": "retry_limit_reached",
    "retry_budget_exhausted": "retry_limit_reached",
    "watchdog_timeout": "stale_base_branch_commit",
    "watchdog_terminal_exit": "stale_run_base_hard_limit",
    "regression_pattern_detected": "regression_detected",
}


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


def _normalize_positive_int(raw_value: Any, *, field_name: str) -> int:
    if not isinstance(raw_value, int) or isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be a positive integer")
    if raw_value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return raw_value


def _stable_id_fragment(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _normalize_cross_project_context(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("cross_project_context must be a list")

    normalized: list[dict[str, Any]] = []
    seen_project_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"cross_project_context[{index}] must be an object")
        project_id = _require_nonempty_text(item.get("project_id"), field_name=f"cross_project_context[{index}].project_id")
        if project_id in seen_project_ids:
            raise ValueError(f"cross_project_context[{index}].project_id must be unique")
        seen_project_ids.add(project_id)
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


def _slug_token(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or _stable_id_fragment(value)


def _normalize_req_011_signal_row(
    raw_value: Any,
    *,
    index: int,
    field_name: str,
    signal_type: str,
) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError(f"{field_name}[{index}] must be an object")

    source_ref_field = {
        "contract": "contract_ref",
        "trace": "trace_ref",
        "declared-integration-point": "integration_point_ref",
    }[signal_type]
    source_project_id = _require_nonempty_text(
        raw_value.get("source_project_id"),
        field_name=f"{field_name}[{index}].source_project_id",
    )
    target_project_id = _require_nonempty_text(
        raw_value.get("target_project_id"),
        field_name=f"{field_name}[{index}].target_project_id",
    )
    if source_project_id == target_project_id:
        raise ValueError(f"{field_name}[{index}] must describe a cross-project dependency edge")

    dependency_key = _require_nonempty_text(
        raw_value.get("dependency_key"),
        field_name=f"{field_name}[{index}].dependency_key",
    )
    signal_slug = "-".join(
        (
            _slug_token(source_project_id),
            _slug_token(target_project_id),
            _slug_token(dependency_key),
            _slug_token(signal_type),
        )
    )
    return {
        "signal_id": _require_nonempty_text(
            raw_value.get("signal_id") if raw_value.get("signal_id") is not None else f"signal-{signal_slug}",
            field_name=f"{field_name}[{index}].signal_id",
        ),
        "signal_type": signal_type,
        "dependency_key": dependency_key,
        "summary": _require_nonempty_text(
            raw_value.get("summary"),
            field_name=f"{field_name}[{index}].summary",
        ),
        "source_project_id": source_project_id,
        "source_project_root": _normalize_root(
            raw_value.get("source_project_root"),
            field_name=f"{field_name}[{index}].source_project_root",
        ),
        "target_project_id": target_project_id,
        "target_project_root": _normalize_root(
            raw_value.get("target_project_root"),
            field_name=f"{field_name}[{index}].target_project_root",
        ),
        source_ref_field: _require_nonempty_text(
            raw_value.get(source_ref_field),
            field_name=f"{field_name}[{index}].{source_ref_field}",
        ),
        "evidence_refs": _normalize_string_list(
            raw_value.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
        ),
    }


def _normalize_req_011_signal_rows(
    raw_value: Any,
    *,
    field_name: str,
    signal_type: str,
) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")

    normalized = [
        _normalize_req_011_signal_row(row, index=index, field_name=field_name, signal_type=signal_type)
        for index, row in enumerate(raw_value)
    ]
    normalized.sort(
        key=lambda row: (
            row["source_project_id"],
            row["target_project_id"],
            row["dependency_key"],
            row["signal_id"],
        )
    )
    return normalized


def _normalize_req_011_broad_sweep_context(raw_value: Any) -> dict[str, Any]:
    if raw_value is None:
        raw_value = {}
    if not isinstance(raw_value, Mapping):
        raise ValueError("broad_sweep_context must be an object")

    return {
        "earth_sweep_evidence_refs": _normalize_string_list(
            raw_value.get("earth_sweep_evidence_refs"),
            field_name="broad_sweep_context.earth_sweep_evidence_refs",
        ),
        "cross_project_context": _normalize_cross_project_context(raw_value.get("cross_project_context")),
        "contract_dependencies": _normalize_req_011_signal_rows(
            raw_value.get("contract_dependencies"),
            field_name="broad_sweep_context.contract_dependencies",
            signal_type="contract",
        ),
        "trace_dependencies": _normalize_req_011_signal_rows(
            raw_value.get("trace_dependencies"),
            field_name="broad_sweep_context.trace_dependencies",
            signal_type="trace",
        ),
        "declared_integration_points": _normalize_req_011_signal_rows(
            raw_value.get("declared_integration_points"),
            field_name="broad_sweep_context.declared_integration_points",
            signal_type="declared-integration-point",
        ),
        "earth_sweep_source_artifacts": _normalize_earth_sweep_source_artifacts(
            raw_value.get("earth_sweep_source_artifacts")
        ),
        "required_context_documents": _normalize_required_context_documents(
            raw_value.get("required_context_documents")
        ),
    }


def _req_011_signal_source_ref(signal: Mapping[str, Any]) -> str:
    if signal["signal_type"] == "contract":
        return str(signal["contract_ref"])
    if signal["signal_type"] == "trace":
        return str(signal["trace_ref"])
    return str(signal["integration_point_ref"])


def _req_011_signal_evidence_refs(signal: Mapping[str, Any]) -> list[str]:
    return _collect_unique_refs(list(signal["evidence_refs"]), [_req_011_signal_source_ref(signal)])


def _req_011_edge_confidence(signal_types: list[str], *, evidence_refs: list[str]) -> tuple[str, str]:
    if len(signal_types) >= 3 and evidence_refs:
        return "high", "Contracts, traces, and declared integration points corroborate the edge."
    if len(signal_types) >= 2 and evidence_refs:
        return "medium", "Multiple broad-sweep signal types corroborate the edge."
    if evidence_refs:
        return "low", "Only one corroborating signal type is attached to the edge."
    return "low", "The edge lacks evidence refs and cannot be treated as confirmed."


def _build_req_011_dependency_edges(
    *,
    broad_sweep_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    cross_project_context = list(broad_sweep_context["cross_project_context"])
    context_refs_by_project = {
        row["project_id"]: list(row["evidence_refs"])
        for row in cross_project_context
    }
    grouped_signals: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for signal in (
        list(broad_sweep_context["contract_dependencies"])
        + list(broad_sweep_context["trace_dependencies"])
        + list(broad_sweep_context["declared_integration_points"])
    ):
        key = (signal["source_project_id"], signal["target_project_id"], signal["dependency_key"])
        grouped_signals.setdefault(key, []).append(signal)

    dependency_edges: list[dict[str, Any]] = []
    for key, signals in grouped_signals.items():
        source_project_id, target_project_id, dependency_key = key
        ordered_signals = sorted(signals, key=lambda row: (row["signal_type"], row["signal_id"]))
        signal_types = sorted({str(row["signal_type"]) for row in ordered_signals})
        signal_evidence_refs = _collect_unique_refs(*[_req_011_signal_evidence_refs(row) for row in ordered_signals])
        supporting_context_project_ids = sorted(
            project_id
            for project_id in {source_project_id, target_project_id}
            if project_id in context_refs_by_project
        )
        supporting_context_evidence_refs = _collect_unique_refs(
            *[context_refs_by_project.get(project_id, []) for project_id in supporting_context_project_ids]
        )
        confidence, confidence_reason = _req_011_edge_confidence(signal_types, evidence_refs=signal_evidence_refs)
        edge_slug = "-".join(
            (
                _slug_token(source_project_id),
                _slug_token(target_project_id),
                _slug_token(dependency_key),
            )
        )

        dependency_edges.append(
            {
                "dependency_edge_id": f"dependency-edge-{edge_slug}",
                "dependency_key": dependency_key,
                "source_project_id": source_project_id,
                "source_project_root": ordered_signals[0]["source_project_root"],
                "target_project_id": target_project_id,
                "target_project_root": ordered_signals[0]["target_project_root"],
                "summary": sorted({str(row["summary"]) for row in ordered_signals})[0],
                "signal_types": signal_types,
                "supporting_signal_ids": [str(row["signal_id"]) for row in ordered_signals],
                "supporting_signal_count": len(ordered_signals),
                "contract_refs": sorted(
                    {str(row["contract_ref"]) for row in ordered_signals if row["signal_type"] == "contract"}
                ),
                "trace_refs": sorted(
                    {str(row["trace_ref"]) for row in ordered_signals if row["signal_type"] == "trace"}
                ),
                "integration_point_refs": sorted(
                    {
                        str(row["integration_point_ref"])
                        for row in ordered_signals
                        if row["signal_type"] == "declared-integration-point"
                    }
                ),
                "confidence": confidence,
                "confidence_reason": confidence_reason,
                "evidence_refs": signal_evidence_refs,
                "supporting_context_project_ids": supporting_context_project_ids,
                "supporting_context_evidence_refs": supporting_context_evidence_refs,
            }
        )

    dependency_edges.sort(
        key=lambda row: (
            row["source_project_id"],
            row["target_project_id"],
            row["dependency_key"],
            row["dependency_edge_id"],
        )
    )
    return dependency_edges


def _req_011_recommendation_decision(
    *,
    dependency_edges: list[dict[str, Any]],
    cross_project_obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
) -> str:
    if cross_project_obligations and not open_risks:
        return "proceed"
    if cross_project_obligations and open_risks:
        return "proceed-with-open-risks"
    if dependency_edges and open_risks:
        return "record-open-risks"
    if open_risks:
        return "resolve-context-gaps"
    if dependency_edges:
        return "observe"
    return "insufficient-context"


def _req_011_recommendation_rationale(*, decision: str) -> str:
    if decision == "proceed":
        return "Cross-project dependency edges are corroborated strongly enough to emit obligations."
    if decision == "proceed-with-open-risks":
        return "Some dependency edges are obligation-ready, while weaker or under-evidenced edges remain open risks."
    if decision == "record-open-risks":
        return "Dependency edges were extracted, but evidence or confidence gaps prevent obligation promotion."
    if decision == "resolve-context-gaps":
        return "Stale or missing context artifacts prevent reliable cross-project dependency replay."
    if decision == "observe":
        return "Dependency edges were extracted for observation, but no cross-project obligation is warranted yet."
    return "No cross-project dependency edges were extracted from the provided broad-sweep context."


def _build_req_011_processing_behavior(
    *,
    broad_sweep_context: dict[str, Any],
) -> dict[str, Any]:
    earth_sweep_evidence_refs = list(broad_sweep_context["earth_sweep_evidence_refs"])
    cross_project_context = list(broad_sweep_context["cross_project_context"])
    earth_sweep_source_artifacts = list(broad_sweep_context["earth_sweep_source_artifacts"])
    required_context_documents = list(broad_sweep_context["required_context_documents"])
    dependency_edges = _build_req_011_dependency_edges(broad_sweep_context=broad_sweep_context)
    source_artifact_refs = _collect_unique_refs(
        *[_collect_unique_refs([row["artifact_ref"]], row["evidence_refs"]) for row in earth_sweep_source_artifacts]
    )
    required_doc_refs = _collect_unique_refs(
        *[_collect_unique_refs([row["doc_ref"]], row["evidence_refs"]) for row in required_context_documents]
    )

    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    matched_context_projects: set[str] = set()

    for source_artifact in earth_sweep_source_artifacts:
        if source_artifact["status"] != "stale":
            continue
        open_risks.append(
            {
                "risk_id": f"risk-earth-source-{_stable_id_fragment(source_artifact['artifact_ref'])}",
                "reason_code": "stale_earth_sweep_source_artifact",
                "summary": f"Earth sweep source artifact is stale: {source_artifact['artifact_ref']}",
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
                "risk_id": (
                    "risk-context-doc-"
                    f"{_stable_id_fragment(required_doc['doc_kind'], required_doc['project_id'], required_doc['doc_ref'])}"
                ),
                "reason_code": reason_code,
                "summary": summary,
                "required_evidence_refs": _collect_unique_refs(
                    [required_doc["doc_ref"]],
                    required_doc["evidence_refs"],
                ),
            }
        )

    for edge in dependency_edges:
        supporting_context_project_ids = list(edge["supporting_context_project_ids"])
        supporting_context_refs = list(edge["supporting_context_evidence_refs"])
        matched_context_projects.update(supporting_context_project_ids)
        required_refs = _collect_unique_refs(edge["evidence_refs"], supporting_context_refs)
        if edge["confidence"] == "low":
            open_risks.append(
                {
                    "risk_id": f"risk-dependency-confidence-{edge['dependency_edge_id']}",
                    "reason_code": "dependency_confidence_below_commit_threshold",
                    "summary": (
                        f"Dependency edge '{edge['dependency_key']}' between '{edge['source_project_id']}' and "
                        f"'{edge['target_project_id']}' remains an open risk because corroboration is weak."
                    ),
                    "required_evidence_refs": required_refs,
                }
            )
            continue
        if not earth_sweep_evidence_refs:
            open_risks.append(
                {
                    "risk_id": f"risk-dependency-earth-evidence-{edge['dependency_edge_id']}",
                    "reason_code": "missing_earth_sweep_evidence_refs",
                    "summary": (
                        f"Dependency edge '{edge['dependency_key']}' between '{edge['source_project_id']}' and "
                        f"'{edge['target_project_id']}' cannot become a cross-project obligation until "
                        "Earth-sweep evidence refs are attached."
                    ),
                    "required_evidence_refs": required_refs,
                }
            )
            continue
        if not supporting_context_refs:
            open_risks.append(
                {
                    "risk_id": f"risk-dependency-context-evidence-{edge['dependency_edge_id']}",
                    "reason_code": "missing_cross_project_context_evidence_refs",
                    "summary": (
                        f"Dependency edge '{edge['dependency_key']}' between '{edge['source_project_id']}' and "
                        f"'{edge['target_project_id']}' lacks Earth-sweep cross-project context evidence refs."
                    ),
                    "required_evidence_refs": _collect_unique_refs(edge["evidence_refs"], earth_sweep_evidence_refs),
                }
            )
            continue

        cross_project_obligations.append(
            {
                "obligation_id": f"obligation-{edge['dependency_edge_id']}",
                "project_id": edge["target_project_id"],
                "summary": (
                    f"Coordinate dependency '{edge['dependency_key']}' between '{edge['source_project_id']}' and "
                    f"'{edge['target_project_id']}' before implementation."
                ),
                "confidence": edge["confidence"],
                "evidence_refs": _collect_unique_refs(
                    earth_sweep_evidence_refs,
                    edge["evidence_refs"],
                    supporting_context_refs,
                ),
            }
        )

    cross_project_obligations.sort(key=lambda row: (row["project_id"], row["obligation_id"]))
    open_risks.sort(key=lambda row: row["risk_id"])
    evidence_refs = _collect_unique_refs(
        earth_sweep_evidence_refs,
        source_artifact_refs,
        required_doc_refs,
        *[row["evidence_refs"] for row in cross_project_context],
        *[row["evidence_refs"] for row in dependency_edges],
        *[row["supporting_context_evidence_refs"] for row in dependency_edges],
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    decision = _req_011_recommendation_decision(
        dependency_edges=dependency_edges,
        cross_project_obligations=cross_project_obligations,
        open_risks=open_risks,
    )

    contract_signal_ids = [row["signal_id"] for row in broad_sweep_context["contract_dependencies"]]
    trace_signal_ids = [row["signal_id"] for row in broad_sweep_context["trace_dependencies"]]
    integration_signal_ids = [row["signal_id"] for row in broad_sweep_context["declared_integration_points"]]
    context_usage = {
        "broad_sweep_context_used": any(
            (
                earth_sweep_evidence_refs,
                cross_project_context,
                broad_sweep_context["contract_dependencies"],
                broad_sweep_context["trace_dependencies"],
                broad_sweep_context["declared_integration_points"],
            )
        ),
        "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
        "cross_project_context_used": bool(cross_project_context),
        "contract_dependency_signal_ids_used": contract_signal_ids,
        "trace_dependency_signal_ids_used": trace_signal_ids,
        "declared_integration_point_signal_ids_used": integration_signal_ids,
        "cross_project_projects_considered": [row["project_id"] for row in cross_project_context],
        "cross_project_context_projects_matched": sorted(matched_context_projects),
        "dependency_keys_extracted": [row["dependency_key"] for row in dependency_edges],
        "dependency_edge_ids_extracted": [row["dependency_edge_id"] for row in dependency_edges],
        "high_confidence_dependency_edge_ids": [
            row["dependency_edge_id"] for row in dependency_edges if row["confidence"] == "high"
        ],
        "medium_confidence_dependency_edge_ids": [
            row["dependency_edge_id"] for row in dependency_edges if row["confidence"] == "medium"
        ],
        "low_confidence_dependency_edge_ids": [
            row["dependency_edge_id"] for row in dependency_edges if row["confidence"] == "low"
        ],
        "evidence_refs_used": evidence_refs,
    }
    if earth_sweep_source_artifacts:
        context_usage["earth_sweep_source_artifacts_used"] = True
        context_usage["earth_sweep_source_artifact_refs_used"] = source_artifact_refs
    if required_context_documents:
        context_usage["required_context_documents_used"] = True
        context_usage["required_context_document_refs_used"] = required_doc_refs

    return {
        "strategy": "cross-project-dependency-extraction",
        "reasoning_mode": EXECUTION_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "broad_sweep_context": broad_sweep_context,
        },
        "context_usage": context_usage,
        "recommendation": {
            "decision": decision,
            "rationale": _req_011_recommendation_rationale(decision=decision),
            "confidence": _recommendation_confidence(evidence_refs=evidence_refs, open_risks=open_risks),
            "evidence_refs": evidence_refs,
            "dependency_edges": dependency_edges,
            "cross_project_obligations": cross_project_obligations,
            "open_risks": open_risks,
        },
    }


def _canonical_req_011_processing_input(*, broad_sweep_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "broad_sweep_context": broad_sweep_context,
    }


def build_req_011_cross_project_dependency_extraction(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    broad_sweep_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_nonempty_text(revision_identity, field_name="revision_identity")
    normalized_broad_sweep_context = _normalize_req_011_broad_sweep_context(broad_sweep_context)

    canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    digest = _canonical_input_digest(canonical_input)
    canonical_processing_input = _canonical_req_011_processing_input(
        broad_sweep_context=normalized_broad_sweep_context,
    )
    processing_digest = _canonical_input_digest(canonical_processing_input)
    processing_behavior = _build_req_011_processing_behavior(
        broad_sweep_context=normalized_broad_sweep_context,
    )

    return {
        "schema_version": REQ_011_SCHEMA_VERSION,
        "requirement_id": REQ_011_REQUIREMENT_ID,
        "cross_project_dependency_extraction": {
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
            "reproducible_call_id": f"req011-{digest[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_digest,
            "processing_call_id": f"req011-processing-{processing_digest[:16]}",
            "canonical_processing_input": canonical_processing_input,
        },
    }


def validate_req_011_cross_project_dependency_extraction(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    top_keys = set(payload.keys())
    required_top = {
        "schema_version",
        "requirement_id",
        "cross_project_dependency_extraction",
        "processing_behavior",
        "call_metadata",
    }
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_011_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_011_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_011_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_011_REQUIREMENT_ID}")

    extraction = payload.get("cross_project_dependency_extraction")
    if not isinstance(extraction, Mapping):
        errors.append("cross_project_dependency_extraction must be an object")
        return errors

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        return errors

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors

    required_processing = {
        "strategy",
        "reasoning_mode",
        "heuristic_summarization_only",
        "context_inputs",
        "context_usage",
        "recommendation",
    }
    missing_processing = sorted(required_processing - set(processing_behavior.keys()))
    if missing_processing:
        errors.append(f"processing_behavior missing keys: {missing_processing}")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        return errors
    if "broad_sweep_context" not in context_inputs:
        errors.append("processing_behavior.context_inputs missing broad_sweep_context")
        return errors

    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
        return errors
    for required_field in (
        "decision",
        "rationale",
        "confidence",
        "evidence_refs",
        "dependency_edges",
        "cross_project_obligations",
        "open_risks",
    ):
        if required_field not in recommendation:
            errors.append(f"processing_behavior.recommendation missing {required_field}")

    try:
        normalized_target_root = _normalize_root(
            extraction.get("target_project_root"),
            field_name="cross_project_dependency_extraction.target_project_root",
        )
        normalized_earth_root = _normalize_root(
            extraction.get("earth_root"),
            field_name="cross_project_dependency_extraction.earth_root",
        )
        normalized_output_root = _normalize_root(
            extraction.get("output_root"),
            field_name="cross_project_dependency_extraction.output_root",
        )
        normalized_revision_identity = _require_nonempty_text(
            extraction.get("revision_identity"),
            field_name="cross_project_dependency_extraction.revision_identity",
        )
        normalized_broad_sweep_context = _normalize_req_011_broad_sweep_context(
            context_inputs.get("broad_sweep_context")
        )
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    if extraction.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"cross_project_dependency_extraction.runtime_mode must be {RUNTIME_MODE}")
    if extraction.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"cross_project_dependency_extraction.execution_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("strategy") != "cross-project-dependency-extraction":
        errors.append("processing_behavior.strategy must be cross-project-dependency-extraction")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    expected_canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    canonical_input = metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
        return errors
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")

    expected_digest = _canonical_input_digest(expected_canonical_input)
    if metadata.get("canonical_input_sha256") != expected_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != f"req011-{expected_digest[:16]}":
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")
    if metadata.get("reproducibility") != "deterministic-input-fingerprint":
        errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")

    expected_processing_behavior = _build_req_011_processing_behavior(
        broad_sweep_context=normalized_broad_sweep_context,
    )
    if payload.get("processing_behavior") != expected_processing_behavior:
        errors.append("processing_behavior must mirror deterministic broad-sweep processing output")

    expected_canonical_processing_input = _canonical_req_011_processing_input(
        broad_sweep_context=normalized_broad_sweep_context,
    )
    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors
    if dict(canonical_processing_input) != expected_canonical_processing_input:
        errors.append("call_metadata.canonical_processing_input must mirror normalized processing input")

    expected_processing_digest = _canonical_input_digest(expected_canonical_processing_input)
    if metadata.get("processing_input_sha256") != expected_processing_digest:
        errors.append("call_metadata.processing_input_sha256 does not match processing input")
    if metadata.get("processing_call_id") != f"req011-processing-{expected_processing_digest[:16]}":
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


def _normalize_req_023_hard_constraints(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("hard_constraints must be a list")

    normalized: list[dict[str, Any]] = []
    seen_constraint_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"hard_constraints[{index}] must be an object")
        constraint_id = _require_nonempty_text(
            item.get("constraint_id"),
            field_name=f"hard_constraints[{index}].constraint_id",
        )
        if constraint_id in seen_constraint_ids:
            raise ValueError(f"hard_constraints[{index}].constraint_id must be unique")
        seen_constraint_ids.add(constraint_id)
        statement = _require_nonempty_text(
            item.get("statement"),
            field_name=f"hard_constraints[{index}].statement",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"hard_constraints[{index}].evidence_refs",
        )
        normalized.append(
            {
                "constraint_id": constraint_id,
                "statement": statement,
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(key=lambda row: row["constraint_id"])
    return normalized


def _normalize_req_023_llm_call_budget(raw_value: Any) -> dict[str, int]:
    if raw_value is None:
        return dict(REQ_023_DEFAULT_LLM_CALL_BUDGET)
    if not isinstance(raw_value, Mapping):
        raise ValueError("llm_call_budget must be an object")

    budget = dict(REQ_023_DEFAULT_LLM_CALL_BUDGET)
    for field_name in REQ_023_DEFAULT_LLM_CALL_BUDGET:
        if field_name in raw_value and raw_value[field_name] is not None:
            budget[field_name] = _normalize_positive_int(
                raw_value[field_name],
                field_name=f"llm_call_budget.{field_name}",
            )
    return budget


def _canonical_req_023_processing_input(
    *,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
    hard_constraints: list[dict[str, Any]],
    llm_call_budget: Mapping[str, int],
) -> dict[str, Any]:
    canonical = _canonical_processing_input(
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
        candidate_recommendations=candidate_recommendations,
        earth_sweep_source_artifacts=earth_sweep_source_artifacts,
        required_context_documents=required_context_documents,
    )
    canonical["hard_constraints"] = hard_constraints
    canonical["llm_call_budget"] = dict(llm_call_budget)
    return canonical


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _req_023_obligation_action_id(obligation_id: str) -> str:
    return obligation_id.removeprefix("obligation-")


def _build_req_023_group_specs(
    *,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    recommended_actions: list[dict[str, Any]],
    cross_project_obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    obligation_by_action_id = {
        _req_023_obligation_action_id(str(row["obligation_id"])): row for row in cross_project_obligations
    }

    if open_risks:
        groups.append(
            {
                "group_kind": "risk",
                "summary": f"Resolve {len(open_risks)} open risk(s) before broad replay expansion.",
                "focus_points": [str(row["summary"]) for row in open_risks],
                "next_steps": [
                    f"Resolve {row['risk_id']} and refresh required evidence refs." for row in open_risks
                ],
                "project_ids": [],
                "source_action_ids": [],
                "source_obligation_ids": [],
                "source_risk_ids": [str(row["risk_id"]) for row in open_risks],
                "traceability_refs": _collect_unique_refs(
                    target_project_evidence_refs,
                    earth_sweep_evidence_refs,
                    *[list(row["required_evidence_refs"]) for row in open_risks],
                ),
            }
        )

    cross_project_actions: dict[str, list[dict[str, Any]]] = {}
    for action in recommended_actions:
        if action["action_scope"] != "cross-project":
            continue
        obligation = obligation_by_action_id.get(str(action["action_id"]))
        if obligation is None:
            project_id = "earth"
        else:
            project_id = str(obligation["project_id"])
        cross_project_actions.setdefault(project_id, []).append(action)

    for project_id in sorted(cross_project_actions):
        actions = sorted(cross_project_actions[project_id], key=lambda row: row["action_id"])
        obligations = [
            obligation_by_action_id[str(action["action_id"])]
            for action in actions
            if str(action["action_id"]) in obligation_by_action_id
        ]
        groups.append(
            {
                "group_kind": "cross-project",
                "summary": f"Cross-project packet for '{project_id}' covering {len(actions)} action(s).",
                "focus_points": [str(row["summary"]) for row in actions],
                "next_steps": [str(row["next_step"]) for row in actions],
                "project_ids": [project_id],
                "source_action_ids": [str(row["action_id"]) for row in actions],
                "source_obligation_ids": [str(row["obligation_id"]) for row in obligations],
                "source_risk_ids": [],
                "traceability_refs": _collect_unique_refs(
                    earth_sweep_evidence_refs,
                    *[list(row["evidence_refs"]) for row in actions],
                    *[list(row["evidence_refs"]) for row in obligations],
                ),
            }
        )

    local_actions = sorted(
        [row for row in recommended_actions if row["action_scope"] != "cross-project"],
        key=lambda row: row["action_id"],
    )
    if local_actions:
        groups.append(
            {
                "group_kind": "target-project",
                "summary": f"Target-project packet covering {len(local_actions)} action(s).",
                "focus_points": [str(row["summary"]) for row in local_actions],
                "next_steps": [str(row["next_step"]) for row in local_actions],
                "project_ids": [],
                "source_action_ids": [str(row["action_id"]) for row in local_actions],
                "source_obligation_ids": [],
                "source_risk_ids": [],
                "traceability_refs": _collect_unique_refs(
                    target_project_evidence_refs,
                    *[list(row["evidence_refs"]) for row in local_actions],
                ),
            }
        )

    return groups


def _build_req_023_compacted_packets(
    *,
    group_specs: list[dict[str, Any]],
    hard_constraints: list[dict[str, Any]],
    llm_call_budget: Mapping[str, int],
) -> list[dict[str, Any]]:
    hard_constraint_ids = [row["constraint_id"] for row in hard_constraints]
    hard_constraint_refs = _collect_unique_refs(*[row["evidence_refs"] for row in hard_constraints])
    max_focus_points = int(llm_call_budget["max_focus_points_per_packet"])
    max_evidence_refs = int(llm_call_budget["max_evidence_refs_per_packet"])
    if not group_specs:
        if not hard_constraints:
            return []
        return [
            {
                "packet_id": "packet-01",
                "packet_kind": "mixed",
                "summary": f"Hard-constraint packet covering {len(hard_constraints)} constraint(s).",
                "focus_points": [str(row["statement"]) for row in hard_constraints][:max_focus_points],
                "project_ids": [],
                "source_action_ids": [],
                "source_obligation_ids": [],
                "source_risk_ids": [],
                "hard_constraint_ids": hard_constraint_ids,
                "traceability_refs": hard_constraint_refs,
                "evidence_focus_refs": hard_constraint_refs[:max_evidence_refs],
                "next_steps": [
                    "Carry all hard constraints and traceability refs forward unchanged into each LLM call."
                ],
            }
        ]

    max_context_packets = int(llm_call_budget["max_context_packets"])
    if len(group_specs) <= max_context_packets:
        packet_groups = [[group_spec] for group_spec in group_specs]
    elif max_context_packets == 1:
        packet_groups = [group_specs]
    else:
        packet_groups = [[group_spec] for group_spec in group_specs[: max_context_packets - 1]]
        packet_groups.append(group_specs[max_context_packets - 1 :])

    packets: list[dict[str, Any]] = []
    for index, packet_group in enumerate(packet_groups, start=1):
        packet_kinds = sorted({str(row["group_kind"]) for row in packet_group})
        packet_kind = packet_kinds[0] if len(packet_kinds) == 1 else "mixed"
        summary = (
            packet_group[0]["summary"]
            if len(packet_group) == 1
            else f"Merged {len(packet_group)} high-signal groups for LLM call budget fit."
        )
        focus_points = _dedupe_preserving_order(
            [point for row in packet_group for point in list(row["focus_points"])]
        )[:max_focus_points]
        next_steps = _dedupe_preserving_order(
            [step for row in packet_group for step in list(row["next_steps"])]
        )[:max_focus_points]
        traceability_refs = _collect_unique_refs(
            hard_constraint_refs,
            *[list(row["traceability_refs"]) for row in packet_group],
        )
        packets.append(
            {
                "packet_id": f"packet-{index:02d}",
                "packet_kind": packet_kind,
                "summary": summary,
                "focus_points": focus_points,
                "project_ids": sorted(
                    {
                        project_id
                        for row in packet_group
                        for project_id in list(row["project_ids"])
                        if project_id
                    }
                ),
                "source_action_ids": sorted(
                    {
                        action_id
                        for row in packet_group
                        for action_id in list(row["source_action_ids"])
                    }
                ),
                "source_obligation_ids": sorted(
                    {
                        obligation_id
                        for row in packet_group
                        for obligation_id in list(row["source_obligation_ids"])
                    }
                ),
                "source_risk_ids": sorted(
                    {
                        risk_id
                        for row in packet_group
                        for risk_id in list(row["source_risk_ids"])
                    }
                ),
                "hard_constraint_ids": hard_constraint_ids,
                "traceability_refs": traceability_refs,
                "evidence_focus_refs": traceability_refs[:max_evidence_refs],
                "next_steps": next_steps,
            }
        )

    return packets


def _build_req_023_context_compaction(
    *,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    hard_constraints: list[dict[str, Any]],
    llm_call_budget: Mapping[str, int],
    recommended_actions: list[dict[str, Any]],
    cross_project_obligations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
    recommendation_evidence_refs: list[str],
) -> dict[str, Any]:
    group_specs = _build_req_023_group_specs(
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        recommended_actions=recommended_actions,
        cross_project_obligations=cross_project_obligations,
        open_risks=open_risks,
    )
    compacted_packets = _build_req_023_compacted_packets(
        group_specs=group_specs,
        hard_constraints=hard_constraints,
        llm_call_budget=llm_call_budget,
    )

    hard_constraint_refs = _collect_unique_refs(*[row["evidence_refs"] for row in hard_constraints])
    mandatory_traceability_refs = _collect_unique_refs(recommendation_evidence_refs, hard_constraint_refs)
    expected_action_ids = sorted({str(row["action_id"]) for row in recommended_actions})
    expected_obligation_ids = sorted({str(row["obligation_id"]) for row in cross_project_obligations})
    expected_risk_ids = sorted({str(row["risk_id"]) for row in open_risks})
    expected_hard_constraint_ids = sorted({str(row["constraint_id"]) for row in hard_constraints})

    covered_action_ids = sorted(
        {
            action_id
            for packet in compacted_packets
            for action_id in list(packet["source_action_ids"])
        }
    )
    covered_obligation_ids = sorted(
        {
            obligation_id
            for packet in compacted_packets
            for obligation_id in list(packet["source_obligation_ids"])
        }
    )
    covered_risk_ids = sorted(
        {
            risk_id
            for packet in compacted_packets
            for risk_id in list(packet["source_risk_ids"])
        }
    )
    covered_hard_constraint_ids = sorted(
        {
            constraint_id
            for packet in compacted_packets
            for constraint_id in list(packet["hard_constraint_ids"])
        }
    )

    return {
        "compaction_strategy": "high-signal-packets-for-multi-call-reasoning",
        "llm_call_budget": dict(llm_call_budget),
        "mandatory_traceability_refs": mandatory_traceability_refs,
        "hard_constraints": hard_constraints,
        "compacted_packets": compacted_packets,
        "coverage": {
            "recommended_action_ids": expected_action_ids,
            "covered_action_ids": covered_action_ids,
            "uncovered_action_ids": sorted(set(expected_action_ids) - set(covered_action_ids)),
            "cross_project_obligation_ids": expected_obligation_ids,
            "covered_obligation_ids": covered_obligation_ids,
            "uncovered_obligation_ids": sorted(set(expected_obligation_ids) - set(covered_obligation_ids)),
            "open_risk_ids": expected_risk_ids,
            "covered_risk_ids": covered_risk_ids,
            "uncovered_risk_ids": sorted(set(expected_risk_ids) - set(covered_risk_ids)),
            "hard_constraint_ids": expected_hard_constraint_ids,
            "covered_hard_constraint_ids": covered_hard_constraint_ids,
            "uncovered_hard_constraint_ids": sorted(
                set(expected_hard_constraint_ids) - set(covered_hard_constraint_ids)
            ),
        },
    }


def _req_023_recommendation_decision(
    *,
    compacted_packets: list[dict[str, Any]],
    coverage: Mapping[str, Any],
    base_decision: str,
) -> str:
    if compacted_packets and not any(list(coverage.get(field_name, [])) for field_name in (
        "uncovered_action_ids",
        "uncovered_obligation_ids",
        "uncovered_risk_ids",
        "uncovered_hard_constraint_ids",
    )):
        if base_decision == "proceed":
            return "compact-ready"
        if base_decision == "insufficient-context" and list(coverage.get("hard_constraint_ids", [])):
            return "compact-ready"
        return base_decision
    if coverage.get("hard_constraint_ids"):
        return "constraints-only"
    return "insufficient-context"


def _build_req_023_processing_behavior(
    *,
    target_project_root: str,
    earth_root: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    candidate_recommendations: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
    hard_constraints: list[dict[str, Any]],
    llm_call_budget: Mapping[str, int],
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
    recommendation = dict(base_behavior["recommendation"])
    context_compaction = _build_req_023_context_compaction(
        target_project_evidence_refs=target_project_evidence_refs,
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        hard_constraints=hard_constraints,
        llm_call_budget=llm_call_budget,
        recommended_actions=list(recommendation["recommended_actions"]),
        cross_project_obligations=list(recommendation["cross_project_obligations"]),
        open_risks=list(recommendation["open_risks"]),
        recommendation_evidence_refs=list(recommendation["evidence_refs"]),
    )

    coverage = context_compaction["coverage"]
    compacted_packets = context_compaction["compacted_packets"]
    base_decision = str(recommendation["decision"])
    recommendation["decision"] = _req_023_recommendation_decision(
        compacted_packets=compacted_packets,
        coverage=coverage,
        base_decision=base_decision,
    )
    compaction_rationale = (
        f"Compacted {len(compacted_packets)} packet(s) covering "
        f"{len(coverage['covered_action_ids'])} action(s), "
        f"{len(coverage['covered_obligation_ids'])} obligation(s), "
        f"{len(coverage['covered_risk_ids'])} risk(s), and "
        f"{len(coverage['covered_hard_constraint_ids'])} hard constraint(s)."
    )
    if recommendation["decision"] == "compact-ready":
        recommendation["rationale"] = compaction_rationale
    elif recommendation["decision"] == "constraints-only":
        recommendation["rationale"] = (
            f"{compaction_rationale} Only hard-constraint packets are ready for downstream reasoning."
        )
    else:
        recommendation["rationale"] = (
            f"{compaction_rationale} {_recommendation_rationale(decision=recommendation['decision'])}"
        )
    recommendation["confidence"] = _recommendation_confidence(
        evidence_refs=context_compaction["mandatory_traceability_refs"],
        open_risks=list(recommendation["open_risks"]),
    )
    recommendation["evidence_refs"] = context_compaction["mandatory_traceability_refs"]

    context_inputs = dict(base_behavior["context_inputs"])
    context_inputs["hard_constraints"] = hard_constraints
    context_inputs["llm_call_budget"] = dict(llm_call_budget)

    context_usage = dict(base_behavior["context_usage"])
    context_usage["context_compaction_used"] = True
    context_usage["context_compaction_packet_ids"] = [row["packet_id"] for row in compacted_packets]
    context_usage["context_compaction_traceability_refs_used"] = context_compaction["mandatory_traceability_refs"]
    context_usage["context_compaction_hard_constraint_ids"] = coverage["hard_constraint_ids"]
    context_usage["context_compaction_covered_action_ids"] = coverage["covered_action_ids"]
    context_usage["context_compaction_covered_obligation_ids"] = coverage["covered_obligation_ids"]
    context_usage["context_compaction_covered_risk_ids"] = coverage["covered_risk_ids"]
    context_usage["evidence_refs_used"] = context_compaction["mandatory_traceability_refs"]

    return {
        "strategy": "context-compaction-broad-sweep",
        "reasoning_mode": EXECUTION_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": context_inputs,
        "context_usage": context_usage,
        "context_compaction": context_compaction,
        "recommendation": recommendation,
    }


def build_req_023_context_compaction_for_llm_call_budget(
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
    hard_constraints: list[Mapping[str, Any]] | None = None,
    llm_call_budget: Mapping[str, Any] | None = None,
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
    normalized_hard_constraints = _normalize_req_023_hard_constraints(hard_constraints)
    normalized_llm_call_budget = _normalize_req_023_llm_call_budget(llm_call_budget)

    canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    digest = _canonical_input_digest(canonical_input)
    canonical_processing_input = _canonical_req_023_processing_input(
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        hard_constraints=normalized_hard_constraints,
        llm_call_budget=normalized_llm_call_budget,
    )
    processing_digest = _canonical_input_digest(canonical_processing_input)
    processing_behavior = _build_req_023_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        hard_constraints=normalized_hard_constraints,
        llm_call_budget=normalized_llm_call_budget,
    )

    return {
        "schema_version": REQ_023_SCHEMA_VERSION,
        "requirement_id": REQ_023_REQUIREMENT_ID,
        "context_compaction_for_llm_call_budget": {
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
            "reproducible_call_id": f"req023-{digest[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_digest,
            "processing_call_id": f"req023-processing-{processing_digest[:16]}",
            "canonical_processing_input": canonical_processing_input,
        },
    }


def validate_req_023_context_compaction_for_llm_call_budget(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    top_keys = set(payload.keys())
    required_top = {
        "schema_version",
        "requirement_id",
        "context_compaction_for_llm_call_budget",
        "processing_behavior",
        "call_metadata",
    }
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_023_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_023_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_023_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_023_REQUIREMENT_ID}")

    compaction_surface = payload.get("context_compaction_for_llm_call_budget")
    if not isinstance(compaction_surface, Mapping):
        errors.append("context_compaction_for_llm_call_budget must be an object")
        return errors

    required_surface = {
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
    }
    surface_keys = set(compaction_surface.keys())
    missing_surface = sorted(required_surface - surface_keys)
    if missing_surface:
        errors.append(f"context_compaction_for_llm_call_budget missing keys: {missing_surface}")
    unexpected_surface = sorted(surface_keys - required_surface)
    if unexpected_surface:
        errors.append(f"context_compaction_for_llm_call_budget has unexpected keys: {unexpected_surface}")

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
        "context_compaction",
        "recommendation",
    }
    processing_keys = set(processing_behavior.keys())
    missing_processing = sorted(required_processing_behavior - processing_keys)
    if missing_processing:
        errors.append(f"processing_behavior missing keys: {missing_processing}")
    unexpected_processing = sorted(processing_keys - required_processing_behavior)
    if unexpected_processing:
        errors.append(f"processing_behavior has unexpected keys: {unexpected_processing}")

    context_compaction = processing_behavior.get("context_compaction")
    if not isinstance(context_compaction, Mapping):
        errors.append("processing_behavior.context_compaction must be an object")
        return errors
    compacted_packets = context_compaction.get("compacted_packets")
    if not isinstance(compacted_packets, list):
        errors.append("processing_behavior.context_compaction.compacted_packets must be a list")
        return errors
    coverage = context_compaction.get("coverage")
    if not isinstance(coverage, Mapping):
        errors.append("processing_behavior.context_compaction.coverage must be an object")
        return errors

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

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors

    try:
        normalized_target_root = _normalize_root(
            compaction_surface.get("target_project_root"),
            field_name="context_compaction_for_llm_call_budget.target_project_root",
        )
        normalized_earth_root = _normalize_root(
            compaction_surface.get("earth_root"),
            field_name="context_compaction_for_llm_call_budget.earth_root",
        )
        normalized_output_root = _normalize_root(
            compaction_surface.get("output_root"),
            field_name="context_compaction_for_llm_call_budget.output_root",
        )
        normalized_revision_identity = _require_nonempty_text(
            compaction_surface.get("revision_identity"),
            field_name="context_compaction_for_llm_call_budget.revision_identity",
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
        normalized_hard_constraints = _normalize_req_023_hard_constraints(
            context_inputs.get("hard_constraints")
        )
        normalized_llm_call_budget = _normalize_req_023_llm_call_budget(
            context_inputs.get("llm_call_budget")
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
    if metadata.get("canonical_input") != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized compaction anchors")

    expected_digest = _canonical_input_digest(expected_canonical_input)
    expected_call_id = f"req023-{expected_digest[:16]}"
    if metadata.get("canonical_input_sha256") != expected_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != expected_call_id:
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    expected_processing_behavior = _build_req_023_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        hard_constraints=normalized_hard_constraints,
        llm_call_budget=normalized_llm_call_budget,
    )
    if dict(processing_behavior) != expected_processing_behavior:
        errors.append("processing_behavior must mirror deterministic context compaction output")

    expected_canonical_processing_input = _canonical_req_023_processing_input(
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
        hard_constraints=normalized_hard_constraints,
        llm_call_budget=normalized_llm_call_budget,
    )
    if metadata.get("canonical_processing_input") != expected_canonical_processing_input:
        errors.append("call_metadata.canonical_processing_input must mirror normalized processing input")

    expected_processing_digest = _canonical_input_digest(expected_canonical_processing_input)
    expected_processing_call_id = f"req023-processing-{expected_processing_digest[:16]}"
    if metadata.get("processing_input_sha256") != expected_processing_digest:
        errors.append("call_metadata.processing_input_sha256 does not match processing input")
    if metadata.get("processing_call_id") != expected_processing_call_id:
        errors.append("call_metadata.processing_call_id does not match processing digest")

    expected_hard_constraint_ids = sorted(
        {str(row["constraint_id"]) for row in normalized_hard_constraints}
    )
    actual_hard_constraint_ids = coverage.get("hard_constraint_ids")
    actual_covered_hard_constraint_ids = coverage.get("covered_hard_constraint_ids")
    actual_uncovered_hard_constraint_ids = coverage.get("uncovered_hard_constraint_ids")
    if actual_hard_constraint_ids != expected_hard_constraint_ids:
        errors.append(
            "processing_behavior.context_compaction.coverage.hard_constraint_ids must mirror normalized hard constraints"
        )

    packet_hard_constraint_ids = sorted(
        {
            str(constraint_id)
            for packet in compacted_packets
            if isinstance(packet, Mapping)
            for constraint_id in list(packet.get("hard_constraint_ids", []))
        }
    )
    if actual_covered_hard_constraint_ids != packet_hard_constraint_ids:
        errors.append(
            "processing_behavior.context_compaction.coverage.covered_hard_constraint_ids must match packet hard_constraint_ids"
        )
    if expected_hard_constraint_ids and not compacted_packets:
        errors.append(
            "processing_behavior.context_compaction.compacted_packets must include at least one packet when hard_constraints are present"
        )
    if expected_hard_constraint_ids and actual_uncovered_hard_constraint_ids != []:
        errors.append(
            "processing_behavior.context_compaction.coverage.uncovered_hard_constraint_ids must be empty when hard_constraints are present"
        )
    if expected_hard_constraint_ids:
        for index, packet in enumerate(compacted_packets):
            if not isinstance(packet, Mapping):
                errors.append(
                    f"processing_behavior.context_compaction.compacted_packets[{index}] must be an object"
                )
                continue
            if packet.get("hard_constraint_ids") != expected_hard_constraint_ids:
                errors.append(
                    f"processing_behavior.context_compaction.compacted_packets[{index}].hard_constraint_ids must include every hard constraint"
                )

    return errors


def _normalize_nonnegative_int(raw_value: Any, *, field_name: str) -> int:
    if not isinstance(raw_value, int) or isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if raw_value < 0:
        raise ValueError(f"{field_name} must be greater than or equal to zero")
    return raw_value


def _normalize_storage_tier(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "standard"
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    value = raw_value.strip().lower()
    if value not in {"standard", "high-throughput"}:
        raise ValueError(f"{field_name} must be either 'standard' or 'high-throughput'")
    return value


def _normalize_model_tier(raw_value: Any, *, field_name: str) -> str:
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string")
    value = raw_value.strip().lower()
    if value not in {"fast", "balanced", "heavy"}:
        raise ValueError(f"{field_name} must be one of: fast, balanced, heavy")
    return value


def _normalize_optional_model_tier(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return ""
    return _normalize_model_tier(raw_value, field_name=field_name)


def _normalize_execution_resource_context(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError("execution_resource_context must be an object")

    hardware_profile = raw_value.get("hardware_profile")
    if not isinstance(hardware_profile, Mapping):
        raise ValueError("execution_resource_context.hardware_profile must be an object")
    rate_limits = raw_value.get("rate_limits")
    if not isinstance(rate_limits, Mapping):
        raise ValueError("execution_resource_context.rate_limits must be an object")
    runtime_budget = raw_value.get("runtime_budget")
    if not isinstance(runtime_budget, Mapping):
        raise ValueError("execution_resource_context.runtime_budget must be an object")

    model_inventory_raw = raw_value.get("model_inventory")
    if not isinstance(model_inventory_raw, list) or not model_inventory_raw:
        raise ValueError("execution_resource_context.model_inventory must be a non-empty list")

    normalized_hardware_profile = {
        "cpu_cores": _normalize_positive_int(
            hardware_profile.get("cpu_cores"),
            field_name="execution_resource_context.hardware_profile.cpu_cores",
        ),
        "memory_gb": _normalize_positive_int(
            hardware_profile.get("memory_gb"),
            field_name="execution_resource_context.hardware_profile.memory_gb",
        ),
        "gpu_count": _normalize_nonnegative_int(
            hardware_profile.get("gpu_count") if hardware_profile.get("gpu_count") is not None else 0,
            field_name="execution_resource_context.hardware_profile.gpu_count",
        ),
        "storage_tier": _normalize_storage_tier(
            hardware_profile.get("storage_tier"),
            field_name="execution_resource_context.hardware_profile.storage_tier",
        ),
        "evidence_refs": _normalize_string_list(
            hardware_profile.get("evidence_refs"),
            field_name="execution_resource_context.hardware_profile.evidence_refs",
        ),
    }

    daily_token_budget_raw = rate_limits.get("daily_token_budget")
    normalized_rate_limits = {
        "max_parallel_tasks": _normalize_positive_int(
            rate_limits.get("max_parallel_tasks"),
            field_name="execution_resource_context.rate_limits.max_parallel_tasks",
        ),
        "tokens_per_minute": _normalize_positive_int(
            rate_limits.get("tokens_per_minute"),
            field_name="execution_resource_context.rate_limits.tokens_per_minute",
        ),
        "requests_per_minute": _normalize_positive_int(
            rate_limits.get("requests_per_minute"),
            field_name="execution_resource_context.rate_limits.requests_per_minute",
        ),
        "daily_token_budget": (
            _normalize_positive_int(
                daily_token_budget_raw,
                field_name="execution_resource_context.rate_limits.daily_token_budget",
            )
            if daily_token_budget_raw is not None
            else 0
        ),
        "evidence_refs": _normalize_string_list(
            rate_limits.get("evidence_refs"),
            field_name="execution_resource_context.rate_limits.evidence_refs",
        ),
    }

    checkpoint_interval = runtime_budget.get("checkpoint_interval_minutes")
    normalized_runtime_budget = {
        "max_execution_minutes": _normalize_positive_int(
            runtime_budget.get("max_execution_minutes"),
            field_name="execution_resource_context.runtime_budget.max_execution_minutes",
        ),
        "checkpoint_interval_minutes": _normalize_positive_int(
            checkpoint_interval if checkpoint_interval is not None else 15,
            field_name="execution_resource_context.runtime_budget.checkpoint_interval_minutes",
        ),
        "evidence_refs": _normalize_string_list(
            runtime_budget.get("evidence_refs"),
            field_name="execution_resource_context.runtime_budget.evidence_refs",
        ),
    }

    normalized_model_inventory: list[dict[str, Any]] = []
    seen_model_ids: set[str] = set()
    for index, model in enumerate(model_inventory_raw):
        if not isinstance(model, Mapping):
            raise ValueError(f"execution_resource_context.model_inventory[{index}] must be an object")
        model_id = _require_nonempty_text(
            model.get("model_id"),
            field_name=f"execution_resource_context.model_inventory[{index}].model_id",
        )
        if model_id in seen_model_ids:
            raise ValueError(f"execution_resource_context.model_inventory[{index}].model_id must be unique")
        seen_model_ids.add(model_id)
        requests_cap = model.get("requests_per_minute_cap")
        normalized_model_inventory.append(
            {
                "model_id": model_id,
                "routing_tier": _normalize_model_tier(
                    model.get("routing_tier"),
                    field_name=f"execution_resource_context.model_inventory[{index}].routing_tier",
                ),
                "max_output_tokens": _normalize_positive_int(
                    model.get("max_output_tokens"),
                    field_name=f"execution_resource_context.model_inventory[{index}].max_output_tokens",
                ),
                "requests_per_minute_cap": (
                    _normalize_positive_int(
                        requests_cap,
                        field_name=f"execution_resource_context.model_inventory[{index}].requests_per_minute_cap",
                    )
                    if requests_cap is not None
                    else normalized_rate_limits["requests_per_minute"]
                ),
                "evidence_refs": _normalize_string_list(
                    model.get("evidence_refs"),
                    field_name=f"execution_resource_context.model_inventory[{index}].evidence_refs",
                ),
            }
        )

    normalized_model_inventory.sort(key=lambda row: (row["routing_tier"], row["model_id"]))
    return {
        "hardware_profile": normalized_hardware_profile,
        "rate_limits": normalized_rate_limits,
        "runtime_budget": normalized_runtime_budget,
        "model_inventory": normalized_model_inventory,
    }


def _normalize_execution_candidate_priority(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "medium"
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    value = raw_value.strip().lower()
    if value not in {"high", "medium", "low"}:
        raise ValueError(f"{field_name} must be one of: high, medium, low")
    return value


def _normalize_execution_candidate_complexity(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "medium"
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    value = raw_value.strip().lower()
    if value not in {"high", "medium", "low"}:
        raise ValueError(f"{field_name} must be one of: high, medium, low")
    return value


def _normalize_execution_candidates(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("execution_candidates must be a list")

    normalized: list[dict[str, Any]] = []
    seen_action_ids: set[str] = set()
    for index, row in enumerate(raw_value):
        if not isinstance(row, Mapping):
            raise ValueError(f"execution_candidates[{index}] must be an object")
        action_id = _require_nonempty_text(row.get("action_id"), field_name=f"execution_candidates[{index}].action_id")
        if action_id in seen_action_ids:
            raise ValueError(f"execution_candidates[{index}].action_id must be unique")
        seen_action_ids.add(action_id)

        complexity = _normalize_execution_candidate_complexity(
            row.get("complexity"),
            field_name=f"execution_candidates[{index}].complexity",
        )
        normalized.append(
            {
                "action_id": action_id,
                "summary": _require_nonempty_text(
                    row.get("summary"),
                    field_name=f"execution_candidates[{index}].summary",
                ),
                "priority": _normalize_execution_candidate_priority(
                    row.get("priority"),
                    field_name=f"execution_candidates[{index}].priority",
                ),
                "complexity": complexity,
                "estimated_token_cost": _normalize_positive_int(
                    row.get("estimated_token_cost") if row.get("estimated_token_cost") is not None else 1200,
                    field_name=f"execution_candidates[{index}].estimated_token_cost",
                ),
                "requires_gpu": bool(row.get("requires_gpu", complexity == "high")),
                "preferred_model_tier": _normalize_optional_model_tier(
                    row.get("preferred_model_tier"),
                    field_name=f"execution_candidates[{index}].preferred_model_tier",
                ),
                "evidence_refs": _normalize_string_list(
                    row.get("evidence_refs"),
                    field_name=f"execution_candidates[{index}].evidence_refs",
                ),
                "next_step": _require_nonempty_text(
                    row.get("next_step")
                    if row.get("next_step") is not None
                    else f"Execute '{action_id}' within resource-aware sequencing policy.",
                    field_name=f"execution_candidates[{index}].next_step",
                ),
            }
        )

    normalized.sort(key=lambda item: item["action_id"])
    return normalized


def _preferred_model_tier_for_complexity(complexity: str) -> str:
    return {"low": "fast", "medium": "balanced", "high": "heavy"}[complexity]


def _model_tier_fallback_order(preferred_tier: str) -> list[str]:
    if preferred_tier == "fast":
        return ["fast", "balanced", "heavy"]
    if preferred_tier == "balanced":
        return ["balanced", "fast", "heavy"]
    return ["heavy", "balanced", "fast"]


def _execution_priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}[priority]


def _execution_complexity_rank(complexity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}[complexity]


def _effective_parallel_slots(resource_context: Mapping[str, Any]) -> int:
    hardware_profile = resource_context["hardware_profile"]
    rate_limits = resource_context["rate_limits"]
    cpu_capacity = int(hardware_profile["cpu_cores"]) + int(hardware_profile["gpu_count"])
    return max(1, min(int(rate_limits["max_parallel_tasks"]), max(1, cpu_capacity)))


def _build_req_019_cross_project_context_summary(
    *,
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "cross_project": bool(cross_project_context),
        "projects_considered": [row["project_id"] for row in cross_project_context],
        "projects_with_evidence_refs": [row["project_id"] for row in cross_project_context if row["evidence_refs"]],
        "projects_without_evidence_refs": [row["project_id"] for row in cross_project_context if not row["evidence_refs"]],
        "earth_sweep_evidence_refs": list(earth_sweep_evidence_refs),
        "evidence_refs_by_project": {
            row["project_id"]: list(row["evidence_refs"])
            for row in cross_project_context
        },
    }


def _build_req_019_cross_project_recommendations(
    *,
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cross_project_obligations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    for row in cross_project_context:
        project_id = str(row["project_id"])
        project_refs = list(row["evidence_refs"])
        if not earth_sweep_evidence_refs:
            open_risks.append(
                {
                    "risk_id": f"risk-cross-project-earth-evidence-{project_id}",
                    "reason_code": "missing_earth_sweep_evidence_refs",
                    "summary": (
                        f"Cross-project execution-resource coordination for '{project_id}' remains unresolved "
                        "until Earth-sweep evidence refs are attached."
                    ),
                    "required_evidence_refs": project_refs,
                }
            )
            continue
        if not project_refs:
            open_risks.append(
                {
                    "risk_id": f"risk-cross-project-context-evidence-{project_id}",
                    "reason_code": "missing_cross_project_context_evidence_refs",
                    "summary": (
                        f"Cross-project execution-resource coordination for '{project_id}' remains unresolved "
                        "because project-specific evidence refs are missing."
                    ),
                    "required_evidence_refs": list(earth_sweep_evidence_refs),
                }
            )
            continue
        cross_project_obligations.append(
            {
                "obligation_id": f"obligation-resource-{project_id}",
                "project_id": project_id,
                "summary": (
                    f"Coordinate execution-resource sequencing and model-routing policy with '{project_id}' "
                    "before shared execution."
                ),
                "evidence_refs": _collect_unique_refs(earth_sweep_evidence_refs, project_refs),
            }
        )
    cross_project_obligations.sort(key=lambda row: (row["project_id"], row["obligation_id"]))
    open_risks.sort(key=lambda row: row["risk_id"])
    return cross_project_obligations, open_risks


def _route_models_for_execution_candidates(
    *,
    execution_candidates: list[dict[str, Any]],
    resource_context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    model_inventory = list(resource_context["model_inventory"])
    models_by_tier: dict[str, list[dict[str, Any]]] = {"fast": [], "balanced": [], "heavy": []}
    for model in model_inventory:
        models_by_tier[str(model["routing_tier"])].append(model)

    suggestions: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    routed_action_ids: set[str] = set()
    for candidate in execution_candidates:
        preferred_tier = candidate["preferred_model_tier"] or _preferred_model_tier_for_complexity(candidate["complexity"])
        fallback_tier_order = _model_tier_fallback_order(preferred_tier)
        selected_model: dict[str, Any] | None = None
        selected_tier = ""
        for tier in fallback_tier_order:
            tier_models = models_by_tier[tier]
            if tier_models:
                selected_model = tier_models[0]
                selected_tier = tier
                break

        if selected_model is None:
            open_risks.append(
                {
                    "risk_id": f"risk-model-route-{candidate['action_id']}",
                    "reason_code": "missing_model_route",
                    "summary": (
                        f"No model route available for action '{candidate['action_id']}' "
                        f"with preferred tier '{preferred_tier}'."
                    ),
                    "required_evidence_refs": candidate["evidence_refs"],
                }
            )
            continue

        routed_action_ids.add(candidate["action_id"])
        suggestions.append(
            {
                "action_id": candidate["action_id"],
                "preferred_model_tier": preferred_tier,
                "suggested_model_id": selected_model["model_id"],
                "suggested_model_tier": selected_tier,
                "fallback_tier_order": fallback_tier_order,
                "routing_reason": (
                    f"Matched complexity '{candidate['complexity']}' and priority '{candidate['priority']}' "
                    f"to tier '{selected_tier}'."
                ),
                "max_output_tokens": selected_model["max_output_tokens"],
                "requests_per_minute_cap": selected_model["requests_per_minute_cap"],
                "evidence_refs": _collect_unique_refs(candidate["evidence_refs"], selected_model["evidence_refs"]),
            }
        )

    suggestions.sort(key=lambda row: row["action_id"])
    open_risks.sort(key=lambda row: row["risk_id"])
    return suggestions, open_risks, routed_action_ids


def _canonical_req_019_processing_input(
    *,
    execution_resource_context: dict[str, Any],
    execution_candidates: list[dict[str, Any]],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "execution_resource_context": execution_resource_context,
        "execution_candidates": execution_candidates,
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
        "cross_project_context": cross_project_context,
    }


def _req_019_recommendation_decision(
    *,
    execution_candidates: list[dict[str, Any]],
    routed_action_ids: set[str],
    open_risks: list[dict[str, Any]],
) -> str:
    if not execution_candidates:
        return "insufficient-context"
    if not routed_action_ids and open_risks:
        return "resource-blocked"
    if open_risks:
        return "proceed-with-constraints"
    return "proceed"


def _req_019_recommendation_rationale(*, decision: str) -> str:
    if decision == "proceed":
        return "Resource context supports deterministic sequencing and model routing for all actions."
    if decision == "proceed-with-constraints":
        return "Resource context allows partial execution, but open risks must be tracked during scheduling."
    if decision == "resource-blocked":
        return "Resource context cannot route actionable work without violating model or runtime constraints."
    return "No execution candidates were provided for resource-aware sequencing."


def _build_req_019_processing_behavior(
    *,
    execution_resource_context: dict[str, Any],
    execution_candidates: list[dict[str, Any]],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
) -> dict[str, Any]:
    routing_suggestions, routing_risks, routed_action_ids = _route_models_for_execution_candidates(
        execution_candidates=execution_candidates,
        resource_context=execution_resource_context,
    )
    route_by_action = {row["action_id"]: row for row in routing_suggestions}
    cross_project_context_summary = _build_req_019_cross_project_context_summary(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
    )
    cross_project_obligations, cross_project_risks = _build_req_019_cross_project_recommendations(
        earth_sweep_evidence_refs=earth_sweep_evidence_refs,
        cross_project_context=cross_project_context,
    )

    hardware_profile = execution_resource_context["hardware_profile"]
    rate_limits = execution_resource_context["rate_limits"]
    runtime_budget = execution_resource_context["runtime_budget"]
    effective_parallel_slots = _effective_parallel_slots(execution_resource_context)
    total_estimated_token_cost = sum(int(row["estimated_token_cost"]) for row in execution_candidates)
    runtime_token_budget = int(rate_limits["tokens_per_minute"]) * int(runtime_budget["max_execution_minutes"])
    daily_token_budget = int(rate_limits["daily_token_budget"])

    open_risks = list(routing_risks)
    if total_estimated_token_cost > runtime_token_budget:
        open_risks.append(
            {
                "risk_id": "risk-runtime-token-budget-exceeded",
                "reason_code": "runtime_token_budget_exceeded",
                "summary": (
                    f"Estimated token cost {total_estimated_token_cost} exceeds runtime budget {runtime_token_budget}."
                ),
                "required_evidence_refs": _collect_unique_refs(*[row["evidence_refs"] for row in execution_candidates]),
            }
        )
    if daily_token_budget and total_estimated_token_cost > daily_token_budget:
        open_risks.append(
            {
                "risk_id": "risk-daily-token-budget-exceeded",
                "reason_code": "daily_token_budget_exceeded",
                "summary": (
                    f"Estimated token cost {total_estimated_token_cost} exceeds daily token budget {daily_token_budget}."
                ),
                "required_evidence_refs": _collect_unique_refs(*[row["evidence_refs"] for row in execution_candidates]),
            }
        )

    for candidate in execution_candidates:
        if candidate["requires_gpu"] and int(hardware_profile["gpu_count"]) == 0:
            open_risks.append(
                {
                    "risk_id": f"risk-gpu-required-{candidate['action_id']}",
                    "reason_code": "gpu_required_but_unavailable",
                    "summary": f"Action '{candidate['action_id']}' requires GPU resources, but gpu_count is zero.",
                    "required_evidence_refs": candidate["evidence_refs"],
                }
            )

    open_risks.extend(cross_project_risks)
    open_risks.sort(key=lambda row: row["risk_id"])
    ordered_candidates = sorted(
        execution_candidates,
        key=lambda row: (
            _execution_priority_rank(str(row["priority"])),
            _execution_complexity_rank(str(row["complexity"])),
            -int(row["estimated_token_cost"]),
            str(row["action_id"]),
        ),
    )

    sequencing_policy_suggestions: list[dict[str, Any]] = []
    for index, candidate in enumerate(ordered_candidates):
        action_id = candidate["action_id"]
        route = route_by_action.get(action_id)
        estimated_runtime_slice_minutes = (
            int(candidate["estimated_token_cost"]) + int(rate_limits["tokens_per_minute"]) - 1
        ) // int(rate_limits["tokens_per_minute"])
        sequencing_policy_suggestions.append(
            {
                "sequence_index": index + 1,
                "execution_batch": (index // effective_parallel_slots) + 1,
                "action_id": action_id,
                "summary": candidate["summary"],
                "priority": candidate["priority"],
                "complexity": candidate["complexity"],
                "estimated_token_cost": candidate["estimated_token_cost"],
                "estimated_runtime_slice_minutes": max(1, estimated_runtime_slice_minutes),
                "routing_status": "routed" if route else "unrouted",
                "suggested_model_id": route["suggested_model_id"] if route else "",
                "suggested_model_tier": route["suggested_model_tier"] if route else "",
                "next_step": candidate["next_step"],
                "sequencing_rationale": (
                    f"Placed using effective_parallel_slots={effective_parallel_slots} under "
                    f"max_parallel_tasks={rate_limits['max_parallel_tasks']} and "
                    f"cpu_cores={hardware_profile['cpu_cores']}."
                ),
                "evidence_refs": _collect_unique_refs(
                    candidate["evidence_refs"],
                    route["evidence_refs"] if route else [],
                ),
            }
        )

    evidence_refs = _collect_unique_refs(
        hardware_profile["evidence_refs"],
        rate_limits["evidence_refs"],
        runtime_budget["evidence_refs"],
        earth_sweep_evidence_refs,
        *[row["evidence_refs"] for row in cross_project_context],
        *[row["evidence_refs"] for row in execution_resource_context["model_inventory"]],
        *[row["evidence_refs"] for row in execution_candidates],
        *[row["evidence_refs"] for row in routing_suggestions],
        *[row["evidence_refs"] for row in sequencing_policy_suggestions],
        *[row["evidence_refs"] for row in cross_project_obligations],
        *[row["required_evidence_refs"] for row in open_risks],
    )
    decision = _req_019_recommendation_decision(
        execution_candidates=execution_candidates,
        routed_action_ids=routed_action_ids,
        open_risks=open_risks,
    )

    context_inputs = {
        "execution_resource_context": execution_resource_context,
        "execution_candidates": execution_candidates,
        "broad_sweep_context": {
            "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
            "cross_project_context": cross_project_context,
        },
    }
    context_usage = {
        "resource_context_used": True,
        "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
        "cross_project_context_used": bool(cross_project_context),
        "cpu_cores_used": hardware_profile["cpu_cores"],
        "gpu_count_used": hardware_profile["gpu_count"],
        "max_parallel_tasks_used": rate_limits["max_parallel_tasks"],
        "effective_parallel_slots_used": effective_parallel_slots,
        "tokens_per_minute_used": rate_limits["tokens_per_minute"],
        "runtime_token_budget_used": runtime_token_budget,
        "daily_token_budget_used": daily_token_budget,
        "model_inventory_ids_used": [row["model_id"] for row in execution_resource_context["model_inventory"]],
        "execution_candidate_ids_used": [row["action_id"] for row in execution_candidates],
        "routed_action_ids_used": sorted(routed_action_ids),
        "cross_project_projects_considered": cross_project_context_summary["projects_considered"],
        "cross_project_projects_with_evidence_refs": cross_project_context_summary["projects_with_evidence_refs"],
        "cross_project_projects_without_evidence_refs": cross_project_context_summary["projects_without_evidence_refs"],
        "earth_sweep_evidence_refs_used": list(earth_sweep_evidence_refs),
        "sequencing_batch_count": max([row["execution_batch"] for row in sequencing_policy_suggestions], default=0),
        "total_estimated_token_cost": total_estimated_token_cost,
        "evidence_refs_used": evidence_refs,
    }

    recommendation = {
        "decision": decision,
        "rationale": _req_019_recommendation_rationale(decision=decision),
        "confidence": _recommendation_confidence(evidence_refs=evidence_refs, open_risks=open_risks),
        "evidence_refs": evidence_refs,
        "sequencing_policy_suggestions": sequencing_policy_suggestions,
        "model_routing_policy_suggestions": routing_suggestions,
        "cross_project_context": cross_project_context_summary,
        "cross_project_obligations": cross_project_obligations,
        "open_risks": open_risks,
    }
    return {
        "strategy": "execution-resource-aware-sequencing",
        "reasoning_mode": EXECUTION_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": context_inputs,
        "context_usage": context_usage,
        "recommendation": recommendation,
    }


def build_req_019_execution_resource_context_ingestion(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
    execution_resource_context: Mapping[str, Any],
    execution_candidates: list[Mapping[str, Any]] | None = None,
    earth_sweep_evidence_refs: list[str] | None = None,
    cross_project_context: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_target_root = _normalize_root(target_project_root, field_name="target_project_root")
    normalized_earth_root = _normalize_root(earth_root, field_name="earth_root")
    normalized_output_root = _normalize_root(output_root, field_name="output_root")
    normalized_revision_identity = _require_nonempty_text(revision_identity, field_name="revision_identity")
    normalized_execution_resource_context = _normalize_execution_resource_context(execution_resource_context)
    normalized_execution_candidates = _normalize_execution_candidates(execution_candidates)
    normalized_earth_sweep_evidence_refs = _normalize_string_list(
        earth_sweep_evidence_refs,
        field_name="earth_sweep_evidence_refs",
    )
    normalized_cross_project_context = _normalize_cross_project_context(cross_project_context)

    canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    digest = _canonical_input_digest(canonical_input)
    canonical_processing_input = _canonical_req_019_processing_input(
        execution_resource_context=normalized_execution_resource_context,
        execution_candidates=normalized_execution_candidates,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
    )
    processing_digest = _canonical_input_digest(canonical_processing_input)
    processing_behavior = _build_req_019_processing_behavior(
        execution_resource_context=normalized_execution_resource_context,
        execution_candidates=normalized_execution_candidates,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
    )

    return {
        "schema_version": REQ_019_SCHEMA_VERSION,
        "requirement_id": REQ_019_REQUIREMENT_ID,
        "execution_resource_context_ingestion": {
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
            "resource_context": normalized_execution_resource_context,
        },
        "processing_behavior": processing_behavior,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": digest,
            "reproducible_call_id": f"req019-{digest[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_digest,
            "processing_call_id": f"req019-processing-{processing_digest[:16]}",
            "canonical_processing_input": canonical_processing_input,
        },
    }


def validate_req_019_execution_resource_context_ingestion(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    top_keys = set(payload.keys())
    required_top = {
        "schema_version",
        "requirement_id",
        "execution_resource_context_ingestion",
        "processing_behavior",
        "call_metadata",
    }
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_019_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_019_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_019_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_019_REQUIREMENT_ID}")

    ingestion = payload.get("execution_resource_context_ingestion")
    if not isinstance(ingestion, Mapping):
        errors.append("execution_resource_context_ingestion must be an object")
        return errors

    required_ingestion = {
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "resource_context",
    }
    ingestion_keys = set(ingestion.keys())
    missing_ingestion = sorted(required_ingestion - ingestion_keys)
    if missing_ingestion:
        errors.append(f"execution_resource_context_ingestion missing keys: {missing_ingestion}")
    unexpected_ingestion = sorted(ingestion_keys - required_ingestion)
    if unexpected_ingestion:
        errors.append(f"execution_resource_context_ingestion has unexpected keys: {unexpected_ingestion}")

    if ingestion.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"runtime_mode must be {RUNTIME_MODE}")
    if ingestion.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"execution_mode must be {EXECUTION_MODE}")

    for root_field in ("target_project_root", "earth_root", "output_root"):
        value = ingestion.get(root_field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{root_field} must be non-empty string")
        elif not value.startswith("/"):
            errors.append(f"{root_field} must be absolute path")

    revision_identity = ingestion.get("revision_identity")
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

    if processing_behavior.get("strategy") != "execution-resource-aware-sequencing":
        errors.append("processing_behavior.strategy must be execution-resource-aware-sequencing")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    context_inputs = processing_behavior.get("context_inputs")
    if not isinstance(context_inputs, Mapping):
        errors.append("processing_behavior.context_inputs must be an object")
        return errors
    for required_field in ("execution_resource_context", "execution_candidates", "broad_sweep_context"):
        if required_field not in context_inputs:
            errors.append(f"processing_behavior.context_inputs missing {required_field}")

    context_usage = processing_behavior.get("context_usage")
    if not isinstance(context_usage, Mapping):
        errors.append("processing_behavior.context_usage must be an object")
    else:
        for required_field in (
            "resource_context_used",
            "earth_sweep_context_used",
            "cross_project_context_used",
            "cpu_cores_used",
            "gpu_count_used",
            "max_parallel_tasks_used",
            "effective_parallel_slots_used",
            "tokens_per_minute_used",
            "runtime_token_budget_used",
            "daily_token_budget_used",
            "model_inventory_ids_used",
            "execution_candidate_ids_used",
            "routed_action_ids_used",
            "cross_project_projects_considered",
            "cross_project_projects_with_evidence_refs",
            "cross_project_projects_without_evidence_refs",
            "earth_sweep_evidence_refs_used",
            "sequencing_batch_count",
            "total_estimated_token_cost",
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
            "sequencing_policy_suggestions",
            "model_routing_policy_suggestions",
            "cross_project_context",
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
        normalized_target_root = _normalize_root(
            ingestion.get("target_project_root"),
            field_name="execution_resource_context_ingestion.target_project_root",
        )
        normalized_earth_root = _normalize_root(
            ingestion.get("earth_root"),
            field_name="execution_resource_context_ingestion.earth_root",
        )
        normalized_output_root = _normalize_root(
            ingestion.get("output_root"),
            field_name="execution_resource_context_ingestion.output_root",
        )
        normalized_revision_identity = _require_nonempty_text(
            ingestion.get("revision_identity"),
            field_name="execution_resource_context_ingestion.revision_identity",
        )
        normalized_resource_context = _normalize_execution_resource_context(ingestion.get("resource_context"))
        normalized_execution_candidates = _normalize_execution_candidates(context_inputs.get("execution_candidates"))
        broad_sweep_context = context_inputs.get("broad_sweep_context")
        if not isinstance(broad_sweep_context, Mapping):
            raise ValueError("processing_behavior.context_inputs.broad_sweep_context must be an object")
        normalized_earth_sweep_evidence_refs = _normalize_string_list(
            broad_sweep_context.get("earth_sweep_evidence_refs"),
            field_name="processing_behavior.context_inputs.broad_sweep_context.earth_sweep_evidence_refs",
        )
        normalized_cross_project_context = _normalize_cross_project_context(
            broad_sweep_context.get("cross_project_context")
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
        errors.append("call_metadata.canonical_input must mirror normalized ingestion anchors")

    expected_digest = _canonical_input_digest(expected_canonical_input)
    expected_call_id = f"req019-{expected_digest[:16]}"
    if metadata.get("canonical_input_sha256") != expected_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != expected_call_id:
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    expected_processing_behavior = _build_req_019_processing_behavior(
        execution_resource_context=normalized_resource_context,
        execution_candidates=normalized_execution_candidates,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
    )
    if dict(processing_behavior) != expected_processing_behavior:
        errors.append("processing_behavior must mirror deterministic resource-aware processing output")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors

    expected_canonical_processing_input = _canonical_req_019_processing_input(
        execution_resource_context=normalized_resource_context,
        execution_candidates=normalized_execution_candidates,
        earth_sweep_evidence_refs=normalized_earth_sweep_evidence_refs,
        cross_project_context=normalized_cross_project_context,
    )
    if dict(canonical_processing_input) != expected_canonical_processing_input:
        errors.append("call_metadata.canonical_processing_input must mirror normalized processing input")

    expected_processing_digest = _canonical_input_digest(expected_canonical_processing_input)
    expected_processing_call_id = f"req019-processing-{expected_processing_digest[:16]}"
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


def _normalize_req_020_timestamp(raw_value: Any, *, field_name: str, allow_empty: bool) -> str:
    if raw_value is None:
        if allow_empty:
            return ""
        raise ValueError(f"{field_name} must be provided")
    if allow_empty and isinstance(raw_value, str) and not raw_value.strip():
        return ""
    text = _require_nonempty_text(raw_value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp: {exc}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_req_020_source(raw_value: Any, *, field_name: str) -> str:
    source = _require_nonempty_text(raw_value, field_name=field_name).strip().lower().replace("-", "_")
    source = REQ_020_SOURCE_ALIASES.get(source, source)
    if source not in REQ_020_ALLOWED_SOURCES:
        raise ValueError(f"{field_name} must be one of: {sorted(REQ_020_ALLOWED_SOURCES)}")
    return source


def _normalize_req_020_reason_code(
    raw_value: Any,
    *,
    field_name: str,
    signal_source: str,
) -> tuple[str, str]:
    if raw_value is None:
        default_reason = REQ_020_DEFAULT_REASON_CODE_BY_SOURCE[signal_source]
        return default_reason, default_reason
    source_reason_code = _require_nonempty_text(raw_value, field_name=field_name).lower().replace("-", "_")
    normalized_reason_code = REQ_020_REASON_CODE_ALIASES.get(source_reason_code, source_reason_code)
    return normalized_reason_code, source_reason_code


def _normalize_req_020_severity(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "medium"
    severity = _require_nonempty_text(raw_value, field_name=field_name).strip().lower()
    if severity not in REQ_020_ALLOWED_SEVERITIES:
        raise ValueError(f"{field_name} must be one of: {sorted(REQ_020_ALLOWED_SEVERITIES)}")
    return severity


def _normalize_req_020_occurrence_count(raw_value: Any, *, field_name: str) -> int:
    if raw_value is None:
        return 1
    if isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be a positive integer")
    if isinstance(raw_value, int):
        if raw_value <= 0:
            raise ValueError(f"{field_name} must be a positive integer")
        return raw_value
    if isinstance(raw_value, float):
        if raw_value <= 0 or not raw_value.is_integer():
            raise ValueError(f"{field_name} must be a positive integer")
        return int(raw_value)
    raise ValueError(f"{field_name} must be a positive integer")


def _normalize_req_020_signal_rows(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        raise ValueError("risk_signals must be a list")
    if not isinstance(raw_value, list):
        raise ValueError("risk_signals must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"risk_signals[{index}] must be an object")
        signal_source = _normalize_req_020_source(
            item.get("signal_source"),
            field_name=f"risk_signals[{index}].signal_source",
        )
        reason_code, source_reason_code = _normalize_req_020_reason_code(
            item.get("reason_code"),
            field_name=f"risk_signals[{index}].reason_code",
            signal_source=signal_source,
        )
        explicit_source_reason_code = item.get("source_reason_code")
        if explicit_source_reason_code is not None:
            source_reason_code = _require_nonempty_text(
                explicit_source_reason_code,
                field_name=f"risk_signals[{index}].source_reason_code",
            ).lower().replace("-", "_")
        summary = _require_nonempty_text(
            item.get("summary"),
            field_name=f"risk_signals[{index}].summary",
        )
        severity = _normalize_req_020_severity(
            item.get("severity"),
            field_name=f"risk_signals[{index}].severity",
        )
        occurrence_count = _normalize_req_020_occurrence_count(
            item.get("occurrence_count"),
            field_name=f"risk_signals[{index}].occurrence_count",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"risk_signals[{index}].evidence_refs",
        )
        first_observed_at_utc = _normalize_req_020_timestamp(
            item.get("first_observed_at_utc"),
            field_name=f"risk_signals[{index}].first_observed_at_utc",
            allow_empty=True,
        )
        last_observed_at_utc = _normalize_req_020_timestamp(
            item.get("last_observed_at_utc"),
            field_name=f"risk_signals[{index}].last_observed_at_utc",
            allow_empty=True,
        )
        if first_observed_at_utc and last_observed_at_utc and first_observed_at_utc > last_observed_at_utc:
            raise ValueError(
                f"risk_signals[{index}] first_observed_at_utc must be <= last_observed_at_utc"
            )

        normalized.append(
            {
                "signal_source": signal_source,
                "reason_code": reason_code,
                "source_reason_code": source_reason_code,
                "summary": summary,
                "severity": severity,
                "occurrence_count": occurrence_count,
                "evidence_refs": evidence_refs,
                "first_observed_at_utc": first_observed_at_utc,
                "last_observed_at_utc": last_observed_at_utc,
            }
        )

    if not normalized:
        raise ValueError("risk_signals must contain at least one signal")

    normalized.sort(
        key=lambda row: (
            row["signal_source"],
            row["reason_code"],
            row["summary"],
            row["severity"],
            row["occurrence_count"],
            row["first_observed_at_utc"],
            row["last_observed_at_utc"],
            tuple(row["evidence_refs"]),
        )
    )
    return normalized


def _select_req_020_earliest(*timestamps: str) -> str:
    values = [value for value in timestamps if value]
    if not values:
        return ""
    return min(values)


def _select_req_020_latest(*timestamps: str) -> str:
    values = [value for value in timestamps if value]
    if not values:
        return ""
    return max(values)


def _build_req_020_aggregate_signals(
    normalized_input_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    alias_pairs: set[tuple[str, str]] = set()
    for row in normalized_input_rows:
        key = (row["signal_source"], row["reason_code"], row["summary"])
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = {
                "signal_source": row["signal_source"],
                "reason_code": row["reason_code"],
                "summary": row["summary"],
                "severity": row["severity"],
                "occurrence_count": row["occurrence_count"],
                "evidence_refs": set(row["evidence_refs"]),
                "first_observed_at_utc": row["first_observed_at_utc"],
                "last_observed_at_utc": row["last_observed_at_utc"],
                "source_reason_codes": {row["source_reason_code"]},
            }
        else:
            if REQ_020_SEVERITY_ORDER[row["severity"]] > REQ_020_SEVERITY_ORDER[existing["severity"]]:
                existing["severity"] = row["severity"]
            existing["occurrence_count"] += row["occurrence_count"]
            existing["evidence_refs"].update(row["evidence_refs"])
            existing["first_observed_at_utc"] = _select_req_020_earliest(
                existing["first_observed_at_utc"],
                row["first_observed_at_utc"],
            )
            existing["last_observed_at_utc"] = _select_req_020_latest(
                existing["last_observed_at_utc"],
                row["last_observed_at_utc"],
            )
            existing["source_reason_codes"].add(row["source_reason_code"])

        if row["source_reason_code"] != row["reason_code"]:
            alias_pairs.add((row["source_reason_code"], row["reason_code"]))

    normalized_signals: list[dict[str, Any]] = []
    for signal_source, reason_code, summary in sorted(by_key.keys()):
        aggregate = by_key[(signal_source, reason_code, summary)]
        normalized_signals.append(
            {
                "normalized_signal_id": (
                    "risk-signal."
                    f"{_stable_id_fragment(signal_source, reason_code, summary)}"
                ),
                "signal_source": signal_source,
                "reason_code": reason_code,
                "source_reason_codes": sorted(aggregate["source_reason_codes"]),
                "summary": summary,
                "severity": aggregate["severity"],
                "occurrence_count": aggregate["occurrence_count"],
                "evidence_refs": sorted(aggregate["evidence_refs"]),
                "first_observed_at_utc": aggregate["first_observed_at_utc"],
                "last_observed_at_utc": aggregate["last_observed_at_utc"],
            }
        )

    alias_rows = [
        {
            "source_reason_code": source_reason_code,
            "normalized_reason_code": normalized_reason_code,
        }
        for source_reason_code, normalized_reason_code in sorted(alias_pairs)
    ]
    return normalized_signals, alias_rows


def _build_req_020_summary(normalized_signals: list[dict[str, Any]], total_input_signals: int) -> dict[str, Any]:
    source_counts = {source: 0 for source in sorted(REQ_020_ALLOWED_SOURCES)}
    severity_counts = {severity: 0 for severity in sorted(REQ_020_ALLOWED_SEVERITIES)}
    for row in normalized_signals:
        source_counts[row["signal_source"]] += 1
        severity_counts[row["severity"]] += 1
    return {
        "total_input_signals": total_input_signals,
        "total_normalized_signals": len(normalized_signals),
        "source_counts": source_counts,
        "severity_counts": severity_counts,
    }


def _derive_req_020_normalized_at_utc(normalized_input_rows: list[dict[str, Any]]) -> str:
    observed_timestamps = [
        timestamp
        for row in normalized_input_rows
        for timestamp in (row["first_observed_at_utc"], row["last_observed_at_utc"])
        if timestamp
    ]
    if observed_timestamps:
        return max(observed_timestamps)
    return REQ_020_FALLBACK_NORMALIZED_AT_UTC


def build_req_020_risk_signal_normalization(
    *,
    risk_signals: list[Mapping[str, Any]],
    normalized_at_utc: str | None = None,
) -> dict[str, Any]:
    normalized_input_rows = _normalize_req_020_signal_rows(risk_signals)
    if normalized_at_utc is None:
        normalized_timestamp = _derive_req_020_normalized_at_utc(normalized_input_rows)
    else:
        normalized_timestamp = _normalize_req_020_timestamp(
            normalized_at_utc,
            field_name="normalized_at_utc",
            allow_empty=False,
        )
    normalized_signals, alias_rows = _build_req_020_aggregate_signals(normalized_input_rows)
    reason_codes = sorted({row["reason_code"] for row in normalized_signals})
    taxonomy = {
        "compatibility_target": "gate_review_reason_codes",
        "canonical_reason_codes": reason_codes,
        "source_reason_code_aliases_applied": alias_rows,
    }

    canonical_input = {
        "risk_signals": normalized_input_rows,
        "normalized_at_utc": normalized_timestamp,
    }
    digest = _canonical_input_digest(canonical_input)
    return {
        "schema_version": REQ_020_SCHEMA_VERSION,
        "requirement_id": REQ_020_REQUIREMENT_ID,
        "analysis_anchors": list(REQ_020_ANALYSIS_ANCHORS),
        "risk_signal_normalization": {
            "normalized_at_utc": normalized_timestamp,
            "signals": normalized_signals,
            "reason_code_taxonomy": taxonomy,
            "summary": _build_req_020_summary(
                normalized_signals=normalized_signals,
                total_input_signals=len(normalized_input_rows),
            ),
        },
        "source": {
            "tool": REQ_020_TOOL,
            "tool_version": REQ_020_TOOL_VERSION,
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": digest,
            "reproducible_call_id": f"req020-{digest[:16]}",
            "canonical_input": canonical_input,
        },
    }


def validate_req_020_risk_signal_normalization(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "schema_version",
        "requirement_id",
        "analysis_anchors",
        "risk_signal_normalization",
        "source",
        "call_metadata",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_020_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_020_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_020_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_020_REQUIREMENT_ID}")

    analysis_anchors = payload.get("analysis_anchors")
    if analysis_anchors != REQ_020_ANALYSIS_ANCHORS:
        errors.append("analysis_anchors must match REQ-020 anchor order")

    normalization = payload.get("risk_signal_normalization")
    if not isinstance(normalization, Mapping):
        errors.append("risk_signal_normalization must be an object")
        return errors

    normalized_at_utc = normalization.get("normalized_at_utc")
    try:
        _normalize_req_020_timestamp(
            normalized_at_utc,
            field_name="risk_signal_normalization.normalized_at_utc",
            allow_empty=False,
        )
    except ValueError as exc:
        errors.append(str(exc))

    signals = normalization.get("signals")
    if not isinstance(signals, list):
        errors.append("risk_signal_normalization.signals must be a list")
    elif not signals:
        errors.append("risk_signal_normalization.signals must contain at least one signal")
    else:
        for index, row in enumerate(signals):
            if not isinstance(row, Mapping):
                errors.append(f"risk_signal_normalization.signals[{index}] must be an object")
                continue
            for field_name in (
                "normalized_signal_id",
                "signal_source",
                "reason_code",
                "source_reason_codes",
                "summary",
                "severity",
                "occurrence_count",
                "evidence_refs",
                "first_observed_at_utc",
                "last_observed_at_utc",
            ):
                if field_name not in row:
                    errors.append(f"risk_signal_normalization.signals[{index}] missing {field_name}")

            signal_source = row.get("signal_source")
            if signal_source not in REQ_020_ALLOWED_SOURCES:
                errors.append(
                    f"risk_signal_normalization.signals[{index}].signal_source must be one of {sorted(REQ_020_ALLOWED_SOURCES)}"
                )

            severity = row.get("severity")
            if severity not in REQ_020_ALLOWED_SEVERITIES:
                errors.append(
                    f"risk_signal_normalization.signals[{index}].severity must be one of {sorted(REQ_020_ALLOWED_SEVERITIES)}"
                )

            occurrence_count = row.get("occurrence_count")
            if not isinstance(occurrence_count, int) or occurrence_count <= 0:
                errors.append(
                    f"risk_signal_normalization.signals[{index}].occurrence_count must be a positive integer"
                )

            source_reason_codes = row.get("source_reason_codes")
            if not isinstance(source_reason_codes, list) or not source_reason_codes:
                errors.append(f"risk_signal_normalization.signals[{index}].source_reason_codes must be a non-empty list")
            else:
                for reason_index, source_reason_code in enumerate(source_reason_codes):
                    if not isinstance(source_reason_code, str) or not source_reason_code.strip():
                        errors.append(
                            "risk_signal_normalization.signals"
                            f"[{index}].source_reason_codes[{reason_index}] must be a non-empty string"
                        )

            evidence_refs = row.get("evidence_refs")
            if not isinstance(evidence_refs, list):
                errors.append(f"risk_signal_normalization.signals[{index}].evidence_refs must be a list")
            else:
                for evidence_index, evidence_ref in enumerate(evidence_refs):
                    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
                        errors.append(
                            f"risk_signal_normalization.signals[{index}].evidence_refs[{evidence_index}] must be a non-empty string"
                        )

            for field_name in ("first_observed_at_utc", "last_observed_at_utc"):
                try:
                    _normalize_req_020_timestamp(
                        row.get(field_name),
                        field_name=f"risk_signal_normalization.signals[{index}].{field_name}",
                        allow_empty=True,
                    )
                except ValueError as exc:
                    errors.append(str(exc))

    taxonomy = normalization.get("reason_code_taxonomy")
    if not isinstance(taxonomy, Mapping):
        errors.append("risk_signal_normalization.reason_code_taxonomy must be an object")
    else:
        if taxonomy.get("compatibility_target") != "gate_review_reason_codes":
            errors.append("risk_signal_normalization.reason_code_taxonomy.compatibility_target must be gate_review_reason_codes")
        canonical_reason_codes = taxonomy.get("canonical_reason_codes")
        if not isinstance(canonical_reason_codes, list):
            errors.append("risk_signal_normalization.reason_code_taxonomy.canonical_reason_codes must be a list")
        alias_rows = taxonomy.get("source_reason_code_aliases_applied")
        if not isinstance(alias_rows, list):
            errors.append("risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied must be a list")
        else:
            for index, row in enumerate(alias_rows):
                if not isinstance(row, Mapping):
                    errors.append(
                        "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied"
                        f"[{index}] must be an object"
                    )
                    continue
                source_reason_field = (
                    "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied"
                    f"[{index}].source_reason_code"
                )
                normalized_reason_field = (
                    "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied"
                    f"[{index}].normalized_reason_code"
                )
                try:
                    source_reason_code = _normalize_context_note(
                        row.get("source_reason_code"),
                        field_name=source_reason_field,
                    )
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if not source_reason_code:
                        errors.append(
                            "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied"
                            f"[{index}].source_reason_code must be a non-empty string"
                        )
                try:
                    normalized_reason_code = _normalize_context_note(
                        row.get("normalized_reason_code"),
                        field_name=normalized_reason_field,
                    )
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if not normalized_reason_code:
                        errors.append(
                            "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied"
                            f"[{index}].normalized_reason_code must be a non-empty string"
                        )

    summary = normalization.get("summary")
    if not isinstance(summary, Mapping):
        errors.append("risk_signal_normalization.summary must be an object")
    else:
        for field_name in ("total_input_signals", "total_normalized_signals", "source_counts", "severity_counts"):
            if field_name not in summary:
                errors.append(f"risk_signal_normalization.summary missing {field_name}")

    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
    else:
        if source.get("tool") != REQ_020_TOOL:
            errors.append(f"source.tool must be {REQ_020_TOOL}")
        if source.get("tool_version") != REQ_020_TOOL_VERSION:
            errors.append(f"source.tool_version must be {REQ_020_TOOL_VERSION}")

    call_metadata = payload.get("call_metadata")
    if not isinstance(call_metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors
    for field_name in ("reproducibility", "canonical_input_sha256", "reproducible_call_id", "canonical_input"):
        if field_name not in call_metadata:
            errors.append(f"call_metadata missing {field_name}")

    canonical_input = call_metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
        return errors

    if errors:
        return errors

    try:
        rebuilt = build_req_020_risk_signal_normalization(
            risk_signals=list(canonical_input.get("risk_signals", [])),
            normalized_at_utc=canonical_input.get("normalized_at_utc"),
        )
    except ValueError as exc:
        errors.append(f"call_metadata.canonical_input is invalid: {exc}")
        return errors

    if dict(payload) != rebuilt:
        errors.append("payload must mirror deterministic REQ-020 normalization output")

    return errors


def _normalize_req_024_timestamp(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return REQ_024_FALLBACK_BUNDLE_GENERATED_AT_UTC
    return _normalize_req_020_timestamp(raw_value, field_name=field_name, allow_empty=False)


def _normalize_req_024_json_value(raw_value: Any, *, field_name: str) -> Any:
    try:
        canonical_json = json.dumps(raw_value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except TypeError as exc:
        raise ValueError(f"{field_name} must be JSON-serializable: {exc}") from exc
    return json.loads(canonical_json)


def _normalize_req_024_strategy_runtime_entrypoint(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError("strategy_context.strategy_runtime_entrypoint must be an object")

    normalized = _normalize_req_024_json_value(
        raw_value,
        field_name="strategy_context.strategy_runtime_entrypoint",
    )
    if not isinstance(normalized, dict) or not normalized:
        raise ValueError("strategy_context.strategy_runtime_entrypoint must include at least one key")

    for field_name in ("runtime_mode", "execution_mode", "revision_identity"):
        if field_name in normalized:
            normalized[field_name] = _require_nonempty_text(
                normalized.get(field_name),
                field_name=f"strategy_context.strategy_runtime_entrypoint.{field_name}",
            )

    for field_name in ("target_project_root", "earth_root", "output_root"):
        if field_name in normalized:
            normalized[field_name] = _normalize_root(
                normalized.get(field_name),
                field_name=f"strategy_context.strategy_runtime_entrypoint.{field_name}",
            )

    return normalized


def _normalize_req_024_context_inputs(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError("strategy_context.processing_behavior.context_inputs must be an object")

    target_project = raw_value.get("target_project")
    if not isinstance(target_project, Mapping):
        raise ValueError("strategy_context.processing_behavior.context_inputs.target_project must be an object")
    normalized_target_project = {
        "project_root": _normalize_root(
            target_project.get("project_root"),
            field_name="strategy_context.processing_behavior.context_inputs.target_project.project_root",
        ),
        "evidence_refs": _normalize_string_list(
            target_project.get("evidence_refs"),
            field_name="strategy_context.processing_behavior.context_inputs.target_project.evidence_refs",
        ),
    }

    earth_sweep = raw_value.get("earth_sweep")
    if not isinstance(earth_sweep, Mapping):
        raise ValueError("strategy_context.processing_behavior.context_inputs.earth_sweep must be an object")
    normalized_earth_sweep = {
        "earth_root": _normalize_root(
            earth_sweep.get("earth_root"),
            field_name="strategy_context.processing_behavior.context_inputs.earth_sweep.earth_root",
        ),
        "evidence_refs": _normalize_string_list(
            earth_sweep.get("evidence_refs"),
            field_name="strategy_context.processing_behavior.context_inputs.earth_sweep.evidence_refs",
        ),
    }

    normalized_cross_project_context = _normalize_cross_project_context(raw_value.get("cross_project_context"))
    normalized_candidate_recommendations = _normalize_candidate_recommendations(raw_value.get("candidate_recommendations"))
    normalized_earth_sweep_source_artifacts = _normalize_earth_sweep_source_artifacts(
        raw_value.get("earth_sweep_source_artifacts")
    )
    normalized_required_context_documents = _normalize_required_context_documents(
        raw_value.get("required_context_documents")
    )

    normalized = {
        "target_project": normalized_target_project,
        "earth_sweep": normalized_earth_sweep,
        "cross_project_context": normalized_cross_project_context,
        "candidate_recommendations": normalized_candidate_recommendations,
    }
    if normalized_earth_sweep_source_artifacts:
        normalized["earth_sweep_source_artifacts"] = normalized_earth_sweep_source_artifacts
    if normalized_required_context_documents:
        normalized["required_context_documents"] = normalized_required_context_documents
    return normalized


def _normalize_req_024_processing_behavior(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError("strategy_context.processing_behavior must be an object")

    normalized_context_inputs = _normalize_req_024_context_inputs(raw_value.get("context_inputs"))
    return _build_processing_behavior(
        target_project_root=normalized_context_inputs["target_project"]["project_root"],
        earth_root=normalized_context_inputs["earth_sweep"]["earth_root"],
        target_project_evidence_refs=list(normalized_context_inputs["target_project"]["evidence_refs"]),
        earth_sweep_evidence_refs=list(normalized_context_inputs["earth_sweep"]["evidence_refs"]),
        cross_project_context=list(normalized_context_inputs["cross_project_context"]),
        candidate_recommendations=list(normalized_context_inputs["candidate_recommendations"]),
        earth_sweep_source_artifacts=list(normalized_context_inputs.get("earth_sweep_source_artifacts", [])),
        required_context_documents=list(normalized_context_inputs.get("required_context_documents", [])),
    )


def _normalize_req_024_open_risks(raw_value: Any, *, field_name: str) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{index}] must be an object")
        risk_id = _require_nonempty_text(item.get("risk_id"), field_name=f"{field_name}[{index}].risk_id")
        summary = _require_nonempty_text(item.get("summary"), field_name=f"{field_name}[{index}].summary")
        reason_code = _require_nonempty_text(item.get("reason_code"), field_name=f"{field_name}[{index}].reason_code")
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"{field_name}[{index}].evidence_refs",
        )
        if not evidence_refs:
            raise ValueError(f"{field_name}[{index}].evidence_refs must include at least one ref")
        normalized.append(
            {
                "risk_id": risk_id,
                "summary": summary,
                "reason_code": reason_code,
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(key=lambda row: (row["risk_id"], row["summary"], row["reason_code"]))
    return normalized


def _normalize_req_024_strategy_context(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError("strategy_context must be an object")
    if not raw_value:
        raise ValueError("strategy_context must include at least one key")

    normalized: dict[str, Any] = {}
    for key in sorted(raw_value.keys()):
        value = raw_value.get(key)
        if key == "processing_behavior":
            normalized[key] = _normalize_req_024_processing_behavior(value)
            continue
        if key == "strategy_runtime_entrypoint":
            normalized[key] = _normalize_req_024_strategy_runtime_entrypoint(value)
            continue
        if key == "open_risks":
            normalized[key] = _normalize_req_024_open_risks(value, field_name="strategy_context.open_risks")
            continue
        normalized[key] = _normalize_req_024_json_value(value, field_name=f"strategy_context.{key}")
    return normalized


def _normalize_req_024_llm_chain_stages(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        raise ValueError("llm_call_chain.stages must be a list")
    if not isinstance(raw_value, list):
        raise ValueError("llm_call_chain.stages must be a list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"llm_call_chain.stages[{index}] must be an object")
        stage_id = _require_nonempty_text(item.get("stage_id"), field_name=f"llm_call_chain.stages[{index}].stage_id")
        purpose = _require_nonempty_text(item.get("purpose"), field_name=f"llm_call_chain.stages[{index}].purpose")
        model = _require_nonempty_text(item.get("model"), field_name=f"llm_call_chain.stages[{index}].model")
        prompt_artifact_ref = _require_nonempty_text(
            item.get("prompt_artifact_ref"),
            field_name=f"llm_call_chain.stages[{index}].prompt_artifact_ref",
        )
        required_context_keys = _normalize_string_list(
            item.get("required_context_keys"),
            field_name=f"llm_call_chain.stages[{index}].required_context_keys",
        )
        if not required_context_keys:
            raise ValueError(f"llm_call_chain.stages[{index}].required_context_keys must include at least one key")
        normalized.append(
            {
                "stage_id": stage_id,
                "purpose": purpose,
                "model": model,
                "prompt_artifact_ref": prompt_artifact_ref,
                "required_context_keys": required_context_keys,
            }
        )
    if not normalized:
        raise ValueError("llm_call_chain.stages must include at least one stage")
    normalized.sort(key=lambda row: (row["stage_id"], row["purpose"], row["model"], row["prompt_artifact_ref"]))
    return normalized


def _normalize_req_024_llm_call_chain(raw_value: Any) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError("llm_call_chain must be an object")
    chain_id = _require_nonempty_text(raw_value.get("chain_id"), field_name="llm_call_chain.chain_id")
    stages = _normalize_req_024_llm_chain_stages(raw_value.get("stages"))
    return {
        "chain_id": chain_id,
        "stages": stages,
    }


def _serialize_req_024_context_bundle(
    *,
    strategy_context: Mapping[str, Any],
    llm_call_chain: Mapping[str, Any],
    bundle_generated_at_utc: str,
) -> tuple[str, str]:
    context_bundle = {
        "bundle_generated_at_utc": bundle_generated_at_utc,
        "llm_call_chain": llm_call_chain,
        "strategy_context": strategy_context,
    }
    serialized = json.dumps(
        context_bundle,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    checksum_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return serialized, checksum_sha256


def _is_lower_hex_sha256(raw_value: Any) -> bool:
    if not isinstance(raw_value, str):
        return False
    return len(raw_value) == 64 and all(character in "0123456789abcdef" for character in raw_value)


def build_req_024_strategy_context_bundle_serialization(
    *,
    strategy_context: Mapping[str, Any],
    llm_call_chain: Mapping[str, Any],
    bundle_generated_at_utc: str | None = None,
) -> dict[str, Any]:
    normalized_strategy_context = _normalize_req_024_strategy_context(strategy_context)
    normalized_llm_call_chain = _normalize_req_024_llm_call_chain(llm_call_chain)
    normalized_bundle_generated_at_utc = _normalize_req_024_timestamp(
        bundle_generated_at_utc,
        field_name="bundle_generated_at_utc",
    )
    serialized_context_bundle, context_bundle_sha256 = _serialize_req_024_context_bundle(
        strategy_context=normalized_strategy_context,
        llm_call_chain=normalized_llm_call_chain,
        bundle_generated_at_utc=normalized_bundle_generated_at_utc,
    )
    context_bundle_byte_length = len(serialized_context_bundle.encode("utf-8"))

    canonical_input = {
        "strategy_context": normalized_strategy_context,
        "llm_call_chain": normalized_llm_call_chain,
        "bundle_generated_at_utc": normalized_bundle_generated_at_utc,
    }
    digest = _canonical_input_digest(canonical_input)
    return {
        "schema_version": REQ_024_SCHEMA_VERSION,
        "requirement_id": REQ_024_REQUIREMENT_ID,
        "strategy_context_bundle_serialization": {
            "bundle_schema_version": REQ_024_BUNDLE_SCHEMA_VERSION,
            "serialization_format": REQ_024_SERIALIZATION_FORMAT,
            "bundle_generated_at_utc": normalized_bundle_generated_at_utc,
            "llm_call_chain": normalized_llm_call_chain,
            "context_bundle_sha256": context_bundle_sha256,
            "context_bundle_byte_length": context_bundle_byte_length,
            "serialized_context_bundle": serialized_context_bundle,
        },
        "source": {
            "tool": REQ_024_TOOL,
            "tool_version": REQ_024_TOOL_VERSION,
        },
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": digest,
            "reproducible_call_id": f"req024-{digest[:16]}",
            "canonical_input": canonical_input,
        },
    }


def validate_req_024_strategy_context_bundle_serialization(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "schema_version",
        "requirement_id",
        "strategy_context_bundle_serialization",
        "source",
        "call_metadata",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_024_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_024_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_024_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_024_REQUIREMENT_ID}")

    serialization = payload.get("strategy_context_bundle_serialization")
    if not isinstance(serialization, Mapping):
        errors.append("strategy_context_bundle_serialization must be an object")
        return errors

    required_serialization_fields = {
        "bundle_schema_version",
        "serialization_format",
        "bundle_generated_at_utc",
        "llm_call_chain",
        "context_bundle_sha256",
        "context_bundle_byte_length",
        "serialized_context_bundle",
    }
    serialization_keys = set(serialization.keys())
    missing_serialization = sorted(required_serialization_fields - serialization_keys)
    if missing_serialization:
        errors.append(f"strategy_context_bundle_serialization missing keys: {missing_serialization}")
    unexpected_serialization = sorted(serialization_keys - required_serialization_fields)
    if unexpected_serialization:
        errors.append(f"strategy_context_bundle_serialization has unexpected keys: {unexpected_serialization}")

    if serialization.get("bundle_schema_version") != REQ_024_BUNDLE_SCHEMA_VERSION:
        errors.append(
            f"strategy_context_bundle_serialization.bundle_schema_version must be {REQ_024_BUNDLE_SCHEMA_VERSION}"
        )
    if serialization.get("serialization_format") != REQ_024_SERIALIZATION_FORMAT:
        errors.append(
            f"strategy_context_bundle_serialization.serialization_format must be {REQ_024_SERIALIZATION_FORMAT}"
        )

    try:
        _normalize_req_024_timestamp(
            serialization.get("bundle_generated_at_utc"),
            field_name="strategy_context_bundle_serialization.bundle_generated_at_utc",
        )
    except ValueError as exc:
        errors.append(str(exc))

    try:
        normalized_llm_call_chain = _normalize_req_024_llm_call_chain(serialization.get("llm_call_chain"))
    except ValueError as exc:
        errors.append(str(exc))
        normalized_llm_call_chain = None

    context_bundle_sha256 = serialization.get("context_bundle_sha256")
    if not _is_lower_hex_sha256(context_bundle_sha256):
        errors.append("strategy_context_bundle_serialization.context_bundle_sha256 must be a lowercase hex sha256 digest")

    context_bundle_byte_length = serialization.get("context_bundle_byte_length")
    if not isinstance(context_bundle_byte_length, int) or context_bundle_byte_length <= 0:
        errors.append("strategy_context_bundle_serialization.context_bundle_byte_length must be a positive integer")

    serialized_context_bundle = serialization.get("serialized_context_bundle")
    if not isinstance(serialized_context_bundle, str) or not serialized_context_bundle:
        errors.append("strategy_context_bundle_serialization.serialized_context_bundle must be a non-empty string")
        parsed_bundle = None
    else:
        try:
            parsed_bundle = json.loads(serialized_context_bundle)
        except json.JSONDecodeError:
            errors.append("strategy_context_bundle_serialization.serialized_context_bundle must be valid JSON")
            parsed_bundle = None

    if isinstance(parsed_bundle, Mapping):
        required_bundle_keys = {"bundle_generated_at_utc", "llm_call_chain", "strategy_context"}
        bundle_keys = set(parsed_bundle.keys())
        missing_bundle_keys = sorted(required_bundle_keys - bundle_keys)
        if missing_bundle_keys:
            errors.append(f"serialized context bundle missing keys: {missing_bundle_keys}")
        unexpected_bundle_keys = sorted(bundle_keys - required_bundle_keys)
        if unexpected_bundle_keys:
            errors.append(f"serialized context bundle has unexpected keys: {unexpected_bundle_keys}")

        if parsed_bundle.get("bundle_generated_at_utc") != serialization.get("bundle_generated_at_utc"):
            errors.append(
                "strategy_context_bundle_serialization.serialized_context_bundle.bundle_generated_at_utc "
                "must match strategy_context_bundle_serialization.bundle_generated_at_utc"
            )
        if normalized_llm_call_chain is not None and parsed_bundle.get("llm_call_chain") != normalized_llm_call_chain:
            errors.append(
                "strategy_context_bundle_serialization.serialized_context_bundle.llm_call_chain "
                "must match normalized strategy_context_bundle_serialization.llm_call_chain"
            )
        strategy_context_in_bundle = parsed_bundle.get("strategy_context")
        try:
            normalized_strategy_context_in_bundle = _normalize_req_024_strategy_context(strategy_context_in_bundle)
        except ValueError as exc:
            errors.append(str(exc))
            normalized_strategy_context_in_bundle = None
        else:
            if strategy_context_in_bundle != normalized_strategy_context_in_bundle:
                errors.append(
                    "strategy_context_bundle_serialization.serialized_context_bundle.strategy_context "
                    "must match normalized strategy context content"
                )

        recomputed_sha256 = hashlib.sha256(serialized_context_bundle.encode("utf-8")).hexdigest()
        if context_bundle_sha256 != recomputed_sha256:
            errors.append(
                "strategy_context_bundle_serialization.context_bundle_sha256 must match serialized_context_bundle digest"
            )
        if isinstance(context_bundle_byte_length, int):
            recomputed_size = len(serialized_context_bundle.encode("utf-8"))
            if context_bundle_byte_length != recomputed_size:
                errors.append(
                    "strategy_context_bundle_serialization.context_bundle_byte_length must match serialized_context_bundle byte length"
                )

    source = payload.get("source")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
    else:
        if source.get("tool") != REQ_024_TOOL:
            errors.append(f"source.tool must be {REQ_024_TOOL}")
        if source.get("tool_version") != REQ_024_TOOL_VERSION:
            errors.append(f"source.tool_version must be {REQ_024_TOOL_VERSION}")

    call_metadata = payload.get("call_metadata")
    if not isinstance(call_metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors

    for field_name in ("reproducibility", "canonical_input_sha256", "reproducible_call_id", "canonical_input"):
        if field_name not in call_metadata:
            errors.append(f"call_metadata missing {field_name}")

    if call_metadata.get("reproducibility") != "deterministic-input-fingerprint":
        errors.append("call_metadata.reproducibility must be deterministic-input-fingerprint")

    canonical_input = call_metadata.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
        return errors

    if errors:
        return errors

    try:
        rebuilt = build_req_024_strategy_context_bundle_serialization(
            strategy_context=canonical_input.get("strategy_context"),
            llm_call_chain=canonical_input.get("llm_call_chain"),
            bundle_generated_at_utc=canonical_input.get("bundle_generated_at_utc"),
        )
    except ValueError as exc:
        errors.append(f"call_metadata.canonical_input is invalid: {exc}")
        return errors

    if dict(payload) != rebuilt:
        errors.append("payload must mirror deterministic REQ-024 strategy context bundle serialization output")
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
detect_reuse_opportunities = _worker_w07_req016.detect_reuse_opportunities
serialize_reuse_opportunity_context_bundle = _worker_w07_req016.serialize_reuse_opportunity_context_bundle
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
serialize_req_017_overlap_and_conflict_bundle = _worker_w08.serialize_req_017_overlap_and_conflict_bundle
build_req_017_overlap_and_conflict_detection = _worker_w08.build_req_017_overlap_and_conflict_detection
validate_req_017_overlap_and_conflict_detection = _worker_w08.validate_req_017_overlap_and_conflict_detection
build_req_021_evidence_provenance_ledger_for_context = _req021.build_req_021_evidence_provenance_ledger_for_context
validate_req_021_evidence_provenance_ledger_for_context = _req021.validate_req_021_evidence_provenance_ledger_for_context
ALLOWED_RISK_LEVELS = _worker_w08.ALLOWED_RISK_LEVELS
REASON_CODE_EARTH_SWEEP_STALE_SOURCE_ARTIFACT = _worker_w08.REASON_CODE_EARTH_SWEEP_STALE_SOURCE_ARTIFACT
REASON_CODE_CONTEXT_DOC_MISSING = _worker_w08.REASON_CODE_CONTEXT_DOC_MISSING
REASON_CODE_PEER_PROJECT_DOC_MISSING = _worker_w08.REASON_CODE_PEER_PROJECT_DOC_MISSING


_DATE_PATTERN = re.compile(r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})")


def _extract_dates_from_refs(evidence_refs: list[str]) -> list[date]:
    dates: list[date] = []
    for ref in evidence_refs:
        if not isinstance(ref, str):
            continue
        match = _DATE_PATTERN.search(ref)
        if not match:
            continue
        try:
            dates.append(
                date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                )
            )
        except ValueError:
            continue
    dates.sort()
    return dates


def _latest_evidence_date(*ref_groups: list[str]) -> date | None:
    latest: date | None = None
    for refs in ref_groups:
        for found in _extract_dates_from_refs(refs):
            if latest is None or found > latest:
                latest = found
    return latest


def _recency_score_for_refs(*, evidence_refs: list[str], anchor_date: date | None) -> float:
    if anchor_date is None:
        return 0.6
    dates = _extract_dates_from_refs(evidence_refs)
    if not dates:
        return 0.6
    element_date = dates[-1]
    delta_days = (anchor_date - element_date).days
    if delta_days <= 0:
        return 1.0
    if delta_days <= 7:
        return 0.9
    if delta_days <= 30:
        return 0.7
    if delta_days <= 90:
        return 0.5
    return 0.3


def _confidence_label_for_score(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _score_context_element(
    *,
    element_kind: str,
    element_id_parts: tuple[str, ...],
    evidence_refs: list[str],
    quality_score: float,
    anchor_date: date | None,
    summary: str,
    notes: str = "",
) -> dict[str, Any]:
    recency_score = _recency_score_for_refs(evidence_refs=evidence_refs, anchor_date=anchor_date)
    blended = (0.55 * quality_score) + (0.45 * recency_score)
    confidence_score = round(max(0.0, min(1.0, blended)), 3)
    confidence = _confidence_label_for_score(confidence_score)
    element_id = f"{element_kind}-{_stable_id_fragment(*element_id_parts)}"
    rationale_bits = [summary, f"Quality={quality_score:.2f}", f"Recency={recency_score:.2f}"]
    if notes:
        rationale_bits.append(notes.strip())
    return {
        "element_id": element_id,
        "element_kind": element_kind,
        "summary": summary,
        "confidence": confidence,
        "confidence_score": confidence_score,
        "quality_score": round(quality_score, 3),
        "recency_score": round(recency_score, 3),
        "rationale": "; ".join(rationale_bits),
        "evidence_refs": list(evidence_refs),
    }


def _build_context_confidence_report(
    *,
    target_project_root: str,
    earth_root: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    anchor_date = _latest_evidence_date(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        *[row.get("evidence_refs", []) for row in cross_project_context],
        *[row.get("evidence_refs", []) for row in earth_sweep_source_artifacts],
        *[row.get("evidence_refs", []) for row in required_context_documents],
    )

    elements: list[dict[str, Any]] = []
    elements.append(
        _score_context_element(
            element_kind="target-project",
            element_id_parts=("target-project", target_project_root),
            evidence_refs=target_project_evidence_refs,
            quality_score=0.9 if target_project_evidence_refs else 0.45,
            anchor_date=anchor_date,
            summary="Target-project context bundle evidence.",
            notes="No target-project evidence refs supplied." if not target_project_evidence_refs else "",
        )
    )
    elements.append(
        _score_context_element(
            element_kind="earth-sweep",
            element_id_parts=("earth-sweep", earth_root),
            evidence_refs=earth_sweep_evidence_refs,
            quality_score=0.85 if earth_sweep_evidence_refs else 0.4,
            anchor_date=anchor_date,
            summary="Earth-sweep context evidence.",
            notes="No Earth-sweep evidence refs supplied." if not earth_sweep_evidence_refs else "",
        )
    )

    for row in cross_project_context:
        project_id = str(row.get("project_id", ""))
        project_root = str(row.get("project_root", ""))
        evidence_refs = list(row.get("evidence_refs", [])) if isinstance(row.get("evidence_refs"), list) else []
        quality = 0.75 if evidence_refs else 0.35
        elements.append(
            _score_context_element(
                element_kind="cross-project",
                element_id_parts=("cross-project", project_id, project_root),
                evidence_refs=evidence_refs,
                quality_score=quality,
                anchor_date=anchor_date,
                summary=f"Cross-project context for '{project_id}'.",
                notes="Missing cross-project evidence refs." if not evidence_refs else "",
            )
        )

    for row in earth_sweep_source_artifacts:
        artifact_ref = str(row.get("artifact_ref", ""))
        status = str(row.get("status", "fresh")).strip().lower()
        evidence_refs = list(row.get("evidence_refs", [])) if isinstance(row.get("evidence_refs"), list) else []
        quality = 0.9 if status == "fresh" else 0.4
        supporting_note = ""
        if evidence_refs:
            supporting_note = f"Supporting evidence refs: {len(evidence_refs)}"
        elements.append(
            _score_context_element(
                element_kind="earth-source-artifact",
                element_id_parts=("earth-source-artifact", artifact_ref, status),
                evidence_refs=[artifact_ref],
                quality_score=quality,
                anchor_date=anchor_date,
                summary=f"Earth sweep source artifact ({status}).",
                notes="; ".join(bit for bit in (f"Artifact ref: {artifact_ref}", supporting_note) if bit),
            )
        )

    for row in required_context_documents:
        doc_kind = str(row.get("doc_kind", ""))
        doc_ref = str(row.get("doc_ref", ""))
        status = str(row.get("status", "present")).strip().lower()
        project_id = str(row.get("project_id", ""))
        evidence_refs = list(row.get("evidence_refs", [])) if isinstance(row.get("evidence_refs"), list) else []
        quality = 0.8 if status == "present" else 0.2
        label = f"{doc_kind} doc"
        if doc_kind == "peer-project":
            label = f"peer-project doc ({project_id})"
        elements.append(
            _score_context_element(
                element_kind="required-context-doc",
                element_id_parts=("required-context-doc", doc_kind, project_id, doc_ref, status),
                evidence_refs=[doc_ref, *evidence_refs],
                quality_score=quality,
                anchor_date=anchor_date,
                summary=f"Required context document: {label} ({status}).",
                notes=f"Doc ref: {doc_ref}",
            )
        )

    elements.sort(key=lambda row: (row["element_kind"], row["element_id"]))
    low_ids = [row["element_id"] for row in elements if row["confidence"] == "low"]
    overall_score = round(sum(row["confidence_score"] for row in elements) / len(elements), 3) if elements else 0.0
    overall_confidence = _confidence_label_for_score(overall_score)
    return {
        "recency_anchor_date": anchor_date.isoformat() if anchor_date else "",
        "overall_confidence": overall_confidence,
        "overall_confidence_score": overall_score,
        "elements": elements,
        "low_confidence_element_ids": low_ids,
    }


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


def build_req_022_context_confidence_scoring(
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
    """Build the REQ-022 context confidence scoring payload."""
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

    base_processing_behavior = _build_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        candidate_recommendations=normalized_candidates,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
    )
    confidence_report = _build_context_confidence_report(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        earth_sweep_source_artifacts=normalized_earth_source_artifacts,
        required_context_documents=normalized_required_documents,
    )

    base_recommendation = dict(base_processing_behavior["recommendation"])
    open_risks: list[dict[str, Any]] = list(base_recommendation["open_risks"])
    low_confidence_ids = list(confidence_report["low_confidence_element_ids"])
    if low_confidence_ids:
        evidence_by_element_id = {row["element_id"]: row.get("evidence_refs", []) for row in confidence_report["elements"]}
        for element_id in low_confidence_ids:
            element_refs = evidence_by_element_id.get(element_id, [])
            open_risks.append(
                {
                    "risk_id": f"risk-low-context-{_stable_id_fragment(element_id)}",
                    "summary": f"Low-confidence context detected for element '{element_id}'.",
                    "reason_code": "low_context_confidence",
                    "required_evidence_refs": list(element_refs),
                }
            )

    open_risks.sort(key=lambda row: row["risk_id"])
    recommendation_refs = _collect_unique_refs(
        list(base_recommendation.get("evidence_refs", [])),
        *[row.get("evidence_refs", []) for row in confidence_report["elements"]],
        *[row.get("required_evidence_refs", []) for row in open_risks],
    )

    decision = str(base_recommendation.get("decision", "insufficient-context"))
    if low_confidence_ids:
        decision = "resolve-context-gaps"

    confidence = str(confidence_report.get("overall_confidence", "low"))
    if not recommendation_refs:
        confidence = "low"
    elif open_risks and confidence == "high":
        confidence = "medium"

    rationale = base_recommendation.get("rationale", "")
    if low_confidence_ids:
        rationale = (
            "Low-confidence context was detected during broad-sweep scoring; refresh or replace weak inputs "
            "before downstream planning relies on them."
        )

    processing_behavior = {
        "strategy": "context-confidence-scoring-broad-sweep",
        "reasoning_mode": EXECUTION_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": base_processing_behavior["context_inputs"],
        "context_usage": base_processing_behavior["context_usage"],
        "context_confidence": confidence_report,
        "recommendation": {
            "decision": decision,
            "rationale": rationale or _recommendation_rationale(decision=decision),
            "confidence": confidence,
            "evidence_refs": recommendation_refs,
            "recommended_actions": list(base_recommendation.get("recommended_actions", [])),
            "cross_project_obligations": list(base_recommendation.get("cross_project_obligations", [])),
            "open_risks": open_risks,
        },
    }

    return {
        "schema_version": REQ_022_SCHEMA_VERSION,
        "requirement_id": REQ_022_REQUIREMENT_ID,
        "context_confidence_scoring_entrypoint": {
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
            "reproducible_call_id": f"req022-{digest[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_digest,
            "processing_call_id": f"req022-processing-{processing_digest[:16]}",
            "canonical_processing_input": canonical_processing_input,
        },
    }

def validate_req_022_context_confidence_scoring(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-022 payload shape and deterministic call metadata."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    top_keys = set(payload.keys())
    required_top = {"schema_version", "requirement_id", "context_confidence_scoring_entrypoint", "processing_behavior", "call_metadata"}
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("schema_version") != REQ_022_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_022_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_022_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_022_REQUIREMENT_ID}")

    entrypoint = payload.get("context_confidence_scoring_entrypoint")
    if not isinstance(entrypoint, Mapping):
        errors.append("context_confidence_scoring_entrypoint must be an object")
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
        errors.append(f"context_confidence_scoring_entrypoint missing keys: {missing_entrypoint}")
    unexpected_entrypoint = sorted(entrypoint_keys - required_entrypoint)
    if unexpected_entrypoint:
        errors.append(f"context_confidence_scoring_entrypoint unexpected keys: {unexpected_entrypoint}")

    if entrypoint.get("runtime_mode") != RUNTIME_MODE:
        errors.append(f"context_confidence_scoring_entrypoint.runtime_mode must be {RUNTIME_MODE}")
    if entrypoint.get("execution_mode") != EXECUTION_MODE:
        errors.append(f"context_confidence_scoring_entrypoint.execution_mode must be {EXECUTION_MODE}")

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        return errors
    for field in ("strategy", "reasoning_mode", "heuristic_summarization_only", "context_inputs", "context_usage", "context_confidence", "recommendation"):
        if field not in processing_behavior:
            errors.append(f"processing_behavior missing {field}")
    if processing_behavior.get("reasoning_mode") != EXECUTION_MODE:
        errors.append(f"processing_behavior.reasoning_mode must be {EXECUTION_MODE}")
    if processing_behavior.get("heuristic_summarization_only") is not False:
        errors.append("processing_behavior.heuristic_summarization_only must be false")

    confidence = processing_behavior.get("context_confidence")
    if isinstance(confidence, Mapping):
        for field in ("recency_anchor_date", "overall_confidence", "overall_confidence_score", "elements", "low_confidence_element_ids"):
            if field not in confidence:
                errors.append(f"processing_behavior.context_confidence missing {field}")
    else:
        errors.append("processing_behavior.context_confidence must be an object")

    recommendation = processing_behavior.get("recommendation")
    if isinstance(recommendation, Mapping):
        for field in (
            "decision",
            "rationale",
            "confidence",
            "evidence_refs",
            "recommended_actions",
            "cross_project_obligations",
            "open_risks",
        ):
            if field not in recommendation:
                errors.append(f"processing_behavior.recommendation missing {field}")
    else:
        errors.append("processing_behavior.recommendation must be an object")

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
    expected_call_id = f"req022-{expected_digest[:16]}"
    if metadata.get("canonical_input_sha256") != expected_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != expected_call_id:
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors
    expected_processing_input = _canonical_processing_input(
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
    if dict(canonical_processing_input) != expected_processing_input:
        errors.append("call_metadata.canonical_processing_input must mirror normalized processing input")

    expected_processing_digest = _canonical_input_digest(expected_processing_input)
    expected_processing_call_id = f"req022-processing-{expected_processing_digest[:16]}"
    if metadata.get("processing_input_sha256") != expected_processing_digest:
        errors.append("call_metadata.processing_input_sha256 does not match processing input")
    if metadata.get("processing_call_id") != expected_processing_call_id:
        errors.append("call_metadata.processing_call_id does not match processing digest")

    return errors

def _looks_like_req008_builder_input(payload: Mapping[str, Any]) -> bool:
    required = {"research_packet", "recommendations", "normalized_at_utc"}
    return required.issubset(payload.keys())


def _looks_like_req011_builder_input(payload: Mapping[str, Any]) -> bool:
    analysis_type = str(payload.get("analysis_type", "")).strip()
    if analysis_type == "cross_project_dependency_extraction":
        return True
    required = {
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "broad_sweep_context",
    }
    return required.issubset(payload.keys())


def _looks_like_req019_builder_input(payload: Mapping[str, Any]) -> bool:
    analysis_type = str(payload.get("analysis_type", "")).strip()
    if analysis_type == "execution_resource_context_ingestion":
        return True
    required = {
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "execution_resource_context",
    }
    return required.issubset(payload.keys())


def _looks_like_req020_builder_input(payload: Mapping[str, Any]) -> bool:
    analysis_type = str(payload.get("analysis_type", "")).strip()
    if analysis_type == "risk_signal_normalization":
        return True
    return "risk_signals" in payload


def _looks_like_req022_builder_input(payload: Mapping[str, Any]) -> bool:
    analysis_type = str(payload.get("analysis_type", "")).strip()
    if analysis_type == "context_confidence_scoring":
        return True
    required = {
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "target_project_evidence_refs",
        "earth_sweep_evidence_refs",
    }
    if not required.issubset(payload.keys()):
        return False
    return any(
        key in payload
        for key in (
            "candidate_recommendations",
            "cross_project_context",
            "earth_sweep_source_artifacts",
            "required_context_documents",
        )
    )


def _looks_like_req024_builder_input(payload: Mapping[str, Any]) -> bool:
    analysis_type = str(payload.get("analysis_type", "")).strip()
    return analysis_type == "strategy_context_bundle_serialization"


def run(payload: dict[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type", "")).strip()
    if analysis_type == "deficit_and_need_signal_extraction":
        return _worker_w02.run(payload)
    if analysis_type == "cross_project_dependency_extraction" or _looks_like_req011_builder_input(payload):
        return build_req_011_cross_project_dependency_extraction(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            broad_sweep_context=payload.get("broad_sweep_context"),
        )
    if analysis_type == "execution_resource_context_ingestion" or _looks_like_req019_builder_input(payload):
        return build_req_019_execution_resource_context_ingestion(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            execution_resource_context=payload.get("execution_resource_context"),
            execution_candidates=payload.get("execution_candidates"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            cross_project_context=payload.get("cross_project_context"),
        )
    if analysis_type == "risk_signal_normalization":
        return build_req_020_risk_signal_normalization(
            risk_signals=list(payload.get("risk_signals", [])),
            normalized_at_utc=payload.get("normalized_at_utc"),
        )
    if analysis_type == "context_confidence_scoring" or _looks_like_req022_builder_input(payload):
        return build_req_022_context_confidence_scoring(
            target_project_root=payload.get("target_project_root"),
            earth_root=payload.get("earth_root"),
            output_root=payload.get("output_root"),
            revision_identity=payload.get("revision_identity"),
            target_project_evidence_refs=payload.get("target_project_evidence_refs"),
            earth_sweep_evidence_refs=payload.get("earth_sweep_evidence_refs"),
            cross_project_context=payload.get("cross_project_context"),
            candidate_recommendations=payload.get("candidate_recommendations"),
            earth_sweep_source_artifacts=payload.get("earth_sweep_source_artifacts"),
            required_context_documents=payload.get("required_context_documents"),
        )
    if analysis_type == "strategy_context_bundle_serialization":
        return build_req_024_strategy_context_bundle_serialization(
            strategy_context=payload.get("strategy_context"),
            llm_call_chain=payload.get("llm_call_chain"),
            bundle_generated_at_utc=payload.get("bundle_generated_at_utc"),
        )

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
        "unable to route run payload: expected deficit/need extraction, cross-project dependency extraction, "
        "execution resource context ingestion, risk signal normalization, context confidence scoring, "
        "strategy context bundle serialization, planning artifact sweep, or runtime telemetry sweep input"
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
        elif _looks_like_req011_builder_input(payload):
            output_payload = build_req_011_cross_project_dependency_extraction(**payload)
        elif _looks_like_req019_builder_input(payload):
            output_payload = build_req_019_execution_resource_context_ingestion(**payload)
        elif _looks_like_req020_builder_input(payload):
            output_payload = build_req_020_risk_signal_normalization(
                risk_signals=list(payload.get("risk_signals", [])),
                normalized_at_utc=payload.get("normalized_at_utc"),
            )
        elif _looks_like_req022_builder_input(payload):
            output_payload = build_req_022_context_confidence_scoring(**payload)
        elif _looks_like_req024_builder_input(payload):
            output_payload = build_req_024_strategy_context_bundle_serialization(
                strategy_context=payload.get("strategy_context"),
                llm_call_chain=payload.get("llm_call_chain"),
                bundle_generated_at_utc=payload.get("bundle_generated_at_utc"),
            )
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
