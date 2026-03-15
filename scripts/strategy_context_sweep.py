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
REQ012_SCHEMA_VERSION = "REQ-012-interface-contract-extraction.v1"
SUPPORTED_DOCUMENT_TYPES = {"mission", "scope"}
OBLIGATION_PATTERN = re.compile(r"\b(must|shall|required|needs?\s+to)\b", re.IGNORECASE)
OPTIONAL_OBLIGATION_PATTERN = re.compile(r"\b(should|may|optional|can|recommended)\b", re.IGNORECASE)
REUSE_PATTERN = re.compile(r"\b(reuse|shared|common|template|library|leverage|integrate)\b", re.IGNORECASE)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
INTERFACE_DECLARATION_PATTERN = re.compile(
    r"\binterface\s*[:\-]\s*([a-z0-9][a-z0-9_.-]*(?:\.v[0-9]+)?)\b",
    re.IGNORECASE,
)
INTERFACE_TOKEN_PATTERN = re.compile(
    r"\b([a-z0-9][a-z0-9-]*(?:[._-][a-z0-9-]+)*\.v[0-9]+)\b",
    re.IGNORECASE,
)

REASON_CODE_MISSING_EARTH_SWEEP_EVIDENCE = "missing_earth_sweep_evidence_refs"
REASON_CODE_STALE_EARTH_SWEEP_SOURCE_ARTIFACT = "stale_earth_sweep_source_artifact_detected"
REASON_CODE_MISSING_PEER_PROJECT_DOCUMENTS = "missing_peer_project_documents"
REASON_CODE_MISSING_MISSION_OR_SCOPE_DOCUMENT = "missing_peer_mission_or_scope_document"


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


