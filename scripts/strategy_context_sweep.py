#!/usr/bin/env python3
"""Sweep planning artifacts and return deterministic freshness metadata."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL = "strategy-context-sweep"
TOOL_VERSION = "1.0.0"
ARTIFACT_KEYS = ("plan_packets", "state", "roadmap", "requirements")
DEFAULT_STALE_AFTER_SECONDS = {
    "plan_packets": 3600,
    "state": 1800,
    "roadmap": 86400,
    "requirements": 86400,
}
DEFAULT_DECISION_POLICY = {"stale": "downgrade", "missing": "exclude"}
ALLOWED_DECISIONS = {"include", "downgrade", "exclude"}


class SweepError(Exception):
    def __init__(self, code: str, message: str, *, stage: str = "runtime") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


def _as_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _parse_input(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise SweepError("input_error", "input must be a JSON object", stage="input")
    return payload


def _required_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise SweepError("input_error", f"{key} must be an object", stage="input")
    return value


def _required_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise SweepError("input_error", f"{key} must be a list", stage="input")
    return value


def _required_str(payload: dict[str, Any], key: str) -> str:
    text = _as_str(payload.get(key))
    if not text:
        raise SweepError("input_error", f"{key} is required", stage="input")
    return text


def _parse_now(payload: dict[str, Any]) -> datetime:
    raw = payload.get("now_utc")
    if raw is None:
        return datetime.now(timezone.utc)
    text = _as_str(raw)
    if not text:
        raise SweepError("input_error", "now_utc must be non-empty when provided", stage="input")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SweepError("input_error", f"invalid now_utc timestamp: {exc}", stage="input") from exc
    if dt.tzinfo is None:
        raise SweepError("input_error", "now_utc must include timezone offset", stage="input")
    return dt.astimezone(timezone.utc)


def _to_iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _coerce_threshold_map(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("stale_after_seconds")
    if raw is None:
        return dict(DEFAULT_STALE_AFTER_SECONDS)
    if not isinstance(raw, dict):
        raise SweepError("input_error", "stale_after_seconds must be an object", stage="input")

    out = dict(DEFAULT_STALE_AFTER_SECONDS)
    for key in ARTIFACT_KEYS:
        if key not in raw:
            continue
        value = raw.get(key)
        if not isinstance(value, int) or value < 0:
            raise SweepError(
                "input_error",
                f"stale_after_seconds.{key} must be a non-negative integer",
                stage="input",
            )
        out[key] = value
    return out


def _coerce_decision_policy(payload: dict[str, Any]) -> dict[str, str]:
    raw = payload.get("decision_policy")
    if raw is None:
        return dict(DEFAULT_DECISION_POLICY)
    if not isinstance(raw, dict):
        raise SweepError("input_error", "decision_policy must be an object", stage="input")
    stale = _as_str(raw.get("stale")) or DEFAULT_DECISION_POLICY["stale"]
    missing = _as_str(raw.get("missing")) or DEFAULT_DECISION_POLICY["missing"]
    if stale not in ALLOWED_DECISIONS:
        raise SweepError(
            "input_error",
            "decision_policy.stale must be include|downgrade|exclude",
            stage="input",
        )
    if missing not in ALLOWED_DECISIONS:
        raise SweepError(
            "input_error",
            "decision_policy.missing must be include|downgrade|exclude",
            stage="input",
        )
    return {"stale": stale, "missing": missing}


def _resolve_artifact_path(project_root: Path, artifact_path: str) -> Path:
    candidate = Path(artifact_path).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def _decision_for_freshness(freshness: str, policy: dict[str, str]) -> str:
    if freshness == "fresh":
        return "include"
    if freshness == "stale":
        return policy["stale"]
    return policy["missing"]


def _validate_project_row(row: Any, index: int) -> tuple[str, Path, dict[str, str]]:
    if not isinstance(row, dict):
        raise SweepError("input_error", f"projects[{index}] must be an object", stage="input")
    project_id = _required_str(row, "project_id")
    root_path = Path(_required_str(row, "root_path")).expanduser().resolve()
    artifacts = _required_object(row, "artifacts")
    artifact_paths: dict[str, str] = {}
    for key in ARTIFACT_KEYS:
        text = _as_str(artifacts.get(key))
        if not text:
            raise SweepError("input_error", f"projects[{index}].artifacts.{key} is required", stage="input")
        artifact_paths[key] = text
    return project_id, root_path, artifact_paths


def run(payload: dict[str, Any]) -> dict[str, Any]:
    now_utc = _parse_now(payload)
    thresholds = _coerce_threshold_map(payload)
    decision_policy = _coerce_decision_policy(payload)
    projects_in = _required_list(payload, "projects")

    results: list[dict[str, Any]] = []
    totals = {
        "projects": 0,
        "artifacts": 0,
        "fresh": 0,
        "stale": 0,
        "missing": 0,
        "include": 0,
        "downgrade": 0,
        "exclude": 0,
    }

    for idx, project_row in enumerate(projects_in):
        project_id, project_root, artifact_paths = _validate_project_row(project_row, idx)
        artifact_out: dict[str, dict[str, Any]] = {}
        project_counts = {"fresh": 0, "stale": 0, "missing": 0, "include": 0, "downgrade": 0, "exclude": 0}
        for artifact_key in ARTIFACT_KEYS:
            resolved_path = _resolve_artifact_path(project_root, artifact_paths[artifact_key])
            threshold = thresholds[artifact_key]
            exists = resolved_path.is_file()
            if not exists:
                freshness = "missing"
                decision = _decision_for_freshness(freshness, decision_policy)
                row = {
                    "path": str(resolved_path),
                    "exists": False,
                    "last_modified_utc": None,
                    "age_seconds": None,
                    "stale_after_seconds": threshold,
                    "freshness": freshness,
                    "decision": decision,
                }
            else:
                modified = datetime.fromtimestamp(resolved_path.stat().st_mtime, tz=timezone.utc)
                age_seconds = max(0, int((now_utc - modified).total_seconds()))
                freshness = "fresh" if age_seconds <= threshold else "stale"
                decision = _decision_for_freshness(freshness, decision_policy)
                row = {
                    "path": str(resolved_path),
                    "exists": True,
                    "last_modified_utc": _to_iso_utc(modified),
                    "age_seconds": age_seconds,
                    "stale_after_seconds": threshold,
                    "freshness": freshness,
                    "decision": decision,
                }

            artifact_out[artifact_key] = row
            project_counts[freshness] += 1
            project_counts[decision] += 1
            totals["artifacts"] += 1
            totals[freshness] += 1
            totals[decision] += 1

        totals["projects"] += 1
        results.append(
            {
                "project_id": project_id,
                "root_path": str(project_root),
                "artifacts": artifact_out,
                "counts": project_counts,
            }
        )

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "checked_at_utc": _to_iso_utc(now_utc),
        "decision_policy": decision_policy,
        "stale_after_seconds": thresholds,
        "projects": results,
        "totals": totals,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep planning artifact freshness across projects")
    parser.add_argument("--input-json", required=True, help="JSON payload path or '-' for stdin")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _print(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    try:
        payload = _parse_input(args.input_json)
        out = run(payload)
        _print(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except SweepError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "reason_code": exc.code,
            "error": {"code": exc.code, "message": exc.message, "stage": exc.stage},
        }
        _print(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "reason_code": "input_error",
            "error": {"code": "input_error", "message": f"invalid JSON input: {exc}", "stage": "input"},
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
