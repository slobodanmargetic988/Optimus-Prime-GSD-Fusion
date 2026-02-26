#!/usr/bin/env python3
"""Build strict tester handoff summary payload from preflight and test run outputs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOOL = "tester-handoff-summary-builder"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"
DECISION_VALUES = {"ready_for_review", "needs_dev_fix", "blocked"}


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class BuilderInput:
    task_identifier: str
    resolved_branch: str
    start_from_branch: str
    start_from_commit: str
    head_commit: str
    preflight_json_path: Path | None
    test_results_json_path: Path | None
    decision_override: str | None
    findings: list[str]
    blockers: list[str]
    dry_run: bool
    include_metadata: bool


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "Input payload must be a JSON object", stage="input")
    return data


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def parse_list_str(data: dict[str, Any], key: str) -> list[str]:
    raw = data.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ToolError("input_error", f"{key} must be a list", stage="input")
    out: list[str] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ToolError("input_error", f"{key}[{idx}] must be non-empty string", stage="input")
        out.append(item.strip())
    return out


def parse_optional_path(data: dict[str, Any], key: str, fallback: Any = None) -> Path | None:
    raw = data.get(key, fallback)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ToolError("input_error", f"{key} must be a non-empty string when provided", stage="input")
    return Path(raw).expanduser().resolve()


def must_str(data: dict[str, Any], key: str, fallback: Any = None) -> str:
    value = data.get(key, fallback)
    if not isinstance(value, str) or not value.strip():
        raise ToolError("input_error", f"{key} is required and must be a non-empty string", stage="input")
    return value.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict tester handoff summary")
    parser.add_argument("--input-json", help="JSON payload path or '-' for stdin")
    parser.add_argument("--task-identifier")
    parser.add_argument("--resolved-branch")
    parser.add_argument("--start-from-branch")
    parser.add_argument("--start-from-commit")
    parser.add_argument("--head-commit")
    parser.add_argument("--preflight-json-path")
    parser.add_argument("--test-results-json-path")
    parser.add_argument("--decision-override")
    parser.add_argument("--include-metadata", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def parse_input(args: argparse.Namespace) -> BuilderInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_json(args.input_json)

    decision_override = payload.get("decision_override", args.decision_override)
    if decision_override is not None:
        if not isinstance(decision_override, str) or decision_override.strip() not in DECISION_VALUES:
            raise ToolError(
                "input_error",
                "decision_override must be one of: ready_for_review, needs_dev_fix, blocked",
                stage="input",
            )
        decision_override = decision_override.strip()

    return BuilderInput(
        task_identifier=must_str(payload, "task_identifier", fallback=args.task_identifier),
        resolved_branch=must_str(payload, "resolved_branch", fallback=args.resolved_branch),
        start_from_branch=must_str(payload, "start_from_branch", fallback=args.start_from_branch),
        start_from_commit=must_str(payload, "start_from_commit", fallback=args.start_from_commit),
        head_commit=must_str(payload, "head_commit", fallback=args.head_commit),
        preflight_json_path=parse_optional_path(payload, "preflight_json_path", fallback=args.preflight_json_path),
        test_results_json_path=parse_optional_path(payload, "test_results_json_path", fallback=args.test_results_json_path),
        decision_override=decision_override,
        findings=parse_list_str(payload, "findings"),
        blockers=parse_list_str(payload, "blockers"),
        dry_run=as_bool(payload.get("dry_run", args.dry_run), default=False),
        include_metadata=as_bool(payload.get("include_metadata", args.include_metadata), default=False),
    )


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def load_json_file(path: Path, label: str) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise ToolError("data", f"{label} not found: {path}", stage="input")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ToolError("data", f"{label} must contain JSON object", stage="input")
    return data


def preflight_checks(data: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    checks: list[dict[str, str]] = []
    blockers: list[str] = []

    ok = bool(data.get("ok", False))
    next_step = data.get("next_step")
    result = "pass" if ok and next_step == "run_tests" else "blocked"
    checks.append({"name": "preflight", "result": result})

    errors = data.get("errors", [])
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, dict):
                code = item.get("code")
                message = item.get("message")
                if isinstance(code, str) and isinstance(message, str):
                    blockers.append(f"preflight:{code}: {message}")

    return checks, blockers


def test_run_checks(data: dict[str, Any]) -> tuple[list[dict[str, str]], str | None, list[str], list[str]]:
    checks: list[dict[str, str]] = []
    findings: list[str] = []
    blockers: list[str] = []

    decision_hint = data.get("decision_hint")
    if isinstance(decision_hint, str) and decision_hint not in DECISION_VALUES:
        decision_hint = None

    runs = data.get("runs", [])
    had_run_entries = False
    if isinstance(runs, list):
        for idx, item in enumerate(runs):
            if not isinstance(item, dict):
                raise ToolError("data", f"test_results.runs[{idx}] must be object", stage="input")
            name = item.get("name")
            result = item.get("result")
            if not isinstance(name, str) or not name.strip():
                raise ToolError("data", f"test_results.runs[{idx}].name must be non-empty string", stage="input")
            if not isinstance(result, str) or not result.strip():
                raise ToolError("data", f"test_results.runs[{idx}].result must be non-empty string", stage="input")
            had_run_entries = True
            checks.append({"name": name.strip(), "result": result.strip()})

            summary = item.get("summary")
            if result.strip() == "fail" and isinstance(summary, str) and summary.strip():
                findings.append(f"{name.strip()}: {summary.strip()}")
            if result.strip() == "blocked":
                signature = item.get("signature")
                if isinstance(signature, str) and signature.strip():
                    blockers.append(f"{name.strip()}: {signature.strip()}")
                else:
                    blockers.append(f"{name.strip()}: blocked")
    elif runs is not None:
        raise ToolError("data", "test_results.runs must be list", stage="input")

    errors = data.get("errors", [])
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, dict):
                code = item.get("code")
                message = item.get("message")
                if isinstance(code, str) and isinstance(message, str):
                    blockers.append(f"test:{code}: {message}")

    if not had_run_entries and blockers:
        checks.append({"name": "test_runner", "result": "blocked"})

    return checks, decision_hint, findings, blockers


def derive_decision(checks: list[dict[str, str]], hint: str | None) -> str:
    if hint in DECISION_VALUES:
        return hint

    if any(item.get("result") == "blocked" for item in checks):
        return "blocked"
    if any(item.get("result") == "fail" for item in checks):
        return "needs_dev_fix"
    return "ready_for_review"


def build_summary(cfg: BuilderInput) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    merged_findings = list(cfg.findings)
    merged_blockers = list(cfg.blockers)
    decision_hint: str | None = None

    if cfg.dry_run:
        checks = [{"name": "preflight", "result": "pass"}, {"name": "test_runs", "result": "pass"}]
    else:
        if cfg.preflight_json_path is not None:
            p = load_json_file(cfg.preflight_json_path, "preflight_json_path")
            p_checks, p_blockers = preflight_checks(p)
            checks.extend(p_checks)
            merged_blockers.extend(p_blockers)

        if cfg.test_results_json_path is not None:
            t = load_json_file(cfg.test_results_json_path, "test_results_json_path")
            t_checks, t_hint, t_findings, t_blockers = test_run_checks(t)
            checks.extend(t_checks)
            merged_findings.extend(t_findings)
            merged_blockers.extend(t_blockers)
            if t_hint in DECISION_VALUES:
                decision_hint = t_hint

        if not checks:
            checks.append({"name": "checks_source", "result": "blocked"})
            merged_blockers.append("No preflight_json_path or test_results_json_path provided")

    decision = derive_decision(checks, decision_hint)

    if cfg.decision_override is not None:
        decision = cfg.decision_override

    if merged_blockers and decision == "ready_for_review":
        decision = "blocked"

    out: dict[str, Any] = {
        "task_identifier": cfg.task_identifier,
        "branch": cfg.resolved_branch,
        "start_from_branch": cfg.start_from_branch,
        "start_from_commit": cfg.start_from_commit,
        "head_commit": cfg.head_commit,
        "checks": checks,
        "decision": decision,
        "findings": dedupe(merged_findings),
        "blockers": dedupe(merged_blockers),
    }
    if cfg.include_metadata:
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            **out,
        }
    return out


def print_json(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def error_payload(args: argparse.Namespace, message: str) -> dict[str, Any]:
    return {
        "task_identifier": args.task_identifier or "",
        "branch": args.resolved_branch or "",
        "start_from_branch": args.start_from_branch or "",
        "start_from_commit": args.start_from_commit or "",
        "head_commit": args.head_commit or "",
        "checks": [{"name": "builder", "result": "blocked"}],
        "decision": "blocked",
        "findings": [],
        "blockers": [message],
    }


def main() -> int:
    args = parse_args()
    try:
        cfg = parse_input(args)
        out = build_summary(cfg)
        print_json(out, args.json_pretty)
        return 0 if out.get("decision") != "blocked" else 1
    except ToolError as exc:
        out = error_payload(args, f"{exc.code}: {exc.message}")
        print_json(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = error_payload(args, f"input_error: Invalid JSON input: {exc}")
        print_json(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
