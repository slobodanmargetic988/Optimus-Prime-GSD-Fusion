from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


SEVERITY_ERROR = "error"
VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"

REASON_CODE_SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
REASON_CODE_CONSTRAINT_ARTIFACT_EMPTY = "constraint_artifact_empty"
REASON_CODE_CONSTRAINT_BUCKET_CLASSIFICATION_MISMATCH = "constraint_bucket_classification_mismatch"
REASON_CODE_CONSTRAINT_POLICY_ROLE_MISMATCH = "constraint_policy_role_mismatch"
REASON_CODE_CONSTRAINT_ID_DUPLICATE = "constraint_id_duplicate"
REASON_CODE_PLANNER_POLICY_ALIGNMENT_MISMATCH = "planner_policy_alignment_mismatch"
REASON_CODE_PLANNER_POLICY_DUPLICATE_ID = "planner_policy_duplicate_id"
REASON_CODE_INPUT_NOT_OBJECT = "input_not_object"
REASON_CODE_SCHEMA_NOT_OBJECT = "schema_not_object"
REASON_CODE_INPUT_LOAD_FAILED = "input_load_failed"
REASON_CODE_SCHEMA_LOAD_FAILED = "schema_load_failed"
REASON_CODE_RECOMMENDATION_COMPLETENESS_FAILED = "recommendation_completeness_failed"
REASON_CODE_RECOMMENDATION_LOW_SUBSTANCE_RATIONALE = "recommendation_low_substance_rationale"
REASON_CODE_RECOMMENDATION_EVIDENCE_CITATIONS_BELOW_MINIMUM = "recommendation_evidence_citations_below_minimum"
REASON_CODE_RECOMMENDATION_ID_DUPLICATE = "recommendation_id_duplicate"

REQ_061_MIN_RATIONALE_WORD_COUNT = 12
REQ_061_MIN_EVIDENCE_CITATIONS = 2

_REQ_061_REQUIRED_RECOMMENDATION_FIELDS: tuple[str, ...] = (
    "recommendation_id",
    "priority",
    "summary",
    "rationale",
    "expected_impact",
    "risk_level",
)
_WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")
_EVIDENCE_CITATION_PATTERN = re.compile(
    r"(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+\.(?:json|md|yaml|yml|txt)(?:#[A-Za-z0-9._/-]+)?"
)

_CONSTRAINT_BUCKETS: tuple[tuple[str, str, str], ...] = (
    ("hard_constraints", "hard", "mandatory_guardrail"),
    ("soft_constraints", "soft", "optional_guidance"),
    ("speculative_constraints", "speculative", "optional_guidance"),
)

_PLANNER_POLICY_PATHS: tuple[tuple[str, str], ...] = (
    ("hard_constraint_ids", "hard_constraints"),
    ("soft_constraint_ids", "soft_constraints"),
    ("speculative_constraint_ids", "speculative_constraints"),
    ("mandatory_guardrail_ids", "hard_constraints"),
    ("optional_guidance_ids", "optional_guidance"),
)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _diagnostic(path: str, reason_code: str, message: str, *, severity: str = SEVERITY_ERROR) -> dict[str, str]:
    return {
        "path": path,
        "severity": severity,
        "reason_code": reason_code,
        "message": message,
    }


def _path_from_parts(parts: Sequence[Any]) -> str:
    if not parts:
        return "$"
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def _schema_error_sort_key(error: ValidationError) -> tuple[str, str]:
    return (_path_from_parts(list(error.absolute_path)), error.message)


def _unique_sorted_reason_codes(diagnostics: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("reason_code"))
            for row in diagnostics
            if isinstance(row, Mapping) and isinstance(row.get("reason_code"), str) and row.get("reason_code")
        }
    )


def _count_words(value: str) -> int:
    return len(_WORD_PATTERN.findall(value))


def _extract_evidence_citations(*values: str) -> list[str]:
    citations: list[str] = []
    seen: set[str] = set()
    for value in values:
        for match in _EVIDENCE_CITATION_PATTERN.findall(value):
            citation = match.strip()
            if citation and citation not in seen:
                seen.add(citation)
                citations.append(citation)
    return citations


