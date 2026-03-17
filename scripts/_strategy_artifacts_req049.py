#!/usr/bin/env python3
"""REQ-049 contract/data-model surface for STRATEGY.json machine artifact generation."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REQ_049_SCHEMA_VERSION = "req-049.strategy-json-generator.v1"
REQ_049_REQUIREMENT_ID = "REQ-049"
REQ_049_ANALYSIS_TYPE = "strategy_json_generator"
REQ_049_CALL_ID = "strategy-artifacts-handoff"
REQ_049_ARTIFACT_KIND = "STRATEGY.json"
REQ_049_ARTIFACT_PATH = "strategy/current/STRATEGY.json"
_RISK_SEVERITIES = ("high", "medium", "low")
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


def _normalize_root(raw_path: Any, *, field_name: str) -> str:
    normalized = str(Path(_require_nonempty_text(raw_path, field_name=field_name)).expanduser().resolve())
    if not normalized.startswith("/"):
        raise ValueError(f"{field_name} must normalize to an absolute path")
    return normalized


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


def _collect_unique_refs(*ref_groups: list[str]) -> list[str]:
    refs: set[str] = set()
    for group in ref_groups:
        refs.update(group)
    return sorted(refs)


def _normalize_target_project(raw_value: Any) -> dict[str, str]:
    target_project = _require_mapping(raw_value, field_name="target_project")
    expected_keys = {"project_id", "project_root"}
    unexpected = sorted(set(target_project.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"target_project has unexpected keys: {unexpected}")
    return {
        "project_id": _require_nonempty_text(target_project.get("project_id"), field_name="target_project.project_id"),
        "project_root": _normalize_root(target_project.get("project_root"), field_name="target_project.project_root"),
    }


def _normalize_strategy_revision(raw_value: Any) -> dict[str, Any]:
    revision = _require_mapping(raw_value, field_name="strategy_revision")
    expected_keys = {"strategy_id", "revision", "generated_by", "source_requirement_ids", "evidence_refs"}
    unexpected = sorted(set(revision.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"strategy_revision has unexpected keys: {unexpected}")
    return {
        "strategy_id": _require_nonempty_text(revision.get("strategy_id"), field_name="strategy_revision.strategy_id"),
        "revision": _require_nonempty_text(revision.get("revision"), field_name="strategy_revision.revision"),
        "generated_by": _require_nonempty_text(revision.get("generated_by"), field_name="strategy_revision.generated_by"),
        "source_requirement_ids": _normalize_string_list(
            revision.get("source_requirement_ids"),
            field_name="strategy_revision.source_requirement_ids",
            allow_empty=False,
        ),
        "evidence_refs": _normalize_string_list(
            revision.get("evidence_refs"),
            field_name="strategy_revision.evidence_refs",
            allow_empty=True,
        ),
    }


def _normalize_recommendation(raw_value: Any, *, field_name: str) -> dict[str, Any]:
    recommendation = _require_mapping(raw_value, field_name=field_name)
    expected_keys = {"recommendation_id", "rationale", "impacts", "risk_ids", "evidence_refs"}
    unexpected = sorted(set(recommendation.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    return {
        "recommendation_id": _require_nonempty_text(
            recommendation.get("recommendation_id"),
            field_name=f"{field_name}.recommendation_id",
        ),
        "rationale": _require_nonempty_text(recommendation.get("rationale"), field_name=f"{field_name}.rationale"),
        "impacts": _normalize_string_list(
            recommendation.get("impacts"),
            field_name=f"{field_name}.impacts",
            allow_empty=False,
        ),
        "risk_ids": _normalize_string_list(
            recommendation.get("risk_ids"),
            field_name=f"{field_name}.risk_ids",
            allow_empty=False,
        ),
        "evidence_refs": _normalize_string_list(
            recommendation.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
            allow_empty=False,
        ),
    }


def _normalize_recommendations(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("recommendations must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    seen_recommendation_ids: set[str] = set()
    for index, row in enumerate(raw_value):
        normalized_row = _normalize_recommendation(row, field_name=f"recommendations[{index}]")
        recommendation_id = normalized_row["recommendation_id"]
        if recommendation_id in seen_recommendation_ids:
            raise ValueError("recommendations[].recommendation_id must be unique")
        seen_recommendation_ids.add(recommendation_id)
        normalized.append(normalized_row)
    return sorted(normalized, key=lambda row: row["recommendation_id"])


def _normalize_risk(raw_value: Any, *, field_name: str) -> dict[str, Any]:
    risk = _require_mapping(raw_value, field_name=field_name)
    expected_keys = {"risk_id", "summary", "severity", "mitigation", "evidence_refs"}
    unexpected = sorted(set(risk.keys()) - expected_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {unexpected}")
    severity = _require_nonempty_text(risk.get("severity"), field_name=f"{field_name}.severity").lower()
    if severity not in _RISK_SEVERITIES:
        raise ValueError(f"{field_name}.severity must be one of: {list(_RISK_SEVERITIES)}")
    return {
        "risk_id": _require_nonempty_text(risk.get("risk_id"), field_name=f"{field_name}.risk_id"),
        "summary": _require_nonempty_text(risk.get("summary"), field_name=f"{field_name}.summary"),
        "severity": severity,
        "mitigation": _require_nonempty_text(risk.get("mitigation"), field_name=f"{field_name}.mitigation"),
        "evidence_refs": _normalize_string_list(
            risk.get("evidence_refs"),
            field_name=f"{field_name}.evidence_refs",
            allow_empty=False,
        ),
    }


def _normalize_risks(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list) or not raw_value:
        raise ValueError("risks must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    seen_risk_ids: set[str] = set()
    for index, row in enumerate(raw_value):
        normalized_row = _normalize_risk(row, field_name=f"risks[{index}]")
        risk_id = normalized_row["risk_id"]
        if risk_id in seen_risk_ids:
            raise ValueError("risks[].risk_id must be unique")
        seen_risk_ids.add(risk_id)
        normalized.append(normalized_row)
    return sorted(normalized, key=lambda row: row["risk_id"])


def build_req_049_strategy_json_generator(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build normalized REQ-049 STRATEGY.json generator payload."""
    raw = _require_mapping(payload, field_name="payload")
    analysis_type = str(raw.get("analysis_type") or "").strip()
    if analysis_type and analysis_type != REQ_049_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_049_ANALYSIS_TYPE}")

    expected_top_keys = {
        "analysis_type",
        "now_utc",
        "target_project",
        "strategy_revision",
        "recommendations",
        "risks",
        "broad_sweep_context",
    }
    unexpected_top = sorted(set(raw.keys()) - expected_top_keys)
    if unexpected_top:
        raise ValueError(f"payload has unexpected keys: {unexpected_top}")

    generated_at_utc = _require_nonempty_text(raw.get("now_utc"), field_name="now_utc")
    target_project = _normalize_target_project(raw.get("target_project"))
    strategy_revision = _normalize_strategy_revision(raw.get("strategy_revision"))
    recommendations = _normalize_recommendations(raw.get("recommendations"))
    risks = _normalize_risks(raw.get("risks"))

    known_risk_ids = {row["risk_id"] for row in risks}
    for recommendation in recommendations:
        unknown_risk_ids = sorted(set(recommendation["risk_ids"]) - known_risk_ids)
        if unknown_risk_ids:
            raise ValueError(
                "recommendations[].risk_ids must reference defined risks; "
                f"unknown ids for {recommendation['recommendation_id']}: {unknown_risk_ids}"
            )

    artifact_evidence_refs = _collect_unique_refs(
        *[list(row["evidence_refs"]) for row in recommendations],
        *[list(row["evidence_refs"]) for row in risks],
    )

    output_payload = {
        "ok": True,
        "schema_version": REQ_049_SCHEMA_VERSION,
        "requirement_id": REQ_049_REQUIREMENT_ID,
        "analysis_type": REQ_049_ANALYSIS_TYPE,
        "call_id": REQ_049_CALL_ID,
        "artifact_kind": REQ_049_ARTIFACT_KIND,
        "generated_at_utc": generated_at_utc,
        "target_project": target_project,
        "strategy_json": {
            "artifact_path": REQ_049_ARTIFACT_PATH,
            "strategy_id": strategy_revision["strategy_id"],
            "revision": strategy_revision["revision"],
            "generated_by": strategy_revision["generated_by"],
            "source_requirement_ids": strategy_revision["source_requirement_ids"],
            "recommendations": recommendations,
            "risks": risks,
            "evidence_refs": artifact_evidence_refs,
        },
        "totals": {
            "recommendations": len(recommendations),
            "risks": len(risks),
            "impacts": sum(len(row["impacts"]) for row in recommendations),
            "evidence_refs": len(artifact_evidence_refs),
        },
    }

    errors = validate_req_049_strategy_json_generator(output_payload)
    if errors:
        raise ValueError(f"built REQ-049 payload failed validation: {errors}")
    return output_payload


