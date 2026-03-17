#!/usr/bin/env python3
"""REQ-020 compatibility surface for risk signal normalization."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

RUNTIME_MODE = "llm-first"
EXECUTION_MODE = "long-thinking"

REQ_020_SCHEMA_VERSION = "req-020.risk-signal-normalization.v1"
REQ_020_REQUIREMENT_ID = "REQ-020"
REQ_020_TOOL = "strategy-context-sweep"
REQ_020_TOOL_VERSION = "1.0.0"
REQ_020_FALLBACK_NORMALIZED_AT_UTC = "1970-01-01T00:00:00Z"

REQ_020_DEFAULT_TARGET_PROJECT_ROOT = "/workspace/projects/optimus-prime"
REQ_020_DEFAULT_EARTH_ROOT = "/workspace/projects/Earth"
REQ_020_DEFAULT_OUTPUT_ROOT = "/workspace/projects/optimus-prime/strategy/out"
REQ_020_DEFAULT_REVISION_ID = "rev-req020-compat"

REQ_020_ALLOWED_SIGNAL_KINDS = {"blocker", "retry", "watchdog-exit", "regression-pattern"}
REQ_020_ALLOWED_DECISIONS = {"proceed", "proceed-with-caution", "pause"}
REQ_020_ALLOWED_CONFIDENCE_LABELS = {"low", "medium", "high"}
REQ_020_ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}

REQ_020_LEGACY_ALLOWED_SOURCES = {
    "blocker",
    "retry",
    "watchdog_exit",
    "regression_pattern",
}
REQ_020_SOURCE_ALIASES = {
    "blocker": "blocker",
    "blockers": "blocker",
    "retry": "retry",
    "retries": "retry",
    "watchdog_exit": "watchdog_exit",
    "watchdog-exit": "watchdog_exit",
    "watchdog": "watchdog_exit",
    "regression_pattern": "regression_pattern",
    "regression-pattern": "regression_pattern",
    "regression": "regression_pattern",
}
REQ_020_ANALYSIS_ANCHORS = [
    "blockers",
    "retries",
    "watchdog_exits",
    "regression_patterns",
]
REQ_020_ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
REQ_020_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
REQ_020_DEFAULT_REASON_CODE_BY_SOURCE = {
    "blocker": "task_blocked",
    "retry": "retry_limit_reached",
    "watchdog_exit": "stale_base_branch_commit",
    "regression_pattern": "regression_detected",
}
REQ_020_REASON_CODE_ALIASES = {
    "blocker_detected": "task_blocked",
    "blocking_issue_detected": "task_blocked",
    "retry_exhausted": "retry_limit_reached",
    "retry_budget_exhausted": "retry_limit_reached",
    "watchdog_timeout": "stale_base_branch_commit",
    "watchdog_terminal_exit": "stale_run_base_hard_limit",
    "regression_pattern_detected": "regression_detected",
}


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _normalize_root(raw_path: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_nonempty_text(raw_path, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


def _canonical_call_input(
    *,
    target_project_root: str,
    earth_root: str,
    output_root: str,
    revision_identity: str,
) -> dict[str, str]:
    return {
        "earth_root": earth_root,
        "execution_mode": EXECUTION_MODE,
        "output_root": output_root,
        "revision_identity": revision_identity,
        "runtime_mode": RUNTIME_MODE,
        "target_project_root": target_project_root,
    }


def _canonical_input_digest(canonical_input: Mapping[str, Any]) -> str:
    raw = json.dumps(canonical_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_string_list(raw_value: Any, *, field_name: str) -> list[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: set[str] = set()
    for index, item in enumerate(raw_value):
        text = _require_nonempty_text(item, field_name=f"{field_name}[{index}]")
        normalized.add(text)
    return sorted(normalized)


def _normalize_context_note(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return ""
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    return raw_value.strip()


def _stable_id_fragment(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _normalize_cross_project_context(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("cross_project_context must be a list")

    normalized: list[dict[str, Any]] = []
    seen_project_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"cross_project_context[{index}] must be an object")
        project_id = _require_nonempty_text(item.get("project_id"), field_name=f"cross_project_context[{index}].project_id")
        if project_id in seen_project_ids:
            raise ValueError(f"cross_project_context[{index}].project_id must be unique")
        seen_project_ids.add(project_id)
        project_root = _normalize_root(
            item.get("project_root", REQ_020_DEFAULT_EARTH_ROOT),
            field_name=f"cross_project_context[{index}].project_root",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"cross_project_context[{index}].evidence_refs",
        )
        context_note = _normalize_context_note(item.get("context_note"), field_name=f"cross_project_context[{index}].context_note")
        normalized.append(
            {
                "project_id": project_id,
                "project_root": project_root,
                "evidence_refs": evidence_refs,
                "context_note": context_note,
            }
        )

    normalized.sort(key=lambda row: (row["project_id"], row["project_root"]))
    return normalized


def _collect_unique_refs(*ref_groups: Any) -> list[str]:
    seen: set[str] = set()
    for refs in ref_groups:
        if isinstance(refs, list):
            iterable = refs
        elif isinstance(refs, tuple):
            iterable = refs
        else:
            iterable = [refs]
        for raw_ref in iterable:
            ref = _as_text(raw_ref)
            if ref:
                seen.add(ref)
    return sorted(seen)


def _parse_utc_iso(raw_value: Any, *, field_name: str) -> datetime:
    text = _require_nonempty_text(raw_value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp: {exc}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _format_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_req_020_timestamp(raw_value: Any, *, field_name: str, allow_empty: bool) -> str:
    if raw_value is None:
        if allow_empty:
            return ""
        raise ValueError(f"{field_name} must be provided")
    if allow_empty and isinstance(raw_value, str) and not raw_value.strip():
        return ""
    return _format_utc_iso(_parse_utc_iso(raw_value, field_name=field_name))


def _coerce_nonneg_int(raw_value: Any, *, field_name: str) -> int:
    if raw_value is None:
        return 0
    if isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    if isinstance(raw_value, int):
        if raw_value < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")
        return raw_value
    if isinstance(raw_value, float):
        if raw_value < 0 or not raw_value.is_integer():
            raise ValueError(f"{field_name} must be a non-negative integer")
        return int(raw_value)
    raise ValueError(f"{field_name} must be a non-negative integer")


def _normalize_legacy_source(raw_value: Any, *, field_name: str) -> str:
    source = _require_nonempty_text(raw_value, field_name=field_name).strip().lower().replace("-", "_")
    source = REQ_020_SOURCE_ALIASES.get(source, source)
    if source not in REQ_020_LEGACY_ALLOWED_SOURCES:
        raise ValueError(f"{field_name} must be one of: {sorted(REQ_020_LEGACY_ALLOWED_SOURCES)}")
    return source


def _normalize_legacy_reason_code(
    raw_value: Any,
    *,
    field_name: str,
    signal_source: str,
) -> tuple[str, str]:
    if raw_value is None:
        default_reason = REQ_020_DEFAULT_REASON_CODE_BY_SOURCE[signal_source]
        return default_reason, default_reason
    source_reason_code = _require_nonempty_text(raw_value, field_name=field_name).lower().replace("-", "_")
    normalized_reason_code = REQ_020_REASON_CODE_ALIASES.get(source_reason_code, source_reason_code)
    return normalized_reason_code, source_reason_code


def _normalize_legacy_severity(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return "medium"
    severity = _require_nonempty_text(raw_value, field_name=field_name).strip().lower()
    if severity not in REQ_020_ALLOWED_SEVERITIES:
        raise ValueError(f"{field_name} must be one of: {sorted(REQ_020_ALLOWED_SEVERITIES)}")
    return severity


def _normalize_legacy_occurrence_count(raw_value: Any, *, field_name: str) -> int:
    if raw_value is None:
        return 1
    if isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be a positive integer")
    if isinstance(raw_value, int):
        if raw_value <= 0:
            raise ValueError(f"{field_name} must be a positive integer")
        return raw_value
    if isinstance(raw_value, float):
        if raw_value <= 0 or not raw_value.is_integer():
            raise ValueError(f"{field_name} must be a positive integer")
        return int(raw_value)
    raise ValueError(f"{field_name} must be a positive integer")


def _normalize_legacy_signal_rows(raw_value: Any) -> list[dict[str, Any]]:
    if raw_value is None:
        raise ValueError("risk_signals must be a list")
    if not isinstance(raw_value, list):
        raise ValueError("risk_signals must be a list")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value):
        if not isinstance(item, Mapping):
            raise ValueError(f"risk_signals[{index}] must be an object")
        signal_source = _normalize_legacy_source(
            item.get("signal_source"),
            field_name=f"risk_signals[{index}].signal_source",
        )
        reason_code, source_reason_code = _normalize_legacy_reason_code(
            item.get("reason_code"),
            field_name=f"risk_signals[{index}].reason_code",
            signal_source=signal_source,
        )
        explicit_source_reason_code = item.get("source_reason_code")
        if explicit_source_reason_code is not None:
            source_reason_code = _require_nonempty_text(
                explicit_source_reason_code,
                field_name=f"risk_signals[{index}].source_reason_code",
            ).lower().replace("-", "_")
        summary = _require_nonempty_text(item.get("summary"), field_name=f"risk_signals[{index}].summary")
        severity = _normalize_legacy_severity(item.get("severity"), field_name=f"risk_signals[{index}].severity")
        occurrence_count = _normalize_legacy_occurrence_count(
            item.get("occurrence_count"),
            field_name=f"risk_signals[{index}].occurrence_count",
        )
        evidence_refs = _normalize_string_list(
            item.get("evidence_refs"),
            field_name=f"risk_signals[{index}].evidence_refs",
        )
        first_observed_at_utc = _normalize_req_020_timestamp(
            item.get("first_observed_at_utc"),
            field_name=f"risk_signals[{index}].first_observed_at_utc",
            allow_empty=True,
        )
        last_observed_at_utc = _normalize_req_020_timestamp(
            item.get("last_observed_at_utc"),
            field_name=f"risk_signals[{index}].last_observed_at_utc",
            allow_empty=True,
        )
        if first_observed_at_utc and last_observed_at_utc and first_observed_at_utc > last_observed_at_utc:
            raise ValueError(f"risk_signals[{index}] first_observed_at_utc must be <= last_observed_at_utc")

        normalized.append(
            {
                "signal_source": signal_source,
                "reason_code": reason_code,
                "source_reason_code": source_reason_code,
                "summary": summary,
                "severity": severity,
                "occurrence_count": occurrence_count,
                "evidence_refs": evidence_refs,
                "first_observed_at_utc": first_observed_at_utc,
                "last_observed_at_utc": last_observed_at_utc,
            }
        )

    if not normalized:
        raise ValueError("risk_signals must contain at least one signal")

    normalized.sort(
        key=lambda row: (
            row["signal_source"],
            row["reason_code"],
            row["summary"],
            row["severity"],
            row["occurrence_count"],
            row["first_observed_at_utc"],
            row["last_observed_at_utc"],
            tuple(row["evidence_refs"]),
        )
    )
    return normalized


def _select_req_020_earliest(*timestamps: str) -> str:
    values = [value for value in timestamps if value]
    if not values:
        return ""
    return min(values)


def _select_req_020_latest(*timestamps: str) -> str:
    values = [value for value in timestamps if value]
    if not values:
        return ""
    return max(values)


def _build_legacy_aggregate_signals(
    normalized_input_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    alias_pairs: set[tuple[str, str]] = set()
    for row in normalized_input_rows:
        key = (row["signal_source"], row["reason_code"], row["summary"])
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = {
                "signal_source": row["signal_source"],
                "reason_code": row["reason_code"],
                "summary": row["summary"],
                "severity": row["severity"],
                "occurrence_count": row["occurrence_count"],
                "evidence_refs": set(row["evidence_refs"]),
                "first_observed_at_utc": row["first_observed_at_utc"],
                "last_observed_at_utc": row["last_observed_at_utc"],
                "source_reason_codes": {row["source_reason_code"]},
            }
        else:
            if REQ_020_SEVERITY_ORDER[row["severity"]] > REQ_020_SEVERITY_ORDER[existing["severity"]]:
                existing["severity"] = row["severity"]
            existing["occurrence_count"] += row["occurrence_count"]
            existing["evidence_refs"].update(row["evidence_refs"])
            existing["first_observed_at_utc"] = _select_req_020_earliest(
                existing["first_observed_at_utc"],
                row["first_observed_at_utc"],
            )
            existing["last_observed_at_utc"] = _select_req_020_latest(
                existing["last_observed_at_utc"],
                row["last_observed_at_utc"],
            )
            existing["source_reason_codes"].add(row["source_reason_code"])

        if row["source_reason_code"] != row["reason_code"]:
            alias_pairs.add((row["source_reason_code"], row["reason_code"]))

    normalized_signals: list[dict[str, Any]] = []
    for signal_source, reason_code, summary in sorted(by_key.keys()):
        aggregate = by_key[(signal_source, reason_code, summary)]
        normalized_signals.append(
            {
                "normalized_signal_id": f"risk-signal.{_stable_id_fragment(signal_source, reason_code, summary)}",
                "signal_source": signal_source,
                "reason_code": reason_code,
                "source_reason_codes": sorted(aggregate["source_reason_codes"]),
                "summary": summary,
                "severity": aggregate["severity"],
                "occurrence_count": aggregate["occurrence_count"],
                "evidence_refs": sorted(aggregate["evidence_refs"]),
                "first_observed_at_utc": aggregate["first_observed_at_utc"],
                "last_observed_at_utc": aggregate["last_observed_at_utc"],
            }
        )

    alias_rows = [
        {
            "source_reason_code": source_reason_code,
            "normalized_reason_code": normalized_reason_code,
        }
        for source_reason_code, normalized_reason_code in sorted(alias_pairs)
    ]
    return normalized_signals, alias_rows


def _build_legacy_summary(normalized_signals: list[dict[str, Any]], total_input_signals: int) -> dict[str, Any]:
    source_counts = {source: 0 for source in sorted(REQ_020_LEGACY_ALLOWED_SOURCES)}
    severity_counts = {severity: 0 for severity in sorted(REQ_020_ALLOWED_SEVERITIES)}
    for row in normalized_signals:
        source_counts[row["signal_source"]] += 1
        severity_counts[row["severity"]] += 1
    return {
        "total_input_signals": total_input_signals,
        "total_normalized_signals": len(normalized_signals),
        "source_counts": source_counts,
        "severity_counts": severity_counts,
    }


def _derive_legacy_normalized_at_utc(normalized_input_rows: list[dict[str, Any]]) -> str:
    observed_timestamps = [
        timestamp
        for row in normalized_input_rows
        for timestamp in (row["first_observed_at_utc"], row["last_observed_at_utc"])
        if timestamp
    ]
    if observed_timestamps:
        return max(observed_timestamps)
    return REQ_020_FALLBACK_NORMALIZED_AT_UTC


def _legacy_bucket_for_signal_kind(signal_kind: str) -> str:
    return {
        "blocker": "blockers",
        "retry": "retries",
        "watchdog-exit": "watchdog_exits",
        "regression-pattern": "regression_patterns",
    }[signal_kind]


def _legacy_source_for_signal_kind(signal_kind: str) -> str:
    return {
        "blocker": "blocker",
        "retry": "retry",
        "watchdog-exit": "watchdog_exit",
        "regression-pattern": "regression_pattern",
    }[signal_kind]


def _normalize_req_020_risk_level(raw_value: Any, *, field_name: str) -> str:
    if raw_value is None:
        return ""
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    risk_level = raw_value.strip().lower()
    if not risk_level:
        return ""
    if risk_level not in REQ_020_ALLOWED_RISK_LEVELS:
        raise ValueError(f"{field_name} must be one of: {sorted(REQ_020_ALLOWED_RISK_LEVELS)}")
    return risk_level


def _req_020_default_risk_level(*, signal_kind: str, retry_count: int, max_retries: int, watchdog_triggered: bool) -> str:
    if signal_kind == "watchdog-exit":
        return "critical" if watchdog_triggered else "high"
    if signal_kind == "regression-pattern":
        return "high"
    if signal_kind == "retry":
        if max_retries > 0 and retry_count >= max_retries:
            return "high"
        return "medium" if retry_count > 0 else "low"
    if signal_kind == "blocker":
        return "medium"
    return "low"


def _normalize_req_020_risk_sources(raw_value: Any) -> dict[str, Any]:
    if raw_value is None:
        raw_value = {}
    if not isinstance(raw_value, Mapping):
        raise ValueError("risk_sources must be an object")

    blockers_raw = raw_value.get("blockers")
    retries_raw = raw_value.get("retries")
    watchdog_raw = raw_value.get("watchdog_exits")
    regressions_raw = raw_value.get("regression_patterns")

    def _normalize_rows(raw_rows: Any, *, kind: str, field_name: str) -> list[dict[str, Any]]:
        if raw_rows is None:
            return []
        if not isinstance(raw_rows, list):
            raise ValueError(f"{field_name} must be a list")
        out: list[dict[str, Any]] = []
        for index, item in enumerate(raw_rows):
            if not isinstance(item, Mapping):
                raise ValueError(f"{field_name}[{index}] must be an object")
            signal_ref = _require_nonempty_text(item.get("signal_ref"), field_name=f"{field_name}[{index}].signal_ref")
            summary = _normalize_context_note(item.get("summary"), field_name=f"{field_name}[{index}].summary")
            project_id = _normalize_context_note(item.get("project_id"), field_name=f"{field_name}[{index}].project_id")
            reason_codes = _normalize_string_list(item.get("reason_codes"), field_name=f"{field_name}[{index}].reason_codes")
            evidence_refs = _normalize_string_list(item.get("evidence_refs"), field_name=f"{field_name}[{index}].evidence_refs")
            detected_at_utc = item.get("detected_at_utc")
            normalized_detected_at = ""
            if detected_at_utc is not None and _as_text(detected_at_utc):
                normalized_detected_at = _format_utc_iso(
                    _parse_utc_iso(detected_at_utc, field_name=f"{field_name}[{index}].detected_at_utc")
                )

            details: dict[str, Any] = {}
            if kind == "retry":
                retry_count = _coerce_nonneg_int(item.get("retry_count"), field_name=f"{field_name}[{index}].retry_count")
                max_retries = _coerce_nonneg_int(item.get("max_retries"), field_name=f"{field_name}[{index}].max_retries")
                details["retry_count"] = retry_count
                details["max_retries"] = max_retries
            elif kind == "watchdog-exit":
                watchdog_kind = _require_nonempty_text(
                    item.get("watchdog_kind"),
                    field_name=f"{field_name}[{index}].watchdog_kind",
                )
                details["watchdog_kind"] = watchdog_kind
                details["triggered"] = bool(item.get("triggered"))
                details["consecutive_no_progress_cycles"] = _coerce_nonneg_int(
                    item.get("consecutive_no_progress_cycles"),
                    field_name=f"{field_name}[{index}].consecutive_no_progress_cycles",
                )
                details["threshold_cycles"] = _coerce_nonneg_int(
                    item.get("threshold_cycles"),
                    field_name=f"{field_name}[{index}].threshold_cycles",
                )
            elif kind == "regression-pattern":
                details["failing_checks"] = _normalize_string_list(
                    item.get("failing_checks"),
                    field_name=f"{field_name}[{index}].failing_checks",
                )

            risk_level = _normalize_req_020_risk_level(item.get("risk_level"), field_name=f"{field_name}[{index}].risk_level")
            if not risk_level:
                retry_count = int(details.get("retry_count", 0) or 0)
                max_retries = int(details.get("max_retries", 0) or 0)
                watchdog_triggered = bool(details.get("triggered", False))
                risk_level = _req_020_default_risk_level(
                    signal_kind=kind,
                    retry_count=retry_count,
                    max_retries=max_retries,
                    watchdog_triggered=watchdog_triggered,
                )

            out.append(
                {
                    "signal_ref": signal_ref,
                    "signal_kind": kind,
                    "project_id": project_id,
                    "summary": summary or f"Risk signal '{signal_ref}' ({kind}).",
                    "risk_level": risk_level,
                    "reason_codes": reason_codes,
                    "evidence_refs": evidence_refs,
                    "detected_at_utc": normalized_detected_at,
                    "details": details,
                }
            )

        out.sort(key=lambda row: (row["signal_kind"], row["signal_ref"]))
        return out

    return {
        "blockers": _normalize_rows(blockers_raw, kind="blocker", field_name="risk_sources.blockers"),
        "retries": _normalize_rows(retries_raw, kind="retry", field_name="risk_sources.retries"),
        "watchdog_exits": _normalize_rows(watchdog_raw, kind="watchdog-exit", field_name="risk_sources.watchdog_exits"),
        "regression_patterns": _normalize_rows(regressions_raw, kind="regression-pattern", field_name="risk_sources.regression_patterns"),
    }


def _req_020_risk_level_rank(risk_level: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(risk_level, 99)


def _canonical_req_020_processing_input(
    *,
    input_variant: str,
    normalized_at_utc: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    risk_sources: dict[str, Any],
    legacy_risk_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "input_variant": input_variant,
        "normalized_at_utc": normalized_at_utc,
        "target_project_evidence_refs": target_project_evidence_refs,
        "earth_sweep_evidence_refs": earth_sweep_evidence_refs,
        "cross_project_context": cross_project_context,
        "risk_sources": risk_sources,
        "legacy_risk_signals": legacy_risk_signals,
    }


def _build_req_020_processing_behavior(
    *,
    target_project_root: str,
    earth_root: str,
    normalized_at_utc: str,
    target_project_evidence_refs: list[str],
    earth_sweep_evidence_refs: list[str],
    cross_project_context: list[dict[str, Any]],
    risk_sources: dict[str, Any],
    normalized_risk_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    cross_project_project_ids = sorted({row["project_id"] for row in cross_project_context})
    cross_project_project_set = set(cross_project_project_ids)

    used_cross_project_refs: list[str] = []
    used_cross_project_projects: set[str] = set()
    for signal in normalized_risk_signals:
        project_id = str(signal.get("project_id") or "").strip()
        if project_id and project_id in cross_project_project_set:
            used_cross_project_projects.add(project_id)
            used_cross_project_refs.extend(list(signal.get("linked_cross_project_evidence_refs") or []))

    used_cross_project_refs = sorted({ref for ref in used_cross_project_refs if ref})
    evidence_refs_used = _collect_unique_refs(
        target_project_evidence_refs,
        earth_sweep_evidence_refs,
        used_cross_project_refs,
        *[row["evidence_refs"] for row in normalized_risk_signals],
    )

    open_risks: list[dict[str, Any]] = []
    for signal in normalized_risk_signals:
        project_id = str(signal.get("project_id") or "").strip()
        if not project_id or project_id not in cross_project_project_set:
            continue
        if earth_sweep_evidence_refs:
            continue
        required_refs = _collect_unique_refs(
            list(signal.get("evidence_refs") or []),
            list(signal.get("linked_cross_project_evidence_refs") or []),
        )
        open_risks.append(
            {
                "risk_id": f"risk-cross-project-{_stable_id_fragment(project_id, str(signal.get('risk_signal_id') or ''))}",
                "summary": f"Cross-project risk signal for '{project_id}' requires Earth-sweep evidence refs before obligations can be committed.",
                "reason_code": "missing_earth_sweep_evidence_refs",
                "required_evidence_refs": required_refs,
            }
        )

    open_risks.sort(key=lambda row: row["risk_id"])

    highest_rank = min((_req_020_risk_level_rank(row["risk_level"]) for row in normalized_risk_signals), default=99)
    if highest_rank <= _req_020_risk_level_rank("critical"):
        decision = "pause"
    elif highest_rank <= _req_020_risk_level_rank("high"):
        decision = "proceed-with-caution"
    else:
        decision = "proceed"

    counts: dict[str, int] = {level: 0 for level in sorted(REQ_020_ALLOWED_RISK_LEVELS)}
    for row in normalized_risk_signals:
        level = row.get("risk_level")
        if isinstance(level, str) and level in counts:
            counts[level] += 1

    if decision == "pause":
        rationale = "Critical risk signals detected; remediate before proceeding with strategy execution."
    elif decision == "proceed-with-caution":
        rationale = "High-severity risk signals detected; proceed only with explicit mitigation and monitoring."
    else:
        rationale = "No high-severity risk signals detected in the provided context sweep inputs."

    confidence = "low"
    if evidence_refs_used:
        confidence = "high" if not open_risks else "medium"

    recommended_actions: list[dict[str, Any]] = []
    for signal in normalized_risk_signals:
        if _req_020_risk_level_rank(signal["risk_level"]) > _req_020_risk_level_rank("high"):
            continue
        action_scope = "cross-project" if str(signal.get("project_id") or "").strip() else "local"
        action_id = f"mitigate-{signal['signal_kind']}-{_stable_id_fragment(signal['risk_signal_id'])}"
        recommended_actions.append(
            {
                "action_id": action_id,
                "summary": f"Mitigate {signal['risk_level']} risk: {signal['summary']}",
                "rationale": "Risk signal normalization surfaced a high-severity risk that can affect strategy execution reliability.",
                "action_scope": action_scope,
                "next_step": "Add a concrete remediation task, attach evidence refs, and rerun the relevant sweep/test to confirm risk reduction.",
                "evidence_refs": list(signal.get("evidence_refs") or []),
            }
        )

    recommended_actions.sort(key=lambda row: row["action_id"])

    return {
        "strategy": "risk-signal-normalization-broad-sweep",
        "reasoning_mode": EXECUTION_MODE,
        "heuristic_summarization_only": False,
        "context_inputs": {
            "normalized_at_utc": normalized_at_utc,
            "target_project": {
                "project_root": target_project_root,
                "evidence_refs": target_project_evidence_refs,
            },
            "earth_sweep": {
                "earth_root": earth_root,
                "evidence_refs": earth_sweep_evidence_refs,
            },
            "cross_project_context": cross_project_context,
            "risk_sources": risk_sources,
        },
        "context_usage": {
            "target_project_context_used": bool(target_project_evidence_refs),
            "earth_sweep_context_used": bool(earth_sweep_evidence_refs),
            "cross_project_context_used": bool(used_cross_project_projects) or bool(cross_project_context),
            "target_project_refs_used": target_project_evidence_refs,
            "earth_sweep_refs_used": earth_sweep_evidence_refs,
            "cross_project_refs_used": used_cross_project_refs,
            "cross_project_projects_considered": cross_project_project_ids,
            "cross_project_projects_used": sorted(used_cross_project_projects),
            "evidence_refs_used": evidence_refs_used,
        },
        "recommendation": {
            "decision": decision,
            "rationale": f"{rationale} Risk counts: {counts}.",
            "confidence": confidence,
            "evidence_refs": evidence_refs_used,
            "recommended_actions": recommended_actions,
            "cross_project_obligations": [],
            "open_risks": open_risks,
        },
    }


def _normalize_legacy_input_to_rich_sources(normalized_input_rows: list[dict[str, Any]]) -> dict[str, Any]:
    risk_sources: dict[str, list[dict[str, Any]]] = {
        "blockers": [],
        "retries": [],
        "watchdog_exits": [],
        "regression_patterns": [],
    }
    for row in normalized_input_rows:
        legacy_source = row["signal_source"]
        signal_kind = {
            "blocker": "blocker",
            "retry": "retry",
            "watchdog_exit": "watchdog-exit",
            "regression_pattern": "regression-pattern",
        }[legacy_source]
        signal_ref = f"{signal_kind}.{_stable_id_fragment(legacy_source, row['reason_code'], row['summary'])}"
        entry: dict[str, Any] = {
            "signal_ref": signal_ref,
            "project_id": "",
            "summary": row["summary"],
            "risk_level": row["severity"],
            "reason_codes": [row["reason_code"]],
            "evidence_refs": list(row["evidence_refs"]),
            "detected_at_utc": row["last_observed_at_utc"] or row["first_observed_at_utc"] or "",
        }
        if signal_kind == "retry":
            entry["retry_count"] = row["occurrence_count"]
            entry["max_retries"] = row["occurrence_count"]
        elif signal_kind == "watchdog-exit":
            entry["watchdog_kind"] = row["reason_code"]
            entry["triggered"] = True
            entry["consecutive_no_progress_cycles"] = row["occurrence_count"]
            entry["threshold_cycles"] = row["occurrence_count"]
        elif signal_kind == "regression-pattern":
            entry["failing_checks"] = []
        risk_sources[_legacy_bucket_for_signal_kind(signal_kind)].append(entry)
    return _normalize_req_020_risk_sources(risk_sources)


def _build_rich_normalized_risk_signals(
    *,
    normalized_risk_sources: dict[str, Any],
    normalized_cross_context: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cross_project_by_id = {row["project_id"]: row for row in normalized_cross_context}
    normalized_risk_signals: list[dict[str, Any]] = []
    for row in (
        *normalized_risk_sources["blockers"],
        *normalized_risk_sources["retries"],
        *normalized_risk_sources["watchdog_exits"],
        *normalized_risk_sources["regression_patterns"],
    ):
        project_id = str(row.get("project_id") or "").strip()
        linked_cross_refs: list[str] = []
        if project_id and project_id in cross_project_by_id:
            linked_cross_refs = list(cross_project_by_id[project_id]["evidence_refs"])
        risk_signal_id = f"risk-signal.{row['signal_kind']}.{_stable_id_fragment(row['signal_kind'], row['signal_ref'])}"
        normalized_risk_signals.append(
            {
                "risk_signal_id": risk_signal_id,
                "signal_ref": row["signal_ref"],
                "signal_kind": row["signal_kind"],
                "project_id": project_id,
                "risk_level": row["risk_level"],
                "summary": row["summary"],
                "reason_codes": row["reason_codes"],
                "evidence_refs": _collect_unique_refs(row["evidence_refs"], linked_cross_refs),
                "linked_cross_project_evidence_refs": linked_cross_refs,
                "detected_at_utc": row["detected_at_utc"],
                "details": row["details"],
            }
        )

    normalized_risk_signals.sort(
        key=lambda row: (
            _req_020_risk_level_rank(row["risk_level"]),
            row["signal_kind"],
            row["risk_signal_id"],
        )
    )
    rollup = {
        "total": len(normalized_risk_signals),
        "by_kind": {kind: 0 for kind in sorted(REQ_020_ALLOWED_SIGNAL_KINDS)},
        "by_risk_level": {level: 0 for level in sorted(REQ_020_ALLOWED_RISK_LEVELS)},
    }
    for row in normalized_risk_signals:
        rollup["by_kind"][row["signal_kind"]] += 1
        rollup["by_risk_level"][row["risk_level"]] += 1
    return normalized_risk_signals, rollup


def _denormalize_req_020_risk_sources(normalized_risk_sources: Mapping[str, Any]) -> dict[str, Any]:
    raw: dict[str, list[dict[str, Any]]] = {
        "blockers": [],
        "retries": [],
        "watchdog_exits": [],
        "regression_patterns": [],
    }
    for bucket_name, rows in raw.items():
        normalized_rows = normalized_risk_sources.get(bucket_name, [])
        if not isinstance(normalized_rows, list):
            continue
        for item in normalized_rows:
            if not isinstance(item, Mapping):
                continue
            details = item.get("details", {})
            row = {
                "signal_ref": item.get("signal_ref"),
                "project_id": item.get("project_id"),
                "summary": item.get("summary"),
                "risk_level": item.get("risk_level"),
                "reason_codes": list(item.get("reason_codes", []) if isinstance(item.get("reason_codes"), list) else []),
                "evidence_refs": list(item.get("evidence_refs", []) if isinstance(item.get("evidence_refs"), list) else []),
            }
            detected_at_utc = _as_text(item.get("detected_at_utc"))
            if detected_at_utc:
                row["detected_at_utc"] = detected_at_utc
            if bucket_name == "retries" and isinstance(details, Mapping):
                row["retry_count"] = details.get("retry_count", 0)
                row["max_retries"] = details.get("max_retries", 0)
            elif bucket_name == "watchdog_exits" and isinstance(details, Mapping):
                row["watchdog_kind"] = details.get("watchdog_kind")
                row["triggered"] = details.get("triggered", False)
                row["consecutive_no_progress_cycles"] = details.get("consecutive_no_progress_cycles", 0)
                row["threshold_cycles"] = details.get("threshold_cycles", 0)
            elif bucket_name == "regression_patterns" and isinstance(details, Mapping):
                row["failing_checks"] = list(details.get("failing_checks", []) if isinstance(details.get("failing_checks"), list) else [])
            raw[bucket_name].append(row)
    return raw


def _build_legacy_projection_from_rich(
    normalized_risk_signals: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    legacy_signals: list[dict[str, Any]] = []
    for row in normalized_risk_signals:
        fragment = _as_text(row.get("risk_signal_id")).split(".")[-1]
        signal_source = _legacy_source_for_signal_kind(_as_text(row.get("signal_kind")))
        reason_codes = list(row.get("reason_codes") or [])
        reason_code = reason_codes[0] if reason_codes else "unknown_risk"
        detected_at_utc = _as_text(row.get("detected_at_utc"))
        legacy_signals.append(
            {
                "normalized_signal_id": f"risk-signal.{fragment}",
                "signal_source": signal_source,
                "reason_code": reason_code,
                "source_reason_codes": reason_codes or [reason_code],
                "summary": _as_text(row.get("summary")),
                "severity": _as_text(row.get("risk_level")),
                "occurrence_count": 1,
                "evidence_refs": list(row.get("evidence_refs") or []),
                "first_observed_at_utc": detected_at_utc,
                "last_observed_at_utc": detected_at_utc,
            }
        )
    legacy_signals.sort(key=lambda row: (row["signal_source"], row["reason_code"], row["summary"], row["normalized_signal_id"]))
    alias_rows: list[dict[str, str]] = []
    summary = _build_legacy_summary(legacy_signals, total_input_signals=len(legacy_signals))
    return legacy_signals, alias_rows, summary


def build_req_020_risk_signal_normalization(
    *,
    risk_signals: list[Mapping[str, Any]] | None = None,
    normalized_at_utc: str | None = None,
    target_project_root: str | None = None,
    earth_root: str | None = None,
    output_root: str | None = None,
    revision_identity: str | None = None,
    target_project_evidence_refs: list[str] | None = None,
    earth_sweep_evidence_refs: list[str] | None = None,
    cross_project_context: list[Mapping[str, Any]] | None = None,
    risk_sources: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    input_variant = "legacy-risk-signals" if risk_signals is not None and risk_sources is None else "rich-risk-sources"

    normalized_target_root = _normalize_root(
        target_project_root or REQ_020_DEFAULT_TARGET_PROJECT_ROOT,
        field_name="target_project_root",
    )
    normalized_earth_root = _normalize_root(
        earth_root or REQ_020_DEFAULT_EARTH_ROOT,
        field_name="earth_root",
    )
    normalized_output_root = _normalize_root(
        output_root or REQ_020_DEFAULT_OUTPUT_ROOT,
        field_name="output_root",
    )
    normalized_revision_identity = _require_nonempty_text(
        revision_identity or REQ_020_DEFAULT_REVISION_ID,
        field_name="revision_identity",
    )
    normalized_target_refs = _normalize_string_list(
        target_project_evidence_refs,
        field_name="target_project_evidence_refs",
    )
    normalized_earth_refs = _normalize_string_list(
        earth_sweep_evidence_refs,
        field_name="earth_sweep_evidence_refs",
    )
    normalized_cross_context = _normalize_cross_project_context(cross_project_context)

    legacy_input_rows: list[dict[str, Any]] = []
    legacy_signals: list[dict[str, Any]]
    alias_rows: list[dict[str, str]]
    legacy_summary: dict[str, Any]

    if risk_signals is not None and risk_sources is None:
        legacy_input_rows = _normalize_legacy_signal_rows(risk_signals)
        normalized_timestamp = (
            _normalize_req_020_timestamp(normalized_at_utc, field_name="normalized_at_utc", allow_empty=False)
            if normalized_at_utc is not None
            else _derive_legacy_normalized_at_utc(legacy_input_rows)
        )
        legacy_signals, alias_rows = _build_legacy_aggregate_signals(legacy_input_rows)
        legacy_summary = _build_legacy_summary(legacy_signals, total_input_signals=len(legacy_input_rows))
        normalized_risk_sources = _normalize_legacy_input_to_rich_sources(legacy_input_rows)
    else:
        normalized_timestamp = (
            _normalize_req_020_timestamp(normalized_at_utc, field_name="normalized_at_utc", allow_empty=False)
            if normalized_at_utc is not None
            else REQ_020_FALLBACK_NORMALIZED_AT_UTC
        )
        normalized_risk_sources = _normalize_req_020_risk_sources(risk_sources)
        normalized_rich_signals, _ = _build_rich_normalized_risk_signals(
            normalized_risk_sources=normalized_risk_sources,
            normalized_cross_context=normalized_cross_context,
        )
        legacy_signals, alias_rows, legacy_summary = _build_legacy_projection_from_rich(normalized_rich_signals)

    normalized_risk_signals, risk_rollup = _build_rich_normalized_risk_signals(
        normalized_risk_sources=normalized_risk_sources,
        normalized_cross_context=normalized_cross_context,
    )

    canonical_input = _canonical_call_input(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        output_root=normalized_output_root,
        revision_identity=normalized_revision_identity,
    )
    canonical_input_sha256 = _canonical_input_digest(canonical_input)
    canonical_processing_input = _canonical_req_020_processing_input(
        input_variant=input_variant,
        normalized_at_utc=normalized_timestamp,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        risk_sources=normalized_risk_sources,
        legacy_risk_signals=legacy_input_rows,
    )
    processing_input_sha256 = _canonical_input_digest(canonical_processing_input)

    processing_behavior = _build_req_020_processing_behavior(
        target_project_root=normalized_target_root,
        earth_root=normalized_earth_root,
        normalized_at_utc=normalized_timestamp,
        target_project_evidence_refs=normalized_target_refs,
        earth_sweep_evidence_refs=normalized_earth_refs,
        cross_project_context=normalized_cross_context,
        risk_sources=normalized_risk_sources,
        normalized_risk_signals=normalized_risk_signals,
    )

    canonical_reason_codes = sorted(
        {
            row["reason_code"]
            for row in legacy_signals
            if isinstance(row.get("reason_code"), str) and row["reason_code"]
        }
    )

    return {
        "schema_version": REQ_020_SCHEMA_VERSION,
        "requirement_id": REQ_020_REQUIREMENT_ID,
        "analysis_anchors": list(REQ_020_ANALYSIS_ANCHORS),
        "risk_signal_normalization": {
            "normalized_at_utc": normalized_timestamp,
            "signals": legacy_signals,
            "reason_code_taxonomy": {
                "compatibility_target": "gate_review_reason_codes",
                "canonical_reason_codes": canonical_reason_codes,
                "source_reason_code_aliases_applied": alias_rows,
            },
            "summary": legacy_summary,
            "runtime_mode": RUNTIME_MODE,
            "execution_mode": EXECUTION_MODE,
            "target_project_root": normalized_target_root,
            "earth_root": normalized_earth_root,
            "output_root": normalized_output_root,
            "revision_identity": normalized_revision_identity,
            "risk_sources": normalized_risk_sources,
            "normalized_risk_signals": normalized_risk_signals,
            "risk_rollup": risk_rollup,
        },
        "source": {
            "tool": REQ_020_TOOL,
            "tool_version": REQ_020_TOOL_VERSION,
        },
        "processing_behavior": processing_behavior,
        "call_metadata": {
            "reproducibility": "deterministic-input-fingerprint",
            "canonical_input_sha256": canonical_input_sha256,
            "reproducible_call_id": f"req020-{canonical_input_sha256[:16]}",
            "canonical_input": canonical_input,
            "processing_input_sha256": processing_input_sha256,
            "processing_call_id": f"req020-processing-{processing_input_sha256[:16]}",
            "canonical_processing_input": canonical_processing_input,
        },
    }


def validate_req_020_risk_signal_normalization(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "schema_version",
        "requirement_id",
        "analysis_anchors",
        "risk_signal_normalization",
        "source",
        "processing_behavior",
        "call_metadata",
    }
    missing_top = sorted(required_top - set(payload.keys()))
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    if payload.get("schema_version") != REQ_020_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_020_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_020_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_020_REQUIREMENT_ID}")
    if payload.get("analysis_anchors") != REQ_020_ANALYSIS_ANCHORS:
        errors.append("analysis_anchors must match REQ-020 anchor order")

    contract = payload.get("risk_signal_normalization")
    if not isinstance(contract, Mapping):
        errors.append("risk_signal_normalization must be an object")
        return errors

    for required_field in (
        "normalized_at_utc",
        "signals",
        "reason_code_taxonomy",
        "summary",
        "runtime_mode",
        "execution_mode",
        "target_project_root",
        "earth_root",
        "output_root",
        "revision_identity",
        "risk_sources",
        "normalized_risk_signals",
        "risk_rollup",
    ):
        if required_field not in contract:
            errors.append(f"risk_signal_normalization missing {required_field}")

    signals = contract.get("signals")
    if not isinstance(signals, list) or not signals:
        errors.append("risk_signal_normalization.signals must contain at least one signal")
    reason_code_taxonomy = contract.get("reason_code_taxonomy")
    if not isinstance(reason_code_taxonomy, Mapping):
        errors.append("risk_signal_normalization.reason_code_taxonomy must be an object")
    else:
        alias_rows = reason_code_taxonomy.get("source_reason_code_aliases_applied")
        if not isinstance(alias_rows, list):
            errors.append("risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied must be a list")
        else:
            for index, row in enumerate(alias_rows):
                if not isinstance(row, Mapping):
                    errors.append(
                        "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied"
                        f"[{index}] must be an object"
                    )
                    continue
                source_reason_code = row.get("source_reason_code")
                if source_reason_code is not None and not isinstance(source_reason_code, str):
                    errors.append(
                        "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied"
                        f"[{index}].source_reason_code must be a string when provided"
                    )
                normalized_reason_code = row.get("normalized_reason_code")
                if normalized_reason_code is not None and not isinstance(normalized_reason_code, str):
                    errors.append(
                        "risk_signal_normalization.reason_code_taxonomy.source_reason_code_aliases_applied"
                        f"[{index}].normalized_reason_code must be a string when provided"
                    )
    normalized_risk_signals = contract.get("normalized_risk_signals")
    if not isinstance(normalized_risk_signals, list):
        errors.append("risk_signal_normalization.normalized_risk_signals must be a list")
    else:
        for index, row in enumerate(normalized_risk_signals):
            if not isinstance(row, Mapping):
                errors.append(f"risk_signal_normalization.normalized_risk_signals[{index}] must be an object")
                continue
            if row.get("signal_kind") not in REQ_020_ALLOWED_SIGNAL_KINDS:
                errors.append(
                    f"risk_signal_normalization.normalized_risk_signals[{index}].signal_kind must be one of: {sorted(REQ_020_ALLOWED_SIGNAL_KINDS)}"
                )
            if row.get("risk_level") not in REQ_020_ALLOWED_RISK_LEVELS:
                errors.append(
                    f"risk_signal_normalization.normalized_risk_signals[{index}].risk_level must be one of: {sorted(REQ_020_ALLOWED_RISK_LEVELS)}"
                )

    processing_behavior = payload.get("processing_behavior")
    if not isinstance(processing_behavior, Mapping):
        errors.append("processing_behavior must be an object")
        return errors
    recommendation = processing_behavior.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append("processing_behavior.recommendation must be an object")
    else:
        decision = recommendation.get("decision")
        if decision not in REQ_020_ALLOWED_DECISIONS:
            errors.append(
                f"processing_behavior.recommendation.decision must be one of: {sorted(REQ_020_ALLOWED_DECISIONS)}"
            )
        confidence = recommendation.get("confidence")
        if confidence not in REQ_020_ALLOWED_CONFIDENCE_LABELS:
            errors.append(
                f"processing_behavior.recommendation.confidence must be one of: {sorted(REQ_020_ALLOWED_CONFIDENCE_LABELS)}"
            )

    metadata = payload.get("call_metadata")
    if not isinstance(metadata, Mapping):
        errors.append("call_metadata must be an object")
        return errors
    canonical_input = metadata.get("canonical_input")
    canonical_processing_input = metadata.get("canonical_processing_input")
    if not isinstance(canonical_input, Mapping):
        errors.append("call_metadata.canonical_input must be an object")
        return errors
    if not isinstance(canonical_processing_input, Mapping):
        errors.append("call_metadata.canonical_processing_input must be an object")
        return errors

    expected_canonical_input = _canonical_call_input(
        target_project_root=_as_text(contract.get("target_project_root")),
        earth_root=_as_text(contract.get("earth_root")),
        output_root=_as_text(contract.get("output_root")),
        revision_identity=_as_text(contract.get("revision_identity")),
    )
    if dict(canonical_input) != expected_canonical_input:
        errors.append("call_metadata.canonical_input must mirror normalized invocation anchors")

    expected_input_digest = _canonical_input_digest(expected_canonical_input)
    if metadata.get("canonical_input_sha256") != expected_input_digest:
        errors.append("call_metadata.canonical_input_sha256 does not match canonical input")
    if metadata.get("reproducible_call_id") != f"req020-{expected_input_digest[:16]}":
        errors.append("call_metadata.reproducible_call_id does not match canonical digest")

    if errors:
        return errors

    try:
        variant = _as_text(canonical_processing_input.get("input_variant"))
        if variant == "legacy-risk-signals":
            rebuilt = build_req_020_risk_signal_normalization(
                risk_signals=list(canonical_processing_input.get("legacy_risk_signals", [])),
                normalized_at_utc=canonical_processing_input.get("normalized_at_utc"),
                target_project_root=canonical_input.get("target_project_root"),
                earth_root=canonical_input.get("earth_root"),
                output_root=canonical_input.get("output_root"),
                revision_identity=canonical_input.get("revision_identity"),
                target_project_evidence_refs=list(canonical_processing_input.get("target_project_evidence_refs", [])),
                earth_sweep_evidence_refs=list(canonical_processing_input.get("earth_sweep_evidence_refs", [])),
                cross_project_context=list(canonical_processing_input.get("cross_project_context", [])),
            )
        else:
            rebuilt = build_req_020_risk_signal_normalization(
                normalized_at_utc=canonical_processing_input.get("normalized_at_utc"),
                target_project_root=canonical_input.get("target_project_root"),
                earth_root=canonical_input.get("earth_root"),
                output_root=canonical_input.get("output_root"),
                revision_identity=canonical_input.get("revision_identity"),
                target_project_evidence_refs=list(canonical_processing_input.get("target_project_evidence_refs", [])),
                earth_sweep_evidence_refs=list(canonical_processing_input.get("earth_sweep_evidence_refs", [])),
                cross_project_context=list(canonical_processing_input.get("cross_project_context", [])),
                risk_sources=_denormalize_req_020_risk_sources(
                    dict(canonical_processing_input.get("risk_sources", {}))
                ),
            )
    except ValueError as exc:
        return [f"call_metadata.canonical_processing_input is invalid: {exc}"]

    if dict(payload) != rebuilt:
        errors.append("payload must mirror deterministic REQ-020 normalization output")
    return errors