def load_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _result(
    *,
    diagnostics: list[dict[str, str]],
    input_path: str | None = None,
    schema_path: str | None = None,
) -> dict[str, Any]:
    passed = not diagnostics
    reason_codes = _unique_sorted_reason_codes(diagnostics)
    constraint_failure_reason_codes = {
        REASON_CODE_SCHEMA_VALIDATION_FAILED,
        REASON_CODE_CONSTRAINT_ARTIFACT_EMPTY,
        REASON_CODE_CONSTRAINT_BUCKET_CLASSIFICATION_MISMATCH,
        REASON_CODE_CONSTRAINT_POLICY_ROLE_MISMATCH,
        REASON_CODE_CONSTRAINT_ID_DUPLICATE,
        REASON_CODE_PLANNER_POLICY_ALIGNMENT_MISMATCH,
        REASON_CODE_PLANNER_POLICY_DUPLICATE_ID,
        REASON_CODE_INPUT_NOT_OBJECT,
        REASON_CODE_SCHEMA_NOT_OBJECT,
        REASON_CODE_INPUT_LOAD_FAILED,
        REASON_CODE_SCHEMA_LOAD_FAILED,
    }
    recommendation_failure_reason_codes = {
        REASON_CODE_RECOMMENDATION_COMPLETENESS_FAILED,
        REASON_CODE_RECOMMENDATION_LOW_SUBSTANCE_RATIONALE,
        REASON_CODE_RECOMMENDATION_EVIDENCE_CITATIONS_BELOW_MINIMUM,
        REASON_CODE_RECOMMENDATION_ID_DUPLICATE,
    }
    planner_failure_reason_codes = (
        constraint_failure_reason_codes | recommendation_failure_reason_codes
    )
    schema_failure_reason_codes = {
        REASON_CODE_SCHEMA_VALIDATION_FAILED,
        REASON_CODE_INPUT_NOT_OBJECT,
        REASON_CODE_SCHEMA_NOT_OBJECT,
        REASON_CODE_INPUT_LOAD_FAILED,
        REASON_CODE_SCHEMA_LOAD_FAILED,
    }
    return {
        "ok": passed,
        "verdict": VERDICT_PASS if passed else VERDICT_FAIL,
        "checked_at_utc": _utc_timestamp(),
        "summary": (
            "Strategy packet passed schema and consumability validation."
            if passed
            else f"Strategy packet failed validation with {len(diagnostics)} diagnostic(s)."
        ),
        "input_path": input_path,
        "schema_path": schema_path,
        "reason_codes": reason_codes,
        "diagnostic_count": len(diagnostics),
        "gate": {
            "schema_valid": not any(
                row["reason_code"] in schema_failure_reason_codes for row in diagnostics
            ),
            "constraint_classification_consumable": not any(
                row["reason_code"] in constraint_failure_reason_codes for row in diagnostics
            ),
            "planner_policy_consumable": not any(
                row["reason_code"] in planner_failure_reason_codes
                for row in diagnostics
            ),
        },
        "diagnostics": diagnostics,
    }


