#!/usr/bin/env python3
"""Contract/data-model surface for REQ-054 recommendation-to-planner mapping artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REQ_054_SCHEMA_VERSION = "req-054.recommendation-to-planner-mapping-artifact.v1"
REQ_054_REQUIREMENT_ID = "REQ-054"
REQ_054_ANALYSIS_TYPE = "recommendation_to_planner_mapping_artifact"
REQ_054_CALL_ID = "recommendation-to-planner-mapping"
_LOG_BUDGET_MAX_BYTES = 3 * 1024 * 1024 * 1024
_LOG_BUDGET_CHECK_INTERVAL_SECONDS = 15 * 60


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_ts_line(message: str, *, now_utc: str | None = None) -> str:
    stamp = now_utc.strip() if isinstance(now_utc, str) and now_utc.strip() else _utc_timestamp()
    return f"[{stamp}] {message}"


def _default_log_dir() -> Path:
    return Path.home() / "projects" / "LOGS"


def _log_path() -> Path:
    return _default_log_dir() / "strategy_artifacts_handoff.log"


def _log_budget_check_stamp() -> Path:
    return _default_log_dir() / ".log_budget_check.strategy_artifacts_handoff"


def _maintain_log_budget() -> None:
    log_dir = _default_log_dir()
    stamp = _log_budget_check_stamp()
    now = time.time()
    try:
        if stamp.exists() and now - stamp.stat().st_mtime < _LOG_BUDGET_CHECK_INTERVAL_SECONDS:
            return
        log_dir.mkdir(parents=True, exist_ok=True)
        for candidate in log_dir.glob("*.log"):
            if candidate.stat().st_size <= _LOG_BUDGET_MAX_BYTES:
                continue
            candidate.write_text("", encoding="utf-8")
        stamp.touch()
    except OSError:
        return


def _emit_debug(message: str, *, now_utc: str | None = None) -> None:
    line = _format_ts_line(message, now_utc=now_utc)
    print(line, file=sys.stderr)
    try:
        _maintain_log_budget()
        log_file = _log_path()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _normalize_positive_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be a positive integer")
    if value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _normalize_string_list(raw_value: Any, *, field_name: str, allow_empty: bool = True) -> list[str]:
    if raw_value is None:
        if allow_empty:
            return []
        raise ValueError(f"{field_name} must be a non-empty list of strings")
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    normalized: set[str] = set()
    for index, item in enumerate(raw_value):
        normalized.add(_require_nonempty_text(item, field_name=f"{field_name}[{index}]"))
    values = sorted(normalized)
    if not allow_empty and not values:
        raise ValueError(f"{field_name} must be a non-empty list of strings")
    return values


def _stable_id_fragment(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _collect_unique_refs(*ref_groups: list[str]) -> list[str]:
    refs: set[str] = set()
    for group in ref_groups:
        refs.update(group)
    return sorted(refs)


def _normalize_input_mapping_row(raw_value: Any, *, field_name: str) -> dict[str, Any]:
    row = _require_mapping(raw_value, field_name=field_name)
    expected_keys = {
        "recommendation_id",
        "planner_task_intent_handle",
        "planner_task_intent_summary",
        "planner_lane",
        "sequence_hint",
        "call_trace_refs",
        "evidence_refs",
        "planner_packet_refs",
    }
    unexpected = sorted(set(row.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    return {
        "recommendation_id": _require_nonempty_text(row.get("recommendation_id"), field_name=f"{field_name}.recommendation_id"),
        "planner_task_intent_handle": _require_nonempty_text(
            row.get("planner_task_intent_handle"),
            field_name=f"{field_name}.planner_task_intent_handle",
        ),
        "planner_task_intent_summary": _require_nonempty_text(
            row.get("planner_task_intent_summary"),
            field_name=f"{field_name}.planner_task_intent_summary",
        ),
        "planner_lane": _require_nonempty_text(row.get("planner_lane"), field_name=f"{field_name}.planner_lane"),
        "sequence_hint": _normalize_positive_int(row.get("sequence_hint"), field_name=f"{field_name}.sequence_hint"),
        "call_trace_refs": _normalize_string_list(
            row.get("call_trace_refs"),
            field_name=f"{field_name}.call_trace_refs",
            allow_empty=False,
        ),
        "evidence_refs": _normalize_string_list(
            row.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
            allow_empty=False,
        ),
        "planner_packet_refs": _normalize_string_list(
            row.get("planner_packet_refs"),
            field_name=f"{field_name}.planner_packet_refs",
            allow_empty=True,
        ),
    }


def _normalize_recommendation_mappings(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("recommendation_mappings must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_value):
        row = _normalize_input_mapping_row(item, field_name=f"recommendation_mappings[{index}]")
        pair = (row["recommendation_id"], row["planner_task_intent_handle"])
        if pair in seen_pairs:
            raise ValueError(
                "recommendation_mappings"
                f"[{index}].recommendation_id + planner_task_intent_handle duplicates {pair[0]} -> {pair[1]}"
            )
        seen_pairs.add(pair)
        normalized.append(row)
    normalized.sort(
        key=lambda row: (
            row["sequence_hint"],
            row["planner_task_intent_handle"],
            row["recommendation_id"],
        )
    )
    return normalized


def build_req_054_recommendation_to_planner_mapping_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-054 recommendation-to-planner mapping artifact payload."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_054_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_054_ANALYSIS_TYPE}")
    checked_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    recommendation_mappings = _normalize_recommendation_mappings(raw.get("recommendation_mappings"))

    output_rows: list[dict[str, Any]] = []
    unique_traceability_refs: set[str] = set()
    for row in recommendation_mappings:
        traceability_refs = _collect_unique_refs(
            row["call_trace_refs"],
            row["evidence_refs"],
            row["planner_packet_refs"],
        )
        unique_traceability_refs.update(traceability_refs)
        output_rows.append(
            {
                "mapping_id": (
                    "rtp."
                    + _stable_id_fragment(
                        row["recommendation_id"],
                        row["planner_task_intent_handle"],
                        row["planner_lane"],
                        str(row["sequence_hint"]),
                    )
                ),
                "recommendation_id": row["recommendation_id"],
                "planner_task_intent_handle": row["planner_task_intent_handle"],
                "planner_task_intent_summary": row["planner_task_intent_summary"],
                "planner_lane": row["planner_lane"],
                "sequence_hint": row["sequence_hint"],
                "traceability_refs": traceability_refs,
                "downstream_audit_trail": {
                    "source_call_trace_refs": row["call_trace_refs"],
                    "source_evidence_refs": row["evidence_refs"],
                    "source_packet_refs": row["planner_packet_refs"],
                    "emitted_at_utc": checked_at_utc,
                    "emitted_by_requirement_id": REQ_054_REQUIREMENT_ID,
                },
            }
        )

    recommendation_ids = sorted({row["recommendation_id"] for row in output_rows})
    planner_task_intent_handles = sorted({row["planner_task_intent_handle"] for row in output_rows})
    mapping_artifact = {
        "recommendation_to_task_intent_mappings": output_rows,
        "recommendation_ids": recommendation_ids,
        "planner_task_intent_handles": planner_task_intent_handles,
    }
    output_payload = {
        "ok": True,
        "schema_version": REQ_054_SCHEMA_VERSION,
        "requirement_id": REQ_054_REQUIREMENT_ID,
        "analysis_type": REQ_054_ANALYSIS_TYPE,
        "call_id": REQ_054_CALL_ID,
        "checked_at_utc": checked_at_utc,
        "recommendation_to_planner_mapping_artifact": mapping_artifact,
        "totals": {
            "input_rows": len(recommendation_mappings),
            "mapping_rows": len(output_rows),
            "unique_recommendation_ids": len(recommendation_ids),
            "unique_planner_task_intent_handles": len(planner_task_intent_handles),
            "traceability_refs": len(unique_traceability_refs),
        },
    }

    errors = validate_req_054_recommendation_to_planner_mapping_artifact(output_payload)
    if errors:
        raise ValueError(f"built REQ-054 payload failed validation: {errors}")
    return output_payload


def validate_req_054_recommendation_to_planner_mapping_artifact(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-054 recommendation-to-planner mapping artifact payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top = {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "checked_at_utc",
        "recommendation_to_planner_mapping_artifact",
        "totals",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_054_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_054_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_054_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_054_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_054_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_054_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_054_CALL_ID:
        errors.append(f"call_id must be {REQ_054_CALL_ID}")
    if not isinstance(payload.get("checked_at_utc"), str) or not str(payload.get("checked_at_utc")).strip():
        errors.append("checked_at_utc must be a non-empty string")

    artifact = payload.get("recommendation_to_planner_mapping_artifact")
    mappings: list[Mapping[str, Any]] = []
    if not isinstance(artifact, Mapping):
        errors.append("recommendation_to_planner_mapping_artifact must be an object")
    else:
        expected_artifact_keys = {
            "recommendation_to_task_intent_mappings",
            "recommendation_ids",
            "planner_task_intent_handles",
        }
        artifact_keys = set(artifact.keys())
        missing_artifact = sorted(expected_artifact_keys - artifact_keys)
        if missing_artifact:
            errors.append(f"recommendation_to_planner_mapping_artifact missing keys: {missing_artifact}")
        unexpected_artifact = sorted(artifact_keys - expected_artifact_keys)
        if unexpected_artifact:
            errors.append(f"recommendation_to_planner_mapping_artifact has unexpected keys: {unexpected_artifact}")

        raw_mappings = artifact.get("recommendation_to_task_intent_mappings")
        if not isinstance(raw_mappings, list) or not raw_mappings:
            errors.append("recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings must be a non-empty list")
        else:
            seen_mapping_ids: set[str] = set()
            seen_pairs: set[tuple[str, str]] = set()
            for index, row in enumerate(raw_mappings):
                if not isinstance(row, Mapping):
                    errors.append(
                        f"recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings[{index}] must be an object"
                    )
                    continue
                mappings.append(row)
                expected_mapping_keys = {
                    "mapping_id",
                    "recommendation_id",
                    "planner_task_intent_handle",
                    "planner_task_intent_summary",
                    "planner_lane",
                    "sequence_hint",
                    "traceability_refs",
                    "downstream_audit_trail",
                }
                mapping_keys = set(row.keys())
                missing_mapping = sorted(expected_mapping_keys - mapping_keys)
                if missing_mapping:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}] missing keys: {missing_mapping}"
                    )
                unexpected_mapping = sorted(mapping_keys - expected_mapping_keys)
                if unexpected_mapping:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}] has unexpected keys: {unexpected_mapping}"
                    )
                mapping_id = row.get("mapping_id")
                if not isinstance(mapping_id, str) or not mapping_id.startswith("rtp."):
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].mapping_id must be like rtp.<id>"
                    )
                elif mapping_id in seen_mapping_ids:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].mapping_id must be unique"
                    )
                else:
                    seen_mapping_ids.add(mapping_id)

                recommendation_id = row.get("recommendation_id")
                planner_task_intent_handle = row.get("planner_task_intent_handle")
                if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].recommendation_id must be a non-empty string"
                    )
                if not isinstance(planner_task_intent_handle, str) or not planner_task_intent_handle.strip():
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].planner_task_intent_handle must be a non-empty string"
                    )
                if (
                    isinstance(recommendation_id, str)
                    and recommendation_id.strip()
                    and isinstance(planner_task_intent_handle, str)
                    and planner_task_intent_handle.strip()
                ):
                    pair = (recommendation_id, planner_task_intent_handle)
                    if pair in seen_pairs:
                        errors.append(
                            "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                            f"[{index}] duplicate recommendation_id + planner_task_intent_handle pair"
                        )
                    else:
                        seen_pairs.add(pair)

                for key in ("planner_task_intent_summary", "planner_lane"):
                    value = row.get(key)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                            f"[{index}].{key} must be a non-empty string"
                        )
                sequence_hint = row.get("sequence_hint")
                if not isinstance(sequence_hint, int) or sequence_hint < 1:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].sequence_hint must be a positive integer"
                    )
                traceability_refs = row.get("traceability_refs")
                if not isinstance(traceability_refs, list) or not traceability_refs:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].traceability_refs must be a non-empty list"
                    )

                downstream_audit_trail = row.get("downstream_audit_trail")
                if not isinstance(downstream_audit_trail, Mapping):
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail must be an object"
                    )
                    continue
                expected_audit_keys = {
                    "source_call_trace_refs",
                    "source_evidence_refs",
                    "source_packet_refs",
                    "emitted_at_utc",
                    "emitted_by_requirement_id",
                }
                audit_keys = set(downstream_audit_trail.keys())
                missing_audit = sorted(expected_audit_keys - audit_keys)
                if missing_audit:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail missing keys: {missing_audit}"
                    )
                unexpected_audit = sorted(audit_keys - expected_audit_keys)
                if unexpected_audit:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail has unexpected keys: {unexpected_audit}"
                    )

                source_call_trace_refs = downstream_audit_trail.get("source_call_trace_refs")
                if not isinstance(source_call_trace_refs, list) or not source_call_trace_refs:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.source_call_trace_refs must be a non-empty list"
                    )
                source_evidence_refs = downstream_audit_trail.get("source_evidence_refs")
                if not isinstance(source_evidence_refs, list) or not source_evidence_refs:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.source_evidence_refs must be a non-empty list"
                    )
                source_packet_refs = downstream_audit_trail.get("source_packet_refs")
                if not isinstance(source_packet_refs, list):
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.source_packet_refs must be a list"
                    )
                emitted_at_utc = downstream_audit_trail.get("emitted_at_utc")
                if not isinstance(emitted_at_utc, str) or not emitted_at_utc.strip():
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.emitted_at_utc must be a non-empty string"
                    )
                emitted_by_requirement_id = downstream_audit_trail.get("emitted_by_requirement_id")
                if emitted_by_requirement_id != REQ_054_REQUIREMENT_ID:
                    errors.append(
                        "recommendation_to_planner_mapping_artifact.recommendation_to_task_intent_mappings"
                        f"[{index}].downstream_audit_trail.emitted_by_requirement_id must be {REQ_054_REQUIREMENT_ID}"
                    )

        recommendation_ids = artifact.get("recommendation_ids")
        if not isinstance(recommendation_ids, list):
            errors.append("recommendation_to_planner_mapping_artifact.recommendation_ids must be a list")
        planner_task_intent_handles = artifact.get("planner_task_intent_handles")
        if not isinstance(planner_task_intent_handles, list):
            errors.append("recommendation_to_planner_mapping_artifact.planner_task_intent_handles must be a list")

        if mappings:
            expected_recommendation_ids = sorted({str(row.get("recommendation_id")) for row in mappings})
            if recommendation_ids != expected_recommendation_ids:
                errors.append(
                    "recommendation_to_planner_mapping_artifact.recommendation_ids must match mapping recommendation ids"
                )
            expected_intent_handles = sorted({str(row.get("planner_task_intent_handle")) for row in mappings})
            if planner_task_intent_handles != expected_intent_handles:
                errors.append(
                    "recommendation_to_planner_mapping_artifact.planner_task_intent_handles must match mapping intent handles"
                )

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {
            "input_rows",
            "mapping_rows",
            "unique_recommendation_ids",
            "unique_planner_task_intent_handles",
            "traceability_refs",
        }
        total_keys = set(totals.keys())
        missing_totals = sorted(expected_total_keys - total_keys)
        if missing_totals:
            errors.append(f"totals missing keys: {missing_totals}")
        unexpected_totals = sorted(total_keys - expected_total_keys)
        if unexpected_totals:
            errors.append(f"totals has unexpected keys: {unexpected_totals}")
        for key in expected_total_keys:
            value = totals.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"totals.{key} must be a non-negative integer")

        if mappings:
            unique_recommendation_ids = {str(row.get("recommendation_id")) for row in mappings}
            unique_intent_handles = {str(row.get("planner_task_intent_handle")) for row in mappings}
            unique_traceability_refs: set[str] = set()
            for row in mappings:
                traceability_refs = row.get("traceability_refs")
                if isinstance(traceability_refs, list):
                    unique_traceability_refs.update(str(item) for item in traceability_refs if str(item).strip())
            if totals.get("input_rows") != len(mappings):
                errors.append("totals.input_rows must match recommendation_to_task_intent_mappings length")
            if totals.get("mapping_rows") != len(mappings):
                errors.append("totals.mapping_rows must match recommendation_to_task_intent_mappings length")
            if totals.get("unique_recommendation_ids") != len(unique_recommendation_ids):
                errors.append("totals.unique_recommendation_ids must match unique recommendation ids in mappings")
            if totals.get("unique_planner_task_intent_handles") != len(unique_intent_handles):
                errors.append(
                    "totals.unique_planner_task_intent_handles must match unique planner task intent handles in mappings"
                )
            if totals.get("traceability_refs") != len(unique_traceability_refs):
                errors.append("totals.traceability_refs must match unique traceability refs in mappings")

    return errors


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type != REQ_054_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_054_ANALYSIS_TYPE}")
    return build_req_054_recommendation_to_planner_mapping_artifact(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit REQ-054 recommendation-to-planner mapping artifact payload.")
    parser.add_argument("--input-json", required=True, help='Input payload path or "-" for stdin.')
    parser.add_argument("--output-json", default="-", help='Output path or "-" for stdout.')
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    try:
        if args.input_json == "-":
            payload = json.loads(sys.stdin.read())
        else:
            payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input payload must be a JSON object")

        output_payload = run(payload)
        rendered = json.dumps(output_payload, indent=2 if args.json_pretty else None, sort_keys=False)
        if args.output_json == "-":
            print(rendered)
        else:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered + "\n", encoding="utf-8")
        return 0
    except Exception as exc:  # pragma: no cover - CLI error path exercised indirectly.
        _emit_debug(f"REQ-054 CLI failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
