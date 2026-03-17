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
    validate_req_057_blocker_handling_policy_artifact,
    validate_req_068_op_plan_strategy_ingestion_hook,
)

REQ_054_REQUIREMENT_ID = "REQ-054"
REQ_054_SCHEMA_VERSION = "1.0"
REQ_054_ANALYSIS_TYPE = "recommendation_to_planner_mapping_artifact"
REQ_054_CALL_ID = "recommendation-to-planner-mapping-artifact"
REQ_057_REQUIREMENT_ID = "REQ-057"
REQ_057_SCHEMA_VERSION = "1.0"
REQ_057_ANALYSIS_TYPE = "blocker_handling_policy_artifact"
REQ_057_CALL_ID = "blocker-handling-policy-artifact"
REQ_060_REQUIREMENT_ID = "REQ-060"
REQ_060_ANALYSIS_TYPE = "strategy_packet_v1_schema_validator"
REQ_066_REQUIREMENT_ID = "REQ-066"
REQ_066_ANALYSIS_TYPE = "validator_runner_and_aggregate_verdict"
REQ_066_STRATEGY_PACKET_VALIDATOR_ID = "strategy_packet_v1_schema_validator"
REQ_068_INGESTION_HOOK_FILE = "REQ-068_op-plan-strategy-ingestion-hook.sample.json"
REQ_068_INGESTION_HOOK_RELATIVE_PATH = Path("strategy/current/samples") / REQ_068_INGESTION_HOOK_FILE

SEVERITY_ERROR = "error"
REASON_REQ_054_CONTRACT_VIOLATION = "req_054_contract_violation"
REASON_REQ_057_CONTRACT_VIOLATION = "req_057_contract_violation"
REASON_PACKET_RECOMMENDATION_MISSING_MAPPING = "packet_recommendation_missing_mapping"
REASON_MAPPING_REFERENCES_UNKNOWN_PACKET_RECOMMENDATION = "mapping_references_unknown_packet_recommendation"
REASON_MAPPING_ARTIFACT_RECOMMENDATION_IDS_MISMATCH = "mapping_artifact_recommendation_ids_mismatch"
REASON_DUPLICATE_RECOMMENDATION_ID_COLLISION = "duplicate_recommendation_id_collision"
REASON_STRATEGY_RECOMMENDATION_ID_DUPLICATE = "strategy_recommendation_id_duplicate"
REASON_TRACEABILITY_GATE_FAILURE = "traceability_gate_failure"
REASON_STRATEGY_TRACEABILITY_REF_MISSING = "strategy_traceability_ref_missing"
REASON_REQ_068_INGESTION_HOOK_MISSING = "req_068_ingestion_hook_missing"
REASON_REQ_068_INGESTION_HOOK_PAYLOAD_NOT_OBJECT = "req_068_ingestion_hook_payload_not_object"
REASON_REQ_068_CONTRACT_VIOLATION = "req_068_contract_violation"
REASON_REQ_068_PACKET_RECOMMENDATION_IDS_MISMATCH = "req_068_packet_recommendation_ids_mismatch"

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


def validate_req_054_recommendation_to_planner_mapping_artifact(payload: Mapping[str, Any]) -> list[str]:
    artifact = payload.get("recommendation_to_planner_mapping_artifact")
    if not isinstance(artifact, Mapping):
        return ["recommendation_to_planner_mapping_artifact must be an object"]

    raw_mappings = artifact.get("recommendation_to_task_intent_mappings")
    if not isinstance(raw_mappings, list) or not raw_mappings:
        return ["recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings must be a non-empty list"]

    errors: list[str] = []
    observed_recommendation_ids: set[str] = set()
    observed_planner_handles: set[str] = set()
    observed_pairs: set[tuple[str, str]] = set()

    for index, row in enumerate(raw_mappings):
        row_path = f"recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings[{index}]"
        if not isinstance(row, Mapping):
            errors.append(f"{row_path} must be an object")
            continue

        recommendation_id = str(row.get("recommendation_id") or "").strip()
        planner_task_intent_handle = str(row.get("planner_task_intent_handle") or "").strip()
        if recommendation_id:
            observed_recommendation_ids.add(recommendation_id)
        if planner_task_intent_handle:
            observed_planner_handles.add(planner_task_intent_handle)

        if recommendation_id and planner_task_intent_handle:
            pair = (recommendation_id, planner_task_intent_handle)
            if pair in observed_pairs:
                errors.append(
                    f"{row_path} has duplicate recommendation_id + planner_task_intent_handle pair"
                )
            else:
                observed_pairs.add(pair)

        sequence_hint = row.get("sequence_hint")
        if not isinstance(sequence_hint, int) or sequence_hint <= 0:
            errors.append(f"{row_path}.sequence_hint must be a positive integer")

    recommendation_ids = artifact.get("recommendation_ids")
    if isinstance(recommendation_ids, list):
        normalized_recommendation_ids = sorted(
            {
                row
                for row in recommendation_ids
                if isinstance(row, str) and row.strip()
            }
        )
        if normalized_recommendation_ids != sorted(observed_recommendation_ids):
            errors.append(
                "recommendation_to_planner_mapping_artifact.recommendation_ids must exactly match "
                "recommendation_to_task_intent_mappings recommendation_id set"
            )

    planner_task_intent_handles = artifact.get("planner_task_intent_handles")
    if isinstance(planner_task_intent_handles, list):
        normalized_planner_handles = sorted(
            {
                row
                for row in planner_task_intent_handles
                if isinstance(row, str) and row.strip()
            }
        )
        if normalized_planner_handles != sorted(observed_planner_handles):
            errors.append(
                "recommendation_to_planner_mapping_artifact.planner_task_intent_handles must exactly match "
                "recommendation_to_task_intent_mappings planner_task_intent_handle set"
            )

    return sorted(errors)


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


