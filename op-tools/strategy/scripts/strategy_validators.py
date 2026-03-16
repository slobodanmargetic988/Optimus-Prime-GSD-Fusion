#!/usr/bin/env python3
"""Deterministic validators for strategy packet consumability gates."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator


GATE_IDS = (
    "citation_coverage",
    "contradiction_status",
    "confidence_distribution",
)

SCHEMA_REASON_CODES = {
    "required": "schema.required",
    "additionalProperties": "schema.additional_properties",
    "type": "schema.type",
    "enum": "schema.enum",
    "pattern": "schema.pattern",
    "minItems": "schema.min_items",
    "minimum": "schema.minimum",
    "maximum": "schema.maximum",
    "const": "schema.const",
    "minLength": "schema.min_length",
}


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: str
    reason_code: str
    field_path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def load_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_strategy_packet_file(
    input_path: str | Path,
    schema_path: str | Path,
) -> dict[str, Any]:
    packet = load_json_file(input_path)
    schema = load_json_file(schema_path)
    return validate_strategy_packet_payload(packet, schema)


def validate_strategy_packet_payload(
    packet: Any,
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    diagnostics: list[Diagnostic] = []

    diagnostics.extend(_collect_schema_diagnostics(packet, schema))
    if isinstance(packet, Mapping):
        diagnostics.extend(_collect_req_059_diagnostics(packet))

    ordered_diagnostics = sorted(
        diagnostics,
        key=lambda item: (item.severity, item.field_path, item.reason_code, item.message),
    )
    error_count = sum(1 for item in ordered_diagnostics if item.severity == "error")
    warning_count = sum(1 for item in ordered_diagnostics if item.severity == "warning")
    ok = error_count == 0

    return {
        "ok": ok,
        "verdict": "pass" if ok else "fail",
        "ready_for_consumption": ok,
        "diagnostics": [item.to_dict() for item in ordered_diagnostics],
        "summary": {
            "diagnostic_count": len(ordered_diagnostics),
            "error_count": error_count,
            "warning_count": warning_count,
        },
    }


def _collect_schema_diagnostics(
    packet: Any,
    schema: Mapping[str, Any],
) -> list[Diagnostic]:
    validator = Draft202012Validator(schema)
    diagnostics = []

    for error in validator.iter_errors(packet):
        field_path = _schema_error_field_path(error)
        reason_code = SCHEMA_REASON_CODES.get(error.validator, f"schema.{error.validator}")
        diagnostics.append(
            Diagnostic(
                severity="error",
                reason_code=reason_code,
                field_path=field_path,
                message=error.message,
            )
        )

    return diagnostics


def _schema_error_field_path(error: Any) -> str:
    path = list(error.absolute_path)
    if error.validator == "required":
        missing = _extract_quoted_name(error.message)
        if missing is not None:
            path.append(missing)
    elif error.validator == "additionalProperties":
        unexpected = _extract_quoted_name(error.message)
        if unexpected is not None:
            path.append(unexpected)
    return _format_field_path(path)


def _collect_req_059_diagnostics(packet: Mapping[str, Any]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    gate_policy = packet.get("gate_policy")
    if not isinstance(gate_policy, Mapping):
        return diagnostics

    quality_report = packet.get("strategy_quality_report")
    if not isinstance(quality_report, Mapping):
        return diagnostics

    citation_coverage = quality_report.get("citation_coverage")
    contradiction_status = quality_report.get("contradiction_status")
    confidence_distribution = quality_report.get("confidence_distribution")
    gate_verdicts = quality_report.get("gate_verdicts")

    if not isinstance(citation_coverage, Mapping):
        return diagnostics
    if not isinstance(contradiction_status, Mapping):
        return diagnostics
    if not isinstance(confidence_distribution, Mapping):
        return diagnostics
    if not isinstance(gate_verdicts, Mapping):
        return diagnostics

    coverage_ratio = _validate_citation_coverage(citation_coverage, diagnostics)
    unresolved_count = _validate_contradiction_status(contradiction_status, diagnostics)
    high_ratio = _validate_confidence_distribution(confidence_distribution, diagnostics)

    expected_gate_verdicts = _compute_expected_gate_verdicts(
        gate_policy=gate_policy,
        coverage_ratio=coverage_ratio,
        unresolved_count=unresolved_count,
        high_ratio=high_ratio,
        diagnostics=diagnostics,
    )
    if expected_gate_verdicts is None:
        return diagnostics

    _validate_gate_verdicts(gate_verdicts, expected_gate_verdicts, diagnostics)
    return diagnostics


def _validate_citation_coverage(
    citation_coverage: Mapping[str, Any],
    diagnostics: list[Diagnostic],
) -> float | None:
    cited_claims = citation_coverage.get("cited_claims")
    uncited_claims = citation_coverage.get("uncited_claims")
    total_claims = citation_coverage.get("total_claims")
    coverage_ratio = citation_coverage.get("coverage_ratio")

    if not _is_non_negative_int(cited_claims):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_integer",
                "strategy_quality_report.citation_coverage.cited_claims",
                "REQ-059 cited_claims must be a non-negative integer.",
            )
        )
    if not _is_non_negative_int(uncited_claims):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_integer",
                "strategy_quality_report.citation_coverage.uncited_claims",
                "REQ-059 uncited_claims must be a non-negative integer.",
            )
        )
    if not _is_non_negative_int(total_claims):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_integer",
                "strategy_quality_report.citation_coverage.total_claims",
                "REQ-059 total_claims must be a non-negative integer.",
            )
        )
    if not _is_ratio_number(coverage_ratio):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_ratio",
                "strategy_quality_report.citation_coverage.coverage_ratio",
                "REQ-059 coverage_ratio must be a numeric ratio between 0 and 1.",
            )
        )

    if not (
        _is_non_negative_int(cited_claims)
        and _is_non_negative_int(uncited_claims)
        and _is_non_negative_int(total_claims)
    ):
        return None

    expected_total = int(cited_claims) + int(uncited_claims)
    if int(total_claims) != expected_total:
        diagnostics.append(
            _diagnostic(
                "req059.total_claims_mismatch",
                "strategy_quality_report.citation_coverage.total_claims",
                f"REQ-059 total_claims must equal cited_claims + uncited_claims ({expected_total}).",
            )
        )
    if expected_total < 1:
        diagnostics.append(
            _diagnostic(
                "req059.total_claims_empty",
                "strategy_quality_report.citation_coverage.total_claims",
                "REQ-059 citation coverage must evaluate at least one claim.",
            )
        )
        return None
    if not _is_ratio_number(coverage_ratio):
        return None

    expected_ratio = round(int(cited_claims) / expected_total, 4)
    if round(float(coverage_ratio), 4) != expected_ratio:
        diagnostics.append(
            _diagnostic(
                "req059.coverage_ratio_mismatch",
                "strategy_quality_report.citation_coverage.coverage_ratio",
                f"REQ-059 coverage_ratio must equal {expected_ratio:.4f}.",
            )
        )

    return expected_ratio


def _validate_contradiction_status(
    contradiction_status: Mapping[str, Any],
    diagnostics: list[Diagnostic],
) -> int | None:
    unresolved_ids = contradiction_status.get("unresolved_contradiction_ids")
    unresolved_count = contradiction_status.get("unresolved_contradiction_count")
    has_unresolved = contradiction_status.get("has_unresolved_contradictions")

    normalized_ids = _normalize_sorted_unique_strings(unresolved_ids)
    if normalized_ids is None:
        diagnostics.append(
            _diagnostic(
                "req059.invalid_string_list",
                "strategy_quality_report.contradiction_status.unresolved_contradiction_ids",
                "REQ-059 unresolved_contradiction_ids must be a sorted unique string list.",
            )
        )
        return None
    if list(unresolved_ids) != normalized_ids:
        diagnostics.append(
            _diagnostic(
                "req059.unsorted_or_duplicate_ids",
                "strategy_quality_report.contradiction_status.unresolved_contradiction_ids",
                "REQ-059 unresolved_contradiction_ids must already be sorted and unique.",
            )
        )
        return None
    if not _is_non_negative_int(unresolved_count):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_integer",
                "strategy_quality_report.contradiction_status.unresolved_contradiction_count",
                "REQ-059 unresolved_contradiction_count must be a non-negative integer.",
            )
        )
        return None
    if not isinstance(has_unresolved, bool):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_boolean",
                "strategy_quality_report.contradiction_status.has_unresolved_contradictions",
                "REQ-059 has_unresolved_contradictions must be a boolean.",
            )
        )
        return None

    expected_count = len(normalized_ids)
    if int(unresolved_count) != expected_count:
        diagnostics.append(
            _diagnostic(
                "req059.unresolved_count_mismatch",
                "strategy_quality_report.contradiction_status.unresolved_contradiction_count",
                f"REQ-059 unresolved_contradiction_count must equal {expected_count}.",
            )
        )
    expected_has_unresolved = expected_count > 0
    if has_unresolved != expected_has_unresolved:
        diagnostics.append(
            _diagnostic(
                "req059.unresolved_flag_mismatch",
                "strategy_quality_report.contradiction_status.has_unresolved_contradictions",
                f"REQ-059 has_unresolved_contradictions must be {str(expected_has_unresolved).lower()}.",
            )
        )

    return expected_count


def _validate_confidence_distribution(
    confidence_distribution: Mapping[str, Any],
    diagnostics: list[Diagnostic],
) -> float | None:
    counts = {
        "high": confidence_distribution.get("high"),
        "medium": confidence_distribution.get("medium"),
        "low": confidence_distribution.get("low"),
    }
    total = confidence_distribution.get("total")
    ratios = {
        "high_ratio": confidence_distribution.get("high_ratio"),
        "medium_ratio": confidence_distribution.get("medium_ratio"),
        "low_ratio": confidence_distribution.get("low_ratio"),
    }

    for field_name, value in counts.items():
        if not _is_non_negative_int(value):
            diagnostics.append(
                _diagnostic(
                    "req059.invalid_integer",
                    f"strategy_quality_report.confidence_distribution.{field_name}",
                    f"REQ-059 {field_name} must be a non-negative integer.",
                )
            )
    if not _is_non_negative_int(total):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_integer",
                "strategy_quality_report.confidence_distribution.total",
                "REQ-059 confidence_distribution.total must be a non-negative integer.",
            )
        )
        return None
    for field_name, value in ratios.items():
        if not _is_ratio_number(value):
            diagnostics.append(
                _diagnostic(
                    "req059.invalid_ratio",
                    f"strategy_quality_report.confidence_distribution.{field_name}",
                    f"REQ-059 {field_name} must be a numeric ratio between 0 and 1.",
                )
            )

    if not all(_is_non_negative_int(value) for value in counts.values()):
        return None
    if not all(_is_ratio_number(value) for value in ratios.values()):
        return None

    expected_total = int(counts["high"]) + int(counts["medium"]) + int(counts["low"])
    if int(total) != expected_total:
        diagnostics.append(
            _diagnostic(
                "req059.confidence_total_mismatch",
                "strategy_quality_report.confidence_distribution.total",
                f"REQ-059 confidence_distribution.total must equal {expected_total}.",
            )
        )
    if expected_total < 1:
        diagnostics.append(
            _diagnostic(
                "req059.confidence_total_empty",
                "strategy_quality_report.confidence_distribution.total",
                "REQ-059 confidence_distribution must score at least one item.",
            )
        )
        return None

    expected_ratios = {
        "high_ratio": round(int(counts["high"]) / expected_total, 4),
        "medium_ratio": round(int(counts["medium"]) / expected_total, 4),
        "low_ratio": round(int(counts["low"]) / expected_total, 4),
    }
    for field_name, expected_value in expected_ratios.items():
        if round(float(ratios[field_name]), 4) != expected_value:
            diagnostics.append(
                _diagnostic(
                    "req059.confidence_ratio_mismatch",
                    f"strategy_quality_report.confidence_distribution.{field_name}",
                    f"REQ-059 {field_name} must equal {expected_value:.4f}.",
                )
            )

    return expected_ratios["high_ratio"]


def _compute_expected_gate_verdicts(
    gate_policy: Mapping[str, Any],
    coverage_ratio: float | None,
    unresolved_count: int | None,
    high_ratio: float | None,
    diagnostics: list[Diagnostic],
) -> dict[str, Any] | None:
    min_coverage_ratio = gate_policy.get("min_citation_coverage_ratio")
    max_unresolved = gate_policy.get("max_unresolved_contradictions")
    min_high_ratio = gate_policy.get("min_high_confidence_ratio")

    if not _is_ratio_number(min_coverage_ratio):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_ratio",
                "gate_policy.min_citation_coverage_ratio",
                "REQ-059 min_citation_coverage_ratio must be a numeric ratio between 0 and 1.",
            )
        )
    if not _is_non_negative_int(max_unresolved):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_integer",
                "gate_policy.max_unresolved_contradictions",
                "REQ-059 max_unresolved_contradictions must be a non-negative integer.",
            )
        )
    if not _is_ratio_number(min_high_ratio):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_ratio",
                "gate_policy.min_high_confidence_ratio",
                "REQ-059 min_high_confidence_ratio must be a numeric ratio between 0 and 1.",
            )
        )
    if coverage_ratio is None or unresolved_count is None or high_ratio is None:
        return None
    if not (
        _is_ratio_number(min_coverage_ratio)
        and _is_non_negative_int(max_unresolved)
        and _is_ratio_number(min_high_ratio)
    ):
        return None

    expected = {
        "citation_coverage_pass": coverage_ratio >= float(min_coverage_ratio),
        "contradiction_pass": unresolved_count <= int(max_unresolved),
        "confidence_distribution_pass": high_ratio >= float(min_high_ratio),
    }
    expected["overall_pass"] = all(expected.values())
    expected["failed_gate_ids"] = [
        gate_id
        for gate_id, key in (
            ("citation_coverage", "citation_coverage_pass"),
            ("contradiction_status", "contradiction_pass"),
            ("confidence_distribution", "confidence_distribution_pass"),
        )
        if not expected[key]
    ]
    return expected


def _validate_gate_verdicts(
    gate_verdicts: Mapping[str, Any],
    expected_gate_verdicts: Mapping[str, Any],
    diagnostics: list[Diagnostic],
) -> None:
    for field_name in (
        "citation_coverage_pass",
        "contradiction_pass",
        "confidence_distribution_pass",
        "overall_pass",
    ):
        if not isinstance(gate_verdicts.get(field_name), bool):
            diagnostics.append(
                _diagnostic(
                    "req059.invalid_boolean",
                    f"strategy_quality_report.gate_verdicts.{field_name}",
                    f"REQ-059 {field_name} must be a boolean.",
                )
            )

    failed_gate_ids = gate_verdicts.get("failed_gate_ids")
    normalized_failed_gate_ids = _normalize_sorted_unique_strings(failed_gate_ids)
    if normalized_failed_gate_ids is None:
        diagnostics.append(
            _diagnostic(
                "req059.invalid_gate_ids",
                "strategy_quality_report.gate_verdicts.failed_gate_ids",
                "REQ-059 failed_gate_ids must be a sorted unique list of known gate ids.",
            )
        )
        return
    if normalized_failed_gate_ids != list(failed_gate_ids):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_gate_ids",
                "strategy_quality_report.gate_verdicts.failed_gate_ids",
                "REQ-059 failed_gate_ids must already be sorted and unique.",
            )
        )
        return
    if any(gate_id not in GATE_IDS for gate_id in normalized_failed_gate_ids):
        diagnostics.append(
            _diagnostic(
                "req059.invalid_gate_ids",
                "strategy_quality_report.gate_verdicts.failed_gate_ids",
                "REQ-059 failed_gate_ids contains an unknown gate id.",
            )
        )
        return

    for field_name in (
        "citation_coverage_pass",
        "contradiction_pass",
        "confidence_distribution_pass",
        "overall_pass",
    ):
        actual_value = gate_verdicts.get(field_name)
        expected_value = expected_gate_verdicts[field_name]
        if isinstance(actual_value, bool) and actual_value != expected_value:
            diagnostics.append(
                _diagnostic(
                    "req059.gate_verdict_mismatch",
                    f"strategy_quality_report.gate_verdicts.{field_name}",
                    f"REQ-059 {field_name} must be {str(expected_value).lower()}.",
                )
            )

    expected_failed_gate_ids = expected_gate_verdicts["failed_gate_ids"]
    if normalized_failed_gate_ids != expected_failed_gate_ids:
        diagnostics.append(
            _diagnostic(
                "req059.failed_gate_ids_mismatch",
                "strategy_quality_report.gate_verdicts.failed_gate_ids",
                "REQ-059 failed_gate_ids must match the computed failed gate ids.",
            )
        )


def _diagnostic(reason_code: str, field_path: str, message: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        reason_code=reason_code,
        field_path=field_path,
        message=message,
    )


def _extract_quoted_name(message: str) -> str | None:
    match = re.search(r"'([^']+)'", message)
    return None if match is None else match.group(1)


def _format_field_path(path: Sequence[Any]) -> str:
    if not path:
        return "<root>"

    parts: list[str] = []
    for item in path:
        if isinstance(item, int):
            if not parts:
                parts.append(f"[{item}]")
            else:
                parts[-1] = f"{parts[-1]}[{item}]"
            continue
        parts.append(str(item))
    return ".".join(parts)


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_ratio_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= float(value) <= 1


def _normalize_sorted_unique_strings(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        if item in seen:
            return None
        seen.add(item)
        normalized.append(item)
    if normalized != sorted(normalized):
        return None
    return normalized
