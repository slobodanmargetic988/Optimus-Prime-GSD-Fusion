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
    for key in ("cross_project_action_candidates", "candidate_actions", "recommendation_candidates"):
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