def _require_positive_int(value: Any, *, field_name: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")
    return value


def _provenance_match_key(*, peer_project_id: str, source_path: str, line_number: int) -> tuple[str, str, int]:
    return peer_project_id, source_path, line_number


def _provenance_match_key_string(*, peer_project_id: str, source_path: str, line_number: int) -> str:
    return f"{peer_project_id}:{source_path}:{line_number}"


def _normalize_optional_sha256(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string when present.")
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty SHA256 string when present.")
    if not SHA256_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase 64-char SHA256 hex value.")
    return normalized


def _index_earth_sweep_evidence_refs(
    payload_obj: dict[str, Any],
) -> tuple[dict[tuple[str, str, int], list[dict[str, Any]]], int]:
    raw_context = payload_obj.get("earth_sweep_context")
    if raw_context is None:
        return {}, 0

    context_obj = _require_mapping(raw_context, field_name="earth_sweep_context")
    raw_evidence_refs = _require_list(context_obj.get("evidence_refs"), field_name="earth_sweep_context.evidence_refs")
    evidence_index: dict[tuple[str, str, int], set[tuple[str, str | None]]] = {}

    for idx, raw_item in enumerate(raw_evidence_refs):
        item = _require_mapping(raw_item, field_name=f"earth_sweep_context.evidence_refs[{idx}]")
        peer_project_id = _require_non_empty_string(
            item.get("peer_project_id"),
            field_name=f"earth_sweep_context.evidence_refs[{idx}].peer_project_id",
        )
        source_path = _require_non_empty_string(
            item.get("source_path"),
            field_name=f"earth_sweep_context.evidence_refs[{idx}].source_path",
        )
        line_number = _require_positive_int(
            item.get("line_number"),
            field_name=f"earth_sweep_context.evidence_refs[{idx}].line_number",
        )
        evidence_ref = _require_non_empty_string(
            item.get("evidence_ref"),
            field_name=f"earth_sweep_context.evidence_refs[{idx}].evidence_ref",
        )
        source_sha256 = _normalize_optional_sha256(
            item.get("source_sha256"),
            field_name=f"earth_sweep_context.evidence_refs[{idx}].source_sha256",
        )
        key = _provenance_match_key(
            peer_project_id=peer_project_id,
            source_path=source_path,
            line_number=line_number,
        )
        evidence_index.setdefault(key, set()).add((evidence_ref, source_sha256))

    normalized_index = {
        key: [
            {
                "evidence_ref": evidence_ref,
                "source_sha256": source_sha256,
            }
            for evidence_ref, source_sha256 in sorted(refs, key=lambda item: (item[0], item[1] or ""))
        ]
        for key, refs in sorted(
            evidence_index.items(),
            key=lambda item: (item[0][0], item[0][1], item[0][2]),
        )
    }
    return normalized_index, len(raw_evidence_refs)


def _collect_evidence_refs_for_provenance(
    *,
    peer_project_id: str,
    source_provenance: list[dict[str, Any]],
    earth_sweep_evidence_index: dict[tuple[str, str, int], list[dict[str, Any]]],
) -> tuple[list[str], list[str], list[str]]:
    recommendation_refs: set[str] = set()
    stale_refs: set[str] = set()
    match_keys: list[str] = []
    for provenance in source_provenance:
        source_path = provenance.get("source_path")
        line_number = provenance.get("line_number")
        source_sha256 = provenance.get("source_sha256")
        if not isinstance(source_path, str) or not source_path:
            continue
        if not isinstance(line_number, int) or line_number <= 0:
            continue
        if not isinstance(source_sha256, str) or not source_sha256:
            source_sha256 = None
        key = _provenance_match_key(
            peer_project_id=peer_project_id,
            source_path=source_path,
            line_number=line_number,
        )
        key_string = _provenance_match_key_string(
            peer_project_id=peer_project_id,
            source_path=source_path,
            line_number=line_number,
        )
        match_keys.append(key_string)
        for entry in earth_sweep_evidence_index.get(key, []):
            evidence_ref = entry.get("evidence_ref")
            expected_sha256 = entry.get("source_sha256")
            if not isinstance(evidence_ref, str) or not evidence_ref:
                continue
            if (
                isinstance(expected_sha256, str)
                and expected_sha256
                and isinstance(source_sha256, str)
                and source_sha256
                and expected_sha256 != source_sha256
            ):
                stale_refs.add(evidence_ref)
                continue
            recommendation_refs.add(evidence_ref)
    return sorted(recommendation_refs), sorted(stale_refs), sorted(set(match_keys))


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _context_evidence_ref(peer_project_id: str, surface: str) -> str:
    return f"peer-project/{peer_project_id}/{surface}"


def _build_context_bundle(
    *,
    current_project_id: str,
    peer_models: list[dict[str, Any]],
    cross_project_recommendations: list[dict[str, Any]],
    open_risks: list[dict[str, Any]],
    earth_sweep_evidence_index: dict[tuple[str, str, int], list[dict[str, Any]]],
) -> dict[str, Any]:
    earth_sweep_index_rows = []
    for key, refs in sorted(earth_sweep_evidence_index.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
        peer_project_id, source_path, line_number = key
        earth_sweep_index_rows.append(
            {
                "peer_project_id": peer_project_id,
                "source_path": source_path,
                "line_number": line_number,
                "evidence_refs": [str(item.get("evidence_ref")) for item in refs if isinstance(item, dict)],
                "source_sha256": sorted(
                    {
                        str(item.get("source_sha256"))
                        for item in refs
                        if isinstance(item, dict) and isinstance(item.get("source_sha256"), str) and item.get("source_sha256")
                    }
                ),
            }
        )

    payload = {
        "current_project_id": current_project_id,
        "peer_project_models": peer_models,
        "cross_project_recommendations": cross_project_recommendations,
        "open_risks": open_risks,
        "earth_sweep_index": earth_sweep_index_rows,
    }
    serialized = _canonical_json(payload)
    return {
        "bundle_version": "REQ-004-context-bundle.v1",
        "serialization_format": "json-canonical-sort-keys",
        "serialization_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "serialization": serialized,
        "entry_counts": {
            "peer_project_model_count": len(peer_models),
            "recommendation_count": len(cross_project_recommendations),
            "open_risk_count": len(open_risks),
            "earth_sweep_index_count": len(earth_sweep_index_rows),
        },
    }


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


def _normalize_applies_to_projects(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return ["*"]
    entries = _require_list(value, field_name=field_name)
    normalized: list[str] = []
    for idx, raw_entry in enumerate(entries):
        entry = _require_non_empty_string(raw_entry, field_name=f"{field_name}[{idx}]")
        normalized.append(entry)
    return normalized


def _source_is_relevant_to_target(*, applies_to_projects: list[str], target_project_id: str) -> bool:
    normalized = {item.strip().lower() for item in applies_to_projects if isinstance(item, str)}
    if "*" in normalized:
        return True
    return target_project_id.lower() in normalized


def _classify_obligation_level(statement: str) -> str | None:
    if OBLIGATION_PATTERN.search(statement):
        return "required"
    if OPTIONAL_OBLIGATION_PATTERN.search(statement):
        return "optional"
    return None


def _extract_interface_id_from_statement(statement: str, *, active_interface_id: str | None) -> str | None:
    declaration_match = INTERFACE_DECLARATION_PATTERN.search(statement)
    if declaration_match:
        return declaration_match.group(1).strip().lower()

    token_match = INTERFACE_TOKEN_PATTERN.search(statement)
    if token_match:
        return token_match.group(1).strip().lower()

    return active_interface_id


def extract_interface_contracts(payload: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    payload_obj = _require_mapping(payload, field_name="payload")
    current_project = _require_mapping(payload_obj.get("current_project"), field_name="current_project")
    current_project_id = _require_non_empty_string(
        current_project.get("project_id"), field_name="current_project.project_id"
    )
    contract_sources = _require_list(payload_obj.get("earth_contract_sources"), field_name="earth_contract_sources")
    earth_sweep_evidence_index, earth_sweep_evidence_entry_count = _index_earth_sweep_evidence_refs(payload_obj)

    interfaces_by_id: dict[str, dict[str, Any]] = {}
    obligation_index = 0
    required_count = 0
    optional_count = 0
    relevant_source_count = 0
    cross_project_recommendations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    used_earth_sweep_refs: set[str] = set()
    recommendation_index = 0
    risk_index = 0

    for source_idx, raw_source in enumerate(contract_sources):
        source = _require_mapping(raw_source, field_name=f"earth_contract_sources[{source_idx}]")
        source_id = _require_non_empty_string(
            source.get("source_id"),
            field_name=f"earth_contract_sources[{source_idx}].source_id",
        )
        source_path = _require_non_empty_string(
            source.get("source_path"),
            field_name=f"earth_contract_sources[{source_idx}].source_path",
        )
        content = _require_non_empty_string(
            source.get("content"),
            field_name=f"earth_contract_sources[{source_idx}].content",
        )
        applies_to_projects = _normalize_applies_to_projects(
            source.get("applies_to_projects"),
            field_name=f"earth_contract_sources[{source_idx}].applies_to_projects",
        )
        if not _source_is_relevant_to_target(
            applies_to_projects=applies_to_projects,
            target_project_id=current_project_id,
        ):
            continue
        relevant_source_count += 1
        source_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        active_interface_id: str | None = None

        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            statement = raw_line.strip()
            if not statement:
                continue
            active_interface_id = _extract_interface_id_from_statement(
                statement,
                active_interface_id=active_interface_id,
            )
            obligation_level = _classify_obligation_level(statement)
            if obligation_level is None or active_interface_id is None:
                continue

            obligation_index += 1
            if obligation_level == "required":
                required_count += 1
            else:
                optional_count += 1

            interface_entry = interfaces_by_id.setdefault(
                active_interface_id,
                {
                    "interface_id": active_interface_id,
                    "source_contract_ids": set(),
                    "required_obligation_count": 0,
                    "optional_obligation_count": 0,
                    "obligations": [],
                },
            )
            interface_entry["source_contract_ids"].add(source_id)
            if obligation_level == "required":
                interface_entry["required_obligation_count"] += 1
            else:
                interface_entry["optional_obligation_count"] += 1

            interface_entry["obligations"].append(
                {
                    "obligation_id": f"ICO-{obligation_index:04d}",
                    "obligation_level": obligation_level,
                    "statement": statement,
                    "source_provenance": [
                        {
                            "source_id": source_id,
                            "source_path": source_path,
                            "source_sha256": source_sha256,
                            "line_number": line_number,
                            "excerpt": statement,
                        }
                    ],
                }
            )

    shared_interface_contracts = []
    for interface_id in sorted(interfaces_by_id.keys()):
        row = interfaces_by_id[interface_id]
        obligations = row["obligations"]
        for obligation in obligations:
            source_provenance = obligation["source_provenance"]
            source_project_id = "earth-contracts"
            if source_provenance and isinstance(source_provenance[0], dict):
                source_id = source_provenance[0].get("source_id")
                if isinstance(source_id, str) and source_id:
                    source_project_id = source_id
            recommendation_refs, stale_refs, context_keys = _collect_evidence_refs_for_provenance(
                peer_project_id=source_project_id,
                source_provenance=source_provenance,
                earth_sweep_evidence_index=earth_sweep_evidence_index,
            )
            if recommendation_refs:
                recommendation_index += 1
                used_earth_sweep_refs.update(recommendation_refs)
                obligation_level = obligation["obligation_level"]
                cross_project_recommendations.append(
                    {
                        "recommendation_id": f"REC-{recommendation_index:04d}",
                        "recommendation_type": "interface_obligation",
                        "source_project_id": source_project_id,
                        "target_project_id": current_project_id,
                        "interface_id": interface_id,
                        "obligation_id": obligation["obligation_id"],
                        "obligation_level": obligation_level,
                        "summary": (
                            f"Adopt {obligation_level} {interface_id} obligation: "
                            f"{obligation['statement']}"
                        ),
                        "rationale": (
                            "Shared interface obligation backed by Earth-sweep evidence."
                            if obligation_level == "required"
                            else (
                                "Shared interface optional guidance backed by Earth-sweep evidence; "
                                "do not over-constrain downstream plans."
                            )
                        ),
                        "source_provenance": source_provenance,
                        "evidence_refs": recommendation_refs,
                        "cross_project_context": {
                            "context_type": "earth_sweep",
                            "match_keys": context_keys,
                            "evidence_ref_count": len(recommendation_refs),
                        },
                    }
                )
            elif stale_refs:
                risk_index += 1
                open_risks.append(
                    {
                        "risk_id": f"RISK-{risk_index:04d}",
                        "risk_type": "stale_earth_sweep_source_artifact",
                        "reason_code": REASON_CODE_STALE_EARTH_SWEEP_SOURCE_ARTIFACT,
                        "recommendation_type": "interface_obligation",
                        "source_project_id": source_project_id,
                        "target_project_id": current_project_id,
                        "interface_id": interface_id,
                        "obligation_id": obligation["obligation_id"],
                        "summary": (
                            "Shared interface obligation matched stale Earth-sweep source artifacts; "
                            f"kept as open risk: {obligation['statement']}"
                        ),
                        "required_context_match_keys": context_keys,
                        "source_provenance": source_provenance,
                        "evidence_refs": stale_refs,
                    }
                )
            else:
                risk_index += 1
                open_risks.append(
                    {
                        "risk_id": f"RISK-{risk_index:04d}",
                        "risk_type": "missing_earth_sweep_evidence",
                        "reason_code": REASON_CODE_MISSING_EARTH_SWEEP_EVIDENCE,
                        "recommendation_type": "interface_obligation",
                        "source_project_id": source_project_id,
                        "target_project_id": current_project_id,
                        "interface_id": interface_id,
                        "obligation_id": obligation["obligation_id"],
                        "summary": (
                            "Shared interface obligation lacks Earth-sweep evidence refs; "
                            f"kept as open risk: {obligation['statement']}"
                        ),
                        "required_context_match_keys": context_keys,
                        "source_provenance": source_provenance,
                        "evidence_refs": [],
                    }
                )

        shared_interface_contracts.append(
            {
                "interface_id": interface_id,
                "source_contract_ids": sorted(row["source_contract_ids"]),
                "required_obligation_count": row["required_obligation_count"],
                "optional_obligation_count": row["optional_obligation_count"],
                "obligations": obligations,
            }
        )

    return {
        "schema_version": REQ012_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now_iso(),
        "current_project_id": current_project_id,
        "shared_interface_contracts": shared_interface_contracts,
        "cross_project_recommendations": cross_project_recommendations,
        "open_risks": open_risks,
        "summary": {
            "earth_contract_source_count": len(contract_sources),
            "relevant_source_count": relevant_source_count,
            "shared_interface_contract_count": len(shared_interface_contracts),
            "required_obligation_count": required_count,
            "optional_obligation_count": optional_count,
            "total_obligation_count": required_count + optional_count,
            "recommendation_count": len(cross_project_recommendations),
            "open_risk_count": len(open_risks),
            "earth_sweep_context_entry_count": earth_sweep_evidence_entry_count,
            "earth_sweep_evidence_refs_used_count": len(used_earth_sweep_refs),
        },
    }


def extract_interface_contracts_file(
    *, input_path: Path, output_path: Path, generated_at: str | None = None
) -> dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    result = extract_interface_contracts(payload, generated_at=generated_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def ingest_peer_project_mission_and_scope(
    payload: dict[str, Any], *, generated_at: str | None = None
) -> dict[str, Any]:
    payload_obj = _require_mapping(payload, field_name="payload")
    current_project = _require_mapping(payload_obj.get("current_project"), field_name="current_project")
    current_project_id = _require_non_empty_string(
        current_project.get("project_id"), field_name="current_project.project_id"
    )
    peer_projects = _require_list(payload_obj.get("peer_projects"), field_name="peer_projects")
    earth_sweep_evidence_index, earth_sweep_evidence_entry_count = _index_earth_sweep_evidence_refs(payload_obj)

    peer_models: list[dict[str, Any]] = []
    cross_project_recommendations: list[dict[str, Any]] = []
    open_risks: list[dict[str, Any]] = []
    used_earth_sweep_refs: set[str] = set()
    recommendation_index = 0
    risk_index = 0
    peer_projects_with_signals = 0

    for peer in peer_projects:
        peer_obj = _require_mapping(peer, field_name="peer_projects[]")
        peer_project_id = _require_non_empty_string(peer_obj.get("project_id"), field_name="peer_projects[].project_id")
        raw_documents = peer_obj.get("documents")
        documents_missing = not isinstance(raw_documents, list)
        documents = raw_documents if isinstance(raw_documents, list) else []

        ingested_documents: list[dict[str, Any]] = []
        interaction_obligations: list[dict[str, Any]] = []
        reuse_opportunities: list[dict[str, Any]] = []
        obligation_counter = 0
        reuse_counter = 0

        if documents_missing:
            risk_index += 1
            open_risks.append(
                {
                    "risk_id": f"RISK-{risk_index:04d}",
                    "risk_type": "missing_peer_project_documents",
                    "reason_code": REASON_CODE_MISSING_PEER_PROJECT_DOCUMENTS,
                    "recommendation_type": "peer_project_documents",
                    "source_project_id": peer_project_id,
                    "target_project_id": current_project_id,
                    "summary": (
                        "Peer project documents are missing or invalid; mission/scope ingestion cannot evaluate this peer."
                    ),
                    "required_context_match_keys": [f"{peer_project_id}:documents"],
                    "source_provenance": [],
                    "evidence_refs": [_context_evidence_ref(peer_project_id, "documents#missing")],
                }
            )

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

        if not documents_missing:
            ingested_document_types = {row["document_type"] for row in ingested_documents if isinstance(row, dict)}
            missing_document_types = sorted(SUPPORTED_DOCUMENT_TYPES - ingested_document_types)
            if missing_document_types:
                signal_provenance: list[dict[str, Any]] = []
                seen_keys: set[tuple[str, str, int]] = set()
                for signal_row in interaction_obligations + reuse_opportunities:
                    source_rows = signal_row.get("source_provenance")
                    if not isinstance(source_rows, list):
                        continue
                    for item in source_rows:
                        if not isinstance(item, dict):
                            continue
                        source_path = item.get("source_path")
                        line_number = item.get("line_number")
                        if not isinstance(source_path, str) or not source_path:
                            continue
                        if not isinstance(line_number, int) or line_number <= 0:
                            continue
                        key = (peer_project_id, source_path, line_number)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        signal_provenance.append(item)

                evidence_refs = sorted(
                    {
                        _context_evidence_ref(peer_project_id, f"{doc['document_type']}#{doc['source_path']}")
                        for doc in ingested_documents
                        if isinstance(doc, dict)
                        and isinstance(doc.get("document_type"), str)
                        and doc.get("document_type")
                        and isinstance(doc.get("source_path"), str)
                        and doc.get("source_path")
                    }
                )
                if not evidence_refs:
                    evidence_refs = [_context_evidence_ref(peer_project_id, "mission-scope#missing")]

                risk_index += 1
                open_risks.append(
                    {
                        "risk_id": f"RISK-{risk_index:04d}",
                        "risk_type": "missing_mission_or_scope_document",
                        "reason_code": REASON_CODE_MISSING_MISSION_OR_SCOPE_DOCUMENT,
                        "recommendation_type": "peer_project_documents",
                        "source_project_id": peer_project_id,
                        "target_project_id": current_project_id,
                        "summary": (
                            "Peer project mission/scope coverage is incomplete; "
                            f"missing document types: {', '.join(missing_document_types)}."
                        ),
                        "missing_document_types": missing_document_types,
                        "required_context_match_keys": [
                            f"{peer_project_id}:{document_type}" for document_type in missing_document_types
                        ],
                        "source_provenance": signal_provenance,
                        "evidence_refs": evidence_refs,
                    }
                )

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
            recommendation_refs, stale_refs, context_keys = _collect_evidence_refs_for_provenance(
                peer_project_id=peer_project_id,
                source_provenance=obligation["source_provenance"],
                earth_sweep_evidence_index=earth_sweep_evidence_index,
            )
            if recommendation_refs:
                recommendation_index += 1
                used_earth_sweep_refs.update(recommendation_refs)
                cross_project_recommendations.append(
                    {
                        "recommendation_id": f"REC-{recommendation_index:04d}",
                        "recommendation_type": "interaction_obligation",
                        "source_project_id": peer_project_id,
                        "target_project_id": current_project_id,
                        "summary": f"Honor peer interaction obligation: {obligation['statement']}",
                        "rationale": "Mission/scope obligation backed by Earth-sweep evidence.",
                        "source_provenance": obligation["source_provenance"],
                        "evidence_refs": recommendation_refs,
                        "cross_project_context": {
                            "context_type": "earth_sweep",
                            "match_keys": context_keys,
                            "evidence_ref_count": len(recommendation_refs),
                        },
                    }
                )
            elif stale_refs:
                risk_index += 1
                open_risks.append(
                    {
                        "risk_id": f"RISK-{risk_index:04d}",
                        "risk_type": "stale_earth_sweep_source_artifact",
                        "reason_code": REASON_CODE_STALE_EARTH_SWEEP_SOURCE_ARTIFACT,
                        "recommendation_type": "interaction_obligation",
                        "source_project_id": peer_project_id,
                        "target_project_id": current_project_id,
                        "summary": (
                            "Inferred interaction obligation matched stale Earth-sweep source artifacts; "
                            f"kept as open risk: {obligation['statement']}"
                        ),
                        "required_context_match_keys": context_keys,
                        "source_provenance": obligation["source_provenance"],
                        "evidence_refs": stale_refs,
                    }
                )
            else:
                risk_index += 1
                open_risks.append(
                    {
                        "risk_id": f"RISK-{risk_index:04d}",
                        "risk_type": "missing_earth_sweep_evidence",
                        "reason_code": REASON_CODE_MISSING_EARTH_SWEEP_EVIDENCE,
                        "recommendation_type": "interaction_obligation",
                        "source_project_id": peer_project_id,
                        "target_project_id": current_project_id,
                        "summary": (
                            "Inferred interaction obligation lacks Earth-sweep evidence refs; "
                            f"kept as open risk: {obligation['statement']}"
                        ),
                        "required_context_match_keys": context_keys,
                        "source_provenance": obligation["source_provenance"],
                        "evidence_refs": [],
                    }
                )
        for opportunity in reuse_opportunities:
            recommendation_refs, stale_refs, context_keys = _collect_evidence_refs_for_provenance(
                peer_project_id=peer_project_id,
                source_provenance=opportunity["source_provenance"],
                earth_sweep_evidence_index=earth_sweep_evidence_index,
            )
            if recommendation_refs:
                recommendation_index += 1
                used_earth_sweep_refs.update(recommendation_refs)
                cross_project_recommendations.append(
                    {
                        "recommendation_id": f"REC-{recommendation_index:04d}",
                        "recommendation_type": "reuse_opportunity",
                        "source_project_id": peer_project_id,
                        "target_project_id": current_project_id,
                        "summary": f"Reuse peer capability or artifact: {opportunity['statement']}",
                        "rationale": "Mission/scope reuse signal backed by Earth-sweep evidence.",
                        "source_provenance": opportunity["source_provenance"],
                        "evidence_refs": recommendation_refs,
                        "cross_project_context": {
                            "context_type": "earth_sweep",
                            "match_keys": context_keys,
                            "evidence_ref_count": len(recommendation_refs),
                        },
                    }
                )
            elif stale_refs:
                risk_index += 1
                open_risks.append(
                    {
                        "risk_id": f"RISK-{risk_index:04d}",
                        "risk_type": "stale_earth_sweep_source_artifact",
                        "reason_code": REASON_CODE_STALE_EARTH_SWEEP_SOURCE_ARTIFACT,
                        "recommendation_type": "reuse_opportunity",
                        "source_project_id": peer_project_id,
                        "target_project_id": current_project_id,
                        "summary": (
                            "Inferred reuse opportunity matched stale Earth-sweep source artifacts; "
                            f"kept as open risk: {opportunity['statement']}"
                        ),
                        "required_context_match_keys": context_keys,
                        "source_provenance": opportunity["source_provenance"],
                        "evidence_refs": stale_refs,
                    }
                )
            else:
                risk_index += 1
                open_risks.append(
                    {
                        "risk_id": f"RISK-{risk_index:04d}",
                        "risk_type": "missing_earth_sweep_evidence",
                        "reason_code": REASON_CODE_MISSING_EARTH_SWEEP_EVIDENCE,
                        "recommendation_type": "reuse_opportunity",
                        "source_project_id": peer_project_id,
                        "target_project_id": current_project_id,
                        "summary": (
                            "Inferred reuse opportunity lacks Earth-sweep evidence refs; "
                            f"kept as open risk: {opportunity['statement']}"
                        ),
                        "required_context_match_keys": context_keys,
                        "source_provenance": opportunity["source_provenance"],
                        "evidence_refs": [],
                    }
                )

    context_bundle = _build_context_bundle(
        current_project_id=current_project_id,
        peer_models=peer_models,
        cross_project_recommendations=cross_project_recommendations,
        open_risks=open_risks,
        earth_sweep_evidence_index=earth_sweep_evidence_index,
    )

    return {
        "schema_version": REQ004_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now_iso(),
        "current_project_id": current_project_id,
        "peer_project_models": peer_models,
        "cross_project_recommendations": cross_project_recommendations,
        "open_risks": open_risks,
        "context_bundle": context_bundle,
        "summary": {
            "peer_projects_evaluated": len(peer_projects),
            "peer_projects_with_signals": peer_projects_with_signals,
            "interaction_obligation_count": sum(len(peer["interaction_obligations"]) for peer in peer_models),
            "reuse_opportunity_count": sum(len(peer["reuse_opportunities"]) for peer in peer_models),
            "recommendation_count": len(cross_project_recommendations),
            "open_risk_count": len(open_risks),
            "earth_sweep_context_entry_count": earth_sweep_evidence_entry_count,
            "earth_sweep_evidence_refs_used_count": len(used_earth_sweep_refs),
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
