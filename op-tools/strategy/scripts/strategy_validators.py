#!/usr/bin/env python3
"""Deterministic strategy packet validators with REQ-056 consumability gate."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

REQ_056_REQUIREMENT_ID = "REQ-056"
REQ_056_VALIDATOR_ID = "kpi_target_artifact_consumability_gate"
REQ_062_REQUIREMENT_ID = "REQ-062"
STRATEGY_PACKET_SCHEMA_VERSION = "strategy-packet.v1"

SEVERITY_RANK = {
    "error": 0,
    "warning": 1,
    "info": 2,
}

EXPECTED_DIRECTIONS = {"increase", "decrease", "maintain"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
RECOMMENDATION_BASIS_FIELDS = (
    "priority",
    "summary",
    "rationale",
    "expected_impact",
    "risk_level",
)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _path_str(path: Path | None) -> str | None:
    return None if path is None else str(path.resolve())


def _diagnostic(
    reason_code: str,
    field_path: str,
    message: str,
    *,
    severity: str = "error",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "severity": severity,
        "reason_code": reason_code,
        "field_path": field_path,
        "message": message,
    }
    if details:
        output["details"] = dict(details)
    return output


def _sort_diagnostics(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        diagnostics,
        key=lambda row: (
            SEVERITY_RANK.get(str(row.get("severity")), 99),
            str(row.get("field_path") or ""),
            str(row.get("reason_code") or ""),
            str(row.get("message") or ""),
        ),
    )


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _json_path(path_parts: Sequence[Any]) -> str:
    if not path_parts:
        return "root"
    chunks: list[str] = []
    for part in path_parts:
        if isinstance(part, int):
            chunks.append(f"[{part}]")
            continue
        token = str(part)
        if not chunks:
            chunks.append(token)
        elif chunks[-1].endswith("]"):
            chunks.append(f".{token}")
        else:
            chunks.append(f".{token}")
    return "".join(chunks)


def _load_json_artifact(
    path: Path,
    *,
    missing_reason_code: str,
    invalid_reason_code: str,
    field_path: str,
    label: str,
    diagnostics: list[dict[str, Any]],
) -> Any | None:
    if not path.exists():
        diagnostics.append(
            _diagnostic(
                missing_reason_code,
                field_path,
                f"{label} file is missing: {path}",
                details={"path": str(path)},
            )
        )
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        diagnostics.append(
            _diagnostic(
                invalid_reason_code,
                field_path,
                f"{label} is not valid JSON",
                details={
                    "path": str(path),
                    "line": exc.lineno,
                    "column": exc.colno,
                    "json_error": exc.msg,
                },
            )
        )
        return None


def _validate_schema_contract(packet: Any, schema: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(schema, Mapping):
        diagnostics.append(
            _diagnostic(
                "strategy_packet_schema_invalid",
                "schema",
                "schema payload must be a JSON object",
            )
        )
        return

    try:
        validator = Draft202012Validator(schema)
    except SchemaError as exc:
        diagnostics.append(
            _diagnostic(
                "strategy_packet_schema_invalid",
                "schema",
                "schema payload is not a valid JSON Schema",
                details={"schema_error": str(exc)},
            )
        )
        return

    schema_errors = sorted(
        validator.iter_errors(packet),
        key=lambda err: (_json_path(err.absolute_path), str(err.validator), err.message),
    )
    for err in schema_errors:
        diagnostics.append(
            _diagnostic(
                "schema_contract_violation",
                _json_path(err.absolute_path),
                err.message,
                details={"validator": str(err.validator)},
            )
        )


def _validate_string_field(
    value: Any,
    *,
    field_path: str,
    diagnostics: list[dict[str, Any]],
    reason_code: str,
    allowed: set[str] | None = None,
) -> str | None:
    if not _is_non_empty_string(value):
        diagnostics.append(
            _diagnostic(
                reason_code,
                field_path,
                f"{field_path} must be a non-empty string",
            )
        )
        return None
    normalized = str(value).strip()
    if allowed is not None and normalized not in allowed:
        diagnostics.append(
            _diagnostic(
                reason_code,
                field_path,
                f"{field_path} must be one of {sorted(allowed)}",
                details={"actual": normalized},
            )
        )
        return None
    return normalized


def _validate_string_list(
    value: Any,
    *,
    field_path: str,
    diagnostics: list[dict[str, Any]],
    reason_code: str,
    min_items: int = 0,
) -> list[str]:
    if not isinstance(value, list):
        diagnostics.append(
            _diagnostic(
                reason_code,
                field_path,
                f"{field_path} must be a list",
            )
        )
        return []
    if len(value) < min_items:
        diagnostics.append(
            _diagnostic(
                reason_code,
                field_path,
                f"{field_path} must include at least {min_items} value(s)",
            )
        )
        return []
    normalized: list[str] = []
    for idx, item in enumerate(value):
        item_path = f"{field_path}[{idx}]"
        if not _is_non_empty_string(item):
            diagnostics.append(
                _diagnostic(
                    reason_code,
                    item_path,
                    f"{item_path} must be a non-empty string",
                )
            )
            continue
        normalized.append(str(item).strip())
    return normalized


def _validate_req_056_kpi_target_artifact(packet: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(packet, Mapping):
        diagnostics.append(
            _diagnostic(
                "strategy_packet_invalid",
                "root",
                "strategy packet payload must be a JSON object",
            )
        )
        return

    if packet.get("schema_version") != STRATEGY_PACKET_SCHEMA_VERSION:
        diagnostics.append(
            _diagnostic(
                "strategy_packet_schema_version_mismatch",
                "schema_version",
                f"schema_version must be {STRATEGY_PACKET_SCHEMA_VERSION}",
                details={"actual": packet.get("schema_version")},
            )
        )

    recommendation_ids: set[str] = set()
    recommendations = packet.get("recommendations")
    if isinstance(recommendations, list):
        for idx, row in enumerate(recommendations):
            if isinstance(row, Mapping) and _is_non_empty_string(row.get("recommendation_id")):
                recommendation_ids.add(str(row.get("recommendation_id")).strip())
            else:
                diagnostics.append(
                    _diagnostic(
                        "recommendation_id_missing",
                        f"recommendations[{idx}].recommendation_id",
                        "each recommendation must include a non-empty recommendation_id",
                    )
                )

    assumption_ids: set[str] = set()
    assumptions = packet.get("assumptions")
    if isinstance(assumptions, list):
        for idx, row in enumerate(assumptions):
            if isinstance(row, Mapping) and _is_non_empty_string(row.get("assumption_id")):
                assumption_ids.add(str(row.get("assumption_id")).strip())
            else:
                diagnostics.append(
                    _diagnostic(
                        "assumption_id_missing",
                        f"assumptions[{idx}].assumption_id",
                        "each assumption must include a non-empty assumption_id",
                    )
                )

    artifact = packet.get("kpi_target_artifact")
    if not isinstance(artifact, Mapping):
        diagnostics.append(
            _diagnostic(
                "kpi_target_artifact_missing",
                "kpi_target_artifact",
                "kpi_target_artifact must be an object",
            )
        )
        return

    targets = artifact.get("kpi_targets")
    if not isinstance(targets, list):
        diagnostics.append(
            _diagnostic(
                "kpi_target_rows_invalid",
                "kpi_target_artifact.kpi_targets",
                "kpi_target_artifact.kpi_targets must be a list",
            )
        )
        return
    if not targets:
        diagnostics.append(
            _diagnostic(
                "kpi_target_rows_empty",
                "kpi_target_artifact.kpi_targets",
                "kpi_target_artifact.kpi_targets must include at least one row",
            )
        )
        return

    seen_target_ids: dict[str, int] = {}
    linked_recommendation_ids: set[str] = set()
    linked_assumption_ids: set[str] = set()

    for idx, row in enumerate(targets):
        row_path = f"kpi_target_artifact.kpi_targets[{idx}]"
        if not isinstance(row, Mapping):
            diagnostics.append(
                _diagnostic(
                    "kpi_target_row_invalid",
                    row_path,
                    f"{row_path} must be an object",
                )
            )
            continue

        target_id = _validate_string_field(
            row.get("target_id"),
            field_path=f"{row_path}.target_id",
            diagnostics=diagnostics,
            reason_code="kpi_target_target_id_invalid",
        )
        if target_id:
            previous_index = seen_target_ids.get(target_id)
            if previous_index is not None:
                diagnostics.append(
                    _diagnostic(
                        "kpi_target_duplicate_target_id",
                        f"{row_path}.target_id",
                        "target_id must be unique across kpi_target_artifact.kpi_targets",
                        details={"target_id": target_id, "first_seen_index": previous_index},
                    )
                )
            else:
                seen_target_ids[target_id] = idx

        _validate_string_field(
            row.get("metric_name"),
            field_path=f"{row_path}.metric_name",
            diagnostics=diagnostics,
            reason_code="kpi_target_metric_name_invalid",
        )

        _validate_string_field(
            row.get("expected_direction"),
            field_path=f"{row_path}.expected_direction",
            diagnostics=diagnostics,
            reason_code="kpi_target_expected_direction_invalid",
            allowed=EXPECTED_DIRECTIONS,
        )

        _validate_string_field(
            row.get("baseline_reference"),
            field_path=f"{row_path}.baseline_reference",
            diagnostics=diagnostics,
            reason_code="kpi_target_baseline_reference_missing",
        )

        _validate_string_field(
            row.get("confidence_level"),
            field_path=f"{row_path}.confidence_level",
            diagnostics=diagnostics,
            reason_code="kpi_target_confidence_level_invalid",
            allowed=CONFIDENCE_LEVELS,
        )

        row_recommendation_ids = _validate_string_list(
            row.get("originating_recommendation_ids"),
            field_path=f"{row_path}.originating_recommendation_ids",
            diagnostics=diagnostics,
            reason_code="kpi_target_originating_recommendation_ids_invalid",
            min_items=1,
        )
        for rec_idx, rec_id in enumerate(row_recommendation_ids):
            linked_recommendation_ids.add(rec_id)
            if rec_id not in recommendation_ids:
                diagnostics.append(
                    _diagnostic(
                        "kpi_target_unknown_originating_recommendation_id",
                        f"{row_path}.originating_recommendation_ids[{rec_idx}]",
                        "originating recommendation id does not exist in recommendations[]",
                        details={"recommendation_id": rec_id},
                    )
                )

        row_assumption_ids = _validate_string_list(
            row.get("assumption_ids"),
            field_path=f"{row_path}.assumption_ids",
            diagnostics=diagnostics,
            reason_code="kpi_target_assumption_ids_invalid",
            min_items=1,
        )
        for assumption_idx, assumption_id in enumerate(row_assumption_ids):
            linked_assumption_ids.add(assumption_id)
            if assumption_id not in assumption_ids:
                diagnostics.append(
                    _diagnostic(
                        "kpi_target_unknown_assumption_id",
                        f"{row_path}.assumption_ids[{assumption_idx}]",
                        "assumption id does not exist in assumptions[]",
                        details={"assumption_id": assumption_id},
                    )
                )

    totals = artifact.get("totals")
    totals_path = "kpi_target_artifact.totals"
    if not isinstance(totals, Mapping):
        diagnostics.append(
            _diagnostic(
                "kpi_target_totals_invalid",
                totals_path,
                f"{totals_path} must be an object",
            )
        )
        return

    expected_totals = {
        "kpi_targets": len(targets),
        "unique_recommendations_linked": len(linked_recommendation_ids),
        "unique_assumptions_linked": len(linked_assumption_ids),
    }
    for field_name, expected_value in expected_totals.items():
        field_path = f"{totals_path}.{field_name}"
        actual_value = totals.get(field_name)
        if not isinstance(actual_value, int):
            diagnostics.append(
                _diagnostic(
                    "kpi_target_totals_invalid",
                    field_path,
                    f"{field_path} must be an integer",
                )
            )
            continue
        if actual_value != expected_value:
            diagnostics.append(
                _diagnostic(
                    "kpi_target_totals_mismatch",
                    field_path,
                    f"{field_path} must equal {expected_value}",
                    details={"actual": actual_value, "expected": expected_value},
                )
            )


def _normalize_recommendation_basis(
    row: Mapping[str, Any],
    *,
    row_path: str,
    diagnostics: list[dict[str, Any]],
    reason_code: str,
) -> dict[str, str]:
    basis: dict[str, str] = {}
    for field_name in RECOMMENDATION_BASIS_FIELDS:
        value = _validate_string_field(
            row.get(field_name),
            field_path=f"{row_path}.{field_name}",
            diagnostics=diagnostics,
            reason_code=reason_code,
        )
        if value is not None:
            basis[field_name] = value
    return basis


def _basis_signature(basis: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple((field_name, basis[field_name]) for field_name in RECOMMENDATION_BASIS_FIELDS)


def _build_packet_recommendation_rows(
    packet: Mapping[str, Any],
    diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recommendations = packet.get("recommendations")
    if not isinstance(recommendations, list):
        return []

    revision_id = ""
    strategy = packet.get("strategy")
    if isinstance(strategy, Mapping) and _is_non_empty_string(strategy.get("revision_id")):
        revision_id = str(strategy.get("revision_id")).strip()

    rows: list[dict[str, Any]] = []
    indexes_by_id: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(recommendations):
        if not isinstance(row, Mapping):
            continue
        recommendation_id = row.get("recommendation_id")
        if not _is_non_empty_string(recommendation_id):
            continue
        normalized_id = str(recommendation_id).strip()
        indexes_by_id[normalized_id].append(index)
        rows.append(
            {
                "index": index,
                "path": f"recommendations[{index}]",
                "recommendation_id": normalized_id,
                "basis": _normalize_recommendation_basis(
                    row,
                    row_path=f"recommendations[{index}]",
                    diagnostics=diagnostics,
                    reason_code="recommendation_id_stability_basis_invalid",
                ),
            }
        )

    for recommendation_id, indexes in sorted(indexes_by_id.items()):
        if len(indexes) < 2:
            continue
        for index in indexes:
            diagnostics.append(
                _diagnostic(
                    "recommendation_id_collision",
                    f"recommendations[{index}].recommendation_id",
                    f"recommendation_id {recommendation_id} must be unique within revision {revision_id or 'unknown'}",
                    details={
                        "recommendation_id": recommendation_id,
                        "revision_id": revision_id,
                        "conflicting_indexes": indexes,
                    },
                )
            )

    return rows


def _parse_recommendation_id_stability_revision(
    revision: Any,
    *,
    field_path: str,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(revision, Mapping):
        diagnostics.append(
            _diagnostic(
                "recommendation_id_stability_contract_invalid",
                field_path,
                f"{field_path} must be an object",
            )
        )
        return None

    revision_id = _validate_string_field(
        revision.get("revision_id"),
        field_path=f"{field_path}.revision_id",
        diagnostics=diagnostics,
        reason_code="recommendation_id_stability_contract_invalid",
    )

    recommendations = revision.get("recommendations")
    if not isinstance(recommendations, list):
        diagnostics.append(
            _diagnostic(
                "recommendation_id_stability_contract_invalid",
                f"{field_path}.recommendations",
                f"{field_path}.recommendations must be a list",
            )
        )
        return None

    rows: list[dict[str, Any]] = []
    rows_by_id: dict[str, dict[str, Any]] = {}
    rows_by_key: dict[str, dict[str, Any]] = {}
    rows_by_signature: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}

    for index, row in enumerate(recommendations):
        row_path = f"{field_path}.recommendations[{index}]"
        if not isinstance(row, Mapping):
            diagnostics.append(
                _diagnostic(
                    "recommendation_id_stability_contract_invalid",
                    row_path,
                    f"{row_path} must be an object",
                )
            )
            continue

        recommendation_key = _validate_string_field(
            row.get("recommendation_key"),
            field_path=f"{row_path}.recommendation_key",
            diagnostics=diagnostics,
            reason_code="recommendation_id_stability_contract_invalid",
        )
        recommendation_id = _validate_string_field(
            row.get("recommendation_id"),
            field_path=f"{row_path}.recommendation_id",
            diagnostics=diagnostics,
            reason_code="recommendation_id_stability_contract_invalid",
        )

        basis_payload = row.get("basis")
        if not isinstance(basis_payload, Mapping):
            diagnostics.append(
                _diagnostic(
                    "recommendation_id_stability_contract_invalid",
                    f"{row_path}.basis",
                    f"{row_path}.basis must be an object",
                )
            )
            continue
        basis = _normalize_recommendation_basis(
            basis_payload,
            row_path=f"{row_path}.basis",
            diagnostics=diagnostics,
            reason_code="recommendation_id_stability_contract_invalid",
        )

        if recommendation_id is None or recommendation_key is None or len(basis) != len(RECOMMENDATION_BASIS_FIELDS):
            continue

        row_info = {
            "index": index,
            "path": row_path,
            "recommendation_key": recommendation_key,
            "recommendation_id": recommendation_id,
            "basis": basis,
        }
        rows.append(row_info)

        previous_id_row = rows_by_id.get(recommendation_id)
        if previous_id_row is not None:
            diagnostics.append(
                _diagnostic(
                    "recommendation_id_stability_contract_collision",
                    f"{row_path}.recommendation_id",
                    f"recommendation_id {recommendation_id} must be unique within {field_path}",
                    details={
                        "recommendation_id": recommendation_id,
                        "conflicting_field_paths": [
                            f"{previous_id_row['path']}.recommendation_id",
                            f"{row_path}.recommendation_id",
                        ],
                    },
                )
            )
        else:
            rows_by_id[recommendation_id] = row_info

        previous_key_row = rows_by_key.get(recommendation_key)
        if previous_key_row is not None:
            diagnostics.append(
                _diagnostic(
                    "recommendation_id_stability_contract_duplicate_key",
                    f"{row_path}.recommendation_key",
                    f"recommendation_key {recommendation_key} must be unique within {field_path}",
                    details={
                        "recommendation_key": recommendation_key,
                        "conflicting_field_paths": [
                            f"{previous_key_row['path']}.recommendation_key",
                            f"{row_path}.recommendation_key",
                        ],
                    },
                )
            )
        else:
            rows_by_key[recommendation_key] = row_info

        rows_by_signature.setdefault(_basis_signature(basis), row_info)

    return {
        "revision_id": revision_id or "",
        "rows": rows,
        "rows_by_id": rows_by_id,
        "rows_by_key": rows_by_key,
        "rows_by_signature": rows_by_signature,
    }


def _parse_recommendation_id_stability_contract(
    contract: Any,
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(contract, Mapping):
        diagnostics.append(
            _diagnostic(
                "recommendation_id_stability_contract_invalid",
                "stability_contract",
                "recommendation id stability contract must be a JSON object",
            )
        )
        return None

    previous_revision = _parse_recommendation_id_stability_revision(
        contract.get("previous_revision"),
        field_path="stability_contract.previous_revision",
        diagnostics=diagnostics,
    )
    current_revision = _parse_recommendation_id_stability_revision(
        contract.get("current_revision"),
        field_path="stability_contract.current_revision",
        diagnostics=diagnostics,
    )
    if previous_revision is None or current_revision is None:
        return None
    return {
        "previous_revision": previous_revision,
        "current_revision": current_revision,
    }


def _validate_req_062_recommendation_id_uniqueness(
    packet: Any,
    *,
    context: Any | None,
    stability_contract: Any | None,
    diagnostics: list[dict[str, Any]],
) -> None:
    if not isinstance(packet, Mapping):
        return
    if context is not None and not isinstance(context, Mapping):
        diagnostics.append(
            _diagnostic(
                "strategy_packet_context_invalid",
                "context",
                "strategy packet context must be a JSON object",
            )
        )

    packet_rows = _build_packet_recommendation_rows(packet, diagnostics)
    if stability_contract is None:
        return

    contract = _parse_recommendation_id_stability_contract(stability_contract, diagnostics)
    if contract is None:
        return

    packet_row_indexes_by_id: dict[str, list[int]] = defaultdict(list)
    for row in packet_rows:
        packet_row_indexes_by_id[row["recommendation_id"]].append(int(row["index"]))

    strategy = packet.get("strategy")
    packet_revision_id = ""
    if isinstance(strategy, Mapping) and _is_non_empty_string(strategy.get("revision_id")):
        packet_revision_id = str(strategy.get("revision_id")).strip()
    contract_revision_id = contract["current_revision"]["revision_id"]
    if packet_revision_id and contract_revision_id and packet_revision_id != contract_revision_id:
        diagnostics.append(
            _diagnostic(
                "recommendation_id_stability_revision_mismatch",
                "strategy.revision_id",
                "strategy.revision_id does not match stability_contract.current_revision.revision_id",
                details={
                    "actual": packet_revision_id,
                    "expected": contract_revision_id,
                },
            )
        )

    contract_rows_by_id = contract["current_revision"]["rows_by_id"]
    contract_rows_by_signature = contract["current_revision"]["rows_by_signature"]

    for row in packet_rows:
        row_path = str(row["path"])
        recommendation_id = str(row["recommendation_id"])
        contract_row = contract_rows_by_id.get(recommendation_id)
        if contract_row is None:
            diagnostics.append(
                _diagnostic(
                    "recommendation_id_missing_from_contract",
                    f"{row_path}.recommendation_id",
                    f"recommendation_id {recommendation_id} is not traceable to the REQ-062 contract",
                    details={"recommendation_id": recommendation_id},
                )
            )
            if len(row["basis"]) == len(RECOMMENDATION_BASIS_FIELDS):
                matching_basis_row = contract_rows_by_signature.get(_basis_signature(row["basis"]))
                if matching_basis_row is not None:
                    diagnostics.append(
                        _diagnostic(
                            "recommendation_id_stability_collision",
                            f"{row_path}.recommendation_id",
                            "recommendation basis is already assigned to another recommendation_id",
                            details={
                                "recommendation_id": recommendation_id,
                                "expected_recommendation_id": matching_basis_row["recommendation_id"],
                                "recommendation_key": matching_basis_row["recommendation_key"],
                            },
                        )
                    )
            continue

        for field_name in RECOMMENDATION_BASIS_FIELDS:
            expected_value = contract_row["basis"][field_name]
            actual_value = row["basis"].get(field_name)
            if actual_value == expected_value:
                continue
            diagnostics.append(
                _diagnostic(
                    "recommendation_id_stability_basis_mismatch",
                    f"{row_path}.{field_name}",
                    f"recommendation_id {recommendation_id} does not match the REQ-062 stability contract for {field_name}",
                    details={
                        "recommendation_id": recommendation_id,
                        "basis_field": field_name,
                        "expected": expected_value,
                        "actual": actual_value,
                    },
                )
            )

    previous_rows_by_key = contract["previous_revision"]["rows_by_key"]
    current_rows_by_key = contract["current_revision"]["rows_by_key"]
    shared_keys = sorted(set(previous_rows_by_key) & set(current_rows_by_key))
    for recommendation_key in shared_keys:
        previous_row = previous_rows_by_key[recommendation_key]
        current_row = current_rows_by_key[recommendation_key]
        previous_recommendation_id = previous_row["recommendation_id"]
        current_recommendation_id = current_row["recommendation_id"]
        if previous_recommendation_id == current_recommendation_id:
            continue
        packet_indexes = packet_row_indexes_by_id.get(current_recommendation_id, [])
        field_path = (
            f"recommendations[{packet_indexes[0]}].recommendation_id"
            if packet_indexes
            else f"{current_row['path']}.recommendation_id"
        )
        diagnostics.append(
            _diagnostic(
                "recommendation_id_drift",
                field_path,
                f"recommendation_key {recommendation_key} drifted across revisions",
                details={
                    "recommendation_key": recommendation_key,
                    "previous_revision_id": contract["previous_revision"]["revision_id"],
                    "current_revision_id": contract["current_revision"]["revision_id"],
                    "previous_recommendation_id": previous_recommendation_id,
                    "current_recommendation_id": current_recommendation_id,
                },
            )
        )


def validate_strategy_packet(
    packet_path: str | Path,
    schema_path: str | Path,
    *,
    context_path: str | Path | None = None,
    stability_contract_path: str | Path | None = None,
) -> dict[str, Any]:
    packet_file = Path(packet_path).resolve()
    schema_file = Path(schema_path).resolve()
    context_file = Path(context_path).resolve() if context_path is not None else None
    stability_contract_file = Path(stability_contract_path).resolve() if stability_contract_path is not None else None

    diagnostics: list[dict[str, Any]] = []
    schema = _load_json_artifact(
        schema_file,
        missing_reason_code="strategy_packet_schema_missing",
        invalid_reason_code="strategy_packet_schema_invalid_json",
        field_path="schema",
        label="strategy packet schema",
        diagnostics=diagnostics,
    )
    packet = _load_json_artifact(
        packet_file,
        missing_reason_code="strategy_packet_missing",
        invalid_reason_code="strategy_packet_invalid_json",
        field_path="strategy_packet",
        label="strategy packet",
        diagnostics=diagnostics,
    )
    context = (
        _load_json_artifact(
            context_file,
            missing_reason_code="strategy_packet_context_missing",
            invalid_reason_code="strategy_packet_context_invalid_json",
            field_path="context",
            label="strategy packet context",
            diagnostics=diagnostics,
        )
        if context_file is not None
        else None
    )
    stability_contract = (
        _load_json_artifact(
            stability_contract_file,
            missing_reason_code="recommendation_id_stability_contract_missing",
            invalid_reason_code="recommendation_id_stability_contract_invalid_json",
            field_path="stability_contract",
            label="recommendation id stability contract",
            diagnostics=diagnostics,
        )
        if stability_contract_file is not None
        else None
    )

    if schema is not None and packet is not None:
        _validate_schema_contract(packet, schema, diagnostics)
        _validate_req_056_kpi_target_artifact(packet, diagnostics)
        _validate_req_062_recommendation_id_uniqueness(
            packet,
            context=context,
            stability_contract=stability_contract,
            diagnostics=diagnostics,
        )

    ordered = _sort_diagnostics(diagnostics)
    reason_codes = sorted({str(row["reason_code"]) for row in ordered})
    error_count = sum(1 for row in ordered if row.get("severity") == "error")
    warning_count = sum(1 for row in ordered if row.get("severity") == "warning")
    ok = error_count == 0

    return {
        "requirement_id": REQ_056_REQUIREMENT_ID,
        "validated_requirements": [REQ_056_REQUIREMENT_ID, REQ_062_REQUIREMENT_ID],
        "validator_id": REQ_056_VALIDATOR_ID,
        "validator_name": REQ_056_VALIDATOR_ID,
        "checked_at_utc": _utc_timestamp(),
        "ok": ok,
        "verdict": "pass" if ok else "fail",
        "blocking": not ok,
        "packet_path": _path_str(packet_file),
        "schema_path": _path_str(schema_file),
        "strategy_packet_context_path": _path_str(context_file),
        "recommendation_id_stability_contract_path": _path_str(stability_contract_file),
        "reason_codes": reason_codes,
        "diagnostics": ordered,
        "counts": {
            "error_count": error_count,
            "warning_count": warning_count,
            "diagnostic_count": len(ordered),
        },
        "gate": {
            "gate_id": "req_056_kpi_target_artifact_consumability",
            "status": "pass" if ok else "fail",
            "decision": "allow_consume" if ok else "block_consume",
            "blocking_reason_codes": reason_codes if not ok else [],
            "failing_field_paths": sorted(
                {str(row["field_path"]) for row in ordered if row.get("severity") == "error"}
            ),
        },
    }


__all__ = ["validate_strategy_packet"]