_REQ_052_REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "identity",
    "strategy",
    "recommendations",
    "constraints",
    "kpi_targets",
    "source",
}
_REQ_052_ALLOWED_TOP_LEVEL_KEYS = _REQ_052_REQUIRED_TOP_LEVEL_KEYS | {
    "recommendation_to_planner_mapping_artifact",
    "blocker_handling_policy_artifact",
}
_REQ_052_PROJECT_ID_RE = re.compile(r"^prj\.[a-z0-9]+(?:-[a-z0-9]+)*$")


def _legacy_strategy_packet_diagnostic(
    *,
    field_path: str,
    schema_path: str,
    reason_code: str,
    message: str,
) -> dict[str, str]:
    return {
        "severity": SEVERITY_ERROR,
        "reason_code": reason_code,
        "field_path": field_path,
        "schema_path": schema_path,
        "message": message,
    }


def _validate_req_052_legacy_contract_packet(packet: Any) -> dict[str, Any]:
    if not isinstance(packet, Mapping):
        return {
            "ok": False,
            "verdict": "fail",
            "error_count": 1,
            "reason_codes": ["packet_payload_not_object"],
            "failing_field_paths": ["$"],
            "diagnostics": [
                _legacy_strategy_packet_diagnostic(
                    field_path="$",
                    schema_path="#",
                    reason_code="packet_payload_not_object",
                    message="strategy packet JSON root must be an object",
                )
            ],
        }

    diagnostics: list[dict[str, str]] = []
    packet_keys = set(packet.keys())
    for key in sorted(packet_keys - _REQ_052_ALLOWED_TOP_LEVEL_KEYS):
        diagnostics.append(
            _legacy_strategy_packet_diagnostic(
                field_path=f"$.{key}",
                schema_path="#/additionalProperties",
                reason_code="unexpected_field",
                message=f"$.{key} is not allowed",
            )
        )

    for key in sorted(_REQ_052_REQUIRED_TOP_LEVEL_KEYS - packet_keys):
        diagnostics.append(
            _legacy_strategy_packet_diagnostic(
                field_path=f"$.{key}",
                schema_path="#/required",
                reason_code="missing_required_field",
                message=f"$.{key} is required",
            )
        )

    identity = packet.get("identity")
    if isinstance(identity, Mapping):
        project_id = identity.get("project_id")
        if isinstance(project_id, str) and project_id.strip() and not _REQ_052_PROJECT_ID_RE.fullmatch(project_id):
            diagnostics.append(
                _legacy_strategy_packet_diagnostic(
                    field_path="$.identity.project_id",
                    schema_path="#/properties/identity/properties/project_id/pattern",
                    reason_code="pattern_mismatch",
                    message="$.identity.project_id does not match required pattern",
                )
            )

    strategy = packet.get("strategy")
    if isinstance(strategy, Mapping):
        summary = strategy.get("summary")
        if isinstance(summary, str) and not summary.strip():
            diagnostics.append(
                _legacy_strategy_packet_diagnostic(
                    field_path="$.strategy.summary",
                    schema_path="#/properties/strategy/properties/summary",
                    reason_code="blank_string_value",
                    message="$.strategy.summary must be a non-blank string",
                )
            )

    recommendations = packet.get("recommendations")
    if isinstance(recommendations, list):
        seen_ids: dict[str, int] = {}
        for index, row in enumerate(recommendations):
            if not isinstance(row, Mapping):
                continue
            recommendation_id = row.get("recommendation_id")
            if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                continue
            if recommendation_id in seen_ids:
                first_index = seen_ids[recommendation_id]
                diagnostics.append(
                    _legacy_strategy_packet_diagnostic(
                        field_path=f"$.recommendations[{index}].recommendation_id",
                        schema_path="#/properties/recommendations",
                        reason_code="duplicate_recommendation_id",
                        message=(
                            f"$.recommendations[{index}].recommendation_id duplicates "
                            f"$.recommendations[{first_index}].recommendation_id"
                        ),
                    )
                )
            else:
                seen_ids[recommendation_id] = index

    diagnostics = sorted(diagnostics, key=lambda row: row["field_path"])
    return {
        "ok": not diagnostics,
        "verdict": "pass" if not diagnostics else "fail",
        "error_count": len(diagnostics),
        "reason_codes": [row["reason_code"] for row in diagnostics],
        "failing_field_paths": [row["field_path"] for row in diagnostics],
        "diagnostics": diagnostics,
    }


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


