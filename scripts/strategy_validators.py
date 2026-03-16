#!/usr/bin/env python3
"""Strategy packet validators and planner consumability gates."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
for candidate in (SCRIPTS_ROOT,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts.strategy_artifacts_handoff import (
    REQ_054_ANALYSIS_TYPE,
    REQ_054_CALL_ID,
    REQ_054_REQUIREMENT_ID,
    REQ_054_SCHEMA_VERSION,
    validate_req_054_recommendation_to_planner_mapping_artifact,
)

SEVERITY_ERROR = "error"
REASON_REQ_054_CONTRACT_VIOLATION = "req_054_contract_violation"
REASON_PACKET_RECOMMENDATION_MISSING_MAPPING = "packet_recommendation_missing_mapping"
REASON_MAPPING_REFERENCES_UNKNOWN_PACKET_RECOMMENDATION = "mapping_references_unknown_packet_recommendation"
REASON_MAPPING_ARTIFACT_RECOMMENDATION_IDS_MISMATCH = "mapping_artifact_recommendation_ids_mismatch"
REASON_DUPLICATE_RECOMMENDATION_ID_COLLISION = "duplicate_recommendation_id_collision"
REASON_TRACEABILITY_GATE_FAILURE = "traceability_gate_failure"

_SCHEMA_REASON_CODE_BY_VALIDATOR = {
    "additionalProperties": "schema_additional_property",
    "const": "schema_const_mismatch",
    "enum": "schema_enum_violation",
    "maximum": "schema_maximum_violation",
    "minItems": "schema_min_items_violation",
    "minLength": "schema_min_length_violation",
    "minimum": "schema_minimum_violation",
    "pattern": "schema_pattern_mismatch",
    "required": "schema_required_field_missing",
    "type": "schema_type_mismatch",
}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_file(path: str | Path) -> Any:
    return _read_json(Path(path).expanduser().resolve())


def load_json_schema(path: str | Path) -> Mapping[str, Any]:
    payload = load_json_file(path)
    if not isinstance(payload, Mapping):
        raise ValueError("schema file must contain a JSON object")
    return payload


def _format_field_path(parts: Sequence[Any]) -> str:
    if not parts:
        return "$"
    rendered: list[str] = []
    for part in parts:
        if isinstance(part, int):
            if not rendered:
                rendered.append(f"[{part}]")
            else:
                rendered[-1] = f"{rendered[-1]}[{part}]"
            continue
        text = str(part)
        if not rendered:
            rendered.append(text)
        else:
            rendered.append(f".{text}")
    return "".join(rendered)


def _schema_field_path(error: Any) -> str:
    path = list(error.absolute_path)
    if error.validator == "required":
        match = re.search(r"'([^']+)' is a required property", error.message)
        if match:
            path.append(match.group(1))
    elif error.validator == "additionalProperties":
        match = re.search(r"\('([^']+)' was unexpected\)", error.message)
        if match:
            path.append(match.group(1))
    return _format_field_path(path)


def _schema_reason_code(error: Any) -> str:
    validator_name = str(error.validator)
    reason_code = _SCHEMA_REASON_CODE_BY_VALIDATOR.get(validator_name)
    if reason_code is not None:
        return reason_code

    normalized_validator = re.sub(r"(?<!^)(?=[A-Z])", "_", validator_name).lower()
    return f"schema_{normalized_validator}_violation"


def _diagnostic(*, field_path: str, reason_code: str, message: str, severity: str = SEVERITY_ERROR) -> dict[str, str]:
    return {
        "severity": severity,
        "reason_code": reason_code,
        "field_path": field_path,
        "message": message,
    }


def _sorted_diagnostics(diagnostics: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        diagnostics,
        key=lambda row: (
            row["field_path"],
            row["severity"],
            row["reason_code"],
            row["message"],
        ),
    )


def _req_054_envelope_from_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    mappings = artifact.get("recommendation_to_task_intent_mappings")
    mapping_rows = mappings if isinstance(mappings, list) else []

    recommendation_ids: set[str] = set()
    planner_task_intent_handles: set[str] = set()
    traceability_refs: set[str] = set()
    for row in mapping_rows:
        if not isinstance(row, Mapping):
            continue
        recommendation_id = row.get("recommendation_id")
        if isinstance(recommendation_id, str) and recommendation_id.strip():
            recommendation_ids.add(recommendation_id)
        planner_handle = row.get("planner_task_intent_handle")
        if isinstance(planner_handle, str) and planner_handle.strip():
            planner_task_intent_handles.add(planner_handle)
        refs = row.get("traceability_refs")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, str) and ref.strip():
                    traceability_refs.add(ref)

    return {
        "ok": True,
        "schema_version": REQ_054_SCHEMA_VERSION,
        "requirement_id": REQ_054_REQUIREMENT_ID,
        "analysis_type": REQ_054_ANALYSIS_TYPE,
        "call_id": REQ_054_CALL_ID,
        "checked_at_utc": "validator-probe",
        "recommendation_to_planner_mapping_artifact": artifact,
        "totals": {
            "input_rows": len(mapping_rows),
            "mapping_rows": len(mapping_rows),
            "unique_recommendation_ids": len(recommendation_ids),
            "unique_planner_task_intent_handles": len(planner_task_intent_handles),
            "traceability_refs": len(traceability_refs),
        },
    }


def _req_054_field_path(message: str) -> str:
    for marker in (" must ", " has ", " missing ", " duplicate "):
        marker_index = message.find(marker)
        if marker_index > 0:
            candidate = message[:marker_index].strip()
            if candidate:
                return candidate
    return "recommendation_to_planner_mapping_artifact"


def _validate_req_054_mapping_artifact(artifact: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    for message in validate_req_054_recommendation_to_planner_mapping_artifact(_req_054_envelope_from_artifact(artifact)):
        diagnostics.append(
            _diagnostic(
                field_path=_req_054_field_path(message),
                reason_code=REASON_REQ_054_CONTRACT_VIOLATION,
                message=message,
            )
        )
    return diagnostics


def _packet_recommendation_index(packet: Mapping[str, Any]) -> dict[str, int]:
    index_by_recommendation_id: dict[str, int] = {}
    raw_recommendations = packet.get("recommendations")
    if not isinstance(raw_recommendations, list):
        return index_by_recommendation_id

    for index, row in enumerate(raw_recommendations):
        if not isinstance(row, Mapping):
            continue
        recommendation_id = row.get("recommendation_id")
        if isinstance(recommendation_id, str) and recommendation_id.strip():
            index_by_recommendation_id[recommendation_id] = index
    return index_by_recommendation_id


def _packet_recommendation_ids(packet: Mapping[str, Any]) -> list[str]:
    raw_recommendations = packet.get("recommendations")
    if not isinstance(raw_recommendations, list):
        return []

    recommendation_ids: list[str] = []
    for row in raw_recommendations:
        if not isinstance(row, Mapping):
            continue
        recommendation_id = row.get("recommendation_id")
        if isinstance(recommendation_id, str) and recommendation_id.strip():
            recommendation_ids.append(recommendation_id)
    return recommendation_ids


def _validate_duplicate_recommendation_ids(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    recommendation_ids = _packet_recommendation_ids(packet)
    if not recommendation_ids:
        return diagnostics

    index_by_recommendation_id: dict[str, list[int]] = {}
    for index, recommendation_id in enumerate(recommendation_ids):
        index_by_recommendation_id.setdefault(recommendation_id, []).append(index)

    artifact = packet.get("recommendation_to_planner_mapping_artifact")
    expected_ids: list[str] = []
    if isinstance(artifact, Mapping):
        raw_expected_ids = artifact.get("recommendation_ids")
        if isinstance(raw_expected_ids, list):
            expected_ids = sorted(
                item for item in raw_expected_ids if isinstance(item, str) and item.strip()
            )
    observed_unique_ids = sorted(index_by_recommendation_id)

    for recommendation_id, indexes in sorted(index_by_recommendation_id.items()):
        if len(indexes) < 2:
            continue
        missing_from_packet = sorted(set(expected_ids) - set(observed_unique_ids))
        unexpected_in_packet = sorted(set(observed_unique_ids) - set(expected_ids))
        diagnostics.append(
            _diagnostic(
                field_path=f"recommendations[{indexes[1]}].recommendation_id",
                reason_code=REASON_DUPLICATE_RECOMMENDATION_ID_COLLISION,
                message=(
                    f"recommendation_id '{recommendation_id}' must be unique; "
                    f"collision_indexes={indexes} "
                    f"missing_from_packet={missing_from_packet} "
                    f"unexpected_in_packet={unexpected_in_packet}"
                ),
            )
        )

    return diagnostics


def _validate_traceability_gate(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    artifact = packet.get("recommendation_to_planner_mapping_artifact")
    if not isinstance(artifact, Mapping):
        return diagnostics

    raw_mappings = artifact.get("recommendation_to_task_intent_mappings")
    if not isinstance(raw_mappings, list):
        return diagnostics

    for index, row in enumerate(raw_mappings):
        if not isinstance(row, Mapping):
            continue
        traceability_refs = row.get("traceability_refs")
        downstream_audit_trail = row.get("downstream_audit_trail")
        if not isinstance(traceability_refs, list) or not isinstance(downstream_audit_trail, Mapping):
            continue

        emitted_refs = sorted({ref for ref in traceability_refs if isinstance(ref, str) and ref.strip()})
        required_refs: set[str] = set()
        for key in ("source_call_trace_refs", "source_evidence_refs", "source_packet_refs"):
            value = downstream_audit_trail.get(key)
            if isinstance(value, list):
                required_refs.update(ref for ref in value if isinstance(ref, str) and ref.strip())
        expected_refs = sorted(required_refs)

        missing_refs = sorted(set(expected_refs) - set(emitted_refs))
        unexpected_refs = sorted(set(emitted_refs) - set(expected_refs))
        if not missing_refs and not unexpected_refs:
            continue

        recommendation_id = row.get("recommendation_id")
        planner_task_intent_handle = row.get("planner_task_intent_handle")
        diagnostics.append(
            _diagnostic(
                field_path=(
                    "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                    f"[{index}].traceability_refs"
                ),
                reason_code=REASON_TRACEABILITY_GATE_FAILURE,
                message=(
                    "traceability_refs must exactly cover downstream_audit_trail refs; "
                    f"recommendation_id={recommendation_id!r} "
                    f"planner_task_intent_handle={planner_task_intent_handle!r} "
                    f"missing_refs={missing_refs} "
                    f"unexpected_refs={unexpected_refs}"
                ),
            )
        )

    return diagnostics


def _validate_req_054_consumability(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    artifact = packet.get("recommendation_to_planner_mapping_artifact")
    if not isinstance(artifact, Mapping):
        return []

    diagnostics = _validate_req_054_mapping_artifact(artifact)
    recommendation_index = _packet_recommendation_index(packet)
    packet_recommendation_ids = sorted(recommendation_index.keys())
    packet_recommendation_id_set = set(packet_recommendation_ids)

    raw_mappings = artifact.get("recommendation_to_task_intent_mappings")
    mapping_rows = raw_mappings if isinstance(raw_mappings, list) else []
    mapped_recommendation_ids: set[str] = set()
    for index, row in enumerate(mapping_rows):
        if not isinstance(row, Mapping):
            continue
        recommendation_id = row.get("recommendation_id")
        if not isinstance(recommendation_id, str) or not recommendation_id.strip():
            continue
        mapped_recommendation_ids.add(recommendation_id)
        if recommendation_id not in packet_recommendation_id_set:
            diagnostics.append(
                _diagnostic(
                    field_path=(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].recommendation_id"
                    ),
                    reason_code=REASON_MAPPING_REFERENCES_UNKNOWN_PACKET_RECOMMENDATION,
                    message=(
                        "mapping recommendation_id must reference a recommendation_id declared in "
                        "recommendations[]"
                    ),
                )
            )

    for recommendation_id in packet_recommendation_ids:
        if recommendation_id in mapped_recommendation_ids:
            continue
        recommendation_index_value = recommendation_index[recommendation_id]
        diagnostics.append(
            _diagnostic(
                field_path=f"recommendations[{recommendation_index_value}].recommendation_id",
                reason_code=REASON_PACKET_RECOMMENDATION_MISSING_MAPPING,
                message=(
                    "recommendation_id must have at least one REQ-054 planner task intent mapping "
                    "for planner consumability"
                ),
            )
        )

    artifact_recommendation_ids = artifact.get("recommendation_ids")
    if isinstance(artifact_recommendation_ids, list):
        normalized_artifact_ids = sorted(
            {
                item
                for item in artifact_recommendation_ids
                if isinstance(item, str) and item.strip()
            }
        )
        if normalized_artifact_ids != packet_recommendation_ids:
            missing_from_packet = sorted(set(normalized_artifact_ids) - set(packet_recommendation_ids))
            unexpected_in_packet = sorted(set(packet_recommendation_ids) - set(normalized_artifact_ids))
            diagnostics.append(
                _diagnostic(
                    field_path="recommendation_to_planner_mapping_artifact.recommendation_ids",
                    reason_code=REASON_MAPPING_ARTIFACT_RECOMMENDATION_IDS_MISMATCH,
                    message=(
                        "recommendation_ids must exactly match the strategy packet recommendation_id set "
                        "for planner consumability; "
                        f"missing_from_packet={missing_from_packet} "
                        f"unexpected_in_packet={unexpected_in_packet}"
                    ),
                )
            )

    return diagnostics


def validate_strategy_packet_payload(
    packet: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    diagnostics: list[dict[str, str]] = []
    validator = Draft202012Validator(schema)

    for error in sorted(
        validator.iter_errors(packet),
        key=lambda row: (
            list(row.absolute_path),
            str(row.validator),
            row.message,
        ),
    ):
        diagnostics.append(
            _diagnostic(
                field_path=_schema_field_path(error),
                reason_code=_schema_reason_code(error),
                message=error.message,
            )
        )

    diagnostics.extend(_validate_duplicate_recommendation_ids(packet))
    diagnostics.extend(_validate_traceability_gate(packet))
    diagnostics.extend(_validate_req_054_consumability(packet))
    diagnostics = _sorted_diagnostics(diagnostics)
    reason_codes = sorted({row["reason_code"] for row in diagnostics})
    ok = not diagnostics

    return {
        "ok": ok,
        "checked_at_utc": _utc_timestamp(),
        "verdict": "pass" if ok else "fail",
        "planner_consumability": "planner_ready" if ok else "planner_blocked",
        "reason_codes": reason_codes,
        "diagnostic_count": len(diagnostics),
        "summary": (
            "Strategy packet is planner-consumable."
            if ok
            else f"Strategy packet is not planner-consumable; {len(diagnostics)} blocking diagnostics detected."
        ),
        "diagnostics": diagnostics,
    }


def validate_strategy_packet_files(input_path: str | Path, schema_path: str | Path) -> dict[str, Any]:
    packet = load_json_file(input_path)
    schema = load_json_schema(schema_path)
    if not isinstance(packet, Mapping):
        return {
            "ok": False,
            "checked_at_utc": _utc_timestamp(),
            "verdict": "fail",
            "planner_consumability": "planner_blocked",
            "reason_codes": ["packet_payload_not_object"],
            "diagnostic_count": 1,
            "summary": "Strategy packet is not planner-consumable; packet JSON root must be an object.",
            "diagnostics": [
                _diagnostic(
                    field_path="$",
                    reason_code="packet_payload_not_object",
                    message="strategy packet JSON root must be an object",
                )
            ],
        }
    return validate_strategy_packet_payload(packet, schema)
