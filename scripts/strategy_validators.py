#!/usr/bin/env python3
"""Strategy packet validators and planner/runtime consumability gates."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SEVERITY_ERROR = "error"

REASON_PACKET_PAYLOAD_NOT_OBJECT = "packet_payload_not_object"
REASON_SCHEMA_PAYLOAD_NOT_OBJECT = "schema_payload_not_object"
REASON_INPUT_LOAD_FAILED = "input_load_failed"
REASON_SCHEMA_LOAD_FAILED = "schema_load_failed"
REASON_REQ_057_ARTIFACT_MISSING = "req_057_artifact_missing"
REASON_REQ_057_ARTIFACT_NOT_OBJECT = "req_057_artifact_not_object"
REASON_REQ_057_ARTIFACT_UNEXPECTED_KEYS = "req_057_artifact_unexpected_keys"
REASON_REQ_057_ARTIFACT_MISSING_KEYS = "req_057_artifact_missing_keys"
REASON_REQ_057_POLICIES_NOT_LIST = "req_057_policies_not_list"
REASON_REQ_057_POLICIES_EMPTY = "req_057_policies_empty"
REASON_REQ_057_POLICY_ROW_NOT_OBJECT = "req_057_policy_row_not_object"
REASON_REQ_057_POLICY_MISSING_KEYS = "req_057_policy_missing_keys"
REASON_REQ_057_POLICY_UNEXPECTED_KEYS = "req_057_policy_unexpected_keys"
REASON_REQ_057_POLICY_ID_INVALID = "req_057_policy_id_invalid"
REASON_REQ_057_POLICY_ID_DUPLICATE = "req_057_policy_id_duplicate"
REASON_REQ_057_BLOCKER_CODE_INVALID = "req_057_blocker_code_invalid"
REASON_REQ_057_PROJECT_ID_INVALID = "req_057_project_id_invalid"
REASON_REQ_057_LIST_NOT_ARRAY = "req_057_list_not_array"
REASON_REQ_057_LIST_ITEM_INVALID = "req_057_list_item_invalid"
REASON_REQ_057_LIST_MIN_ITEMS = "req_057_list_min_items"
REASON_REQ_057_LIST_DUPLICATE = "req_057_list_duplicate"
REASON_REQ_057_LIST_UNSORTED = "req_057_list_unsorted"
REASON_REQ_057_ESCALATION_TRIGGER_NOT_OBJECT = "req_057_escalation_trigger_not_object"
REASON_REQ_057_ESCALATION_TRIGGER_MISSING_KEYS = "req_057_escalation_trigger_missing_keys"
REASON_REQ_057_ESCALATION_TRIGGER_UNEXPECTED_KEYS = "req_057_escalation_trigger_unexpected_keys"
REASON_REQ_057_ESCALATION_TRIGGER_TYPE_INVALID = "req_057_escalation_trigger_type_invalid"
REASON_REQ_057_ESCALATION_TRIGGER_THRESHOLD_INVALID = "req_057_escalation_trigger_threshold_invalid"
REASON_REQ_057_ESCALATION_TRIGGER_WINDOW_INVALID = "req_057_escalation_trigger_window_invalid"
REASON_RECOMMENDATION_ID_DUPLICATE = "strategy_recommendation_id_duplicate"
REASON_TRACEABILITY_REF_INVALID = "strategy_traceability_ref_invalid"
REASON_TRACEABILITY_REF_MISSING = "strategy_traceability_ref_missing"

_SCHEMA_REASON_CODE_BY_VALIDATOR = {
    "additionalProperties": "schema_additional_property",
    "const": "schema_const_mismatch",
    "enum": "schema_enum_violation",
    "minItems": "schema_min_items_violation",
    "minLength": "schema_min_length_violation",
    "minimum": "schema_minimum_violation",
    "pattern": "schema_pattern_mismatch",
    "required": "schema_required_field_missing",
    "type": "schema_type_mismatch",
}

_REQ_057_ESCALATION_TRIGGER_TYPES = {
    "attempts_exhausted",
    "dependency_timeout",
    "guardrail_violation",
}
_REQ_057_ESCALATION_WINDOWS = {"attempts", "cycles", "minutes"}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return _format_field_path(path)


def _schema_reason_code(error: Any) -> str:
    return _SCHEMA_REASON_CODE_BY_VALIDATOR.get(str(error.validator), "schema_validation_failed")


def _reason_codes(diagnostics: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("reason_code"))
            for row in diagnostics
            if isinstance(row.get("reason_code"), str) and row.get("reason_code")
        }
    )


def _result(
    diagnostics: list[dict[str, str]],
    *,
    input_path: str | None = None,
    schema_path: str | None = None,
) -> dict[str, Any]:
    sorted_diagnostics = _sorted_diagnostics(diagnostics)
    reason_codes = _reason_codes(sorted_diagnostics)
    ok = not sorted_diagnostics
    schema_valid = not any(code.startswith("schema_") for code in reason_codes)
    req_057_consumable = not any(code.startswith("req_057_") for code in reason_codes)

    return {
        "ok": ok,
        "checked_at_utc": _utc_timestamp(),
        "verdict": "pass" if ok else "fail",
        "planner_consumability": "planner_ready" if ok else "planner_blocked",
        "reason_codes": reason_codes,
        "diagnostic_count": len(sorted_diagnostics),
        "summary": (
            "Strategy packet is planner/runtime-consumable."
            if ok
            else f"Strategy packet is not planner/runtime-consumable; {len(sorted_diagnostics)} blocking diagnostics detected."
        ),
        "input_path": input_path,
        "schema_path": schema_path,
        "gate": {
            "schema_valid": schema_valid,
            "req_057_blocker_policy_consumable": req_057_consumable,
        },
        "diagnostics": sorted_diagnostics,
    }


def load_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validate_sorted_unique_string_list(
    *,
    value: Any,
    field_path: str,
    min_items: int,
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    if not isinstance(value, list):
        diagnostics.append(
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_REQ_057_LIST_NOT_ARRAY,
                message=f"{field_path} must be an array of non-empty strings.",
            )
        )
        return diagnostics

    valid_values: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            diagnostics.append(
                _diagnostic(
                    field_path=f"{field_path}[{index}]",
                    reason_code=REASON_REQ_057_LIST_ITEM_INVALID,
                    message=f"{field_path}[{index}] must be a non-empty string.",
                )
            )
            continue
        valid_values.append(item)

    if len(valid_values) < min_items:
        diagnostics.append(
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_REQ_057_LIST_MIN_ITEMS,
                message=f"{field_path} must include at least {min_items} item(s).",
            )
        )

    if len(set(valid_values)) != len(valid_values):
        diagnostics.append(
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_REQ_057_LIST_DUPLICATE,
                message=f"{field_path} must not contain duplicate values.",
            )
        )

    if valid_values != sorted(valid_values):
        diagnostics.append(
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_REQ_057_LIST_UNSORTED,
                message=f"{field_path} must be sorted in ascending order.",
            )
        )

    return diagnostics


def _validate_escalation_trigger(value: Any, *, field_path: str) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    if not isinstance(value, Mapping):
        diagnostics.append(
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_REQ_057_ESCALATION_TRIGGER_NOT_OBJECT,
                message=f"{field_path} must be an object.",
            )
        )
        return diagnostics

    expected_keys = {"trigger_type", "threshold", "window"}
    row_keys = set(value.keys())
    missing_keys = sorted(expected_keys - row_keys)
    if missing_keys:
        diagnostics.append(
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_REQ_057_ESCALATION_TRIGGER_MISSING_KEYS,
                message=f"{field_path} missing required keys: {missing_keys}.",
            )
        )
    unexpected_keys = sorted(row_keys - expected_keys)
    if unexpected_keys:
        diagnostics.append(
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_REQ_057_ESCALATION_TRIGGER_UNEXPECTED_KEYS,
                message=f"{field_path} has unexpected keys: {unexpected_keys}.",
            )
        )

    trigger_type = value.get("trigger_type")
    if trigger_type not in _REQ_057_ESCALATION_TRIGGER_TYPES:
        diagnostics.append(
            _diagnostic(
                field_path=f"{field_path}.trigger_type",
                reason_code=REASON_REQ_057_ESCALATION_TRIGGER_TYPE_INVALID,
                message=(
                    f"{field_path}.trigger_type must be one of: "
                    f"{sorted(_REQ_057_ESCALATION_TRIGGER_TYPES)}."
                ),
            )
        )

    threshold = value.get("threshold")
    if not isinstance(threshold, int) or threshold <= 0:
        diagnostics.append(
            _diagnostic(
                field_path=f"{field_path}.threshold",
                reason_code=REASON_REQ_057_ESCALATION_TRIGGER_THRESHOLD_INVALID,
                message=f"{field_path}.threshold must be a positive integer.",
            )
        )

    window = value.get("window")
    if window not in _REQ_057_ESCALATION_WINDOWS:
        diagnostics.append(
            _diagnostic(
                field_path=f"{field_path}.window",
                reason_code=REASON_REQ_057_ESCALATION_TRIGGER_WINDOW_INVALID,
                message=f"{field_path}.window must be one of: {sorted(_REQ_057_ESCALATION_WINDOWS)}.",
            )
        )

    return diagnostics


def _resolve_traceability_ref(ref_value: str, *, base_dir: Path) -> Path | None:
    ref_target = ref_value.split("#", 1)[0].strip()
    if not ref_target or ref_target.startswith("missing:"):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", ref_target) and not ref_target.startswith("/"):
        return None

    resolved = Path(ref_target).expanduser()
    if not resolved.is_absolute():
        resolved = base_dir / resolved
    return resolved


def _validate_traceability_ref(
    value: Any,
    *,
    field_path: str,
    base_dir: Path,
) -> list[dict[str, str]]:
    if not isinstance(value, str) or not value.strip():
        return [
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_TRACEABILITY_REF_INVALID,
                message=f"{field_path} must be a non-empty file reference.",
            )
        ]

    ref_value = value.strip()
    resolved = _resolve_traceability_ref(ref_value, base_dir=base_dir)
    if resolved is None:
        return [
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_TRACEABILITY_REF_INVALID,
                message=(
                    f"{field_path} must use a repo-relative or absolute file reference; "
                    f"received '{ref_value}'."
                ),
            )
        ]

    if not resolved.exists():
        return [
            _diagnostic(
                field_path=field_path,
                reason_code=REASON_TRACEABILITY_REF_MISSING,
                message=f"{field_path} references missing file '{ref_value}'.",
            )
        ]

    return []


def _validate_strategy_recommendations(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    recommendations = packet.get("recommendations")
    if not isinstance(recommendations, list):
        return diagnostics

    seen_recommendation_ids: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for index, row in enumerate(recommendations):
        row_path = f"recommendations[{index}]"
        if not isinstance(row, Mapping):
            continue

        recommendation_id = row.get("recommendation_id")
        if not isinstance(recommendation_id, str) or not recommendation_id.strip():
            continue

        current_path = f"{row_path}.recommendation_id"
        normalized_recommendation_id = recommendation_id.strip()
        if normalized_recommendation_id not in seen_recommendation_ids:
            seen_recommendation_ids[normalized_recommendation_id] = (current_path, row)
            continue

        first_path, first_row = seen_recommendation_ids[normalized_recommendation_id]
        differing_fields = sorted(
            key
            for key in (set(first_row.keys()) | set(row.keys()))
            if key != "recommendation_id" and first_row.get(key) != row.get(key)
        )
        diff_details = (
            f"differing fields: {differing_fields}."
            if differing_fields
            else "duplicate row is identical to the first declaration."
        )
        diagnostics.append(
            _diagnostic(
                field_path=current_path,
                reason_code=REASON_RECOMMENDATION_ID_DUPLICATE,
                message=(
                    f"{current_path} duplicates recommendation_id '{normalized_recommendation_id}' "
                    f"first declared at {first_path}; {diff_details}"
                ),
            )
        )

    return diagnostics


def _validate_strategy_traceability(packet: Mapping[str, Any], *, base_dir: Path) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []

    strategy = packet.get("strategy")
    if isinstance(strategy, Mapping) and isinstance(strategy.get("link_map_ref"), str):
        diagnostics.extend(
            _validate_traceability_ref(
                strategy.get("link_map_ref"),
                field_path="strategy.link_map_ref",
                base_dir=base_dir,
            )
        )

    artifact = packet.get("blocker_handling_policy_artifact")
    if not isinstance(artifact, Mapping):
        return diagnostics

    policies = artifact.get("policies")
    if not isinstance(policies, list):
        return diagnostics

    for index, row in enumerate(policies):
        if not isinstance(row, Mapping):
            continue
        evidence_refs = row.get("evidence_refs", [])
        if not isinstance(evidence_refs, list):
            continue
        for evidence_index, evidence_ref in enumerate(evidence_refs):
            diagnostics.extend(
                _validate_traceability_ref(
                    evidence_ref,
                    field_path=(
                        "blocker_handling_policy_artifact."
                        f"policies[{index}].evidence_refs[{evidence_index}]"
                    ),
                    base_dir=base_dir,
                )
            )

    return diagnostics


def _validate_req_057_blocker_policy_artifact(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    artifact_path = "blocker_handling_policy_artifact"
    artifact = packet.get("blocker_handling_policy_artifact")

    if artifact is None:
        diagnostics.append(
            _diagnostic(
                field_path=artifact_path,
                reason_code=REASON_REQ_057_ARTIFACT_MISSING,
                message=(
                    "blocker_handling_policy_artifact is required for REQ-057 and must be provided for "
                    "planner/runtime routing."
                ),
            )
        )
        return diagnostics

    if not isinstance(artifact, Mapping):
        diagnostics.append(
            _diagnostic(
                field_path=artifact_path,
                reason_code=REASON_REQ_057_ARTIFACT_NOT_OBJECT,
                message=f"{artifact_path} must be an object.",
            )
        )
        return diagnostics

    expected_artifact_keys = {"policies"}
    artifact_keys = set(artifact.keys())
    missing_keys = sorted(expected_artifact_keys - artifact_keys)
    if missing_keys:
        diagnostics.append(
            _diagnostic(
                field_path=artifact_path,
                reason_code=REASON_REQ_057_ARTIFACT_MISSING_KEYS,
                message=f"{artifact_path} missing required keys: {missing_keys}.",
            )
        )
    unexpected_keys = sorted(artifact_keys - expected_artifact_keys)
    if unexpected_keys:
        diagnostics.append(
            _diagnostic(
                field_path=artifact_path,
                reason_code=REASON_REQ_057_ARTIFACT_UNEXPECTED_KEYS,
                message=f"{artifact_path} has unexpected keys: {unexpected_keys}.",
            )
        )

    policies_path = f"{artifact_path}.policies"
    policies = artifact.get("policies")
    if not isinstance(policies, list):
        diagnostics.append(
            _diagnostic(
                field_path=policies_path,
                reason_code=REASON_REQ_057_POLICIES_NOT_LIST,
                message=f"{policies_path} must be an array.",
            )
        )
        return diagnostics

    if not policies:
        diagnostics.append(
            _diagnostic(
                field_path=policies_path,
                reason_code=REASON_REQ_057_POLICIES_EMPTY,
                message=f"{policies_path} must include at least one policy row.",
            )
        )
        return diagnostics

    seen_policy_ids: dict[str, str] = {}
    for index, row in enumerate(policies):
        row_path = f"{policies_path}[{index}]"
        if not isinstance(row, Mapping):
            diagnostics.append(
                _diagnostic(
                    field_path=row_path,
                    reason_code=REASON_REQ_057_POLICY_ROW_NOT_OBJECT,
                    message=f"{row_path} must be an object.",
                )
            )
            continue

        required_keys = {
            "policy_id",
            "blocker_code",
            "escalation_trigger",
            "owner_hints",
            "fallback_paths",
        }
        optional_keys = {"project_id", "evidence_refs"}
        row_keys = set(row.keys())
        row_missing_keys = sorted(required_keys - row_keys)
        if row_missing_keys:
            diagnostics.append(
                _diagnostic(
                    field_path=row_path,
                    reason_code=REASON_REQ_057_POLICY_MISSING_KEYS,
                    message=f"{row_path} missing required keys: {row_missing_keys}.",
                )
            )
        row_unexpected_keys = sorted(row_keys - (required_keys | optional_keys))
        if row_unexpected_keys:
            diagnostics.append(
                _diagnostic(
                    field_path=row_path,
                    reason_code=REASON_REQ_057_POLICY_UNEXPECTED_KEYS,
                    message=f"{row_path} has unexpected keys: {row_unexpected_keys}.",
                )
            )

        policy_id = row.get("policy_id")
        if not isinstance(policy_id, str) or not policy_id.strip():
            diagnostics.append(
                _diagnostic(
                    field_path=f"{row_path}.policy_id",
                    reason_code=REASON_REQ_057_POLICY_ID_INVALID,
                    message=f"{row_path}.policy_id must be a non-empty string.",
                )
            )
        elif policy_id in seen_policy_ids:
            diagnostics.append(
                _diagnostic(
                    field_path=f"{row_path}.policy_id",
                    reason_code=REASON_REQ_057_POLICY_ID_DUPLICATE,
                    message=(
                        f"{row_path}.policy_id duplicates policy_id '{policy_id}' first declared at "
                        f"{seen_policy_ids[policy_id]}."
                    ),
                )
            )
        else:
            seen_policy_ids[policy_id] = f"{row_path}.policy_id"

        blocker_code = row.get("blocker_code")
        if not isinstance(blocker_code, str) or not blocker_code.strip():
            diagnostics.append(
                _diagnostic(
                    field_path=f"{row_path}.blocker_code",
                    reason_code=REASON_REQ_057_BLOCKER_CODE_INVALID,
                    message=f"{row_path}.blocker_code must be a non-empty string.",
                )
            )

        diagnostics.extend(
            _validate_escalation_trigger(
                row.get("escalation_trigger"),
                field_path=f"{row_path}.escalation_trigger",
            )
        )
        diagnostics.extend(
            _validate_sorted_unique_string_list(
                value=row.get("owner_hints"),
                field_path=f"{row_path}.owner_hints",
                min_items=1,
            )
        )
        diagnostics.extend(
            _validate_sorted_unique_string_list(
                value=row.get("fallback_paths"),
                field_path=f"{row_path}.fallback_paths",
                min_items=1,
            )
        )

        if "project_id" in row and not isinstance(row.get("project_id"), str):
            diagnostics.append(
                _diagnostic(
                    field_path=f"{row_path}.project_id",
                    reason_code=REASON_REQ_057_PROJECT_ID_INVALID,
                    message=f"{row_path}.project_id must be a string when provided.",
                )
            )

        diagnostics.extend(
            _validate_sorted_unique_string_list(
                value=row.get("evidence_refs", []),
                field_path=f"{row_path}.evidence_refs",
                min_items=0,
            )
        )

    return diagnostics


def validate_strategy_packet_payload(
    packet: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    diagnostics: list[dict[str, str]] = []
    validator = Draft202012Validator(schema)
    traceability_base_dir = Path(base_dir).expanduser().resolve() if base_dir is not None else REPO_ROOT

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

    diagnostics.extend(_validate_strategy_recommendations(packet))
    diagnostics.extend(_validate_strategy_traceability(packet, base_dir=traceability_base_dir))
    diagnostics.extend(_validate_req_057_blocker_policy_artifact(packet))
    return _result(diagnostics)


def validate_strategy_packet_files(input_path: str | Path, schema_path: str | Path) -> dict[str, Any]:
    input_file = Path(input_path).expanduser().resolve()
    schema_file = Path(schema_path).expanduser().resolve()

    try:
        packet = load_json_file(input_file)
    except Exception as exc:
        return _result(
            [
                _diagnostic(
                    field_path="$",
                    reason_code=REASON_INPUT_LOAD_FAILED,
                    message=f"Failed to load strategy packet JSON: {exc}",
                )
            ],
            input_path=str(input_file),
            schema_path=str(schema_file),
        )

    try:
        schema = load_json_file(schema_file)
    except Exception as exc:
        return _result(
            [
                _diagnostic(
                    field_path="$",
                    reason_code=REASON_SCHEMA_LOAD_FAILED,
                    message=f"Failed to load schema JSON: {exc}",
                )
            ],
            input_path=str(input_file),
            schema_path=str(schema_file),
        )

    if not isinstance(packet, Mapping):
        return _result(
            [
                _diagnostic(
                    field_path="$",
                    reason_code=REASON_PACKET_PAYLOAD_NOT_OBJECT,
                    message="strategy packet JSON root must be an object.",
                )
            ],
            input_path=str(input_file),
            schema_path=str(schema_file),
        )
    if not isinstance(schema, Mapping):
        return _result(
            [
                _diagnostic(
                    field_path="$",
                    reason_code=REASON_SCHEMA_PAYLOAD_NOT_OBJECT,
                    message="schema JSON root must be an object.",
                )
            ],
            input_path=str(input_file),
            schema_path=str(schema_file),
        )

    result = validate_strategy_packet_payload(packet, schema, base_dir=REPO_ROOT)
    result["input_path"] = str(input_file)
    result["schema_path"] = str(schema_file)
    return result