def _req_057_envelope_from_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    policies = artifact.get("policies")
    policy_rows = policies if isinstance(policies, list) else []
    unique_blocker_codes = {
        str(row.get("blocker_code")).strip()
        for row in policy_rows
        if isinstance(row, Mapping) and isinstance(row.get("blocker_code"), str) and str(row.get("blocker_code")).strip()
    }
    unique_owner_hints = {
        str(owner).strip()
        for row in policy_rows
        if isinstance(row, Mapping) and isinstance(row.get("owner_hints"), list)
        for owner in row.get("owner_hints", [])
        if isinstance(owner, str) and owner.strip()
    }
    unique_fallback_paths = {
        str(path).strip()
        for row in policy_rows
        if isinstance(row, Mapping) and isinstance(row.get("fallback_paths"), list)
        for path in row.get("fallback_paths", [])
        if isinstance(path, str) and path.strip()
    }
    unique_evidence_refs = {
        str(reference).strip()
        for row in policy_rows
        if isinstance(row, Mapping) and isinstance(row.get("evidence_refs"), list)
        for reference in row.get("evidence_refs", [])
        if isinstance(reference, str) and reference.strip()
    }
    return {
        "ok": True,
        "schema_version": REQ_057_SCHEMA_VERSION,
        "requirement_id": REQ_057_REQUIREMENT_ID,
        "analysis_type": REQ_057_ANALYSIS_TYPE,
        "call_id": REQ_057_CALL_ID,
        "checked_at_utc": "validator-probe",
        "target_project": {
            "project_id": "validator-probe",
            "project_root": str(Path.cwd().resolve()),
        },
        "blocker_handling_policy_artifact": artifact,
        "totals": {
            "policies": len(policy_rows),
            "unique_blocker_codes": len(unique_blocker_codes),
            "unique_owner_hints": len(unique_owner_hints),
            "unique_fallback_paths": len(unique_fallback_paths),
            "unique_evidence_refs": len(unique_evidence_refs),
        },
    }


def _req_057_field_path(message: str) -> str:
    for marker in (" must ", " has ", " missing ", " duplicates "):
        marker_index = message.find(marker)
        if marker_index > 0:
            candidate = message[:marker_index].strip()
            if candidate:
                return candidate
    return "blocker_handling_policy_artifact"