def _validate_constraint_artifact(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    constraints = packet.get("constraints")
    if not isinstance(constraints, Mapping):
        return diagnostics

    bucket_presence: dict[str, bool] = {}
    expected_ids: dict[str, list[str]] = {
        "hard_constraints": [],
        "soft_constraints": [],
        "speculative_constraints": [],
        "optional_guidance": [],
    }
    seen_constraint_ids: dict[str, str] = {}

    for bucket_name, expected_classification, expected_policy_role in _CONSTRAINT_BUCKETS:
        bucket_value = constraints.get(bucket_name)
        bucket_presence[bucket_name] = isinstance(bucket_value, list)
        if not isinstance(bucket_value, list):
            continue
        for index, row in enumerate(bucket_value):
            if not isinstance(row, Mapping):
                continue
            row_path = f"$.constraints.{bucket_name}[{index}]"
            constraint_id = row.get("constraint_id")
            if isinstance(constraint_id, str) and constraint_id:
                existing_path = seen_constraint_ids.get(constraint_id)
                if existing_path is not None:
                    diagnostics.append(
                        _diagnostic(
                            f"{row_path}.constraint_id",
                            REASON_CODE_CONSTRAINT_ID_DUPLICATE,
                            (
                                f"Constraint ID '{constraint_id}' is duplicated; "
                                f"first seen at {existing_path}."
                            ),
                        )
                    )
                else:
                    seen_constraint_ids[constraint_id] = f"{row_path}.constraint_id"
                    expected_ids[bucket_name].append(constraint_id)
                    if expected_policy_role == "optional_guidance":
                        expected_ids["optional_guidance"].append(constraint_id)

            classification = row.get("classification")
            if isinstance(classification, str) and classification != expected_classification:
                diagnostics.append(
                    _diagnostic(
                        f"{row_path}.classification",
                        REASON_CODE_CONSTRAINT_BUCKET_CLASSIFICATION_MISMATCH,
                        (
                            f"{bucket_name} entries must declare classification "
                            f"'{expected_classification}', found '{classification}'."
                        ),
                    )
                )

            policy_role = row.get("policy_role")
            if isinstance(policy_role, str) and policy_role != expected_policy_role:
                diagnostics.append(
                    _diagnostic(
                        f"{row_path}.policy_role",
                        REASON_CODE_CONSTRAINT_POLICY_ROLE_MISMATCH,
                        (
                            f"{bucket_name} entries must declare policy_role "
                            f"'{expected_policy_role}', found '{policy_role}'."
                        ),
                    )
                )

    total_constraints = sum(len(expected_ids[bucket_name]) for bucket_name, _, _ in _CONSTRAINT_BUCKETS)
    if total_constraints == 0:
        diagnostics.append(
            _diagnostic(
                "$.constraints",
                REASON_CODE_CONSTRAINT_ARTIFACT_EMPTY,
                "Constraint classification artifact must include at least one constraint row.",
            )
        )

    planner_policy = constraints.get("planner_policy")
    if not isinstance(planner_policy, Mapping):
        return diagnostics

    for list_name, _ in _PLANNER_POLICY_PATHS:
        list_value = planner_policy.get(list_name)
        if not isinstance(list_value, list):
            continue
        seen_ids: set[str] = set()
        for index, item in enumerate(list_value):
            if not isinstance(item, str):
                continue
            if item in seen_ids:
                diagnostics.append(
                    _diagnostic(
                        f"$.constraints.planner_policy.{list_name}[{index}]",
                        REASON_CODE_PLANNER_POLICY_DUPLICATE_ID,
                        f"Planner policy list '{list_name}' must not contain duplicate ID '{item}'.",
                    )
                )
            seen_ids.add(item)

    expected_policy_lists = (
        ("hard_constraint_ids", expected_ids["hard_constraints"], bucket_presence["hard_constraints"]),
        ("soft_constraint_ids", expected_ids["soft_constraints"], bucket_presence["soft_constraints"]),
        (
            "speculative_constraint_ids",
            expected_ids["speculative_constraints"],
            bucket_presence["speculative_constraints"],
        ),
        ("mandatory_guardrail_ids", expected_ids["hard_constraints"], bucket_presence["hard_constraints"]),
        (
            "optional_guidance_ids",
            expected_ids["optional_guidance"],
            bucket_presence["soft_constraints"] and bucket_presence["speculative_constraints"],
        ),
    )
    for list_name, expected_list, should_compare in expected_policy_lists:
        if not should_compare:
            continue
        actual_list = planner_policy.get(list_name)
        if not isinstance(actual_list, list):
            continue
        if actual_list != expected_list:
            diagnostics.append(
                _diagnostic(
                    f"$.constraints.planner_policy.{list_name}",
                    REASON_CODE_PLANNER_POLICY_ALIGNMENT_MISMATCH,
                    f"{list_name} must equal {expected_list}.",
                )
            )

    return diagnostics


def _validate_recommendation_quality(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    recommendations = packet.get("recommendations")
    if not isinstance(recommendations, list):
        return diagnostics

    seen_recommendation_ids: dict[str, str] = {}
    for index, row in enumerate(recommendations):
        row_path = f"$.recommendations[{index}]"
        if not isinstance(row, Mapping):
            continue

        recommendation_id = row.get("recommendation_id")
        if isinstance(recommendation_id, str) and recommendation_id:
            id_path = f"{row_path}.recommendation_id"
            existing_path = seen_recommendation_ids.get(recommendation_id)
            if existing_path is not None:
                diagnostics.append(
                    _diagnostic(
                        id_path,
                        REASON_CODE_RECOMMENDATION_ID_DUPLICATE,
                        (
                            f"Recommendation ID '{recommendation_id}' is duplicated; "
                            f"first seen at {existing_path}."
                        ),
                    )
                )
            else:
                seen_recommendation_ids[recommendation_id] = id_path

        for field_name in _REQ_061_REQUIRED_RECOMMENDATION_FIELDS:
            field_path = f"{row_path}.{field_name}"
            value = row.get(field_name)
            if not isinstance(value, str) or not value.strip():
                diagnostics.append(
                    _diagnostic(
                        field_path,
                        REASON_CODE_RECOMMENDATION_COMPLETENESS_FAILED,
                        (
                            "Recommendation field must be a non-empty string for REQ-061 "
                            "quality gate completeness."
                        ),
                    )
                )

        rationale = row.get("rationale")
        if isinstance(rationale, str):
            word_count = _count_words(rationale)
            if word_count < REQ_061_MIN_RATIONALE_WORD_COUNT:
                diagnostics.append(
                    _diagnostic(
                        f"{row_path}.rationale",
                        REASON_CODE_RECOMMENDATION_LOW_SUBSTANCE_RATIONALE,
                        (
                            "Recommendation rationale is below REQ-061 minimum word count: "
                            f"{word_count} < {REQ_061_MIN_RATIONALE_WORD_COUNT}."
                        ),
                    )
                )

        summary = row.get("summary")
        expected_impact = row.get("expected_impact")
        citations = _extract_evidence_citations(
            summary if isinstance(summary, str) else "",
            rationale if isinstance(rationale, str) else "",
            expected_impact if isinstance(expected_impact, str) else "",
        )
        if len(citations) < REQ_061_MIN_EVIDENCE_CITATIONS:
            diagnostics.append(
                _diagnostic(
                    f"{row_path}.expected_impact",
                    REASON_CODE_RECOMMENDATION_EVIDENCE_CITATIONS_BELOW_MINIMUM,
                    (
                        "Recommendation evidence citations are below REQ-061 minimum count "
                        f"across summary/rationale/expected_impact: {len(citations)} < "
                        f"{REQ_061_MIN_EVIDENCE_CITATIONS}; detected={json.dumps(citations)}."
                    ),
                )
            )

    return diagnostics


def validate_strategy_packet(packet: Any, schema: Any, *, input_path: str | None = None, schema_path: str | None = None) -> dict[str, Any]:
    diagnostics: list[dict[str, str]] = []
    if not isinstance(packet, Mapping):
        diagnostics.append(
            _diagnostic("$", REASON_CODE_INPUT_NOT_OBJECT, "Input strategy packet must be a JSON object.")
        )
        return _result(diagnostics=diagnostics, input_path=input_path, schema_path=schema_path)

    if not isinstance(schema, Mapping):
        diagnostics.append(_diagnostic("$", REASON_CODE_SCHEMA_NOT_OBJECT, "Schema must be a JSON object."))
        return _result(diagnostics=diagnostics, input_path=input_path, schema_path=schema_path)

    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(packet), key=_schema_error_sort_key):
        diagnostics.append(
            _diagnostic(
                _path_from_parts(list(error.absolute_path)),
                REASON_CODE_SCHEMA_VALIDATION_FAILED,
                error.message,
            )
        )

    diagnostics.extend(_validate_constraint_artifact(packet))
    diagnostics.extend(_validate_recommendation_quality(packet))
    diagnostics.sort(key=lambda row: (row["path"], row["reason_code"], row["message"]))
    return _result(diagnostics=diagnostics, input_path=input_path, schema_path=schema_path)


def build_failure_result(
    reason_code: str,
    message: str,
    *,
    path: str = "$",
    input_path: str | None = None,
    schema_path: str | None = None,
) -> dict[str, Any]:
    return _result(
        diagnostics=[_diagnostic(path, reason_code, message)],
        input_path=input_path,
        schema_path=schema_path,
    )


def validate_strategy_packet_files(input_path: str | Path, schema_path: str | Path) -> dict[str, Any]:
    input_file = Path(input_path)
    schema_file = Path(schema_path)
    try:
        packet = load_json_file(input_file)
    except Exception as exc:
        return build_failure_result(
            REASON_CODE_INPUT_LOAD_FAILED,
            f"Failed to load input packet: {exc}",
            input_path=str(input_file),
            schema_path=str(schema_file),
        )
    try:
        schema = load_json_file(schema_file)
    except Exception as exc:
        return build_failure_result(
            REASON_CODE_SCHEMA_LOAD_FAILED,
            f"Failed to load schema: {exc}",
            input_path=str(input_file),
            schema_path=str(schema_file),
        )
    return validate_strategy_packet(
        packet,
        schema,
        input_path=str(input_file),
        schema_path=str(schema_file),
    )
