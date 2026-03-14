#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQ004_SCHEMA_VERSION = "REQ-004-peer-project-mission-and-scope-ingestion.v1"
SUPPORTED_DOCUMENT_TYPES = {"mission", "scope"}
OBLIGATION_PATTERN = re.compile(r"\b(must|shall|required|needs?\s+to)\b", re.IGNORECASE)
REUSE_PATTERN = re.compile(r"\b(reuse|shared|common|template|library|leverage|integrate)\b", re.IGNORECASE)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamped_print(message: str) -> None:
    print(f"[{_utc_now_iso()}] {message}")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _require_non_empty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return normalized


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object.")
    return value


def _require_list(value: Any, *, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array.")
    return value


def _extract_signals_from_document(
    *,
    peer_project_id: str,
    document_type: str,
    source_path: str,
    source_sha256: str,
    content: str,
    obligation_start_index: int,
    reuse_start_index: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    interaction_obligations: list[dict[str, Any]] = []
    reuse_opportunities: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        statement = raw_line.strip()
        if not statement:
            continue
        provenance = {
            "document_type": document_type,
            "source_path": source_path,
            "source_sha256": source_sha256,
            "line_number": line_number,
            "excerpt": statement,
        }
        if OBLIGATION_PATTERN.search(statement):
            obligation_start_index += 1
            interaction_obligations.append(
                {
                    "obligation_id": f"OBL-{_slug(peer_project_id)}-{obligation_start_index:03d}",
                    "statement": statement,
                    "source_provenance": [provenance],
                }
            )
        if REUSE_PATTERN.search(statement):
            reuse_start_index += 1
            reuse_opportunities.append(
                {
                    "opportunity_id": f"REUSE-{_slug(peer_project_id)}-{reuse_start_index:03d}",
                    "statement": statement,
                    "source_provenance": [provenance],
                }
            )

    return interaction_obligations, reuse_opportunities, obligation_start_index, reuse_start_index


def ingest_peer_project_mission_and_scope(
    payload: dict[str, Any], *, generated_at: str | None = None
) -> dict[str, Any]:
    payload_obj = _require_mapping(payload, field_name="payload")
    current_project = _require_mapping(payload_obj.get("current_project"), field_name="current_project")
    current_project_id = _require_non_empty_string(
        current_project.get("project_id"), field_name="current_project.project_id"
    )
    peer_projects = _require_list(payload_obj.get("peer_projects"), field_name="peer_projects")

    peer_models: list[dict[str, Any]] = []
    cross_project_recommendations: list[dict[str, Any]] = []
    recommendation_index = 0
    peer_projects_with_signals = 0

    for peer in peer_projects:
        peer_obj = _require_mapping(peer, field_name="peer_projects[]")
        peer_project_id = _require_non_empty_string(peer_obj.get("project_id"), field_name="peer_projects[].project_id")
        documents = _require_list(peer_obj.get("documents"), field_name=f"peer_projects[{peer_project_id}].documents")

        ingested_documents: list[dict[str, Any]] = []
        interaction_obligations: list[dict[str, Any]] = []
        reuse_opportunities: list[dict[str, Any]] = []
        obligation_counter = 0
        reuse_counter = 0

        for document in documents:
            document_obj = _require_mapping(document, field_name=f"peer_projects[{peer_project_id}].documents[]")
            document_type = _require_non_empty_string(
                document_obj.get("document_type"),
                field_name=f"peer_projects[{peer_project_id}].documents[].document_type",
            ).lower()
            source_path = _require_non_empty_string(
                document_obj.get("source_path"),
                field_name=f"peer_projects[{peer_project_id}].documents[].source_path",
            )
            content = _require_non_empty_string(
                document_obj.get("content"),
                field_name=f"peer_projects[{peer_project_id}].documents[].content",
            )

            if document_type not in SUPPORTED_DOCUMENT_TYPES:
                continue

            source_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
            ingested_documents.append(
                {
                    "document_type": document_type,
                    "source_path": source_path,
                    "source_sha256": source_sha256,
                    "line_count": len(content.splitlines()),
                }
            )

            extracted_obligations, extracted_reuse, obligation_counter, reuse_counter = _extract_signals_from_document(
                peer_project_id=peer_project_id,
                document_type=document_type,
                source_path=source_path,
                source_sha256=source_sha256,
                content=content,
                obligation_start_index=obligation_counter,
                reuse_start_index=reuse_counter,
            )
            interaction_obligations.extend(extracted_obligations)
            reuse_opportunities.extend(extracted_reuse)

        if interaction_obligations or reuse_opportunities:
            peer_projects_with_signals += 1

        peer_model = {
            "peer_project_id": peer_project_id,
            "ingested_documents": ingested_documents,
            "interaction_obligations": interaction_obligations,
            "reuse_opportunities": reuse_opportunities,
        }
        peer_models.append(peer_model)

        for obligation in interaction_obligations:
            recommendation_index += 1
            cross_project_recommendations.append(
                {
                    "recommendation_id": f"REC-{recommendation_index:04d}",
                    "recommendation_type": "interaction_obligation",
                    "source_project_id": peer_project_id,
                    "target_project_id": current_project_id,
                    "summary": f"Honor peer interaction obligation: {obligation['statement']}",
                    "source_provenance": obligation["source_provenance"],
                }
            )
        for opportunity in reuse_opportunities:
            recommendation_index += 1
            cross_project_recommendations.append(
                {
                    "recommendation_id": f"REC-{recommendation_index:04d}",
                    "recommendation_type": "reuse_opportunity",
                    "source_project_id": peer_project_id,
                    "target_project_id": current_project_id,
                    "summary": f"Reuse peer capability or artifact: {opportunity['statement']}",
                    "source_provenance": opportunity["source_provenance"],
                }
            )

    return {
        "schema_version": REQ004_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now_iso(),
        "current_project_id": current_project_id,
        "peer_project_models": peer_models,
        "cross_project_recommendations": cross_project_recommendations,
        "summary": {
            "peer_projects_evaluated": len(peer_projects),
            "peer_projects_with_signals": peer_projects_with_signals,
            "interaction_obligation_count": sum(len(peer["interaction_obligations"]) for peer in peer_models),
            "reuse_opportunity_count": sum(len(peer["reuse_opportunities"]) for peer in peer_models),
            "recommendation_count": len(cross_project_recommendations),
        },
    }


def ingest_peer_project_mission_and_scope_file(
    *, input_path: Path, output_path: Path, generated_at: str | None = None
) -> dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    result = ingest_peer_project_mission_and_scope(payload, generated_at=generated_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="REQ-004 peer project mission/scope ingestion context sweep.")
    parser.add_argument(
        "--input",
        default="examples/fixtures/peer-project-mission-and-scope-ingestion.json",
        help="Path to REQ-004 ingestion fixture.",
    )
    parser.add_argument(
        "--output",
        default="strategy/current/samples/REQ-004_peer-project-mission-and-scope-ingestion.sample.json",
        help="Path to write REQ-004 sample output.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Optional RFC3339 UTC timestamp (for deterministic samples).",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    _timestamped_print(f"Starting REQ-004 ingestion using input: {input_path}")
    try:
        result = ingest_peer_project_mission_and_scope_file(
            input_path=input_path,
            output_path=output_path,
            generated_at=args.generated_at,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        _timestamped_print(f"REQ-004 ingestion failed: {exc}")
        return 2
    _timestamped_print(
        "REQ-004 ingestion completed. "
        f"Output={output_path} Recommendations={result['summary']['recommendation_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