def _validate_req_057_consumability(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    artifact = packet.get("blocker_handling_policy_artifact")
    if not isinstance(artifact, Mapping):
        return [
            _diagnostic(
                field_path="blocker_handling_policy_artifact",
                reason_code=REASON_REQ_057_CONTRACT_VIOLATION,
                message="blocker_handling_policy_artifact must be present for planner/runtime consumability",
            )
        ]

    diagnostics: list[dict[str, str]] = []
    for message in validate_req_057_blocker_handling_policy_artifact(_req_057_envelope_from_artifact(artifact)):
        field_path = _req_057_field_path(message)
        reason_code = REASON_REQ_057_CONTRACT_VIOLATION
        normalized_message = message
        if message.endswith("must include at least 1 value(s)"):
            reason_code = "req_057_list_min_items"
            normalized_message = f"{field_path} must include at least 1 item(s)."
        elif message.endswith("must not contain duplicates"):
            reason_code = "req_057_list_duplicate"
            normalized_message = f"{field_path} must not contain duplicate values."
        elif message.endswith("must be sorted"):
            reason_code = "req_057_list_unsorted"
            normalized_message = f"{field_path} must be sorted in ascending order."
        diagnostics.append(
            _diagnostic(
                field_path=field_path,
                reason_code=reason_code,
                message=normalized_message,
            )
        )
    return diagnostics


def _req_068_field_path(message: str) -> str:
    for marker in (" must ", " has ", " missing ", " duplicate "):
        marker_index = message.find(marker)
        if marker_index > 0:
            candidate = message[:marker_index].strip()
            if candidate:
                return candidate
    return "op_plan_strategy_ingestion_hook"


def _sorted_unique_strings(values: list[str]) -> list[str]:
    return sorted({value for value in values if value.strip()})


def _req_068_recommendation_ids(hook_payload: Mapping[str, Any]) -> list[str]:
    ingestion = hook_payload.get("op_plan_strategy_ingestion")
    if not isinstance(ingestion, Mapping):
        return []
    planner_inputs = ingestion.get("planner_inputs")
    if not isinstance(planner_inputs, Mapping):
        return []

    recommendation_ids: list[str] = []

    strategy_packet_inputs = planner_inputs.get("strategy_packet_inputs")
    if isinstance(strategy_packet_inputs, list):
        for row in strategy_packet_inputs:
            if not isinstance(row, Mapping):
                continue
            row_ids = row.get("recommendation_ids")
            if not isinstance(row_ids, list):
                continue
            for recommendation_id in row_ids:
                if isinstance(recommendation_id, str) and recommendation_id.strip():
                    recommendation_ids.append(recommendation_id)

    recommendation_traceability_index = planner_inputs.get("recommendation_traceability_index")
    if isinstance(recommendation_traceability_index, list):
        for row in recommendation_traceability_index:
            if not isinstance(row, Mapping):
                continue
            recommendation_id = row.get("recommendation_id")
            if isinstance(recommendation_id, str) and recommendation_id.strip():
                recommendation_ids.append(recommendation_id)

    return _sorted_unique_strings(recommendation_ids)


def _validate_req_068_consumability(
    packet: Mapping[str, Any],
    op_plan_ingestion_hook: Any,
    *,
    require_op_plan_ingestion_hook: bool,
) -> list[dict[str, str]]:
    if op_plan_ingestion_hook is None:
        if not require_op_plan_ingestion_hook:
            return []
        return [
            _diagnostic(
                field_path="op_plan_strategy_ingestion_hook",
                reason_code=REASON_REQ_068_INGESTION_HOOK_MISSING,
                message=(
                    "REQ-068 op-plan strategy ingestion hook payload is required for planner consumability gate "
                    "(expected strategy/current/samples/REQ-068_op-plan-strategy-ingestion-hook.sample.json)"
                ),
            )
        ]

    if not isinstance(op_plan_ingestion_hook, Mapping):
        return [
            _diagnostic(
                field_path="op_plan_strategy_ingestion_hook",
                reason_code=REASON_REQ_068_INGESTION_HOOK_PAYLOAD_NOT_OBJECT,
                message="REQ-068 op-plan strategy ingestion hook payload must be a JSON object",
            )
        ]

    diagnostics: list[dict[str, str]] = []
    contract_errors = validate_req_068_op_plan_strategy_ingestion_hook(op_plan_ingestion_hook)
    for message in contract_errors:
        diagnostics.append(
            _diagnostic(
                field_path=_req_068_field_path(message),
                reason_code=REASON_REQ_068_CONTRACT_VIOLATION,
                message=message,
            )
        )

    if diagnostics:
        return diagnostics

    packet_recommendation_ids = _sorted_unique_strings(_packet_recommendation_ids(packet))
    hook_recommendation_ids = _req_068_recommendation_ids(op_plan_ingestion_hook)
    unexpected_in_hook = sorted(set(hook_recommendation_ids) - set(packet_recommendation_ids))
    if unexpected_in_hook:
        diagnostics.append(
            _diagnostic(
                field_path="op_plan_strategy_ingestion.planner_inputs.recommendation_traceability_index",
                reason_code=REASON_REQ_068_PACKET_RECOMMENDATION_IDS_MISMATCH,
                message=(
                    "REQ-068 recommendation IDs must reference strategy packet recommendation_id values for "
                    "planner consumability; "
                    f"unexpected_in_hook={unexpected_in_hook} "
                    f"packet_recommendation_ids={packet_recommendation_ids}"
                ),
            )
        )

    return diagnostics


def _discover_req_068_ingestion_hook_path(input_path: Path) -> Path | None:
    candidates: list[Path] = []
    candidates.append(input_path.parent / "samples" / REQ_068_INGESTION_HOOK_FILE)
    for parent in input_path.parents:
        candidates.append(parent / REQ_068_INGESTION_HOOK_RELATIVE_PATH)
    candidates.append(Path.cwd().resolve() / REQ_068_INGESTION_HOOK_RELATIVE_PATH)

    visited: set[Path] = set()
    for candidate in candidates:
        resolved_candidate = candidate.expanduser().resolve()
        if resolved_candidate in visited:
            continue
        visited.add(resolved_candidate)
        if resolved_candidate.is_file():
            return resolved_candidate
    return None


def _load_req_068_ingestion_hook_payload(
    input_path: str | Path,
    op_plan_ingestion_hook_path: str | Path | None,
) -> Any | None:
    if op_plan_ingestion_hook_path is not None:
        return load_json_file(op_plan_ingestion_hook_path)

    discovered_path = _discover_req_068_ingestion_hook_path(Path(input_path).expanduser().resolve())
    if discovered_path is None:
        return None
    return load_json_file(discovered_path)


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


def _duplicate_recommendation_collisions(
    packet: Mapping[str, Any],
) -> list[dict[str, Any]]:
    collisions: list[dict[str, Any]] = []
    raw_recommendations = packet.get("recommendations")
    if not isinstance(raw_recommendations, list):
        return collisions

    recommendation_ids = _packet_recommendation_ids(packet)
    if not recommendation_ids:
        return collisions

    index_by_recommendation_id: dict[str, list[int]] = {}
    for index, recommendation_id in enumerate(recommendation_ids):
        index_by_recommendation_id.setdefault(recommendation_id, []).append(index)

    for recommendation_id, indexes in sorted(index_by_recommendation_id.items()):
        if len(indexes) < 2:
            continue
        first_index, duplicate_index = indexes[0], indexes[1]
        first_row = raw_recommendations[first_index] if first_index < len(raw_recommendations) else {}
        duplicate_row = raw_recommendations[duplicate_index] if duplicate_index < len(raw_recommendations) else {}
        differing_fields: list[str] = []
        if isinstance(first_row, Mapping) and isinstance(duplicate_row, Mapping):
            for key in sorted((set(first_row.keys()) | set(duplicate_row.keys())) - {"recommendation_id"}):
                if first_row.get(key) != duplicate_row.get(key):
                    differing_fields.append(str(key))
        collisions.append(
            {
                "recommendation_id": recommendation_id,
                "collision_indexes": list(indexes),
                "first_index": first_index,
                "duplicate_index": duplicate_index,
                "differing_fields": differing_fields,
            }
        )

    return collisions


def _validate_duplicate_recommendation_ids(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    collisions = _duplicate_recommendation_collisions(packet)
    if not collisions:
        return diagnostics

    artifact = packet.get("recommendation_to_planner_mapping_artifact")
    expected_ids: list[str] = []
    if isinstance(artifact, Mapping):
        raw_expected_ids = artifact.get("recommendation_ids")
        if isinstance(raw_expected_ids, list):
            expected_ids = sorted(item for item in raw_expected_ids if isinstance(item, str) and item.strip())

    observed_unique_ids = sorted({row["recommendation_id"] for row in collisions} | set(_packet_recommendation_ids(packet)))

    missing_from_packet = sorted(set(expected_ids) - set(observed_unique_ids))
    unexpected_in_packet = sorted(set(observed_unique_ids) - set(expected_ids))

    for collision in collisions:
        diagnostics.append(
            _diagnostic(
                field_path=f"recommendations[{collision['duplicate_index']}].recommendation_id",
                reason_code=REASON_DUPLICATE_RECOMMENDATION_ID_COLLISION,
                message=(
                    f"recommendation_id '{collision['recommendation_id']}' must be unique; "
                    f"collision_indexes={collision['collision_indexes']} "
                    f"missing_from_packet={missing_from_packet} "
                    f"unexpected_in_packet={unexpected_in_packet}"
                ),
            )
        )

    return diagnostics


def _validate_strategy_packet_evidence_refs(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    repo_root = SCRIPT_DIR.parent
    artifact = packet.get("blocker_handling_policy_artifact")
    if not isinstance(artifact, Mapping):
        return diagnostics
    policies = artifact.get("policies")
    if not isinstance(policies, list):
        return diagnostics

    for policy_index, row in enumerate(policies):
        if not isinstance(row, Mapping):
            continue
        evidence_refs = row.get("evidence_refs")
        if not isinstance(evidence_refs, list):
            continue
        for ref_index, raw_ref in enumerate(evidence_refs):
            if not isinstance(raw_ref, str) or not raw_ref.strip():
                continue
            reference = raw_ref.strip()
            reference_path = reference.split("#", 1)[0]
            if not reference_path or "::" in reference_path or "://" in reference_path or reference_path.startswith("missing:"):
                continue
            candidate_path = (repo_root / reference_path).resolve()
            if candidate_path.exists():
                continue
            diagnostics.append(
                _diagnostic(
                    field_path=f"blocker_handling_policy_artifact.policies[{policy_index}].evidence_refs[{ref_index}]",
                    reason_code=REASON_STRATEGY_TRACEABILITY_REF_MISSING,
                    message=(
                        f"blocker_handling_policy_artifact.policies[{policy_index}].evidence_refs[{ref_index}] "
                        f"references missing file '{reference_path}'."
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


def _validate_req_054_consumability(
    packet: Mapping[str, Any],
    *,
    include_packet_diff_details: bool = False,
) -> list[dict[str, str]]:
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
            message = "recommendation_ids must exactly match the strategy packet recommendation_id set for planner consumability"
            if include_packet_diff_details:
                message = (
                    f"{message}; missing_from_packet={missing_from_packet} "
                    f"unexpected_in_packet={unexpected_in_packet}"
                )
            diagnostics.append(
                _diagnostic(
                    field_path="recommendation_to_planner_mapping_artifact.recommendation_ids",
                    reason_code=REASON_MAPPING_ARTIFACT_RECOMMENDATION_IDS_MISMATCH,
                    message=message,
                )
            )

    return diagnostics


def validate_strategy_packet_payload(
    packet: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    op_plan_ingestion_hook: Any | None = None,
    require_op_plan_ingestion_hook: bool = False,
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

    duplicate_recommendation_diagnostics = _validate_duplicate_recommendation_ids(packet)
    has_duplicate_recommendation_collisions = bool(duplicate_recommendation_diagnostics)
    diagnostics.extend(duplicate_recommendation_diagnostics)
    diagnostics.extend(_validate_traceability_gate(packet))
    diagnostics.extend(_validate_strategy_packet_evidence_refs(packet))
    diagnostics.extend(
        _validate_req_054_consumability(
            packet,
            include_packet_diff_details=has_duplicate_recommendation_collisions,
        )
    )
    diagnostics.extend(_validate_req_057_consumability(packet))
    diagnostics.extend(
        _validate_req_068_consumability(
            packet,
            op_plan_ingestion_hook,
            require_op_plan_ingestion_hook=require_op_plan_ingestion_hook,
        )
    )
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


def _packet_payload_not_object_validation_result(*, checked_at_utc: str | None = None) -> dict[str, Any]:
    checked_at = checked_at_utc or _utc_timestamp()
    return {
        "ok": False,
        "checked_at_utc": checked_at,
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


def _looks_like_legacy_req_052_packet(packet: Mapping[str, Any]) -> bool:
    return not (
        isinstance(packet.get("recommendation_to_planner_mapping_artifact"), Mapping)
        or isinstance(packet.get("blocker_handling_policy_artifact"), Mapping)
    )


def _schema_valid_from_diagnostics(diagnostics: Sequence[Mapping[str, Any]]) -> bool:
    for row in diagnostics:
        reason_code = str(row.get("reason_code") or "")
        if reason_code.startswith("schema_"):
            return False
    return True


def _req_057_gate_from_diagnostics(diagnostics: Sequence[Mapping[str, Any]]) -> bool:
    for row in diagnostics:
        reason_code = str(row.get("reason_code") or "")
        if reason_code.startswith("req_057_"):
            return False
    return True


def _file_level_summary(packet: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    ok = bool(payload.get("ok"))
    diagnostics = payload.get("diagnostics")
    diagnostic_count = len(diagnostics) if isinstance(diagnostics, list) else int(payload.get("diagnostic_count") or 0)
    reason_codes = payload.get("reason_codes")
    normalized_reason_codes = list(reason_codes) if isinstance(reason_codes, list) else []
    runtime_wording = isinstance(packet.get("blocker_handling_policy_artifact"), Mapping) and (
        ok or any(str(code).startswith("req_057_") for code in normalized_reason_codes)
    )
    if ok:
        return "Strategy packet is planner/runtime-consumable." if runtime_wording else "Strategy packet is planner-consumable."
    if runtime_wording:
        return f"Strategy packet is not planner/runtime-consumable; {diagnostic_count} blocking diagnostics detected."
    return f"Strategy packet is not planner-consumable; {diagnostic_count} blocking diagnostics detected."


def _enrich_file_level_payload(
    packet: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    input_path: str | Path,
    schema_path: str | Path,
) -> dict[str, Any]:
    diagnostics = payload.get("diagnostics")
    normalized_diagnostics = list(diagnostics) if isinstance(diagnostics, list) else []
    collision_rows = _duplicate_recommendation_collisions(packet)
    if collision_rows:
        suppressed_reason_codes = {
            REASON_DUPLICATE_RECOMMENDATION_ID_COLLISION,
            REASON_MAPPING_ARTIFACT_RECOMMENDATION_IDS_MISMATCH,
            REASON_MAPPING_REFERENCES_UNKNOWN_PACKET_RECOMMENDATION,
            REASON_REQ_068_PACKET_RECOMMENDATION_IDS_MISMATCH,
        }
        normalized_diagnostics = [
            row
            for row in normalized_diagnostics
            if str(row.get("reason_code") or "") not in suppressed_reason_codes
        ]
        for collision in collision_rows:
            normalized_diagnostics.append(
                _diagnostic(
                    field_path=f"recommendations[{collision['duplicate_index']}].recommendation_id",
                    reason_code=REASON_STRATEGY_RECOMMENDATION_ID_DUPLICATE,
                    message=(
                        f"recommendations[{collision['duplicate_index']}].recommendation_id duplicates recommendation_id "
                        f"'{collision['recommendation_id']}' first declared at "
                        f"recommendations[{collision['first_index']}].recommendation_id; "
                        f"differing fields: {collision['differing_fields']}."
                    ),
                )
            )
        normalized_diagnostics = _sorted_diagnostics(normalized_diagnostics)
    enriched = dict(payload)
    enriched["diagnostics"] = normalized_diagnostics
    enriched["diagnostic_count"] = len(normalized_diagnostics)
    enriched["reason_codes"] = sorted({str(row.get("reason_code") or "") for row in normalized_diagnostics})
    enriched["summary"] = _file_level_summary(packet, enriched)
    enriched["input_path"] = str(Path(input_path).expanduser().resolve())
    enriched["schema_path"] = str(Path(schema_path).expanduser().resolve())
    enriched["gate"] = {
        "schema_valid": _schema_valid_from_diagnostics(normalized_diagnostics),
        "req_057_blocker_policy_consumable": _req_057_gate_from_diagnostics(normalized_diagnostics),
    }
    return enriched


def _run_req_060_strategy_packet_v1_schema_validator(
    packet: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    op_plan_ingestion_hook: Any | None = None,
    require_op_plan_ingestion_hook: bool = False,
) -> dict[str, Any]:
    return validate_strategy_packet_payload(
        packet,
        schema,
        op_plan_ingestion_hook=op_plan_ingestion_hook,
        require_op_plan_ingestion_hook=require_op_plan_ingestion_hook,
    )


def _req_066_validator_registry() -> tuple[dict[str, Any], ...]:
    return (
        {
            "validator_id": REQ_066_STRATEGY_PACKET_VALIDATOR_ID,
            "requirement_id": REQ_060_REQUIREMENT_ID,
            "analysis_type": REQ_060_ANALYSIS_TYPE,
            "runner": _run_req_060_strategy_packet_v1_schema_validator,
        },
    )


def _req_066_validator_row(definition: Mapping[str, Any], output: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = output.get("diagnostics")
    normalized_diagnostics = list(diagnostics) if isinstance(diagnostics, list) else []
    reason_codes = output.get("reason_codes")
    normalized_reason_codes = list(reason_codes) if isinstance(reason_codes, list) else []
    return {
        "validator_id": definition["validator_id"],
        "requirement_id": definition["requirement_id"],
        "analysis_type": definition["analysis_type"],
        "ok": bool(output.get("ok")),
        "verdict": "pass" if output.get("ok") else "fail",
        "blocking_reason_codes": sorted(
            code for code in normalized_reason_codes if isinstance(code, str) and code.strip()
        ),
        "diagnostic_count": len(normalized_diagnostics),
        "summary": str(output.get("summary") or ""),
        "diagnostics": normalized_diagnostics,
    }


def _req_066_aggregate_diagnostics(validators: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    aggregate: list[dict[str, str]] = []
    for row in validators:
        validator_id = str(row.get("validator_id") or "")
        diagnostics = row.get("diagnostics")
        if not isinstance(diagnostics, list):
            continue
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, Mapping):
                continue
            aggregate.append(
                {
                    "validator_id": validator_id,
                    "severity": str(diagnostic.get("severity") or ""),
                    "reason_code": str(diagnostic.get("reason_code") or ""),
                    "field_path": str(diagnostic.get("field_path") or ""),
                    "message": str(diagnostic.get("message") or ""),
                }
            )

    return sorted(
        aggregate,
        key=lambda row: (
            row["validator_id"],
            row["field_path"],
            row["severity"],
            row["reason_code"],
            row["message"],
        ),
    )


def _build_req_066_aggregate_verdict(
    validators: Sequence[Mapping[str, Any]],
    *,
    checked_at_utc: str,
) -> dict[str, Any]:
    validator_rows = [dict(row) for row in validators]
    validator_count = len(validator_rows)
    failed_validator_count = sum(1 for row in validator_rows if row.get("ok") is False)
    passed_validator_count = validator_count - failed_validator_count
    ok = failed_validator_count == 0
    blocking_reason_codes = sorted(
        {
            reason_code
            for row in validator_rows
            for reason_code in row.get("blocking_reason_codes", [])
            if isinstance(reason_code, str) and reason_code.strip()
        }
    )
    diagnostics = _req_066_aggregate_diagnostics(validator_rows)
    return {
        "requirement_id": REQ_066_REQUIREMENT_ID,
        "analysis_type": REQ_066_ANALYSIS_TYPE,
        "checked_at_utc": checked_at_utc,
        "ok": ok,
        "verdict": "pass" if ok else "fail",
        "planner_consumability": "planner_ready" if ok else "planner_blocked",
        "blocking_reason_codes": blocking_reason_codes,
        "validator_count": validator_count,
        "passed_validator_count": passed_validator_count,
        "failed_validator_count": failed_validator_count,
        "diagnostic_count": len(diagnostics),
        "summary": (
            "All validators passed; aggregate verdict is pass."
            if ok
            else f"{failed_validator_count} of {validator_count} validators reported blocking failures."
        ),
        "validators": validator_rows,
        "diagnostics": diagnostics,
    }


def run_strategy_packet_validator_runner(
    packet: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    checked_at_utc: str | None = None,
    op_plan_ingestion_hook: Any | None = None,
    require_op_plan_ingestion_hook: bool = False,
) -> dict[str, Any]:
    normalized_checked_at = checked_at_utc or _utc_timestamp()
    validator_rows: list[dict[str, Any]] = []
    for definition in _req_066_validator_registry():
        runner = definition["runner"]
        output = runner(
            packet,
            schema,
            op_plan_ingestion_hook=op_plan_ingestion_hook,
            require_op_plan_ingestion_hook=require_op_plan_ingestion_hook,
        )
        validator_rows.append(_req_066_validator_row(definition, output))
    return _build_req_066_aggregate_verdict(validator_rows, checked_at_utc=normalized_checked_at)


def run_strategy_packet_validator_runner_files(
    input_path: str | Path,
    schema_path: str | Path,
    *,
    op_plan_ingestion_hook_path: str | Path | None = None,
) -> dict[str, Any]:
    packet = load_json_file(input_path)
    schema = load_json_schema(schema_path)
    checked_at_utc = _utc_timestamp()
    if not isinstance(packet, Mapping):
        output = _packet_payload_not_object_validation_result(checked_at_utc=checked_at_utc)
        definition = _req_066_validator_registry()[0]
        row = _req_066_validator_row(definition, output)
        return _build_req_066_aggregate_verdict([row], checked_at_utc=checked_at_utc)
    op_plan_ingestion_hook = _load_req_068_ingestion_hook_payload(input_path, op_plan_ingestion_hook_path)
    return run_strategy_packet_validator_runner(
        packet,
        schema,
        checked_at_utc=checked_at_utc,
        op_plan_ingestion_hook=op_plan_ingestion_hook,
        require_op_plan_ingestion_hook=True,
    )


def validate_strategy_packet_files(
    input_path: str | Path,
    schema_path: str | Path,
    *,
    op_plan_ingestion_hook_path: str | Path | None = None,
) -> dict[str, Any]:
    packet = load_json_file(input_path)
    if not isinstance(packet, Mapping):
        return _packet_payload_not_object_validation_result()
    if _looks_like_legacy_req_052_packet(packet):
        return _validate_req_052_legacy_contract_packet(packet)
    schema = load_json_schema(schema_path)
    op_plan_ingestion_hook = _load_req_068_ingestion_hook_payload(input_path, op_plan_ingestion_hook_path)
    payload = validate_strategy_packet_payload(
        packet,
        schema,
        op_plan_ingestion_hook=op_plan_ingestion_hook,
        require_op_plan_ingestion_hook=True,
    )
    return _enrich_file_level_payload(
        packet,
        payload,
        input_path=input_path,
        schema_path=schema_path,
    )


def validate_strategy_packet_paths(
    input_path: str | Path,
    schema_path: str | Path,
    *,
    op_plan_ingestion_hook_path: str | Path | None = None,
) -> dict[str, Any]:
    packet = load_json_file(input_path)
    return _validate_req_052_legacy_contract_packet(packet)


def validate_strategy_packet(
    packet: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    input_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    op_plan_ingestion_hook: Any | None = None,
    op_plan_ingestion_hook_path: str | Path | None = None,
    require_op_plan_ingestion_hook: bool = False,
) -> dict[str, Any]:
    if _looks_like_legacy_req_052_packet(packet):
        return _validate_req_052_legacy_contract_packet(packet)

    resolved_op_plan_ingestion_hook = op_plan_ingestion_hook
    should_require_hook = require_op_plan_ingestion_hook
    if resolved_op_plan_ingestion_hook is None and input_path is not None:
        resolved_op_plan_ingestion_hook = _load_req_068_ingestion_hook_payload(
            input_path,
            op_plan_ingestion_hook_path,
        )
        should_require_hook = True

    payload = validate_strategy_packet_payload(
        packet,
        schema,
        op_plan_ingestion_hook=resolved_op_plan_ingestion_hook,
        require_op_plan_ingestion_hook=should_require_hook,
    )
    return _enrich_file_level_payload(
        packet,
        payload,
        input_path=input_path or "<in-memory-packet>",
        schema_path=schema_path or "<in-memory-schema>",
    )