def validate_req_049_strategy_json_generator(payload: Mapping[str, Any]) -> list[str]:
    """Validate REQ-049 STRATEGY.json generator payload shape."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["payload must be a JSON object"]

    required_top_keys = {
        "ok",
        "schema_version",
        "requirement_id",
        "analysis_type",
        "call_id",
        "artifact_kind",
        "generated_at_utc",
        "target_project",
        "strategy_json",
        "totals",
    }
    top_keys = set(payload.keys())
    missing_top = sorted(required_top_keys - top_keys)
    if missing_top:
        errors.append(f"missing top-level keys: {missing_top}")
    unexpected_top = sorted(top_keys - required_top_keys)
    if unexpected_top:
        errors.append(f"unexpected top-level keys: {unexpected_top}")

    if payload.get("ok") is not True:
        errors.append("ok must be true")
    if payload.get("schema_version") != REQ_049_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REQ_049_SCHEMA_VERSION}")
    if payload.get("requirement_id") != REQ_049_REQUIREMENT_ID:
        errors.append(f"requirement_id must be {REQ_049_REQUIREMENT_ID}")
    if payload.get("analysis_type") != REQ_049_ANALYSIS_TYPE:
        errors.append(f"analysis_type must be {REQ_049_ANALYSIS_TYPE}")
    if payload.get("call_id") != REQ_049_CALL_ID:
        errors.append(f"call_id must be {REQ_049_CALL_ID}")
    if payload.get("artifact_kind") != REQ_049_ARTIFACT_KIND:
        errors.append(f"artifact_kind must be {REQ_049_ARTIFACT_KIND}")
    if not isinstance(payload.get("generated_at_utc"), str) or not str(payload.get("generated_at_utc")).strip():
        errors.append("generated_at_utc must be a non-empty string")

    target_project = payload.get("target_project")
    if not isinstance(target_project, Mapping):
        errors.append("target_project must be an object")
    else:
        expected_target_keys = {"project_id", "project_root"}
        target_keys = set(target_project.keys())
        missing_target = sorted(expected_target_keys - target_keys)
        if missing_target:
            errors.append(f"target_project missing keys: {missing_target}")
        unexpected_target = sorted(target_keys - expected_target_keys)
        if unexpected_target:
            errors.append(f"target_project has unexpected keys: {unexpected_target}")
        project_id = target_project.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            errors.append("target_project.project_id must be a non-empty string")
        project_root = target_project.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            errors.append("target_project.project_root must be a non-empty string")
        elif not project_root.startswith("/"):
            errors.append("target_project.project_root must be an absolute path")

    strategy_json = payload.get("strategy_json")
    recommendation_risk_ids: set[str] = set()
    strategy_evidence_refs: list[str] = []
    risks_by_id: dict[str, Mapping[str, Any]] = {}
    recommendations: list[Mapping[str, Any]] = []
    risks: list[Mapping[str, Any]] = []
    if not isinstance(strategy_json, Mapping):
        errors.append("strategy_json must be an object")
    else:
        expected_strategy_keys = {
            "artifact_path",
            "strategy_id",
            "revision",
            "generated_by",
            "source_requirement_ids",
            "recommendations",
            "risks",
            "evidence_refs",
        }
        strategy_keys = set(strategy_json.keys())
        missing_strategy_keys = sorted(expected_strategy_keys - strategy_keys)
        if missing_strategy_keys:
            errors.append(f"strategy_json missing keys: {missing_strategy_keys}")
        unexpected_strategy_keys = sorted(strategy_keys - expected_strategy_keys)
        if unexpected_strategy_keys:
            errors.append(f"strategy_json has unexpected keys: {unexpected_strategy_keys}")

        if strategy_json.get("artifact_path") != REQ_049_ARTIFACT_PATH:
            errors.append(f"strategy_json.artifact_path must be {REQ_049_ARTIFACT_PATH}")
        for key in ("strategy_id", "revision", "generated_by"):
            value = strategy_json.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"strategy_json.{key} must be a non-empty string")

        source_requirement_ids = strategy_json.get("source_requirement_ids")
        if not isinstance(source_requirement_ids, list) or not source_requirement_ids:
            errors.append("strategy_json.source_requirement_ids must be a non-empty list")
        else:
            for index, value in enumerate(source_requirement_ids):
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"strategy_json.source_requirement_ids[{index}] must be a non-empty string")

        raw_recommendations = strategy_json.get("recommendations")
        seen_recommendation_ids: set[str] = set()
        if not isinstance(raw_recommendations, list) or not raw_recommendations:
            errors.append("strategy_json.recommendations must be a non-empty list")
        else:
            recommendations = [row for row in raw_recommendations if isinstance(row, Mapping)]
            if len(recommendations) != len(raw_recommendations):
                errors.append("strategy_json.recommendations entries must be objects")
            for index, row in enumerate(raw_recommendations):
                if not isinstance(row, Mapping):
                    continue
                expected_keys = {"recommendation_id", "rationale", "impacts", "risk_ids", "evidence_refs"}
                row_keys = set(row.keys())
                missing_keys = sorted(expected_keys - row_keys)
                if missing_keys:
                    errors.append(f"strategy_json.recommendations[{index}] missing keys: {missing_keys}")
                unexpected_keys = sorted(row_keys - expected_keys)
                if unexpected_keys:
                    errors.append(f"strategy_json.recommendations[{index}] has unexpected keys: {unexpected_keys}")
                recommendation_id = row.get("recommendation_id")
                if not isinstance(recommendation_id, str) or not recommendation_id.strip():
                    errors.append(f"strategy_json.recommendations[{index}].recommendation_id must be a non-empty string")
                elif recommendation_id in seen_recommendation_ids:
                    errors.append("strategy_json.recommendations[].recommendation_id must be unique")
                else:
                    seen_recommendation_ids.add(recommendation_id)
                rationale = row.get("rationale")
                if not isinstance(rationale, str) or not rationale.strip():
                    errors.append(f"strategy_json.recommendations[{index}].rationale must be a non-empty string")
                impacts = row.get("impacts")
                if not isinstance(impacts, list) or not impacts:
                    errors.append(f"strategy_json.recommendations[{index}].impacts must be a non-empty list")
                else:
                    for impact_index, impact in enumerate(impacts):
                        if not isinstance(impact, str) or not impact.strip():
                            errors.append(
                                f"strategy_json.recommendations[{index}].impacts[{impact_index}] must be a non-empty string"
                            )
                risk_ids = row.get("risk_ids")
                if not isinstance(risk_ids, list) or not risk_ids:
                    errors.append(f"strategy_json.recommendations[{index}].risk_ids must be a non-empty list")
                else:
                    for risk_index, risk_id in enumerate(risk_ids):
                        if not isinstance(risk_id, str) or not risk_id.strip():
                            errors.append(
                                f"strategy_json.recommendations[{index}].risk_ids[{risk_index}] must be a non-empty string"
                            )
                        else:
                            recommendation_risk_ids.add(risk_id)
                evidence_refs = row.get("evidence_refs")
                if not isinstance(evidence_refs, list) or not evidence_refs:
                    errors.append(f"strategy_json.recommendations[{index}].evidence_refs must be a non-empty list")
                else:
                    for ref_index, ref in enumerate(evidence_refs):
                        if not isinstance(ref, str) or not ref.strip():
                            errors.append(
                                f"strategy_json.recommendations[{index}].evidence_refs[{ref_index}] must be a non-empty string"
                            )

        raw_risks = strategy_json.get("risks")
        seen_risk_ids: set[str] = set()
        if not isinstance(raw_risks, list) or not raw_risks:
            errors.append("strategy_json.risks must be a non-empty list")
        else:
            risks = [row for row in raw_risks if isinstance(row, Mapping)]
            if len(risks) != len(raw_risks):
                errors.append("strategy_json.risks entries must be objects")
            for index, row in enumerate(raw_risks):
                if not isinstance(row, Mapping):
                    continue
                expected_keys = {"risk_id", "summary", "severity", "mitigation", "evidence_refs"}
                row_keys = set(row.keys())
                missing_keys = sorted(expected_keys - row_keys)
                if missing_keys:
                    errors.append(f"strategy_json.risks[{index}] missing keys: {missing_keys}")
                unexpected_keys = sorted(row_keys - expected_keys)
                if unexpected_keys:
                    errors.append(f"strategy_json.risks[{index}] has unexpected keys: {unexpected_keys}")
                risk_id = row.get("risk_id")
                if not isinstance(risk_id, str) or not risk_id.strip():
                    errors.append(f"strategy_json.risks[{index}].risk_id must be a non-empty string")
                elif risk_id in seen_risk_ids:
                    errors.append("strategy_json.risks[].risk_id must be unique")
                else:
                    seen_risk_ids.add(risk_id)
                    risks_by_id[risk_id] = row
                summary = row.get("summary")
                if not isinstance(summary, str) or not summary.strip():
                    errors.append(f"strategy_json.risks[{index}].summary must be a non-empty string")
                severity = row.get("severity")
                if severity not in _RISK_SEVERITIES:
                    errors.append(
                        f"strategy_json.risks[{index}].severity must be one of: {list(_RISK_SEVERITIES)}"
                    )
                mitigation = row.get("mitigation")
                if not isinstance(mitigation, str) or not mitigation.strip():
                    errors.append(f"strategy_json.risks[{index}].mitigation must be a non-empty string")
                evidence_refs = row.get("evidence_refs")
                if not isinstance(evidence_refs, list) or not evidence_refs:
                    errors.append(f"strategy_json.risks[{index}].evidence_refs must be a non-empty list")
                else:
                    for ref_index, ref in enumerate(evidence_refs):
                        if not isinstance(ref, str) or not ref.strip():
                            errors.append(
                                f"strategy_json.risks[{index}].evidence_refs[{ref_index}] must be a non-empty string"
                            )

        strategy_evidence_refs_raw = strategy_json.get("evidence_refs")
        if not isinstance(strategy_evidence_refs_raw, list):
            errors.append("strategy_json.evidence_refs must be a list")
        else:
            strategy_evidence_refs = [str(ref) for ref in strategy_evidence_refs_raw if isinstance(ref, str) and ref.strip()]
            if len(strategy_evidence_refs) != len(strategy_evidence_refs_raw):
                errors.append("strategy_json.evidence_refs entries must be non-empty strings")

    undefined_risk_ids = sorted(recommendation_risk_ids - set(risks_by_id))
    if undefined_risk_ids:
        errors.append(f"strategy_json.recommendations[].risk_ids reference undefined risks: {undefined_risk_ids}")

    if recommendations and risks and not errors:
        computed_evidence_refs = _collect_unique_refs(
            *[list(row.get("evidence_refs", [])) for row in recommendations],
            *[list(row.get("evidence_refs", [])) for row in risks],
        )
        if sorted(strategy_evidence_refs) != computed_evidence_refs:
            errors.append("strategy_json.evidence_refs must match the unique sorted union of recommendation and risk evidence refs")

    totals = payload.get("totals")
    if not isinstance(totals, Mapping):
        errors.append("totals must be an object")
    else:
        expected_total_keys = {"recommendations", "risks", "impacts", "evidence_refs"}
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

        if isinstance(totals.get("recommendations"), int) and recommendations:
            if totals["recommendations"] != len(recommendations):
                errors.append("totals.recommendations must match strategy_json.recommendations length")
        if isinstance(totals.get("risks"), int) and risks:
            if totals["risks"] != len(risks):
                errors.append("totals.risks must match strategy_json.risks length")
        if isinstance(totals.get("impacts"), int) and recommendations:
            impact_rows = sum(
                len(row.get("impacts", []))
                for row in recommendations
                if isinstance(row.get("impacts"), list)
            )
            if totals["impacts"] != impact_rows:
                errors.append("totals.impacts must match strategy_json.recommendations impacts row count")
        if isinstance(totals.get("evidence_refs"), int) and strategy_evidence_refs:
            if totals["evidence_refs"] != len(strategy_evidence_refs):
                errors.append("totals.evidence_refs must match strategy_json.evidence_refs length")

    return errors


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = str(payload.get("analysis_type") or "").strip()
    if analysis_type != REQ_049_ANALYSIS_TYPE:
        raise ValueError(f"analysis_type must be {REQ_049_ANALYSIS_TYPE}")
    return build_req_049_strategy_json_generator(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit REQ-049 STRATEGY.json generator payload.")
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
        _emit_debug(f"REQ-049 CLI failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
