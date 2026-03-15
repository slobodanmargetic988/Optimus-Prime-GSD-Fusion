#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REQ_007_SCHEMA_VERSION = "req-007.ground-graph-snapshot-ingestion.v1"
REQ_007_CONTEXT_BUNDLE_SCHEMA_VERSION = "req-007.ground-graph-context-bundle.v1"
REQ_015_SCHEMA_VERSION = "req-015.integration-opportunity-detection.v1"
REQ_015_CONTEXT_BUNDLE_SCHEMA_VERSION = "req-015.integration-opportunity-context-bundle.v1"
REQ_016_SCHEMA_VERSION = "req-016.reuse-opportunity-detection.v1"
REQ_016_CONTEXT_BUNDLE_SCHEMA_VERSION = "req-016.reuse-opportunity-context-bundle.v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _print_human(message: str) -> None:
    print(f"[{_utc_now_iso()}] {message}")


def _require_nonempty_str(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _require_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _normalize_string_list(value: Any, *, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    out: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(value):
        item_str = _require_nonempty_str(item, label=f"{label}[{idx}]")
        if item_str in seen:
            continue
        seen.add(item_str)
        out.append(item_str)
    out.sort()
    return out


def _normalize_string_list_in_order(value: Any, *, label: str, allow_empty: bool = True) -> list[str]:
    if value is None:
        if allow_empty:
            return []
        raise ValueError(f"{label} must be a non-empty list")
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    out: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(value):
        item_str = _require_nonempty_str(item, label=f"{label}[{idx}]")
        if item_str in seen:
            continue
        seen.add(item_str)
        out.append(item_str)
    if not allow_empty and not out:
        raise ValueError(f"{label} must be a non-empty list")
    return out


def _normalize_source_artifact_status(value: Any, *, label: str) -> str:
    if value is None:
        return "fresh"
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string when provided")
    status = value.strip().lower()
    if status not in {"fresh", "stale"}:
        raise ValueError(f"{label} must be either 'fresh' or 'stale'")
    return status


def _normalize_required_doc_kind(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    doc_kind = value.strip().lower()
    if doc_kind not in {"mission", "scope", "peer-project"}:
        raise ValueError(f"{label} must be one of: mission, scope, peer-project")
    return doc_kind


def _normalize_required_doc_status(value: Any, *, label: str) -> str:
    if value is None:
        return "present"
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string when provided")
    status = value.strip().lower()
    if status not in {"present", "missing"}:
        raise ValueError(f"{label} must be either 'present' or 'missing'")
    return status


def _parse_iso8601_utc(value: Any, *, label: str) -> datetime:
    text = _require_nonempty_str(value, label=label)
    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone information")
    return parsed.astimezone(timezone.utc)


def _require_nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _checksum_sha256(payload: Mapping[str, Any]) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _anchor_id(anchor: Mapping[str, str]) -> str:
    return "::".join(
        [
            anchor["project_id"],
            anchor["era_id"],
            anchor["plan_id"],
            anchor["phase_id"],
            anchor["run_id"],
            anchor["linked_project_id"],
            anchor["relationship"],
        ]
    )


def load_ground_graph_snapshot(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("ground_graph_snapshot must be a JSON object")
    return payload


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload at {path} must be an object")
    return payload


def ingest_ground_graph_snapshot(
    snapshot: Mapping[str, Any],
    *,
    source_path: str | None = None,
    ingested_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise ValueError("ground_graph_snapshot must be an object")
    schema_version = _require_nonempty_str(snapshot.get("schema_version"), label="ground_graph_snapshot.schema_version")
    captured_at = _require_nonempty_str(snapshot.get("captured_at"), label="ground_graph_snapshot.captured_at")
    graph_id = _require_nonempty_str(snapshot.get("graph_id"), label="ground_graph_snapshot.graph_id")
    raw_links = snapshot.get("lineage_links")
    if not isinstance(raw_links, list) or not raw_links:
        raise ValueError("ground_graph_snapshot.lineage_links must be a non-empty list")

    anchors: list[dict[str, str]] = []
    seen_anchor_ids: set[str] = set()
    for idx, row in enumerate(raw_links):
        if not isinstance(row, Mapping):
            raise ValueError(f"ground_graph_snapshot.lineage_links[{idx}] must be an object")
        anchor = {
            "project_id": _require_nonempty_str(
                row.get("project_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].project_id"
            ),
            "era_id": _require_nonempty_str(row.get("era_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].era_id"),
            "plan_id": _require_nonempty_str(
                row.get("plan_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].plan_id"
            ),
            "phase_id": _require_nonempty_str(
                row.get("phase_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].phase_id"
            ),
            "run_id": _require_nonempty_str(row.get("run_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].run_id"),
            "linked_project_id": _require_nonempty_str(
                row.get("linked_project_id"), label=f"ground_graph_snapshot.lineage_links[{idx}].linked_project_id"
            ),
            "relationship": _require_nonempty_str(
                row.get("relationship"), label=f"ground_graph_snapshot.lineage_links[{idx}].relationship"
            ),
        }
        anchor["anchor_id"] = _anchor_id(anchor)
        if anchor["anchor_id"] in seen_anchor_ids:
            continue
        seen_anchor_ids.add(anchor["anchor_id"])
        anchors.append(anchor)

    anchors.sort(key=lambda item: item["anchor_id"])
    ingested_at_value = _require_nonempty_str(ingested_at or _utc_now_iso(), label="ingested_at")
    output = {
        "requirement_id": "REQ-007",
        "surface": "ground_graph_snapshot_ingestion",
        "schema_version": REQ_007_SCHEMA_VERSION,
        "ingested_at": ingested_at_value,
        "source_artifact": {
            "path": source_path or "<inline>",
            "schema_version": schema_version,
            "captured_at": captured_at,
            "graph_id": graph_id,
            "checksum_sha256": _checksum_sha256(snapshot),
        },
        "lineage_anchors": anchors,
        "lineage_index": {
            "project_ids": sorted({item["project_id"] for item in anchors}),
            "era_ids": sorted({item["era_id"] for item in anchors}),
            "plan_ids": sorted({item["plan_id"] for item in anchors}),
            "phase_ids": sorted({item["phase_id"] for item in anchors}),
            "run_ids": sorted({item["run_id"] for item in anchors}),
            "linked_project_ids": sorted({item["linked_project_id"] for item in anchors}),
        },
    }
    return output


def _lineage_context_rows(anchors: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for anchor in anchors:
        linked_project_id = anchor["linked_project_id"]
        row = rows.setdefault(
            linked_project_id,
            {
                "linked_project_id": linked_project_id,
                "lineage_anchor_count": 0,
                "relationship_types": set(),
                "anchor_ids": [],
            },
        )
        row["lineage_anchor_count"] += 1
        row["relationship_types"].add(anchor["relationship"])
        row["anchor_ids"].append(anchor["anchor_id"])

    ordered: list[dict[str, Any]] = []
    for linked_project_id in sorted(rows):
        row = rows[linked_project_id]
        ordered.append(
            {
                "linked_project_id": linked_project_id,
                "lineage_anchor_count": row["lineage_anchor_count"],
                "relationship_types": sorted(row["relationship_types"]),
                "anchor_ids": sorted(row["anchor_ids"]),
            }
        )
    return ordered


def _candidate_actions_from_context(broad_sweep_context: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in (
        "integration_opportunity_candidates",
        "cross_project_action_candidates",
        "candidate_actions",
        "recommendation_candidates",
    ):
        value = broad_sweep_context.get(key)
        if value is None:
            continue
        if not isinstance(value, list):
            raise ValueError(f"broad_sweep_context.{key} must be a list")
        out: list[Mapping[str, Any]] = []
        for idx, row in enumerate(value):
            out.append(_require_mapping(row, label=f"broad_sweep_context.{key}[{idx}]"))
        return out
    return []


def _normalize_reuse_required_capabilities(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("reuse_opportunity_detection.required_capabilities must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    required_by_capability: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(raw_value):
        item = _require_mapping(row, label=f"reuse_opportunity_detection.required_capabilities[{idx}]")
        capability_id = _require_nonempty_str(
            item.get("capability_id"),
            label=f"reuse_opportunity_detection.required_capabilities[{idx}].capability_id",
        )
        intent = _require_nonempty_str(
            item.get("intent"),
            label=f"reuse_opportunity_detection.required_capabilities[{idx}].intent",
        )
        required_interfaces = _normalize_string_list(
            item.get("required_interfaces"),
            label=f"reuse_opportunity_detection.required_capabilities[{idx}].required_interfaces",
        )

        existing = required_by_capability.get(capability_id)
        if existing is None:
            required = {
                "capability_id": capability_id,
                "intent": intent,
                "required_interfaces": required_interfaces,
            }
            required_by_capability[capability_id] = required
            normalized.append(required)
            continue

        if existing["intent"] != intent:
            raise ValueError(
                "reuse_opportunity_detection.required_capabilities contains conflicting intent values "
                f"for capability_id '{capability_id}'"
            )
        existing_interfaces = set(existing["required_interfaces"])
        existing_interfaces.update(required_interfaces)
        existing["required_interfaces"] = sorted(existing_interfaces)

    normalized.sort(key=lambda row: row["capability_id"])
    return normalized


def _normalize_reuse_existing_functionality(
    raw_value: Any,
    *,
    active_project_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("reuse_opportunity_detection.existing_functionality must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    seen_functionality_keys: set[str] = set()
    source_project_ids: set[str] = set()

    for idx, row in enumerate(raw_value):
        item = _require_mapping(row, label=f"reuse_opportunity_detection.existing_functionality[{idx}]")
        source_project_id = _require_nonempty_str(
            item.get("source_project_id"),
            label=f"reuse_opportunity_detection.existing_functionality[{idx}].source_project_id",
        )
        if source_project_id == active_project_id:
            raise ValueError(
                "reuse_opportunity_detection.existing_functionality contains active_project_id; "
                "reuse candidates must come from other apps"
            )
        capability_id = _require_nonempty_str(
            item.get("capability_id"),
            label=f"reuse_opportunity_detection.existing_functionality[{idx}].capability_id",
        )
        functionality = _require_nonempty_str(
            item.get("functionality"),
            label=f"reuse_opportunity_detection.existing_functionality[{idx}].functionality",
        )
        adoption_path = _normalize_string_list_in_order(
            item.get("adoption_path"),
            label=f"reuse_opportunity_detection.existing_functionality[{idx}].adoption_path",
            allow_empty=False,
        )
        compatibility_constraints = _normalize_string_list_in_order(
            item.get("compatibility_constraints"),
            label=f"reuse_opportunity_detection.existing_functionality[{idx}].compatibility_constraints",
            allow_empty=False,
        )
        provided_interfaces = _normalize_string_list(
            item.get("provided_interfaces"),
            label=f"reuse_opportunity_detection.existing_functionality[{idx}].provided_interfaces",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            label=f"reuse_opportunity_detection.existing_functionality[{idx}].evidence_refs",
        )
        key = f"{source_project_id}::{capability_id}::{functionality}"
        if key in seen_functionality_keys:
            continue
        seen_functionality_keys.add(key)
        source_project_ids.add(source_project_id)
        normalized.append(
            {
                "source_project_id": source_project_id,
                "capability_id": capability_id,
                "functionality": functionality,
                "provided_interfaces": provided_interfaces,
                "adoption_path": adoption_path,
                "compatibility_constraints": compatibility_constraints,
                "evidence_refs": evidence_refs,
            }
        )

    normalized.sort(key=lambda row: (row["source_project_id"], row["capability_id"], row["functionality"]))
    return normalized, sorted(source_project_ids)


def _normalize_reuse_earth_sweep_source_artifacts(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("reuse_opportunity_detection.earth_sweep_source_artifacts must be a list")

    normalized: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_value):
        item = _require_mapping(row, label=f"reuse_opportunity_detection.earth_sweep_source_artifacts[{idx}]")
        artifact_ref = _require_nonempty_str(
            item.get("artifact_ref"),
            label=f"reuse_opportunity_detection.earth_sweep_source_artifacts[{idx}].artifact_ref",
        )
        status = _normalize_source_artifact_status(
            item.get("status"),
            label=f"reuse_opportunity_detection.earth_sweep_source_artifacts[{idx}].status",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            label=f"reuse_opportunity_detection.earth_sweep_source_artifacts[{idx}].evidence_refs",
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


def _normalize_reuse_required_context_documents(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("reuse_opportunity_detection.required_context_documents must be a list")

    normalized: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_value):
        item = _require_mapping(row, label=f"reuse_opportunity_detection.required_context_documents[{idx}]")
        doc_kind = _normalize_required_doc_kind(
            item.get("doc_kind"),
            label=f"reuse_opportunity_detection.required_context_documents[{idx}].doc_kind",
        )
        doc_ref = _require_nonempty_str(
            item.get("doc_ref"),
            label=f"reuse_opportunity_detection.required_context_documents[{idx}].doc_ref",
        )
        status = _normalize_required_doc_status(
            item.get("status"),
            label=f"reuse_opportunity_detection.required_context_documents[{idx}].status",
        )
        project_id = (
            _require_nonempty_str(
                item.get("project_id"),
                label=f"reuse_opportunity_detection.required_context_documents[{idx}].project_id",
            )
            if doc_kind == "peer-project"
            else ""
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            label=f"reuse_opportunity_detection.required_context_documents[{idx}].evidence_refs",
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


def _stable_fragment(*parts: str) -> str:
    joined = "::".join(part.strip() for part in parts if part and part.strip())
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def _build_reuse_open_risks(
    *,
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    open_risks: list[dict[str, Any]] = []

    for source_artifact in earth_sweep_source_artifacts:
        if source_artifact["status"] != "stale":
            continue
        open_risks.append(
            {
                "risk_id": f"risk-earth-source-{_stable_fragment(source_artifact['artifact_ref'])}",
                "summary": f"Earth sweep source artifact is stale: {source_artifact['artifact_ref']}",
                "reason_code": "stale_earth_sweep_source_artifact",
                "required_evidence_refs": sorted(
                    {source_artifact["artifact_ref"], *source_artifact["evidence_refs"]}
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
                    f"{_stable_fragment(required_doc['doc_kind'], required_doc['project_id'], required_doc['doc_ref'])}"
                ),
                "summary": summary,
                "reason_code": reason_code,
                "required_evidence_refs": sorted({required_doc["doc_ref"], *required_doc["evidence_refs"]}),
            }
        )

    open_risks.sort(key=lambda row: row["risk_id"])
    return open_risks


def _canonical_reuse_opportunity_context_bundle(
    *,
    active_project_id: str,
    required_capabilities: list[dict[str, Any]],
    existing_functionality: list[dict[str, Any]],
    earth_sweep_source_artifacts: list[dict[str, Any]],
    required_context_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical: dict[str, Any] = {
        "active_project_id": active_project_id,
        "required_capabilities": required_capabilities,
        "existing_functionality": existing_functionality,
    }
    if earth_sweep_source_artifacts:
        canonical["earth_sweep_source_artifacts"] = earth_sweep_source_artifacts
    if required_context_documents:
        canonical["required_context_documents"] = required_context_documents
    return canonical


def _hardening_open_risks(
    *,
    canonical_ingestion: Mapping[str, Any],
    broad_sweep_context: Mapping[str, Any],
    earth_sweep_evidence_refs: list[str],
    linked_project_ids: set[str],
    active_project_id: str,
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    context = _require_mapping(broad_sweep_context, label="broad_sweep_context")
    source_artifact = _require_mapping(canonical_ingestion.get("source_artifact"), label="source_artifact")
    source_path = _require_nonempty_str(source_artifact.get("path"), label="source_artifact.path")
    source_graph_id = _require_nonempty_str(source_artifact.get("graph_id"), label="source_artifact.graph_id")

    source_artifact_max_age_seconds_raw = context.get("source_artifact_max_age_seconds")
    earth_sweep_started_at_raw = context.get("earth_sweep_started_at")
    if source_artifact_max_age_seconds_raw is not None:
        source_artifact_max_age_seconds = _require_nonnegative_int(
            source_artifact_max_age_seconds_raw,
            label="broad_sweep_context.source_artifact_max_age_seconds",
        )
        if earth_sweep_started_at_raw is None:
            raise ValueError(
                "broad_sweep_context.earth_sweep_started_at is required when "
                "broad_sweep_context.source_artifact_max_age_seconds is set"
            )
        earth_sweep_started_at = _parse_iso8601_utc(
            earth_sweep_started_at_raw,
            label="broad_sweep_context.earth_sweep_started_at",
        )
        captured_at = _parse_iso8601_utc(
            source_artifact.get("captured_at"),
            label="source_artifact.captured_at",
        )
        source_age_seconds = max(0, int((earth_sweep_started_at - captured_at).total_seconds()))
        if source_age_seconds > source_artifact_max_age_seconds:
            risks.append(
                {
                    "risk_id": f"source_artifact::{source_graph_id}::stale_during_earth_sweep",
                    "reason": "source_artifact_stale_during_earth_sweep",
                    "reason_code": "source_artifact_stale_during_earth_sweep",
                    "source_artifact_path": source_path,
                    "source_artifact_captured_at": source_artifact.get("captured_at"),
                    "earth_sweep_started_at": earth_sweep_started_at_raw,
                    "source_age_seconds": source_age_seconds,
                    "max_source_age_seconds": source_artifact_max_age_seconds,
                    "evidence_refs": sorted({source_path, *earth_sweep_evidence_refs}),
                }
            )

    active_project_docs_raw = context.get("active_project_docs")
    if active_project_docs_raw is not None:
        active_project_docs = _require_mapping(
            active_project_docs_raw,
            label="broad_sweep_context.active_project_docs",
        )
        missing_doc_fields: list[str] = []
        present_doc_refs: list[str] = []
        for field in ("mission", "scope"):
            value = active_project_docs.get(field)
            if isinstance(value, str) and value.strip():
                present_doc_refs.append(value.strip())
            else:
                missing_doc_fields.append(field)
        if missing_doc_fields:
            risks.append(
                {
                    "risk_id": (
                        f"{active_project_id}::active_project_docs_missing::"
                        + "-".join(sorted(missing_doc_fields))
                    ),
                    "reason": "active_project_missing_mission_or_scope_doc",
                    "reason_code": "active_project_missing_mission_or_scope_doc",
                    "active_project_id": active_project_id,
                    "missing_docs": sorted(missing_doc_fields),
                    "evidence_refs": sorted({source_path, *earth_sweep_evidence_refs, *present_doc_refs}),
                }
            )

    peer_project_docs_raw = context.get("peer_project_docs")
    if peer_project_docs_raw is not None:
        peer_project_docs = _require_mapping(
            peer_project_docs_raw,
            label="broad_sweep_context.peer_project_docs",
        )
        for linked_project_id in sorted(linked_project_ids):
            doc_ref = peer_project_docs.get(linked_project_id)
            if isinstance(doc_ref, str) and doc_ref.strip():
                continue
            risks.append(
                {
                    "risk_id": f"{linked_project_id}::peer_project_doc_missing",
                    "reason": "linked_project_missing_peer_doc",
                    "reason_code": "linked_project_missing_peer_doc",
                    "linked_project_id": linked_project_id,
                    "evidence_refs": sorted({source_path, *earth_sweep_evidence_refs}),
                }
            )
    return risks


def process_ground_graph_snapshot(
    snapshot: Mapping[str, Any],
    *,
    broad_sweep_context: Mapping[str, Any],
    source_path: str | None = None,
    ingested_at: str | None = None,
) -> dict[str, Any]:
    canonical_ingestion = ingest_ground_graph_snapshot(snapshot, source_path=source_path, ingested_at=ingested_at)
    anchors = canonical_ingestion["lineage_anchors"]
    linked_project_ids = set(canonical_ingestion["lineage_index"]["linked_project_ids"])

    context = _require_mapping(broad_sweep_context, label="broad_sweep_context")
    active_project_id = _require_nonempty_str(
        context.get("active_project_id"), label="broad_sweep_context.active_project_id"
    )
    earth_sweep_evidence_refs = _normalize_string_list(
        context.get("earth_sweep_evidence_refs"), label="broad_sweep_context.earth_sweep_evidence_refs"
    )
    earth_ref_set = set(earth_sweep_evidence_refs)

    lineage_context_rows = _lineage_context_rows(anchors)
    lineage_context_by_project = {row["linked_project_id"]: row for row in lineage_context_rows}
    candidate_actions = _candidate_actions_from_context(context)

    supported_actions: list[dict[str, Any]] = []
    deferred_actions: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    recommendation_evidence_refs: set[str] = set()

    for idx, candidate in enumerate(candidate_actions):
        linked_project_id = _require_nonempty_str(
            candidate.get("linked_project_id"), label=f"broad_sweep_context.candidate_actions[{idx}].linked_project_id"
        )
        action = _require_nonempty_str(
            candidate.get("action"), label=f"broad_sweep_context.candidate_actions[{idx}].action"
        )
        candidate_evidence_refs = _normalize_string_list(
            candidate.get("evidence_refs"), label=f"broad_sweep_context.candidate_actions[{idx}].evidence_refs"
        )
        supported_evidence_refs = sorted(ref for ref in candidate_evidence_refs if ref in earth_ref_set)
        missing_evidence_refs = sorted(ref for ref in candidate_evidence_refs if ref not in earth_ref_set)

        if linked_project_id not in linked_project_ids:
            open_risks.append(
                {
                    "risk_id": f"{linked_project_id}::{action}::not_in_ground_graph",
                    "reason": "candidate_linked_project_missing_from_ground_graph",
                    "linked_project_id": linked_project_id,
                    "action": action,
                    "evidence_refs": supported_evidence_refs,
                }
            )
            continue
        if not supported_evidence_refs:
            open_risks.append(
                {
                    "risk_id": f"{linked_project_id}::{action}::missing_earth_evidence",
                    "reason": "candidate_action_missing_earth_sweep_evidence_refs",
                    "linked_project_id": linked_project_id,
                    "action": action,
                    "evidence_refs": [],
                }
            )
            continue

        recommendation_evidence_refs.update(supported_evidence_refs)
        recommendation_row = {
            "linked_project_id": linked_project_id,
            "action": action,
            "evidence_refs": supported_evidence_refs,
            "lineage_anchor_ids": list(lineage_context_by_project[linked_project_id]["anchor_ids"]),
        }
        if missing_evidence_refs:
            recommendation_row["out_of_scope_evidence_refs"] = missing_evidence_refs
        supported_actions.append(recommendation_row)

    open_risks.extend(
        _hardening_open_risks(
            canonical_ingestion=canonical_ingestion,
            broad_sweep_context=context,
            earth_sweep_evidence_refs=earth_sweep_evidence_refs,
            linked_project_ids=linked_project_ids,
            active_project_id=active_project_id,
        )
    )

    for row in supported_actions:
        if row.get("out_of_scope_evidence_refs"):
            deferred_actions.append(
                {
                    "linked_project_id": row["linked_project_id"],
                    "action": row["action"],
                    "reason": "candidate_includes_non_earth_evidence_refs",
                    "out_of_scope_evidence_refs": row["out_of_scope_evidence_refs"],
                }
            )

    supported_actions.sort(key=lambda row: (row["linked_project_id"], row["action"]))
    deferred_actions.sort(key=lambda row: (row["linked_project_id"], row["action"], row["reason"]))
    open_risks.sort(key=lambda row: row["risk_id"])
    recommendation_evidence_ref_list = sorted(recommendation_evidence_refs)

    if supported_actions:
        decision = "ready_for_planning" if not open_risks else "planning_with_open_risks"
    elif open_risks:
        decision = "blocked_missing_evidence"
    else:
        decision = "no_cross_project_candidates"

    recommendation = {
        "decision": decision,
        "summary": (
            f"{len(supported_actions)} supported cross-project action(s); "
            f"{len(open_risks)} open risk(s); {len(deferred_actions)} deferred action(s)."
        ),
        "supported_actions": supported_actions,
        "deferred_actions": deferred_actions,
        "open_risks": open_risks,
        "evidence_refs": recommendation_evidence_ref_list,
    }

    return {
        **canonical_ingestion,
        "cross_project_context": {
            "active_project_id": active_project_id,
            "linked_projects": [row["linked_project_id"] for row in lineage_context_rows],
            "linked_project_context": lineage_context_rows,
            "active_project_anchor_count": len([row for row in anchors if row["project_id"] == active_project_id]),
            "total_anchor_count": len(anchors),
        },
        "evidence_refs": {
            "earth_sweep": earth_sweep_evidence_refs,
            "recommendation": recommendation_evidence_ref_list,
        },
        "recommendation": recommendation,
    }


def detect_integration_opportunities(
    snapshot: Mapping[str, Any],
    *,
    broad_sweep_context: Mapping[str, Any],
    source_path: str | None = None,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    canonical_ingestion = ingest_ground_graph_snapshot(
        snapshot,
        source_path=source_path,
        ingested_at=_require_nonempty_str(evaluated_at or _utc_now_iso(), label="evaluated_at"),
    )
    anchors = canonical_ingestion["lineage_anchors"]
    linked_project_ids = set(canonical_ingestion["lineage_index"]["linked_project_ids"])

    context = _require_mapping(broad_sweep_context, label="broad_sweep_context")
    active_project_id = _require_nonempty_str(
        context.get("active_project_id"), label="broad_sweep_context.active_project_id"
    )
    earth_sweep_evidence_refs = _normalize_string_list(
        context.get("earth_sweep_evidence_refs"), label="broad_sweep_context.earth_sweep_evidence_refs"
    )
    earth_ref_set = set(earth_sweep_evidence_refs)

    lineage_context_rows = _lineage_context_rows(anchors)
    lineage_context_by_project = {row["linked_project_id"]: row for row in lineage_context_rows}
    candidate_actions = _candidate_actions_from_context(context)

    supported_opportunities: list[dict[str, Any]] = []
    deferred_opportunities: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    recommendation_evidence_refs: set[str] = set()

    for idx, candidate in enumerate(candidate_actions):
        candidate_label = f"broad_sweep_context.integration_opportunity_candidates[{idx}]"
        linked_project_id = _require_nonempty_str(
            candidate.get("linked_project_id"), label=f"{candidate_label}.linked_project_id"
        )
        action = _require_nonempty_str(candidate.get("action"), label=f"{candidate_label}.action")

        candidate_evidence_refs = _normalize_string_list(
            candidate.get("evidence_refs"), label=f"{candidate_label}.evidence_refs"
        )
        supported_evidence_refs = sorted(ref for ref in candidate_evidence_refs if ref in earth_ref_set)
        missing_evidence_refs = sorted(ref for ref in candidate_evidence_refs if ref not in earth_ref_set)

        if linked_project_id not in linked_project_ids:
            open_risks.append(
                {
                    "risk_id": f"{linked_project_id}::{action}::not_in_ground_graph",
                    "reason": "candidate_linked_project_missing_from_ground_graph",
                    "reason_code": "candidate_linked_project_missing_from_ground_graph",
                    "linked_project_id": linked_project_id,
                    "action": action,
                    "evidence_refs": supported_evidence_refs,
                }
            )
            continue

        if not supported_evidence_refs:
            open_risks.append(
                {
                    "risk_id": f"{linked_project_id}::{action}::missing_earth_evidence",
                    "reason": "candidate_opportunity_missing_earth_sweep_evidence_refs",
                    "reason_code": "candidate_opportunity_missing_earth_sweep_evidence_refs",
                    "linked_project_id": linked_project_id,
                    "action": action,
                    "evidence_refs": [],
                }
            )
            continue

        interaction_contract: dict[str, Any] | None = None
        interaction_contract_raw = candidate.get("interaction_contract")
        if interaction_contract_raw is None:
            contract_ref_raw = candidate.get("interaction_contract_ref")
            if isinstance(contract_ref_raw, str) and contract_ref_raw.strip():
                interaction_contract = {"contract_ref": contract_ref_raw.strip(), "expected_interactions": []}
        elif isinstance(interaction_contract_raw, Mapping):
            contract_ref = interaction_contract_raw.get("contract_ref")
            if isinstance(contract_ref, str) and contract_ref.strip():
                expected_interactions = _normalize_string_list_in_order(
                    interaction_contract_raw.get("expected_interactions"),
                    label=f"{candidate_label}.interaction_contract.expected_interactions",
                    allow_empty=True,
                )
                interaction_contract = {
                    "contract_ref": contract_ref.strip(),
                    "expected_interactions": expected_interactions,
                }

        dependency_side_effect_notes_raw = candidate.get("dependency_side_effect_notes")
        dependency_side_effect_notes = (
            dependency_side_effect_notes_raw.strip()
            if isinstance(dependency_side_effect_notes_raw, str) and dependency_side_effect_notes_raw.strip()
            else None
        )

        missing_fields: list[str] = []
        if interaction_contract is None:
            missing_fields.append("interaction_contract")
        if dependency_side_effect_notes is None:
            missing_fields.append("dependency_side_effect_notes")
        if missing_fields:
            open_risks.append(
                {
                    "risk_id": f"{linked_project_id}::{action}::missing_required_fields::{'+'.join(missing_fields)}",
                    "reason": "integration_opportunity_candidate_missing_required_fields",
                    "reason_code": "integration_opportunity_candidate_missing_required_fields",
                    "linked_project_id": linked_project_id,
                    "action": action,
                    "missing_fields": sorted(missing_fields),
                    "evidence_refs": supported_evidence_refs,
                }
            )
            continue

        recommendation_evidence_refs.update(supported_evidence_refs)
        opportunity_row: dict[str, Any] = {
            "linked_project_id": linked_project_id,
            "action": action,
            "interaction_contract": interaction_contract,
            "dependency_side_effect_notes": dependency_side_effect_notes,
            "evidence_refs": supported_evidence_refs,
            "lineage_anchor_ids": list(lineage_context_by_project[linked_project_id]["anchor_ids"]),
        }
        if missing_evidence_refs:
            opportunity_row["out_of_scope_evidence_refs"] = missing_evidence_refs
        supported_opportunities.append(opportunity_row)

    open_risks.extend(
        _hardening_open_risks(
            canonical_ingestion=canonical_ingestion,
            broad_sweep_context=context,
            earth_sweep_evidence_refs=earth_sweep_evidence_refs,
            linked_project_ids=linked_project_ids,
            active_project_id=active_project_id,
        )
    )

    for row in supported_opportunities:
        if row.get("out_of_scope_evidence_refs"):
            deferred_opportunities.append(
                {
                    "linked_project_id": row["linked_project_id"],
                    "action": row["action"],
                    "reason": "candidate_includes_non_earth_evidence_refs",
                    "reason_code": "candidate_includes_non_earth_evidence_refs",
                    "out_of_scope_evidence_refs": row["out_of_scope_evidence_refs"],
                }
            )

    supported_opportunities.sort(key=lambda row: (row["linked_project_id"], row["action"]))
    deferred_opportunities.sort(key=lambda row: (row["linked_project_id"], row["action"], row["reason"]))
    open_risks.sort(key=lambda row: row["risk_id"])
    recommendation_evidence_ref_list = sorted(recommendation_evidence_refs)

    if supported_opportunities:
        decision = "ready_for_planning" if not open_risks else "planning_with_open_risks"
    elif open_risks:
        decision = "blocked_missing_evidence"
    else:
        decision = "no_integration_opportunities"

    recommendation = {
        "decision": decision,
        "summary": (
            f"{len(supported_opportunities)} supported integration opportunity(ies); "
            f"{len(open_risks)} open risk(s); {len(deferred_opportunities)} deferred opportunity(ies)."
        ),
        "integration_opportunities": supported_opportunities,
        "deferred_opportunities": deferred_opportunities,
        "open_risks": open_risks,
        "evidence_refs": recommendation_evidence_ref_list,
    }

    return {
        "requirement_id": "REQ-015",
        "surface": "integration_opportunity_detection",
        "schema_version": REQ_015_SCHEMA_VERSION,
        "evaluated_at": canonical_ingestion["ingested_at"],
        "source_artifact": canonical_ingestion["source_artifact"],
        "lineage_anchors": canonical_ingestion["lineage_anchors"],
        "lineage_index": canonical_ingestion["lineage_index"],
        "integration_context": {
            "active_project_id": active_project_id,
            "linked_projects": [row["linked_project_id"] for row in lineage_context_rows],
            "linked_project_context": lineage_context_rows,
            "active_project_anchor_count": len([row for row in anchors if row["project_id"] == active_project_id]),
            "total_anchor_count": len(anchors),
        },
        "evidence_refs": {
            "earth_sweep": earth_sweep_evidence_refs,
            "recommendation": recommendation_evidence_ref_list,
        },
        "recommendation": recommendation,
    }


def serialize_integration_opportunity_context_bundle(payload: Mapping[str, Any]) -> dict[str, str]:
    context_bundle = _require_mapping(payload, label="integration_opportunity_context_bundle")
    serialized_payload = json.dumps(
        context_bundle,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "requirement_id": "REQ-015",
        "surface": "integration_opportunity_context_bundle",
        "schema_version": REQ_015_CONTEXT_BUNDLE_SCHEMA_VERSION,
        "serialization_format": "json-canonical-v1",
        "checksum_sha256": hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest(),
        "serialized_payload": serialized_payload,
    }


def detect_reuse_opportunities(
    payload: Mapping[str, Any],
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    context = _require_mapping(payload, label="reuse_opportunity_detection")
    active_project_id = _require_nonempty_str(
        context.get("active_project_id"),
        label="reuse_opportunity_detection.active_project_id",
    )
    required_capabilities = _normalize_reuse_required_capabilities(context.get("required_capabilities"))
    existing_functionality, source_project_id_list = _normalize_reuse_existing_functionality(
        context.get("existing_functionality"),
        active_project_id=active_project_id,
    )
    earth_sweep_source_artifacts = _normalize_reuse_earth_sweep_source_artifacts(
        context.get("earth_sweep_source_artifacts")
    )
    required_context_documents = _normalize_reuse_required_context_documents(
        context.get("required_context_documents")
    )

    existing_by_capability: dict[str, list[dict[str, Any]]] = {}
    for row in existing_functionality:
        existing_by_capability.setdefault(row["capability_id"], []).append(row)

    reuse_recommendations: list[dict[str, Any]] = []
    no_reuse_detected: list[dict[str, Any]] = []
    recommendation_evidence_refs: set[str] = set()

    for required in required_capabilities:
        capability_id = required["capability_id"]
        required_interfaces = set(required["required_interfaces"])
        compatible_candidates: list[dict[str, Any]] = []

        for candidate in existing_by_capability.get(capability_id, []):
            provided_interfaces = set(candidate["provided_interfaces"])
            if required_interfaces and not required_interfaces.issubset(provided_interfaces):
                continue
            recommendation_evidence_refs.update(candidate["evidence_refs"])
            compatible_candidates.append(candidate)

        if compatible_candidates:
            reuse_recommendations.append(
                {
                    "capability_id": capability_id,
                    "intent": required["intent"],
                    "required_interfaces": required["required_interfaces"],
                    "reuse_candidates": compatible_candidates,
                }
            )
        else:
            no_reuse_detected.append(
                {
                    "capability_id": capability_id,
                    "intent": required["intent"],
                    "required_interfaces": required["required_interfaces"],
                    "reason": "no_compatible_existing_functionality",
                }
            )

    reuse_recommendations.sort(key=lambda row: row["capability_id"])
    no_reuse_detected.sort(key=lambda row: row["capability_id"])
    open_risks = _build_reuse_open_risks(
        earth_sweep_source_artifacts=earth_sweep_source_artifacts,
        required_context_documents=required_context_documents,
    )
    recommendation_evidence_ref_list = sorted(
        recommendation_evidence_refs.union(
            ref for row in open_risks for ref in row["required_evidence_refs"]
        )
    )

    if reuse_recommendations and not no_reuse_detected and not open_risks:
        decision = "reuse_before_reimplement"
    elif reuse_recommendations and not open_risks:
        decision = "partial_reuse_recommended"
    elif reuse_recommendations:
        decision = "partial_reuse_recommended_with_open_risks"
    elif open_risks:
        decision = "blocked_context_gaps"
    else:
        decision = "no_reuse_opportunity_detected"

    return {
        "requirement_id": "REQ-016",
        "surface": "reuse_opportunity_detection",
        "schema_version": REQ_016_SCHEMA_VERSION,
        "evaluated_at": _require_nonempty_str(evaluated_at or _utc_now_iso(), label="evaluated_at"),
        "active_project_id": active_project_id,
        "reuse_index": {
            "required_capability_ids": [row["capability_id"] for row in required_capabilities],
            "source_project_ids": source_project_id_list,
        },
        "reuse_recommendations": reuse_recommendations,
        "no_reuse_detected": no_reuse_detected,
        "open_risks": open_risks,
        "evidence_refs": recommendation_evidence_ref_list,
        "decision": decision,
        "summary": (
            f"{len(reuse_recommendations)} capability reuse recommendation(s); "
            f"{len(no_reuse_detected)} capability gap(s); "
            f"{len(open_risks)} open risk(s)."
        ),
    }


def serialize_reuse_opportunity_context_bundle(payload: Mapping[str, Any]) -> dict[str, str]:
    context = _require_mapping(payload, label="reuse_opportunity_context_bundle")
    active_project_id = _require_nonempty_str(
        context.get("active_project_id"),
        label="reuse_opportunity_context_bundle.active_project_id",
    )
    required_capabilities = _normalize_reuse_required_capabilities(context.get("required_capabilities"))
    existing_functionality, _ = _normalize_reuse_existing_functionality(
        context.get("existing_functionality"),
        active_project_id=active_project_id,
    )
    earth_sweep_source_artifacts = _normalize_reuse_earth_sweep_source_artifacts(
        context.get("earth_sweep_source_artifacts")
    )
    required_context_documents = _normalize_reuse_required_context_documents(
        context.get("required_context_documents")
    )
    canonical_bundle = _canonical_reuse_opportunity_context_bundle(
        active_project_id=active_project_id,
        required_capabilities=required_capabilities,
        existing_functionality=existing_functionality,
        earth_sweep_source_artifacts=earth_sweep_source_artifacts,
        required_context_documents=required_context_documents,
    )
    serialized_payload = json.dumps(
        canonical_bundle,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "requirement_id": "REQ-016",
        "surface": "reuse_opportunity_context_bundle",
        "schema_version": REQ_016_CONTEXT_BUNDLE_SCHEMA_VERSION,
        "serialization_format": "json-canonical-v1",
        "checksum_sha256": hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest(),
        "serialized_payload": serialized_payload,
    }


def serialize_ground_graph_context_bundle(payload: Mapping[str, Any]) -> dict[str, str]:
    context_bundle = _require_mapping(payload, label="ground_graph_context_bundle")
    serialized_payload = json.dumps(
        context_bundle,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "requirement_id": "REQ-007",
        "surface": "ground_graph_context_bundle",
        "schema_version": REQ_007_CONTEXT_BUNDLE_SCHEMA_VERSION,
        "serialization_format": "json-canonical-v1",
        "checksum_sha256": hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest(),
        "serialized_payload": serialized_payload,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="REQ-007 Ground graph snapshot ingestion")
    parser.add_argument("--input", required=True, help="Path to Ground graph snapshot JSON")
    parser.add_argument("--output", help="Path to write canonical ingestion JSON")
    parser.add_argument("--source-path", help="Source path string stored in output")
    parser.add_argument("--ingested-at", help="ISO-8601 timestamp to stamp in output")
    parser.add_argument(
        "--broad-sweep-context",
        help="Optional path to broad-sweep context JSON for deterministic REQ-007 recommendation processing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser().resolve()
    source_path = args.source_path or str(input_path)
    _print_human(f"Loading Ground graph snapshot from {input_path}")
    snapshot = load_ground_graph_snapshot(input_path)

    if args.broad_sweep_context:
        broad_sweep_context_path = Path(args.broad_sweep_context).expanduser().resolve()
        _print_human(f"Loading broad-sweep context from {broad_sweep_context_path}")
        broad_sweep_context = load_json_object(broad_sweep_context_path)
        _print_human("Processing snapshot with broad-sweep context for deterministic REQ-007 recommendation output")
        ingested = process_ground_graph_snapshot(
            snapshot,
            broad_sweep_context=broad_sweep_context,
            source_path=source_path,
            ingested_at=args.ingested_at,
        )
    else:
        _print_human("Ingesting snapshot into canonical REQ-007 lineage context")
        ingested = ingest_ground_graph_snapshot(snapshot, source_path=source_path, ingested_at=args.ingested_at)

    rendered = json.dumps(ingested, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        _print_human(
            f"Wrote ingestion artifact to {output_path} with {len(ingested['lineage_anchors'])} lineage anchor rows"
        )
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
