#!/usr/bin/env python3
"""Deterministic strategy artifact helpers for handoff-oriented reports."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REQUIRED_RECOMMENDATION_FIELDS = (
    "recommendation_id",
    "priority",
    "summary",
    "rationale",
    "expected_impact",
    "risk_level",
)
REQUIRED_PLANNER_MAPPING_FIELDS = ("op_plan_ref", "op_initialize_ref")
PASS_STATUSES = {"resolved", "closed", "cleared", "none"}
CONFIDENCE_LEVELS = ("high", "medium", "low", "unknown")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def _unique_sorted_strings(values: Iterable[Any]) -> list[str]:
    normalized = {
        str(item).strip()
        for item in values
        if item is not None and str(item).strip()
    }
    return sorted(normalized)


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _is_present_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def _coalesce_string(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return ""


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _project_id_from_item(item: Any) -> str | None:
    if isinstance(item, dict):
        for key in ("project_id", "id", "project", "repo", "name"):
            value = item.get(key)
            if value:
                return str(value)
        return None
    if isinstance(item, str) and item.strip():
        return item.strip()
    return None


def _path_tokens(path: str) -> list[str]:
    if not isinstance(path, str):
        return []
    normalized = path.strip()
    if not normalized:
        return []
    tokens: list[str] = []
    for part in normalized.split("."):
        segment = part.strip()
        if not segment:
            return []
        while "[" in segment and segment.endswith("]"):
            prefix, _, suffix = segment.partition("[")
            if prefix:
                tokens.append(prefix)
            index_token = "[" + suffix
            if not index_token.endswith("]"):
                return []
            tokens.append(index_token)
            segment = ""
        if segment:
            tokens.append(segment)
    return tokens


def _resolve_path(payload: Any, path: str) -> tuple[bool, Any]:
    tokens = _path_tokens(path)
    if not tokens:
        return False, None
    current = payload
    for token in tokens:
        if token.startswith("[") and token.endswith("]"):
            if not isinstance(current, list):
                return False, None
            raw_index = token[1:-1]
            if not raw_index.isdigit():
                return False, None
            index = int(raw_index)
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]
            continue
        if not isinstance(current, dict) or token not in current:
            return False, None
        current = current[token]
    return True, current


def _normalize_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _coalesce(
        payload.get("recommendations"),
        _as_dict(payload.get("strategy_packet")).get("recommendations"),
        _as_dict(payload.get("strategy")).get("recommendations"),
    )
    recommendations = []
    for index, item in enumerate(_as_list(raw), start=1):
        record = _as_dict(item).copy()
        if not record:
            continue
        record.setdefault("recommendation_id", f"rec.generated-{index:03d}")
        recommendations.append(record)
    recommendations.sort(key=lambda item: item["recommendation_id"])
    return recommendations


def _build_evidence_index(payload: dict[str, Any]) -> dict[str, list[str]]:
    index: dict[str, set[str]] = {}

    candidates = []
    candidates.extend(_as_list(payload.get("evidence_provenance")))
    candidates.extend(_as_list(payload.get("source_traceability")))
    candidates.extend(_as_list(_as_dict(payload.get("context_bundle")).get("evidence_provenance")))
    candidates.extend(_as_list(_as_dict(payload.get("reasoning_trace")).get("evidence_provenance")))

    for candidate in candidates:
        record = _as_dict(candidate)
        recommendation_id = _coalesce(
            record.get("recommendation_id"),
            record.get("ref"),
            record.get("id"),
        )
        if not recommendation_id:
            continue
        refs = _unique_sorted_strings(
            _as_list(record.get("evidence_refs"))
            + _as_list(record.get("refs"))
            + _as_list(record.get("evidence"))
        )
        if refs:
            index.setdefault(str(recommendation_id), set()).update(refs)

    return {key: sorted(values) for key, values in sorted(index.items())}


def _recommendation_evidence_refs(
    recommendation: dict[str, Any],
    evidence_index: dict[str, list[str]],
) -> list[str]:
    recommendation_id = str(recommendation.get("recommendation_id", "")).strip()
    refs = _unique_sorted_strings(
        _as_list(recommendation.get("evidence_refs"))
        + _as_list(recommendation.get("evidence"))
        + _as_list(recommendation.get("source_refs"))
        + evidence_index.get(recommendation_id, [])
    )
    return refs


def _normalize_contradictions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    candidates.extend(_as_list(payload.get("contradictions")))
    candidates.extend(_as_list(_as_dict(payload.get("reasoning_trace")).get("contradictions")))

    for call in _as_list(payload.get("reasoning_calls")):
        record = _as_dict(call)
        if "contradiction_status" in record:
            candidates.append(record["contradiction_status"])

    normalized = []
    for index, item in enumerate(candidates, start=1):
        record = _as_dict(item).copy()
        if not record:
            continue
        status = str(_coalesce(record.get("status"), record.get("verdict"), "open")).strip().lower()
        contradiction_id = str(_coalesce(record.get("id"), record.get("contradiction_id"), f"contradiction-{index:03d}"))
        normalized.append(
            {
                "contradiction_id": contradiction_id,
                "status": status,
                "summary": str(_coalesce(record.get("summary"), record.get("detail"), contradiction_id)),
                "evidence_refs": _unique_sorted_strings(
                    _as_list(record.get("evidence_refs")) + _as_list(record.get("evidence"))
                ),
            }
        )

    normalized.sort(key=lambda item: item["contradiction_id"])
    return normalized


def _confidence_distribution(
    recommendations: list[dict[str, Any]],
    payload: dict[str, Any],
) -> dict[str, int]:
    counts = {level: 0 for level in CONFIDENCE_LEVELS}

    for recommendation in recommendations:
        raw = str(
            _coalesce(
                recommendation.get("confidence"),
                recommendation.get("confidence_level"),
                recommendation.get("context_confidence"),
                "unknown",
            )
        ).strip().lower()
        level = raw if raw in counts else "unknown"
        counts[level] += 1

    if sum(counts.values()) == 0:
        for item in _as_list(payload.get("context_confidence")):
            raw = str(item).strip().lower()
            counts[raw if raw in counts else "unknown"] += 1

    return counts


def _collect_projects(payload: dict[str, Any]) -> list[str]:
    project_ids: set[str] = set()
    for source in (
        payload.get("earth_sweep"),
        payload.get("broad_sweep"),
        payload.get("ecosystem_context"),
        _as_dict(payload.get("context_bundle")).get("earth_sweep"),
    ):
        for item in _as_list(_as_dict(source).get("projects")):
            project_id = _project_id_from_item(item)
            if project_id:
                project_ids.add(project_id)

    for source in (
        payload.get("cross_project_context"),
        _as_dict(payload.get("context_bundle")).get("cross_project_context"),
    ):
        for item in _as_list(source):
            project_id = _project_id_from_item(item)
            if project_id:
                project_ids.add(project_id)

    target_project_id = _coalesce(
        _as_dict(payload.get("identity")).get("project_id"),
        _as_dict(_as_dict(payload.get("strategy_packet")).get("identity")).get("project_id"),
        _as_dict(_as_dict(payload.get("strategy_output")).get("identity")).get("project_id"),
        payload.get("project_id"),
    )
    if target_project_id:
        project_ids.add(str(target_project_id))

    return sorted(project_ids)


def _collect_obligation_risks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    open_risks = []
    obligations = []
    obligations.extend(_as_list(payload.get("ecosystem_obligations")))
    obligations.extend(_as_list(payload.get("obligations")))
    obligations.extend(_as_list(_as_dict(payload.get("context_bundle")).get("ecosystem_obligations")))

    for index, item in enumerate(obligations, start=1):
        record = _as_dict(item)
        if not record:
            continue
        evidence_refs = _unique_sorted_strings(
            _as_list(record.get("evidence_refs")) + _as_list(record.get("evidence"))
        )
        if evidence_refs:
            continue
        project_id = _project_id_from_item(record) or f"project-{index:03d}"
        open_risks.append(
            {
                "risk_id": f"risk.unsupported-cross-project-obligation.{index:03d}",
                "severity": "medium",
                "category": "open_risk",
                "summary": f"Cross-project obligation for {project_id} has no Earth-sweep evidence refs.",
                "project_id": project_id,
                "recommendation": "Keep this as an open risk until Earth-sweep evidence refs exist.",
            }
        )

    open_risks.sort(key=lambda item: item["risk_id"])
    return open_risks


def build_strategy_quality_report(payload: dict[str, Any]) -> dict[str, Any]:
    recommendations = _normalize_recommendations(payload)
    evidence_index = _build_evidence_index(payload)

    recommendation_rows = []
    missing_evidence = []
    missing_fields: dict[str, list[str]] = {}
    all_evidence_refs: set[str] = set()

    for recommendation in recommendations:
        recommendation_id = recommendation["recommendation_id"]
        evidence_refs = _recommendation_evidence_refs(recommendation, evidence_index)
        missing = [
            field
            for field in REQUIRED_RECOMMENDATION_FIELDS
            if str(recommendation.get(field, "")).strip() == ""
        ]

        if not evidence_refs:
            missing_evidence.append(recommendation_id)
        if missing:
            missing_fields[recommendation_id] = missing

        all_evidence_refs.update(evidence_refs)
        recommendation_rows.append(
            {
                "recommendation_id": recommendation_id,
                "evidence_refs": evidence_refs,
                "missing_required_fields": missing,
                "confidence": str(
                    _coalesce(
                        recommendation.get("confidence"),
                        recommendation.get("confidence_level"),
                        recommendation.get("context_confidence"),
                        "unknown",
                    )
                ).strip().lower(),
            }
        )

    contradictions = _normalize_contradictions(payload)
    open_contradictions = [
        item for item in contradictions if item["status"] not in PASS_STATUSES
    ]
    for contradiction in contradictions:
        all_evidence_refs.update(contradiction["evidence_refs"])

    project_ids = _collect_projects(payload)
    target_project_id = _coalesce(
        _as_dict(payload.get("identity")).get("project_id"),
        _as_dict(_as_dict(payload.get("strategy_packet")).get("identity")).get("project_id"),
        payload.get("project_id"),
    )
    peer_project_ids = [
        project_id for project_id in project_ids if project_id != target_project_id
    ]

    open_risks = _collect_obligation_risks(payload)
    confidence_distribution = _confidence_distribution(recommendations, payload)

    citation_coverage_pass = bool(recommendations) and not missing_evidence
    contradiction_pass = not open_contradictions
    recommendation_fields_pass = not missing_fields
    cross_project_context_pass = bool(peer_project_ids)
    open_risk_blockers = [risk["risk_id"] for risk in open_risks]

    blocking_reasons = []
    if not citation_coverage_pass:
        blocking_reasons.append("missing_evidence_refs")
    if not contradiction_pass:
        blocking_reasons.append("open_contradictions")
    if not recommendation_fields_pass:
        blocking_reasons.append("incomplete_recommendations")
    if not cross_project_context_pass:
        blocking_reasons.append("missing_cross_project_context")
    if open_risk_blockers:
        blocking_reasons.append("unsupported_cross_project_obligations")

    verdict = "pass" if not blocking_reasons else "fail"

    return {
        "artifact_type": "strategy_quality_report",
        "requirement_id": "REQ-059",
        "quality_report_version": "1.0",
        "recommendations_analyzed": len(recommendations),
        "evidence_refs": sorted(all_evidence_refs),
        "citation_coverage": {
            "recommendations_total": len(recommendations),
            "recommendations_with_evidence_refs": len(recommendations) - len(missing_evidence),
            "coverage_ratio": (
                0.0
                if not recommendations
                else round((len(recommendations) - len(missing_evidence)) / len(recommendations), 4)
            ),
            "missing_recommendation_ids": sorted(missing_evidence),
        },
        "recommendation_field_completeness": {
            "required_fields": list(REQUIRED_RECOMMENDATION_FIELDS),
            "complete_recommendations": len(recommendations) - len(missing_fields),
            "incomplete_recommendations": len(missing_fields),
            "missing_by_recommendation": {
                key: value for key, value in sorted(missing_fields.items())
            },
        },
        "contradiction_status": {
            "has_open_contradictions": bool(open_contradictions),
            "open_count": len(open_contradictions),
            "resolved_count": len(contradictions) - len(open_contradictions),
            "items": contradictions,
        },
        "confidence_distribution": confidence_distribution,
        "cross_project_context": {
            "target_project_id": target_project_id,
            "project_ids": project_ids,
            "peer_project_ids": peer_project_ids,
            "project_count": len(project_ids),
            "peer_project_count": len(peer_project_ids),
            "used_in_quality_report": bool(peer_project_ids),
        },
        "recommendations": recommendation_rows,
        "open_risks": open_risks,
        "gate_verdict": {
            "verdict": verdict,
            "ready_for_build": verdict == "pass",
            "citation_coverage_pass": citation_coverage_pass,
            "contradiction_pass": contradiction_pass,
            "recommendation_fields_pass": recommendation_fields_pass,
            "cross_project_context_pass": cross_project_context_pass,
            "blocking_reasons": blocking_reasons,
            "warning_reasons": [],
        },
    }


def write_strategy_quality_report(
    payload: dict[str, Any],
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_strategy_quality_report(payload)
    if output_path is not None:
        _write_json(output_path, report)
    return report


def _normalize_required_files(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    required_files = _unique_sorted_strings(
        _as_list(
            _coalesce(
                payload.get("required_files"),
                _as_dict(payload.get("planner_consumability")).get("required_files"),
            )
        )
    )
    available_files = _unique_sorted_strings(
        _as_list(
            _coalesce(
                payload.get("available_files"),
                _as_dict(payload.get("planner_consumability")).get("available_files"),
                _as_dict(payload.get("artifacts")).get("files"),
            )
        )
    )
    return required_files, available_files


def _normalize_required_keys(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    required_keys = _unique_sorted_strings(
        _as_list(
            _coalesce(
                payload.get("required_keys"),
                _as_dict(payload.get("planner_consumability")).get("required_keys"),
            )
        )
    )
    strategy_output = _as_dict(
        _coalesce(
            payload.get("strategy_output"),
            payload.get("strategy_packet"),
            _as_dict(payload.get("planner_consumability")).get("strategy_output"),
        )
    )
    return required_keys, strategy_output


def _extract_recommendation_ids(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    recommendations = _as_list(
        _coalesce(
            _as_dict(payload.get("strategy_output")).get("recommendations"),
            _as_dict(payload.get("strategy_packet")).get("recommendations"),
            payload.get("recommendations"),
        )
    )
    recommendation_ids: set[str] = set()
    missing_ids: list[str] = []

    for index, item in enumerate(recommendations, start=1):
        recommendation = _as_dict(item)
        recommendation_id = _coalesce(
            recommendation.get("recommendation_id"),
            recommendation.get("id"),
        )
        if recommendation_id:
            recommendation_ids.add(str(recommendation_id).strip())
        else:
            missing_ids.append(f"recommendations[{index}]")

    return sorted(recommendation_ids), missing_ids


def _normalize_recommendation_mapping(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    raw_mapping = _coalesce(
        payload.get("recommendation_mapping"),
        _as_dict(payload.get("planner_consumability")).get("recommendation_mapping"),
        _as_dict(payload.get("strategy_output")).get("recommendation_mapping"),
        _as_dict(payload.get("strategy_packet")).get("recommendation_mapping"),
    )
    normalized: dict[str, dict[str, str]] = {}

    if isinstance(raw_mapping, dict):
        iterator = raw_mapping.items()
        for mapping_id, mapping_payload in iterator:
            record = _as_dict(mapping_payload)
            recommendation_id = _coalesce_string(
                record.get("recommendation_id"),
                record.get("id"),
                mapping_id,
            )
            if not recommendation_id:
                continue
            normalized[recommendation_id] = {
                "op_plan_ref": _coalesce_string(
                    record.get("op_plan_ref"),
                    record.get("op_plan"),
                    record.get("plan_ref"),
                ),
                "op_initialize_ref": _coalesce_string(
                    record.get("op_initialize_ref"),
                    record.get("op_initialize"),
                    record.get("initialize_ref"),
                ),
            }
        return normalized

    for mapping_payload in _as_list(raw_mapping):
        record = _as_dict(mapping_payload)
        recommendation_id = _coalesce_string(
            record.get("recommendation_id"),
            record.get("id"),
        )
        if not recommendation_id:
            continue
        normalized[recommendation_id] = {
            "op_plan_ref": _coalesce_string(
                record.get("op_plan_ref"),
                record.get("op_plan"),
                record.get("plan_ref"),
            ),
            "op_initialize_ref": _coalesce_string(
                record.get("op_initialize_ref"),
                record.get("op_initialize"),
                record.get("initialize_ref"),
            ),
        }
    return normalized


def build_planner_consumability_validator(payload: dict[str, Any]) -> dict[str, Any]:
    required_files, available_files = _normalize_required_files(payload)
    missing_required_files = [
        path for path in required_files if path not in set(available_files)
    ]
    required_files_pass = bool(required_files) and not missing_required_files

    required_keys, strategy_output = _normalize_required_keys(payload)
    missing_required_keys: list[str] = []
    empty_required_keys: list[str] = []
    for key_path in required_keys:
        found, value = _resolve_path(strategy_output, key_path)
        if not found:
            missing_required_keys.append(key_path)
            continue
        if not _is_present_value(value):
            empty_required_keys.append(key_path)

    required_keys_pass = (
        bool(required_keys)
        and not missing_required_keys
        and not empty_required_keys
    )

    recommendation_ids, recommendations_missing_id = _extract_recommendation_ids(payload)
    recommendation_mapping = _normalize_recommendation_mapping(payload)
    mapped_recommendation_ids = sorted(recommendation_mapping)
    missing_mapping_ids = [
        recommendation_id
        for recommendation_id in recommendation_ids
        if recommendation_id not in recommendation_mapping
    ]
    incomplete_mappings = []
    for recommendation_id in recommendation_ids:
        mapping = recommendation_mapping.get(recommendation_id)
        if not mapping:
            continue
        missing_fields = [
            field
            for field in REQUIRED_PLANNER_MAPPING_FIELDS
            if not _is_present_value(mapping.get(field))
        ]
        if missing_fields:
            incomplete_mappings.append(
                {
                    "recommendation_id": recommendation_id,
                    "missing_fields": missing_fields,
                }
            )
    incomplete_mappings.sort(key=lambda item: item["recommendation_id"])
    recommendation_mapping_pass = (
        bool(recommendation_ids)
        and not missing_mapping_ids
        and not recommendations_missing_id
        and not incomplete_mappings
    )

    evidence_index = _build_evidence_index(payload)
    recommendation_items = _as_list(
        _coalesce(
            _as_dict(strategy_output).get("recommendations"),
            _as_dict(payload.get("strategy_packet")).get("recommendations"),
            payload.get("recommendations"),
        )
    )

    recommendation_rows: list[dict[str, Any]] = []
    missing_evidence_ids: list[str] = []
    missing_fields: dict[str, list[str]] = {}
    all_evidence_refs: set[str] = set()
    for index, raw_recommendation in enumerate(recommendation_items, start=1):
        recommendation = _as_dict(raw_recommendation)
        recommendation_id = _coalesce_string(
            recommendation.get("recommendation_id"),
            recommendation.get("id"),
        )
        recommendation_ref = recommendation_id or f"recommendations[{index}]"
        evidence_refs = _recommendation_evidence_refs(recommendation, evidence_index)
        required_field_gaps = [
            field
            for field in REQUIRED_RECOMMENDATION_FIELDS
            if not _is_present_value(recommendation.get(field))
        ]
        if not evidence_refs:
            missing_evidence_ids.append(recommendation_ref)
        if required_field_gaps:
            missing_fields[recommendation_ref] = required_field_gaps

        all_evidence_refs.update(evidence_refs)
        recommendation_rows.append(
            {
                "recommendation_ref": recommendation_ref,
                "recommendation_id": recommendation_id,
                "evidence_refs": evidence_refs,
                "missing_required_fields": required_field_gaps,
            }
        )

    recommendation_rows.sort(key=lambda item: item["recommendation_ref"])
    recommendations_total = len(recommendation_rows)
    recommendations_with_evidence = recommendations_total - len(missing_evidence_ids)
    coverage_ratio = (
        0.0
        if recommendations_total == 0
        else round(recommendations_with_evidence / recommendations_total, 4)
    )
    citation_coverage_pass = recommendations_total > 0 and not missing_evidence_ids
    recommendation_fields_pass = not missing_fields

    target_project_id = _coalesce(
        _as_dict(payload.get("identity")).get("project_id"),
        _as_dict(strategy_output.get("identity")).get("project_id"),
        _as_dict(_as_dict(payload.get("strategy_packet")).get("identity")).get("project_id"),
        payload.get("project_id"),
    )
    project_ids = _collect_projects(payload)
    if target_project_id and target_project_id not in project_ids:
        project_ids = sorted(project_ids + [str(target_project_id)])
    peer_project_ids = [project_id for project_id in project_ids if project_id != target_project_id]
    used_cross_project_context = bool(peer_project_ids)

    open_risks = _collect_obligation_risks(payload)

    blocking_reasons = []
    if not required_files_pass:
        blocking_reasons.append("required_files_check_failed")
    if not required_keys_pass:
        blocking_reasons.append("required_keys_check_failed")
    if not recommendation_mapping_pass:
        blocking_reasons.append("recommendation_mapping_check_failed")

    verdict = "pass" if not blocking_reasons else "fail"
    return {
        "artifact_type": "planner_consumability_validator",
        "requirement_id": "REQ-065",
        "validator_version": "1.0",
        "planner_targets": ["op-plan", "op-initialize"],
        "evidence_refs": sorted(all_evidence_refs),
        "citation_coverage": {
            "recommendations_total": recommendations_total,
            "recommendations_with_evidence_refs": recommendations_with_evidence,
            "coverage_ratio": coverage_ratio,
            "missing_recommendation_ids": sorted(missing_evidence_ids),
            "pass": citation_coverage_pass,
        },
        "recommendation_field_completeness": {
            "required_fields": list(REQUIRED_RECOMMENDATION_FIELDS),
            "complete_recommendations": recommendations_total - len(missing_fields),
            "incomplete_recommendations": len(missing_fields),
            "missing_by_recommendation": {key: value for key, value in sorted(missing_fields.items())},
            "pass": recommendation_fields_pass,
        },
        "cross_project_context": {
            "target_project_id": target_project_id,
            "project_ids": project_ids,
            "peer_project_ids": peer_project_ids,
            "project_count": len(project_ids),
            "peer_project_count": len(peer_project_ids),
            "used_in_validator": used_cross_project_context,
            "pass": used_cross_project_context,
        },
        "recommendations": recommendation_rows,
        "open_risks": open_risks,
        "checks": {
            "required_files": {
                "required_files": required_files,
                "available_files": available_files,
                "missing_required_files": missing_required_files,
                "pass": required_files_pass,
            },
            "required_keys": {
                "required_keys": required_keys,
                "missing_required_keys": missing_required_keys,
                "empty_required_keys": empty_required_keys,
                "pass": required_keys_pass,
            },
            "recommendation_mapping": {
                "recommendation_ids": recommendation_ids,
                "recommendations_missing_id": recommendations_missing_id,
                "mapped_recommendation_ids": mapped_recommendation_ids,
                "missing_mapping_ids": missing_mapping_ids,
                "incomplete_mappings": incomplete_mappings,
                "required_mapping_fields": list(REQUIRED_PLANNER_MAPPING_FIELDS),
                "pass": recommendation_mapping_pass,
            },
        },
        "gate_verdict": {
            "verdict": verdict,
            "ready_for_planner_consumption": verdict == "pass",
            "blocking_reasons": blocking_reasons,
            "warning_reasons": [],
        },
    }


def write_planner_consumability_validator(
    payload: dict[str, Any],
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_planner_consumability_validator(payload)
    if output_path is not None:
        _write_json(output_path, report)
    return report


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _print_status(message: str) -> None:
    print(f"[{_timestamp()}] {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic strategy quality reports.")
    parser.add_argument("--input", required=True, help="Path to JSON payload used to build the report.")
    parser.add_argument(
        "--output",
        help="Optional output path. When omitted, the report is printed to stdout.",
    )
    args = parser.parse_args(argv)

    _print_status(f"Loading strategy quality-report input from {args.input}.")
    payload = _load_json(args.input)
    report = write_strategy_quality_report(payload, args.output)

    if args.output:
        _print_status(f"Wrote strategy quality report to {args.output}.")
    else:
        _print_status("Printing strategy quality report to stdout.")
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
